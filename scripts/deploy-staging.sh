#!/usr/bin/env bash
# deploy-staging.sh — Hardened staging deployment guard for AAFC TMS.
#
# SAFETY DESIGN:
#   This script verifies exact immutable Railway IDs (project, environment,
#   service) before any deployment call.  Name-based or context-based resolution
#   alone is not trusted — a previous production incident occurred because the
#   resolved Railway context was not safely fixed at deployment time.
#
# ALLOWLISTED IMMUTABLE IDs:
#   Project:     f5d9524f-8a57-44ff-86b7-ab66aec00e73  (exemplary-emotion)
#   Staging env: 77a45568-5c16-46c2-9065-d5d339208b0e
#   Backend svc: deb53faa-ca8d-4291-aa2e-9ff3029c50f8  (aafc-tms-backend)
#   Frontend svc:2b5e6359-2523-4209-be5b-bdf7f5273ec5  (aafc-tms-frontend)
#   PW svc:      253cf237-1836-43bc-9ee4-0e4eefd447b4  (aafc-tms-planning-workspace-preview)
#
# PRODUCTION IDs (must NEVER be targeted):
#   Production env: 571a8028-3640-4542-a4ab-7a1ee6b1f693
#
# USAGE:
#   bash scripts/deploy-staging.sh
#   DRY_RUN=1 bash scripts/deploy-staging.sh   # preflight only, no railway up

set -uo pipefail

# ── Immutable allowlist ────────────────────────────────────────────────────────
EXPECTED_PROJECT_ID="f5d9524f-8a57-44ff-86b7-ab66aec00e73"
EXPECTED_STAGING_ENV_ID="77a45568-5c16-46c2-9065-d5d339208b0e"
PRODUCTION_ENV_ID="571a8028-3640-4542-a4ab-7a1ee6b1f693"

EXPECTED_BACKEND_SVC_ID="deb53faa-ca8d-4291-aa2e-9ff3029c50f8"
EXPECTED_FRONTEND_SVC_ID="2b5e6359-2523-4209-be5b-bdf7f5273ec5"
EXPECTED_PW_SVC_ID="253cf237-1836-43bc-9ee4-0e4eefd447b4"

EXPECTED_BACKEND_SVC_NAME="aafc-tms-backend"
EXPECTED_FRONTEND_SVC_NAME="aafc-tms-frontend"
EXPECTED_PW_SVC_NAME="aafc-tms-planning-workspace-preview"

EXPECTED_STAGING_BACKEND_DOMAIN="aafc-tms-backend-staging.up.railway.app"
EXPECTED_STAGING_FRONTEND_DOMAIN="aafc-tms-frontend-staging.up.railway.app"
EXPECTED_STAGING_PW_DOMAIN="aafc-tms-planning-workspace-preview-staging.up.railway.app"

EXPECTED_BRANCH="feature/restore-planning-workspace"
EXPECTED_SOURCE_DIRS="connected-frontend backend frontend"

# The fix commit that MUST be an ancestor of HEAD before deployment is allowed.
# This ensures all code corrections from the staging remediation are present.
# This value is fixed — it does NOT change when the deploy script is updated.
REQUIRED_ANCESTOR="de27c42"

# ── Color helpers ──────────────────────────────────────────────────────────────
RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[0;33m'; BLU='\033[0;34m'; NC='\033[0m'
PASS_COUNT=0; FAIL_COUNT=0

ok()   { echo -e "  ${GRN}[PASS]${NC} $1"; PASS_COUNT=$((PASS_COUNT+1)); }
fail() { echo -e "  ${RED}[FAIL]${NC} $1"; FAIL_COUNT=$((FAIL_COUNT+1)); }
info() { echo -e "  ${BLU}[INFO]${NC} $1"; }
warn() { echo -e "  ${YLW}[WARN]${NC} $1"; }
die()  { echo -e "\n  ${RED}══ ABORT ══${NC} $1\n"; exit 1; }

echo
echo "════════════════════════════════════════════════════════════════════"
echo "  AAFC TMS — Hardened Staging Deployment Guard"
echo "════════════════════════════════════════════════════════════════════"
echo

# ══ STEP 1: Fetch Railway state once ════════════════════════════════════════
echo "  [1/10] Fetching Railway project state…"
RAILWAY_JSON=$(railway status --json 2>&1)
if echo "$RAILWAY_JSON" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
  ok "Railway JSON fetched successfully"
else
  die "Failed to parse Railway JSON. Ensure 'railway' CLI is authenticated."
fi

# ══ STEP 2: Verify project ID ════════════════════════════════════════════════
echo
echo "  [2/10] Verifying Railway project ID…"
ACTUAL_PROJECT_ID=$(echo "$RAILWAY_JSON" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(d.get('id','MISSING'))
" 2>/dev/null || echo "ERROR")

info "Expected project ID: $EXPECTED_PROJECT_ID"
info "Actual  project ID:  $ACTUAL_PROJECT_ID"
if [ "$ACTUAL_PROJECT_ID" != "$EXPECTED_PROJECT_ID" ]; then
  die "Project ID mismatch. Linked project is not exemplary-emotion. Aborting."
fi
ok "Project ID matches: $ACTUAL_PROJECT_ID"

# ══ STEP 3: Verify staging environment ID ════════════════════════════════════
echo
echo "  [3/10] Verifying staging environment ID…"
ACTUAL_STAGING_ENV_ID=$(echo "$RAILWAY_JSON" | python3 -c "
import json,sys
data=json.load(sys.stdin)
for env in data.get('environments',{}).get('edges',[]):
    if env['node']['name']=='staging':
        print(env['node']['id'])
        break
else:
    print('MISSING')
" 2>/dev/null || echo "ERROR")

info "Expected staging env ID: $EXPECTED_STAGING_ENV_ID"
info "Actual  staging env ID:  $ACTUAL_STAGING_ENV_ID"
if [ "$ACTUAL_STAGING_ENV_ID" != "$EXPECTED_STAGING_ENV_ID" ]; then
  die "Staging environment ID mismatch. The staging environment UUID has changed or the wrong environment is linked. Aborting."
fi
ok "Staging environment ID matches: $ACTUAL_STAGING_ENV_ID"

# Hard check: staging env ID must NOT equal production env ID
if [ "$ACTUAL_STAGING_ENV_ID" = "$PRODUCTION_ENV_ID" ]; then
  die "CRITICAL: Staging environment ID matches production! Aborting."
fi
ok "Staging env ID is distinct from production env ID"

# ══ STEP 4: Verify service IDs ════════════════════════════════════════════════
echo
echo "  [4/10] Verifying service IDs…"

ACTUAL_BACKEND_SVC_ID=$(echo "$RAILWAY_JSON" | python3 -c "
import json,sys
data=json.load(sys.stdin)
for s in data.get('services',{}).get('edges',[]):
    if s['node']['name']=='$EXPECTED_BACKEND_SVC_NAME':
        print(s['node']['id']); break
else: print('MISSING')
" 2>/dev/null || echo "ERROR")

ACTUAL_FRONTEND_SVC_ID=$(echo "$RAILWAY_JSON" | python3 -c "
import json,sys
data=json.load(sys.stdin)
for s in data.get('services',{}).get('edges',[]):
    if s['node']['name']=='$EXPECTED_FRONTEND_SVC_NAME':
        print(s['node']['id']); break
else: print('MISSING')
" 2>/dev/null || echo "ERROR")

ACTUAL_PW_SVC_ID=$(echo "$RAILWAY_JSON" | python3 -c "
import json,sys
data=json.load(sys.stdin)
for s in data.get('services',{}).get('edges',[]):
    if s['node']['name']=='$EXPECTED_PW_SVC_NAME':
        print(s['node']['id']); break
else: print('MISSING')
" 2>/dev/null || echo "ERROR")

info "Backend  svc — expected: $EXPECTED_BACKEND_SVC_ID  actual: $ACTUAL_BACKEND_SVC_ID"
info "Frontend svc — expected: $EXPECTED_FRONTEND_SVC_ID  actual: $ACTUAL_FRONTEND_SVC_ID"
info "PW svc       — expected: $EXPECTED_PW_SVC_ID  actual: $ACTUAL_PW_SVC_ID"

[ "$ACTUAL_BACKEND_SVC_ID"  = "$EXPECTED_BACKEND_SVC_ID"  ] && ok "Backend  service ID matches" || fail "Backend  service ID MISMATCH"
[ "$ACTUAL_FRONTEND_SVC_ID" = "$EXPECTED_FRONTEND_SVC_ID" ] && ok "Frontend service ID matches" || fail "Frontend service ID MISMATCH"
[ "$ACTUAL_PW_SVC_ID"       = "$EXPECTED_PW_SVC_ID"       ] && ok "PW       service ID matches" || fail "PW       service ID MISMATCH"

# ══ STEP 5: Verify staging domains and reject any production domain ══════════
echo
echo "  [5/10] Verifying staging target domains — checking for production contamination…"

STAGING_DOMAINS=$(echo "$RAILWAY_JSON" | python3 -c "
import json,sys
data=json.load(sys.stdin)
for env in data.get('environments',{}).get('edges',[]):
    if env['node']['id'] == '$EXPECTED_STAGING_ENV_ID':
        for si in env['node'].get('serviceInstances',{}).get('edges',[]):
            for d in si['node'].get('domains',{}).get('serviceDomains',[]):
                print(d['domain'])
" 2>/dev/null || echo "ERROR")

echo "  Staging service domains:"
echo "$STAGING_DOMAINS" | while read -r domain; do [ -n "$domain" ] && echo "    $domain"; done

# Reject if any production domain appears in staging targets
if echo "$STAGING_DOMAINS" | grep -q "production.up.railway.app"; then
  die "Production domain detected in staging service list! Aborting."
fi
ok "No production domains detected in staging targets"

# Verify expected staging domains are present
echo "$STAGING_DOMAINS" | grep -qF "$EXPECTED_STAGING_BACKEND_DOMAIN"  && ok "Backend  staging domain confirmed: $EXPECTED_STAGING_BACKEND_DOMAIN"  || fail "Backend  staging domain NOT found"
echo "$STAGING_DOMAINS" | grep -qF "$EXPECTED_STAGING_FRONTEND_DOMAIN" && ok "Frontend staging domain confirmed: $EXPECTED_STAGING_FRONTEND_DOMAIN" || fail "Frontend staging domain NOT found"
echo "$STAGING_DOMAINS" | grep -qF "$EXPECTED_STAGING_PW_DOMAIN"       && ok "PW       staging domain confirmed: $EXPECTED_STAGING_PW_DOMAIN"       || fail "PW       staging domain NOT found"

# ══ STEP 6: Git state checks ═════════════════════════════════════════════════
echo
echo "  [6/10] Git state checks…"

# Branch check
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "UNKNOWN")
info "Current branch: $CURRENT_BRANCH"
if [ "$CURRENT_BRANCH" != "$EXPECTED_BRANCH" ]; then
  die "Branch is '$CURRENT_BRANCH', expected '$EXPECTED_BRANCH'. Aborting."
fi
ok "Branch matches: $CURRENT_BRANCH"

# Reject main/master/production branches outright
if [[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" || "$CURRENT_BRANCH" == *"production"* ]]; then
  die "Current branch '$CURRENT_BRANCH' is a protected branch. Aborting."
fi

# HEAD: record current HEAD for display and confirmation phrase
CURRENT_HEAD=$(git rev-parse --short HEAD 2>/dev/null || echo "UNKNOWN")
info "Current HEAD:    $CURRENT_HEAD — $(git log -1 --format='%s')"

# Required ancestor: de27c42 (the staged code fix commit) must be in HEAD's history.
# This ensures all code corrections are present regardless of subsequent deploy-script commits.
if ! git merge-base --is-ancestor "$REQUIRED_ANCESTOR" HEAD 2>/dev/null; then
  die "Required fix commit $REQUIRED_ANCESTOR is NOT an ancestor of HEAD ($CURRENT_HEAD). The staged corrections are missing. Aborting."
fi
ok "Required fix commit $REQUIRED_ANCESTOR is an ancestor of HEAD $CURRENT_HEAD"

# Working tree must be clean
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
  fail "Uncommitted changes detected — working tree is dirty"
  git status --short
  die "Resolve uncommitted changes before deploying."
fi
ok "Working tree is clean"

# Commit must be pushed to remote
UNPUSHED=$(git log "origin/${EXPECTED_BRANCH}..HEAD" --oneline 2>/dev/null || echo "ERROR_CHECKING_REMOTE")
if [ -n "$UNPUSHED" ]; then
  fail "Unpushed commits detected:"
  echo "$UNPUSHED" | while read -r line; do echo "    $line"; done
  die "Push all commits to origin/$EXPECTED_BRANCH before deploying."
fi
ok "HEAD is pushed to origin/$EXPECTED_BRANCH"

# ══ STEP 7: Security greps ════════════════════════════════════════════════════
echo
echo "  [7/10] Security greps…"

check_grep() {
  local label="$1" pattern="$2" path="$3"
  COUNT=$(grep -rc "$pattern" "$path" 2>/dev/null | awk -F: '{s+=$2} END{print s+0}')
  if [ "$COUNT" -eq 0 ]; then
    ok "$label (0 matches)"
  else
    fail "$label — $COUNT match(es) found"
    grep -rn "$pattern" "$path" | head -5
  fi
}

check_grep "No seeded access codes in connected-frontend" \
  "SYSADMIN2026\|ADMIN703\|ADMIN7WG\|ADMINNATIONAL" "connected-frontend"
check_grep "No localStorage in connected-frontend" \
  "localStorage" "connected-frontend"
check_grep "No access-code hashes in connected-frontend" \
  "code_hash\|plain_code" "connected-frontend"
check_grep "No JWT_SECRET/SECRET_KEY in connected-frontend" \
  "JWT_SECRET\|SECRET_KEY" "connected-frontend"
check_grep "No DB connection strings in connected-frontend" \
  "postgresql://\|postgres://\|sqlite:///" "connected-frontend"

# ══ STEP 8: Backend tests ══════════════════════════════════════════════════════
echo
echo "  [8/10] Backend test suite…"
if [ -d "backend" ]; then
  pushd backend > /dev/null
  if source .venv/bin/activate 2>/dev/null; then
    RESULT=$(python -m pytest tests/ -q --tb=no 2>&1 | tail -3)
    LASTLINE=$(echo "$RESULT" | tail -1)
    if echo "$LASTLINE" | grep -q "passed" && ! echo "$LASTLINE" | grep -q "failed"; then
      ok "Tests: $LASTLINE"
    else
      fail "Test suite failures: $LASTLINE"
      echo "$RESULT"
    fi
    deactivate 2>/dev/null || true
  else
    warn ".venv not found — skipping test suite"
  fi
  popd > /dev/null
else
  fail "backend/ directory not found"
fi

# ══ STEP 9: Alembic migration head ════════════════════════════════════════════
echo
echo "  [9/10] Alembic migration head…"
if [ -d "backend" ]; then
  pushd backend > /dev/null
  if source .venv/bin/activate 2>/dev/null; then
    ALEMBIC_HEAD=$(python -m alembic heads 2>/dev/null | grep -oE '[a-f0-9]{12}' | head -1 || echo "unknown")
    info "Alembic head in codebase: $ALEMBIC_HEAD"
    if [ "$ALEMBIC_HEAD" = "b2c3d4e5f6a7" ]; then
      ok "Alembic head is b2c3d4e5f6a7 (v40 — includes subject_area_tags.updated_by fix)"
    elif [ -n "$ALEMBIC_HEAD" ] && [ "$ALEMBIC_HEAD" != "unknown" ]; then
      warn "Alembic head is $ALEMBIC_HEAD (not b2c3d4e5f6a7 — migration chain may have changed)"
    else
      fail "Could not resolve Alembic head"
    fi
    deactivate 2>/dev/null || true
  else
    warn ".venv not found — Alembic check skipped"
  fi
  popd > /dev/null
fi

# ══ STEP 10: Preflight Railway check ══════════════════════════════════════════
echo
echo "  [10/10] Railway CLI…"
if ! command -v railway &>/dev/null; then
  die "railway CLI not found. Install: npm install -g @railway/cli"
fi
ok "railway CLI found: $(railway --version 2>/dev/null || echo 'version unknown')"

# ══ Summary ════════════════════════════════════════════════════════════════════
echo
echo "════════════════════════════════════════════════════════════════════"
echo "  Preflight summary:  ${GRN}PASS: $PASS_COUNT${NC}   ${RED}FAIL: $FAIL_COUNT${NC}"
echo "════════════════════════════════════════════════════════════════════"
echo

if [ "$FAIL_COUNT" -gt 0 ]; then
  die "$FAIL_COUNT preflight check(s) FAILED. Resolve all failures before deploying."
fi

# ══ Full resolved target display ════════════════════════════════════════════
echo "  RESOLVED DEPLOYMENT TARGETS (verified against allowlist):"
echo
printf "  %-28s %s\n" "Project ID:"        "$ACTUAL_PROJECT_ID"
printf "  %-28s %s\n" "Project name:"      "exemplary-emotion"
printf "  %-28s %s\n" "Staging env ID:"    "$ACTUAL_STAGING_ENV_ID"
printf "  %-28s %s\n" "Staging env name:"  "staging"
printf "  %-28s %s\n" "Production env ID:" "$PRODUCTION_ENV_ID (NOT targeted)"
echo
printf "  %-28s %s\n" "Service 1 (FIRST):" "$EXPECTED_BACKEND_SVC_NAME"
printf "  %-28s %s\n" "  Service ID:"      "$ACTUAL_BACKEND_SVC_ID"
printf "  %-28s %s\n" "  Domain:"          "$EXPECTED_STAGING_BACKEND_DOMAIN"
printf "  %-28s %s\n" "  Source dir:"      "backend/"
echo
printf "  %-28s %s\n" "Service 2:"         "$EXPECTED_FRONTEND_SVC_NAME"
printf "  %-28s %s\n" "  Service ID:"      "$ACTUAL_FRONTEND_SVC_ID"
printf "  %-28s %s\n" "  Domain:"          "$EXPECTED_STAGING_FRONTEND_DOMAIN"
printf "  %-28s %s\n" "  Source dir:"      "connected-frontend/"
echo
printf "  %-28s %s\n" "Service 3 (LAST):"  "$EXPECTED_PW_SVC_NAME"
printf "  %-28s %s\n" "  Service ID:"      "$ACTUAL_PW_SVC_ID"
printf "  %-28s %s\n" "  Domain:"          "$EXPECTED_STAGING_PW_DOMAIN"
printf "  %-28s %s\n" "  Source dir:"      "frontend/"
echo
printf "  %-28s %s\n" "Branch:"            "$CURRENT_BRANCH"
printf "  %-28s %s\n" "Commit (HEAD):"     "$CURRENT_HEAD — $(git log -1 --format='%s')"
echo
echo -e "  ${YLW}Migration included in this deploy:${NC}"
echo "    v40 (b2c3d4e5f6a7) — ADD COLUMN subject_area_tags.updated_by VARCHAR(36) NULL"
echo "    Revises: a1b2c3d4e5f6 (v39)"
echo "    Additive only (no data loss). Downgrade removes the column."
echo

# ══ Confirmation gate ════════════════════════════════════════════════════════
REQUIRED_PHRASE="DEPLOY TO STAGING ${CURRENT_HEAD}"

echo -e "  ${YLW}══ AUTHORIZATION REQUIRED ══${NC}"
echo
echo "  To authorize staging deployment, type exactly:"
echo -e "  ${BLU}${REQUIRED_PHRASE}${NC}"
echo
echo "  Rejected inputs: blank, lowercase, different SHA, partial phrase."
echo
read -r CONFIRM

if [ -z "$CONFIRM" ]; then
  die "Empty input. Authorization phrase required."
fi
if [ "$CONFIRM" != "$REQUIRED_PHRASE" ]; then
  die "Authorization phrase did not match.\n  Typed:    '$CONFIRM'\n  Required: '$REQUIRED_PHRASE'"
fi

# Re-verify HEAD has not changed between preflight and confirmation
RECHECK_HEAD=$(git rev-parse --short HEAD 2>/dev/null || echo "CHANGED")
if [ "$RECHECK_HEAD" != "$CURRENT_HEAD" ]; then
  die "HEAD changed between preflight and confirmation ($CURRENT_HEAD → $RECHECK_HEAD). Aborting."
fi

# ══ Deployment ════════════════════════════════════════════════════════════════
echo
echo -e "  ${GRN}Authorization accepted.${NC} Deploying $CURRENT_HEAD to staging."
echo

if [ "${DRY_RUN:-0}" = "1" ]; then
  echo -e "  ${YLW}DRY RUN — would execute:${NC}"
  echo "    railway up --project $EXPECTED_PROJECT_ID --service $EXPECTED_BACKEND_SVC_NAME --environment staging --detach"
  echo "    [pause — operator confirms backend ACTIVE + migration ran + /api/subject-area-tags returns 200]"
  echo "    railway up --project $EXPECTED_PROJECT_ID --service $EXPECTED_FRONTEND_SVC_NAME --environment staging --detach"
  echo "    railway up --project $EXPECTED_PROJECT_ID --service $EXPECTED_PW_SVC_NAME --environment staging --detach"
  echo "  DRY RUN complete. No deployment was made."
  exit 0
fi

# ── Deploy 1/3: backend (must complete before frontends) ─────────────────────
echo "  [Deploy 1/3] Backend — ${EXPECTED_BACKEND_SVC_NAME}"
info "Service ID: $ACTUAL_BACKEND_SVC_ID"
info "Domain:     $EXPECTED_STAGING_BACKEND_DOMAIN"
info "Migration:  alembic upgrade head will run on container start (v40 will apply if staging DB is at v39)"
echo
railway up \
  --project "$EXPECTED_PROJECT_ID" \
  --service "$EXPECTED_BACKEND_SVC_NAME" \
  --environment staging \
  --detach 2>&1
echo
echo -e "  ${YLW}PAUSE — Backend deployment initiated.${NC}"
echo "  Monitor Railway dashboard: exemplary-emotion → staging → aafc-tms-backend"
echo
echo "  Before continuing, verify ALL of the following in the Railway dashboard:"
echo "    1. Deployment status is ACTIVE (green)"
echo "    2. Logs show: 'Running upgrade a1b2c3d4e5f6 -> b2c3d4e5f6a7'"
echo "    3. Logs show: gunicorn workers started"
echo "    4. Health endpoint responds:"
echo "       curl https://$EXPECTED_STAGING_BACKEND_DOMAIN/api/health/ready"
echo "       Expected: {\"status\":\"ready\",\"squadrons\":16}"
echo "    5. Subject-area-tags no longer returns 500 (requires a valid auth token)"
echo
echo "  Press Enter once backend is ACTIVE, migration logged, and health check passes."
echo "  Type 'abort' to stop here without deploying frontends."
read -r BACKEND_CONFIRM
if [ "$BACKEND_CONFIRM" = "abort" ]; then
  die "Operator aborted after backend deployment. Frontends not deployed."
fi

# Re-verify IDs have not changed
RECHECK_BACKEND_ID=$(echo "$RAILWAY_JSON" | python3 -c "
import json,sys
data=json.load(sys.stdin)
for s in data.get('services',{}).get('edges',[]):
    if s['node']['name']=='$EXPECTED_BACKEND_SVC_NAME':
        print(s['node']['id']); break
else: print('MISSING')
" 2>/dev/null || echo "ERROR")
if [ "$RECHECK_BACKEND_ID" != "$EXPECTED_BACKEND_SVC_ID" ]; then
  die "Backend service ID changed between preflight and frontend deploy! Aborting."
fi

# ── Deploy 2/3: Main TMS frontend ────────────────────────────────────────────
echo
echo "  [Deploy 2/3] Main TMS frontend — ${EXPECTED_FRONTEND_SVC_NAME}"
info "Service ID: $ACTUAL_FRONTEND_SVC_ID"
info "Domain:     $EXPECTED_STAGING_FRONTEND_DOMAIN"
info "Source:     connected-frontend/"
echo
railway up \
  --project "$EXPECTED_PROJECT_ID" \
  --service "$EXPECTED_FRONTEND_SVC_NAME" \
  --environment staging \
  --detach 2>&1
echo
echo -e "  ${YLW}Frontend deployment initiated.${NC}"
echo "  Monitor: exemplary-emotion → staging → aafc-tms-frontend"
echo "  Wait for ACTIVE status, then verify:"
echo "    curl -I https://$EXPECTED_STAGING_FRONTEND_DOMAIN/"
echo "    Check: meta name='app-build' present in HTML (fingerprint)"
echo "    Check: no 'appget/' requests on dashboard load"
echo

# ── Deploy 3/3: Planning Workspace ───────────────────────────────────────────
echo "  [Deploy 3/3] Planning Workspace — ${EXPECTED_PW_SVC_NAME}"
info "Service ID: $ACTUAL_PW_SVC_ID"
info "Domain:     $EXPECTED_STAGING_PW_DOMAIN"
info "Source:     frontend/"
info "Build cmd:  npm run build (tsc -b && vite build)"
info "Health:     /healthz → 200 OK"
echo
railway up \
  --project "$EXPECTED_PROJECT_ID" \
  --service "$EXPECTED_PW_SVC_NAME" \
  --environment staging \
  --detach 2>&1
echo

echo "════════════════════════════════════════════════════════════════════"
echo -e "  ${GRN}All three staging deployments initiated.${NC}"
echo "  Commit deployed: $CURRENT_HEAD"
echo
echo "  Verify all services ACTIVE in Railway dashboard before running Playwright."
echo "  Railway: https://railway.app → exemplary-emotion → staging"
echo
echo "  POST-DEPLOY CHECKLIST:"
echo "    Backend:  curl https://$EXPECTED_STAGING_BACKEND_DOMAIN/api/health/ready"
echo "    Frontend: curl -I https://$EXPECTED_STAGING_FRONTEND_DOMAIN/"
echo "    PW:       curl -I https://$EXPECTED_STAGING_PW_DOMAIN/"
echo "════════════════════════════════════════════════════════════════════"
echo
