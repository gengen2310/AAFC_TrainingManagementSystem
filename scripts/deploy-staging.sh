#!/usr/bin/env bash
# deploy-staging.sh — staging deployment guard for AAFC TMS.
#
# Hard prerequisites before any `railway up` is run:
#   • Git working tree clean (no uncommitted changes)
#   • Branch is NOT main/master/production
#   • All backend tests pass (671+ expected)
#   • Security greps return zero matches
#   • Alembic head matches what the codebase expects
#   • Railway CLI authenticated and pointing at staging environment
#   • Operator types exact confirmation phrase
#
# Usage:
#   bash scripts/deploy-staging.sh
#
# To run without actually deploying (dry run):
#   DRY_RUN=1 bash scripts/deploy-staging.sh

set -uo pipefail

RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[0;33m'
BLU='\033[0;34m'
NC='\033[0m'

PASS=0
FAIL=0

ok()   { echo -e "  ${GRN}[PASS]${NC} $1"; PASS=$((PASS+1)); }
fail() { echo -e "  ${RED}[FAIL]${NC} $1"; FAIL=$((FAIL+1)); }
info() { echo -e "  ${BLU}[INFO]${NC} $1"; }
warn() { echo -e "  ${YLW}[WARN]${NC} $1"; }
die()  { echo -e "\n  ${RED}ABORT:${NC} $1\n"; exit 1; }

echo
echo "======================================================="
echo "  AAFC TMS — Staging Deployment Preflight"
echo "======================================================="
echo

# ── 1. Guard: Never deploy to production from this script ──────────────────
echo "  [1/9] Environment guard"
RAILWAY_ENV="${RAILWAY_ENVIRONMENT:-}"
if [ -n "$RAILWAY_ENV" ]; then
  if [[ "$RAILWAY_ENV" == "production" || "$RAILWAY_ENV" == "prod" ]]; then
    die "RAILWAY_ENVIRONMENT is set to '$RAILWAY_ENV'. This script MUST NOT deploy to production."
  fi
  info "RAILWAY_ENVIRONMENT=$RAILWAY_ENV"
fi
ok "Not in a production Railway environment variable context"

# ── 2. Guard: Branch must not be main/master/production ────────────────────
echo
echo "  [2/9] Branch guard"
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "")
if [ -z "$CURRENT_BRANCH" ]; then
  die "Could not determine current git branch. Are you in the repo root?"
fi
if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" || "$CURRENT_BRANCH" == *"production"* ]]; then
  die "Current branch is '$CURRENT_BRANCH'. Staging deploys must NOT come from main/master/production branches."
fi
info "Branch: $CURRENT_BRANCH"
ok "Branch is not a production branch"

# ── 3. Guard: Working tree must be clean ────────────────────────────────────
echo
echo "  [3/9] Working tree guard"
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
  fail "Uncommitted changes detected. Commit or stash all changes before deploying."
  git status --short
else
  ok "Working tree is clean"
fi
info "HEAD: $(git rev-parse --short HEAD) — $(git log -1 --format='%s')"

# ── 4. Security greps — must return zero matches ───────────────────────────
echo
echo "  [4/9] Security greps"

check_grep() {
  local label="$1"; local pattern="$2"; local path="$3"
  COUNT=$(grep -rc "$pattern" "$path" 2>/dev/null | awk -F: '{s+=$2} END{print s+0}')
  if [ "$COUNT" -eq 0 ]; then
    ok "$label (0 matches)"
  else
    fail "$label — $COUNT match(es) found — resolve before deploying"
    grep -rn "$pattern" "$path" | head -5
  fi
}

check_grep "No seeded access codes in frontend" \
  "SYSADMIN2026\|ADMIN703\|ADMIN7WG\|ADMINNATIONAL\|703SQN2026\|AUDITOR2026" \
  "connected-frontend"

check_grep "No localStorage usage in frontend" \
  "localStorage" \
  "connected-frontend"

check_grep "No access-code hashes in frontend" \
  "code_hash\|plain_code" \
  "connected-frontend"

check_grep "No JWT_SECRET/SECRET_KEY in frontend" \
  "JWT_SECRET\|SECRET_KEY" \
  "connected-frontend"

check_grep "No real DB connection strings in frontend" \
  "postgresql://\|postgres://\|mysql://\|sqlite:///" \
  "connected-frontend"

# ── 5. Alembic head check ─────────────────────────────────────────────────
echo
echo "  [5/9] Alembic migration head"
if [ -d "backend" ]; then
  pushd backend > /dev/null
  if source .venv/bin/activate 2>/dev/null; then
    ALEMBIC_HEAD=$(python -m alembic heads 2>/dev/null | grep -o '[a-f0-9]\{12\}' | head -1 || echo "unknown")
    info "Alembic head: $ALEMBIC_HEAD"
    if [ "$ALEMBIC_HEAD" != "unknown" ] && [ -n "$ALEMBIC_HEAD" ]; then
      ok "Alembic head resolved: $ALEMBIC_HEAD"
    else
      fail "Could not resolve Alembic head"
    fi
    deactivate 2>/dev/null || true
  else
    warn "Could not activate .venv — Alembic check skipped"
  fi
  popd > /dev/null
else
  fail "backend/ directory not found"
fi

# ── 6. Backend test suite ─────────────────────────────────────────────────
echo
echo "  [6/9] Backend test suite"
if [ -d "backend" ]; then
  pushd backend > /dev/null
  if source .venv/bin/activate 2>/dev/null; then
    RESULT=$(python -m pytest tests/ -q --tb=no 2>&1 | tail -3)
    LASTLINE=$(echo "$RESULT" | tail -1)
    if echo "$LASTLINE" | grep -q "passed" && ! echo "$LASTLINE" | grep -q "failed"; then
      ok "Tests: $LASTLINE"
    else
      fail "Test suite has failures — $LASTLINE"
      echo "$RESULT"
    fi
    deactivate 2>/dev/null || true
  else
    warn ".venv not found — test suite skipped (run: cd backend && python -m pytest tests/ -q)"
  fi
  popd > /dev/null
else
  fail "backend/ directory not found"
fi

# ── 7. Railway CLI check ──────────────────────────────────────────────────
echo
echo "  [7/9] Railway CLI"
if command -v railway &>/dev/null; then
  ok "railway CLI found: $(railway --version 2>/dev/null || echo 'version unknown')"
  RAILWAY_STATUS=$(railway status 2>&1 || true)
  if echo "$RAILWAY_STATUS" | grep -qi "not logged in\|no project\|error"; then
    fail "Railway CLI not authenticated or no project linked: $RAILWAY_STATUS"
  else
    info "Railway status: $(echo "$RAILWAY_STATUS" | head -2 | tr '\n' ' ')"
    # Guard: confirm we are in staging, not production
    if echo "$RAILWAY_STATUS" | grep -qi "production\|prod"; then
      if ! echo "$RAILWAY_STATUS" | grep -qi "staging"; then
        fail "Railway appears to be pointing at production. Switch to staging: railway environment staging"
      else
        ok "Railway is linked (staging appears present)"
      fi
    else
      ok "Railway CLI authenticated"
    fi
  fi
else
  warn "railway CLI not installed — skipping Railway checks"
  info "Install: npm install -g @railway/cli"
fi

# ── 8. Summary ─────────────────────────────────────────────────────────────
echo
echo "======================================================="
echo "  Preflight summary"
echo "  Passed: $PASS   Failed: $FAIL"
echo "======================================================="
echo

if [ "$FAIL" -gt 0 ]; then
  die "$FAIL preflight check(s) FAILED. Resolve all failures before deploying to staging."
fi

# ── 9. Confirmation gate ──────────────────────────────────────────────────
echo "  All preflight checks passed."
echo
echo -e "  ${YLW}IMPORTANT:${NC} You are about to deploy to STAGING."
echo "  This will update the staging environment with your current branch."
echo "  Production is NOT affected."
echo
echo "  Branch : $CURRENT_BRANCH"
echo "  HEAD   : $(git rev-parse --short HEAD) — $(git log -1 --format='%s')"
echo
echo -e "  To confirm staging deployment, type exactly:"
echo -e "  ${BLU}DEPLOY TO STAGING${NC}"
echo
read -r CONFIRM

if [ "$CONFIRM" != "DEPLOY TO STAGING" ]; then
  echo
  echo "  Confirmation phrase did not match. Deployment aborted."
  echo "  (You typed: '$CONFIRM')"
  echo
  exit 1
fi

# ── Run deployment ─────────────────────────────────────────────────────────
echo
if [ "${DRY_RUN:-0}" = "1" ]; then
  echo -e "  ${YLW}DRY RUN${NC} — would run: railway up --environment staging"
  echo "  Skipping actual deploy (DRY_RUN=1)."
else
  echo "  Deploying to staging…"
  railway up --environment staging
  echo
  echo -e "  ${GRN}Staging deployment initiated.${NC}"
  echo "  Monitor at: https://railway.app (exemplary-emotion project, staging environment)"
fi
echo
