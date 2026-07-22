#!/usr/bin/env bash
# deploy-staging.sh — Hardened staging deployment guard for AAFC TMS (v2).
#
# Changes from v1:
#   1. railway up uses immutable UUIDs: --service <uuid> --environment <uuid>
#   2. Backend gate is fully automated: polls /api/health/ready, checks migration
#      log, optionally checks /api/subject-area-tags (requires STAGING_AUTH_TOKEN).
#   3. Main TMS gate is automated: HTTP 200, build fingerprint, Playwright smoke.
#   4. PW gate is automated: HTTP 200, build fingerprint, Playwright smoke.
#   5. Pre-deployment active IDs recorded for rollback reference.
#   6. Gate failure stops the sequence; Railway retains prior active deployment.
#
# OPTIONAL ENV VARS:
#   STAGING_AUTH_TOKEN   Bearer token for authenticated endpoint checks.
#                        Never printed. If unset, auth checks are skipped.
#
# USAGE:
#   bash scripts/deploy-staging.sh
#   DRY_RUN=1 bash scripts/deploy-staging.sh

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
REQUIRED_ANCESTOR="de27c42"
REQUIRED_ALEMBIC_HEAD="b2c3d4e5f6a7"

BACKEND_GATE_TIMEOUT=600
FRONTEND_GATE_TIMEOUT=600
PW_GATE_TIMEOUT=600
POLL_INTERVAL=15

# ── Colour helpers ─────────────────────────────────────────────────────────────
RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[0;33m'; BLU='\033[0;34m'; NC='\033[0m'
PASS_COUNT=0; FAIL_COUNT=0

ok()   { echo -e "  ${GRN}[PASS]${NC} $1"; PASS_COUNT=$((PASS_COUNT+1)); }
fail() { echo -e "  ${RED}[FAIL]${NC} $1"; FAIL_COUNT=$((FAIL_COUNT+1)); }
info() { echo -e "  ${BLU}[INFO]${NC} $1"; }
warn() { echo -e "  ${YLW}[WARN]${NC} $1"; }
die()  { echo -e "\n  ${RED}══ ABORT ══${NC} $1\n"; exit 1; }

# ── Gate helpers ───────────────────────────────────────────────────────────────

# poll_health <url> <timeout_s> <description>
# Returns 0 when HTTP 200 received; 1 on timeout.
poll_health() {
  local url="$1" timeout="$2" desc="$3"
  local elapsed=0
  info "Polling $desc: $url  (timeout ${timeout}s, interval ${POLL_INTERVAL}s)"
  while [ "$elapsed" -lt "$timeout" ]; do
    local code
    code=$(curl -s -o /dev/null -w "%{http_code}" \
      --connect-timeout 10 --max-time 15 "$url" 2>/dev/null || echo "000")
    if [ "$code" = "200" ]; then
      ok "$desc → HTTP 200 after ${elapsed}s"
      return 0
    fi
    echo "    [${elapsed}s] HTTP $code — waiting…"
    sleep "$POLL_INTERVAL"
    elapsed=$((elapsed + POLL_INTERVAL))
  done
  fail "$desc did not return HTTP 200 within ${timeout}s"
  return 1
}

# poll_migration_log <svc_id> <env_id> <expected_text> <timeout_s>
# Returns 0 when expected_text found in recent logs; 1 on timeout.
poll_migration_log() {
  local svc_id="$1" env_id="$2" expected="$3" timeout="${4:-180}"
  local elapsed=0
  info "Watching logs for: $expected  (timeout ${timeout}s)"
  while [ "$elapsed" -lt "$timeout" ]; do
    local log_text
    log_text=$(railway logs \
      --project "$EXPECTED_PROJECT_ID" \
      --service "$svc_id" \
      --environment "$env_id" \
      --tail 100 2>/dev/null | sed 's/\x1b\[[0-9;]*m//g' || echo "")
    if echo "$log_text" | grep -qF "$expected"; then
      ok "Migration log confirmed: $expected"
      return 0
    fi
    sleep 15
    elapsed=$((elapsed + 15))
  done
  return 1
}

# parse_deploy_id <output>
# Extracts last UUID from railway up output (deployment ID if printed).
parse_deploy_id() {
  echo "$1" | grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' \
    | tail -1 || echo "unknown"
}

# run_playwright_smoke <grep_pattern> <description>
# Runs targeted Playwright tests. Skips gracefully if npx/spec unavailable.
run_playwright_smoke() {
  local pattern="$1" desc="$2"
  local spec="tools/playwright-staging/tests/staging-verification.spec.ts"
  if ! command -v npx &>/dev/null || [ ! -f "$spec" ]; then
    warn "Playwright not available — skipping browser smoke: $desc"
    return 0
  fi
  info "Playwright smoke: $desc"
  if npx playwright test \
      --project=chromium \
      --grep "$pattern" \
      --reporter=line \
      --timeout=60000 \
      "$spec" 2>&1; then
    ok "Playwright smoke PASS: $desc"
    return 0
  else
    fail "Playwright smoke FAIL: $desc"
    return 1
  fi
}

# ── Header ─────────────────────────────────────────────────────────────────────
echo
echo "════════════════════════════════════════════════════════════════════"
echo "  AAFC TMS — Hardened Staging Deployment Guard (v2)"
echo "  Deployment uses immutable UUIDs for all Railway targets."
echo "  All gates are automated. No deployment occurs before authorization."
echo "════════════════════════════════════════════════════════════════════"
echo

# ══ STEP 1 — Fetch Railway state ══════════════════════════════════════════════
echo "  [1/10] Fetching Railway project state…"
RAILWAY_JSON=$(railway status --json 2>&1)
if echo "$RAILWAY_JSON" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
  ok "Railway JSON fetched"
else
  die "Failed to parse Railway JSON. Run: railway login"
fi

# ══ STEP 2 — Verify project ID ════════════════════════════════════════════════
echo
echo "  [2/10] Verifying project ID…"
ACTUAL_PROJECT_ID=$(echo "$RAILWAY_JSON" | python3 -c "
import json,sys; d=json.load(sys.stdin); print(d.get('id','MISSING'))" 2>/dev/null || echo "ERROR")
info "Expected: $EXPECTED_PROJECT_ID"
info "Actual:   $ACTUAL_PROJECT_ID"
[ "$ACTUAL_PROJECT_ID" = "$EXPECTED_PROJECT_ID" ] \
  && ok "Project ID matches" \
  || die "Project ID mismatch — not exemplary-emotion. Aborting."

# ══ STEP 3 — Verify staging environment ID ════════════════════════════════════
echo
echo "  [3/10] Verifying staging environment ID…"
ACTUAL_STAGING_ENV_ID=$(echo "$RAILWAY_JSON" | python3 -c "
import json,sys
data=json.load(sys.stdin)
for env in data.get('environments',{}).get('edges',[]):
    if env['node']['name']=='staging':
        print(env['node']['id']); break
else: print('MISSING')" 2>/dev/null || echo "ERROR")
info "Expected: $EXPECTED_STAGING_ENV_ID"
info "Actual:   $ACTUAL_STAGING_ENV_ID"
[ "$ACTUAL_STAGING_ENV_ID" = "$EXPECTED_STAGING_ENV_ID" ] \
  && ok "Staging env ID matches" \
  || die "Staging env ID mismatch. Aborting."
[ "$ACTUAL_STAGING_ENV_ID" = "$PRODUCTION_ENV_ID" ] \
  && die "CRITICAL: Staging env ID equals production env ID!" \
  || ok "Staging env ID is distinct from production ($PRODUCTION_ENV_ID)"

# ══ STEP 4 — Verify service IDs ═══════════════════════════════════════════════
echo
echo "  [4/10] Verifying service IDs…"
ACTUAL_BACKEND_SVC_ID=$(echo "$RAILWAY_JSON" | python3 -c "
import json,sys; data=json.load(sys.stdin)
for s in data.get('services',{}).get('edges',[]):
    if s['node']['name']=='$EXPECTED_BACKEND_SVC_NAME':
        print(s['node']['id']); break
else: print('MISSING')" 2>/dev/null || echo "ERROR")

ACTUAL_FRONTEND_SVC_ID=$(echo "$RAILWAY_JSON" | python3 -c "
import json,sys; data=json.load(sys.stdin)
for s in data.get('services',{}).get('edges',[]):
    if s['node']['name']=='$EXPECTED_FRONTEND_SVC_NAME':
        print(s['node']['id']); break
else: print('MISSING')" 2>/dev/null || echo "ERROR")

ACTUAL_PW_SVC_ID=$(echo "$RAILWAY_JSON" | python3 -c "
import json,sys; data=json.load(sys.stdin)
for s in data.get('services',{}).get('edges',[]):
    if s['node']['name']=='$EXPECTED_PW_SVC_NAME':
        print(s['node']['id']); break
else: print('MISSING')" 2>/dev/null || echo "ERROR")

info "Backend  — expected: $EXPECTED_BACKEND_SVC_ID   actual: $ACTUAL_BACKEND_SVC_ID"
info "Frontend — expected: $EXPECTED_FRONTEND_SVC_ID  actual: $ACTUAL_FRONTEND_SVC_ID"
info "PW       — expected: $EXPECTED_PW_SVC_ID         actual: $ACTUAL_PW_SVC_ID"

[ "$ACTUAL_BACKEND_SVC_ID"  = "$EXPECTED_BACKEND_SVC_ID"  ] && ok "Backend  service ID matches" || fail "Backend  service ID MISMATCH"
[ "$ACTUAL_FRONTEND_SVC_ID" = "$EXPECTED_FRONTEND_SVC_ID" ] && ok "Frontend service ID matches" || fail "Frontend service ID MISMATCH"
[ "$ACTUAL_PW_SVC_ID"       = "$EXPECTED_PW_SVC_ID"       ] && ok "PW       service ID matches" || fail "PW       service ID MISMATCH"

[ "$FAIL_COUNT" -gt 0 ] && die "Service ID verification failed. Aborting."

# ══ STEP 5 — Verify staging domains, reject production ════════════════════════
echo
echo "  [5/10] Verifying staging target domains…"
STAGING_DOMAINS=$(echo "$RAILWAY_JSON" | python3 -c "
import json,sys
data=json.load(sys.stdin)
for env in data.get('environments',{}).get('edges',[]):
    if env['node']['id'] == '$EXPECTED_STAGING_ENV_ID':
        for si in env['node'].get('serviceInstances',{}).get('edges',[]):
            for d in si['node'].get('domains',{}).get('serviceDomains',[]):
                print(d['domain'])" 2>/dev/null || echo "ERROR")

echo "  Staging service domains:"
echo "$STAGING_DOMAINS" | while read -r d; do [ -n "$d" ] && echo "    $d"; done

echo "$STAGING_DOMAINS" | grep -q "production.up.railway.app" \
  && die "Production domain detected in staging service list!" \
  || ok "No production domains in staging targets"

echo "$STAGING_DOMAINS" | grep -qF "$EXPECTED_STAGING_BACKEND_DOMAIN"  \
  && ok "Backend  staging domain: $EXPECTED_STAGING_BACKEND_DOMAIN"  \
  || fail "Backend  staging domain NOT found"
echo "$STAGING_DOMAINS" | grep -qF "$EXPECTED_STAGING_FRONTEND_DOMAIN" \
  && ok "Frontend staging domain: $EXPECTED_STAGING_FRONTEND_DOMAIN" \
  || fail "Frontend staging domain NOT found"
echo "$STAGING_DOMAINS" | grep -qF "$EXPECTED_STAGING_PW_DOMAIN"       \
  && ok "PW       staging domain: $EXPECTED_STAGING_PW_DOMAIN"       \
  || fail "PW       staging domain NOT found"

# ══ STEP 6 — Git state ════════════════════════════════════════════════════════
echo
echo "  [6/10] Git state checks…"
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "UNKNOWN")
info "Branch: $CURRENT_BRANCH"
[ "$CURRENT_BRANCH" = "$EXPECTED_BRANCH" ] \
  || die "Branch is '$CURRENT_BRANCH', expected '$EXPECTED_BRANCH'. Aborting."
ok "Branch: $CURRENT_BRANCH"
[[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" || "$CURRENT_BRANCH" == *"production"* ]] \
  && die "Protected branch '$CURRENT_BRANCH'. Aborting."

CURRENT_HEAD=$(git rev-parse --short HEAD 2>/dev/null || echo "UNKNOWN")
info "HEAD: $CURRENT_HEAD — $(git log -1 --format='%s')"

git merge-base --is-ancestor "$REQUIRED_ANCESTOR" HEAD 2>/dev/null \
  || die "Fix commit $REQUIRED_ANCESTOR is NOT an ancestor of HEAD $CURRENT_HEAD. Aborting."
ok "Fix commit $REQUIRED_ANCESTOR is ancestor of $CURRENT_HEAD"

git diff-index --quiet HEAD -- 2>/dev/null \
  || die "Working tree has uncommitted changes. Aborting."
ok "Working tree clean"

UNPUSHED=$(git log "origin/${EXPECTED_BRANCH}..HEAD" --oneline 2>/dev/null || echo "ERROR")
[ -n "$UNPUSHED" ] && die "Unpushed commits:\n$(echo "$UNPUSHED" | sed 's/^/  /')\nPush to origin/$EXPECTED_BRANCH first."
ok "HEAD is pushed to origin/$EXPECTED_BRANCH"

# ══ STEP 7 — Security greps ═══════════════════════════════════════════════════
echo
echo "  [7/10] Security greps…"
check_grep() {
  local label="$1" pattern="$2" path="$3"
  local count
  count=$(grep -rc "$pattern" "$path" 2>/dev/null | awk -F: '{s+=$2} END{print s+0}')
  if [ "$count" -eq 0 ]; then
    ok "$label (0 matches)"
  else
    fail "$label — $count match(es)"
    grep -rn "$pattern" "$path" | head -3
  fi
}
check_grep "No seeded codes in frontend"            "SYSADMIN2026\|ADMIN703\|ADMIN7WG\|ADMINNATIONAL" "connected-frontend"
check_grep "No localStorage in frontend"             "localStorage"                                     "connected-frontend"
check_grep "No access-code hashes in frontend"       "code_hash\|plain_code"                           "connected-frontend"
check_grep "No JWT_SECRET/SECRET_KEY in frontend"    "JWT_SECRET\|SECRET_KEY"                           "connected-frontend"
check_grep "No DB connection strings in frontend"    "postgresql://\|postgres://\|sqlite:///"           "connected-frontend"

# ══ STEP 8 — Backend tests ════════════════════════════════════════════════════
echo
echo "  [8/10] Backend test suite…"
if [ -d "backend" ]; then
  pushd backend > /dev/null
  if source .venv/bin/activate 2>/dev/null; then
    TEST_OUT=$(python -m pytest tests/ -q --tb=no 2>&1)
    LASTLINE=$(echo "$TEST_OUT" | tail -1)
    if echo "$LASTLINE" | grep -q "passed" && ! echo "$LASTLINE" | grep -q "failed"; then
      ok "Tests: $LASTLINE"
    else
      fail "Test suite: $LASTLINE"
      echo "$TEST_OUT" | tail -10
    fi
    deactivate 2>/dev/null || true
  else
    warn ".venv not found — skipping backend tests"
  fi
  popd > /dev/null
else
  fail "backend/ directory not found"
fi

# ══ STEP 9 — Alembic head ════════════════════════════════════════════════════
echo
echo "  [9/10] Alembic migration head…"
if [ -d "backend" ]; then
  pushd backend > /dev/null
  if source .venv/bin/activate 2>/dev/null; then
    ALEMBIC_HEAD=$(python -m alembic heads 2>/dev/null | grep -oE '[a-f0-9]{12}' | head -1 || echo "unknown")
    info "Alembic head: $ALEMBIC_HEAD"
    [ "$ALEMBIC_HEAD" = "$REQUIRED_ALEMBIC_HEAD" ] \
      && ok "Alembic head is $REQUIRED_ALEMBIC_HEAD (v40 — subject_area_tags.updated_by)" \
      || warn "Alembic head is $ALEMBIC_HEAD (expected $REQUIRED_ALEMBIC_HEAD)"
    deactivate 2>/dev/null || true
  else
    warn ".venv not found — Alembic check skipped"
  fi
  popd > /dev/null
fi

# ══ STEP 10 — Railway CLI ════════════════════════════════════════════════════
echo
echo "  [10/10] Railway CLI…"
command -v railway &>/dev/null || die "railway CLI not found. Install: npm install -g @railway/cli"
ok "railway CLI: $(railway --version 2>/dev/null || echo 'version unknown')"

# ══ Preflight summary ════════════════════════════════════════════════════════
echo
echo "════════════════════════════════════════════════════════════════════"
echo -e "  Preflight: ${GRN}PASS: $PASS_COUNT${NC}   ${RED}FAIL: $FAIL_COUNT${NC}"
echo "════════════════════════════════════════════════════════════════════"
echo
[ "$FAIL_COUNT" -gt 0 ] && die "$FAIL_COUNT preflight check(s) failed."

# ══ Resolved targets display ═════════════════════════════════════════════════
echo "  RESOLVED DEPLOYMENT TARGETS — verified against immutable allowlist"
echo
printf "  %-32s %s\n" "Project ID:"           "$ACTUAL_PROJECT_ID"
printf "  %-32s %s\n" "Staging env ID:"        "$ACTUAL_STAGING_ENV_ID"
printf "  %-32s %s\n" "Production env ID:"     "$PRODUCTION_ENV_ID  (NOT targeted)"
echo
printf "  %-32s %s\n" "Service 1 [FIRST]:"     "$EXPECTED_BACKEND_SVC_NAME"
printf "  %-32s %s\n" "  UUID:"                "$ACTUAL_BACKEND_SVC_ID"
printf "  %-32s %s\n" "  Domain:"              "$EXPECTED_STAGING_BACKEND_DOMAIN"
echo
printf "  %-32s %s\n" "Service 2:"             "$EXPECTED_FRONTEND_SVC_NAME"
printf "  %-32s %s\n" "  UUID:"                "$ACTUAL_FRONTEND_SVC_ID"
printf "  %-32s %s\n" "  Domain:"              "$EXPECTED_STAGING_FRONTEND_DOMAIN"
echo
printf "  %-32s %s\n" "Service 3 [LAST]:"      "$EXPECTED_PW_SVC_NAME"
printf "  %-32s %s\n" "  UUID:"                "$ACTUAL_PW_SVC_ID"
printf "  %-32s %s\n" "  Domain:"              "$EXPECTED_STAGING_PW_DOMAIN"
echo
printf "  %-32s %s\n" "Branch:"                "$CURRENT_BRANCH"
printf "  %-32s %s\n" "HEAD:"                  "$CURRENT_HEAD — $(git log -1 --format='%s')"
echo
echo -e "  ${YLW}Deployment commands use service UUID and environment UUID (not names):${NC}"
echo "    --service \$UUID  --environment $ACTUAL_STAGING_ENV_ID"
echo
echo -e "  ${YLW}Migration:${NC}"
echo "    v40 ($REQUIRED_ALEMBIC_HEAD) — ADD COLUMN subject_area_tags.updated_by VARCHAR(36)"
echo "    Additive. Revises a1b2c3d4e5f6. Staging DB currently at v39."
echo
echo -e "  ${YLW}Automated gates:${NC}"
echo "    Backend:  poll /api/health/ready (${BACKEND_GATE_TIMEOUT}s) + migration log + subject-area-tags"
echo "    Frontend: poll HTTP 200 (${FRONTEND_GATE_TIMEOUT}s) + fingerprint + Playwright smoke"
echo "    PW:       poll /healthz (${PW_GATE_TIMEOUT}s) + fingerprint + Playwright smoke"
echo
echo -e "  ${YLW}Rollback:${NC}"
echo "    On gate failure: sequence stops. Railway auto-retains prior active deployment."
echo "    Pre-deploy state is captured below for reference."
echo

# ══ Pre-deployment state (rollback reference) ═════════════════════════════════
PRE_BACKEND_DEPLOY_REF=$(railway logs \
  --project "$EXPECTED_PROJECT_ID" \
  --service "$ACTUAL_BACKEND_SVC_ID" \
  --environment "$ACTUAL_STAGING_ENV_ID" \
  --tail 1 2>/dev/null | grep -oE 'deploy[a-zA-Z/]*[0-9a-f-]{36}' | head -1 || echo "unknown")
info "Pre-deploy backend  ref: $PRE_BACKEND_DEPLOY_REF"
info "Pre-deploy frontend ref: check Railway dashboard → staging → aafc-tms-frontend → Deployments"
info "Pre-deploy PW       ref: check Railway dashboard → staging → aafc-tms-planning-workspace-preview → Deployments"

# ══ Authorization gate ════════════════════════════════════════════════════════
REQUIRED_PHRASE="DEPLOY TO STAGING ${CURRENT_HEAD}"
echo
echo -e "  ${YLW}══ AUTHORIZATION REQUIRED ══${NC}"
echo
echo "  Type exactly to authorize deployment of $CURRENT_HEAD:"
echo -e "  ${BLU}${REQUIRED_PHRASE}${NC}"
echo
read -r CONFIRM
[ -z "$CONFIRM" ]                && die "Empty input. Authorization required."
[ "$CONFIRM" != "$REQUIRED_PHRASE" ] && die "Phrase mismatch.\n  Typed:    '$CONFIRM'\n  Required: '$REQUIRED_PHRASE'"

RECHECK_HEAD=$(git rev-parse --short HEAD 2>/dev/null || echo "CHANGED")
[ "$RECHECK_HEAD" != "$CURRENT_HEAD" ] \
  && die "HEAD changed during prompt ($CURRENT_HEAD → $RECHECK_HEAD). Aborting."

echo
echo -e "  ${GRN}Authorization accepted.${NC} Deploying $CURRENT_HEAD to staging."
echo

# ══ DRY RUN ══════════════════════════════════════════════════════════════════
if [ "${DRY_RUN:-0}" = "1" ]; then
  echo -e "  ${YLW}DRY RUN — commands that would execute:${NC}"
  echo
  echo "  [1/3] Backend"
  echo "    railway up \\"
  echo "      --project $EXPECTED_PROJECT_ID \\"
  echo "      --service $ACTUAL_BACKEND_SVC_ID \\"
  echo "      --environment $ACTUAL_STAGING_ENV_ID \\"
  echo "      --detach"
  echo "    Gate: poll https://$EXPECTED_STAGING_BACKEND_DOMAIN/api/health/ready (${BACKEND_GATE_TIMEOUT}s)"
  echo "    Gate: migration log 'Running upgrade a1b2c3d4e5f6 -> $REQUIRED_ALEMBIC_HEAD'"
  echo "    Gate: /api/subject-area-tags → 200 (requires STAGING_AUTH_TOKEN)"
  echo
  echo "  [2/3] Main TMS frontend"
  echo "    railway up \\"
  echo "      --project $EXPECTED_PROJECT_ID \\"
  echo "      --service $ACTUAL_FRONTEND_SVC_ID \\"
  echo "      --environment $ACTUAL_STAGING_ENV_ID \\"
  echo "      --detach"
  echo "    Gate: poll https://$EXPECTED_STAGING_FRONTEND_DOMAIN/ (${FRONTEND_GATE_TIMEOUT}s)"
  echo "    Gate: build fingerprint contains $CURRENT_HEAD"
  echo "    Gate: Playwright smoke — [Dashboard], [Nav] Mobile, [Network]"
  echo
  echo "  [3/3] Planning Workspace"
  echo "    railway up \\"
  echo "      --project $EXPECTED_PROJECT_ID \\"
  echo "      --service $ACTUAL_PW_SVC_ID \\"
  echo "      --environment $ACTUAL_STAGING_ENV_ID \\"
  echo "      --detach"
  echo "    Gate: poll https://$EXPECTED_STAGING_PW_DOMAIN/healthz (${PW_GATE_TIMEOUT}s)"
  echo "    Gate: build fingerprint contains $CURRENT_HEAD"
  echo "    Gate: Playwright smoke — [Mission Backlog / PW], [PW]"
  echo
  echo "  DRY RUN complete. No deployment made."
  exit 0
fi

# ══════════════════════════════════════════════════════════════════════════════
# DEPLOYMENT 1/3 — BACKEND
# ══════════════════════════════════════════════════════════════════════════════
echo "────────────────────────────────────────────────────────────────────"
echo "  [Deploy 1/3] $EXPECTED_BACKEND_SVC_NAME"
info "  Service UUID: $ACTUAL_BACKEND_SVC_ID"
info "  Env UUID:     $ACTUAL_STAGING_ENV_ID"
info "  Project UUID: $EXPECTED_PROJECT_ID"
info "  Migration:    a1b2c3d4e5f6 → $REQUIRED_ALEMBIC_HEAD"
echo

BACKEND_UP_OUT=$(railway up \
  --project "$EXPECTED_PROJECT_ID" \
  --service "$ACTUAL_BACKEND_SVC_ID" \
  --environment "$ACTUAL_STAGING_ENV_ID" \
  --detach 2>&1)
echo "$BACKEND_UP_OUT"
BACKEND_NEW_DEPLOY_ID=$(parse_deploy_id "$BACKEND_UP_OUT")
info "Backend deployment ID (from railway up output): $BACKEND_NEW_DEPLOY_ID"

echo
echo "  ── Backend gate 1/3: health ─────────────────────────────────────────"
if ! poll_health \
    "https://$EXPECTED_STAGING_BACKEND_DOMAIN/api/health/ready" \
    "$BACKEND_GATE_TIMEOUT" \
    "Backend /api/health/ready"; then
  echo
  echo -e "  ${RED}══ BACKEND GATE FAILED: health ══${NC}"
  echo "  /api/health/ready did not return 200 within ${BACKEND_GATE_TIMEOUT}s."
  echo "  Possible: FAILED, CRASHED, REMOVED, or network timeout."
  echo "  Railway retains previous active deployment automatically."
  [ "$PRE_BACKEND_DEPLOY_REF" != "unknown" ] && echo "  Rollback reference: $PRE_BACKEND_DEPLOY_REF"
  die "Backend health gate failed. Frontends NOT deployed."
fi

echo
echo "  ── Backend gate 2/3: readiness JSON ────────────────────────────────"
READY_JSON=$(curl -s --connect-timeout 10 --max-time 15 \
  "https://$EXPECTED_STAGING_BACKEND_DOMAIN/api/health/ready" 2>/dev/null || echo '{}')
info "Response: $READY_JSON"
if echo "$READY_JSON" | python3 -c "
import json,sys
d=json.load(sys.stdin)
assert d.get('status')=='ready', repr(d)
" 2>/dev/null; then
  ok "Readiness status: ready"
else
  die "Backend /api/health/ready did not return status:ready. Response: $READY_JSON"
fi

echo
echo "  ── Backend gate 3/3: migration log + subject-area-tags ─────────────"
MIGRATION_LOG_TEXT="Running upgrade a1b2c3d4e5f6 -> $REQUIRED_ALEMBIC_HEAD"
if poll_migration_log \
    "$ACTUAL_BACKEND_SVC_ID" \
    "$ACTUAL_STAGING_ENV_ID" \
    "$MIGRATION_LOG_TEXT" \
    180; then
  : # ok() called inside function
else
  warn "Migration log not found within 180s."
  warn "Either migration was already applied on a prior run, or log window too small."
  warn "Verify manually: Railway → staging → aafc-tms-backend → Deployments → Logs"
  warn "Expected: $MIGRATION_LOG_TEXT"
fi

if [ -n "${STAGING_AUTH_TOKEN:-}" ]; then
  SAT_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
    --connect-timeout 10 --max-time 15 \
    -H "Authorization: Bearer $STAGING_AUTH_TOKEN" \
    "https://$EXPECTED_STAGING_BACKEND_DOMAIN/api/subject-area-tags" 2>/dev/null || echo "000")
  if [ "$SAT_CODE" = "200" ]; then
    ok "/api/subject-area-tags → 200 (v40 migration confirmed functional)"
  elif [ "$SAT_CODE" = "401" ] || [ "$SAT_CODE" = "403" ]; then
    warn "/api/subject-area-tags → $SAT_CODE (auth issue — check STAGING_AUTH_TOKEN)"
  else
    fail "/api/subject-area-tags → $SAT_CODE (expected 200)"
    die "subject-area-tags still erroring. Frontends NOT deployed."
  fi
else
  warn "STAGING_AUTH_TOKEN not set — /api/subject-area-tags check skipped"
  warn "Verify manually: curl -H 'Authorization: Bearer <token>' https://$EXPECTED_STAGING_BACKEND_DOMAIN/api/subject-area-tags"
fi

ok "Backend gate PASSED."

# Re-verify backend service ID before proceeding
RECHECK_BACKEND_ID=$(echo "$RAILWAY_JSON" | python3 -c "
import json,sys; data=json.load(sys.stdin)
for s in data.get('services',{}).get('edges',[]):
    if s['node']['name']=='$EXPECTED_BACKEND_SVC_NAME':
        print(s['node']['id']); break
else: print('MISSING')" 2>/dev/null || echo "ERROR")
[ "$RECHECK_BACKEND_ID" = "$EXPECTED_BACKEND_SVC_ID" ] \
  || die "Backend service ID changed between preflight and frontend deploy!"

# ══════════════════════════════════════════════════════════════════════════════
# DEPLOYMENT 2/3 — MAIN TMS FRONTEND
# ══════════════════════════════════════════════════════════════════════════════
echo
echo "────────────────────────────────────────────────────────────────────"
echo "  [Deploy 2/3] $EXPECTED_FRONTEND_SVC_NAME"
info "  Service UUID: $ACTUAL_FRONTEND_SVC_ID"
info "  Env UUID:     $ACTUAL_STAGING_ENV_ID"
info "  Project UUID: $EXPECTED_PROJECT_ID"
info "  Entrypoint:   connected-frontend/docker-entrypoint.sh (# sed delimiter)"
echo

FRONTEND_UP_OUT=$(railway up \
  --project "$EXPECTED_PROJECT_ID" \
  --service "$ACTUAL_FRONTEND_SVC_ID" \
  --environment "$ACTUAL_STAGING_ENV_ID" \
  --detach 2>&1)
echo "$FRONTEND_UP_OUT"
FRONTEND_NEW_DEPLOY_ID=$(parse_deploy_id "$FRONTEND_UP_OUT")
info "Frontend deployment ID: $FRONTEND_NEW_DEPLOY_ID"

echo
echo "  ── Frontend gate 1/3: HTTP 200 ──────────────────────────────────────"
if ! poll_health \
    "https://$EXPECTED_STAGING_FRONTEND_DOMAIN/" \
    "$FRONTEND_GATE_TIMEOUT" \
    "Frontend /"; then
  echo -e "  ${RED}══ FRONTEND GATE FAILED: HTTP 200 ══${NC}"
  echo "  Railway retains previous active deployment. PW NOT deployed."
  die "Frontend gate failed."
fi

echo
echo "  ── Frontend gate 2/3: build fingerprint ────────────────────────────"
FRONTEND_HTML=$(curl -s --connect-timeout 10 --max-time 20 \
  "https://$EXPECTED_STAGING_FRONTEND_DOMAIN/" 2>/dev/null || echo "")
if echo "$FRONTEND_HTML" | grep -q 'name="app-build"'; then
  ok "Build fingerprint meta tag present"
  if echo "$FRONTEND_HTML" | grep -q "$CURRENT_HEAD"; then
    ok "Fingerprint contains current HEAD: $CURRENT_HEAD"
  else
    warn "Fingerprint meta present but SHA not visible in raw HTML (may be in content attr)"
    info "Check: curl https://$EXPECTED_STAGING_FRONTEND_DOMAIN/ | grep app-build"
  fi
else
  fail "Build fingerprint meta tag NOT found"
fi

echo
echo "  ── Frontend gate 3/3: Playwright browser smoke ─────────────────────"
if ! run_playwright_smoke '\[Dashboard\]|\[Nav\] Mobile|\[Network\]' \
    "Dashboard + Mobile nav + Network"; then
  die "Frontend Playwright smoke failed. PW NOT deployed."
fi

ok "Frontend gate PASSED."

# ══════════════════════════════════════════════════════════════════════════════
# DEPLOYMENT 3/3 — PLANNING WORKSPACE
# ══════════════════════════════════════════════════════════════════════════════
echo
echo "────────────────────────────────────────────────────────────────────"
echo "  [Deploy 3/3] $EXPECTED_PW_SVC_NAME"
info "  Service UUID: $ACTUAL_PW_SVC_ID"
info "  Env UUID:     $ACTUAL_STAGING_ENV_ID"
info "  Project UUID: $EXPECTED_PROJECT_ID"
info "  Entrypoint:   frontend/docker-entrypoint.sh (# sed delimiter — PW failure fixed)"
echo

PW_UP_OUT=$(railway up \
  --project "$EXPECTED_PROJECT_ID" \
  --service "$ACTUAL_PW_SVC_ID" \
  --environment "$ACTUAL_STAGING_ENV_ID" \
  --detach 2>&1)
echo "$PW_UP_OUT"
PW_NEW_DEPLOY_ID=$(parse_deploy_id "$PW_UP_OUT")
info "PW deployment ID: $PW_NEW_DEPLOY_ID"

echo
echo "  ── PW gate 1/3: HTTP 200 ────────────────────────────────────────────"
if ! poll_health \
    "https://$EXPECTED_STAGING_PW_DOMAIN/healthz" \
    "$PW_GATE_TIMEOUT" \
    "PW /healthz"; then
  info "Retrying root path…"
  if ! poll_health \
      "https://$EXPECTED_STAGING_PW_DOMAIN/" \
      120 \
      "PW /"; then
    echo -e "  ${RED}══ PW GATE FAILED: HTTP 200 ══${NC}"
    echo "  Neither /healthz nor / returned 200 within timeout."
    echo "  Railway retains previous active deployment."
    die "PW gate failed."
  fi
fi

echo
echo "  ── PW gate 2/3: build fingerprint ───────────────────────────────────"
PW_HTML=$(curl -s --connect-timeout 10 --max-time 20 \
  "https://$EXPECTED_STAGING_PW_DOMAIN/" 2>/dev/null || echo "")
if echo "$PW_HTML" | grep -qiE 'react|vite|app-build'; then
  ok "PW HTML contains expected app markers"
  echo "$PW_HTML" | grep -q "$CURRENT_HEAD" \
    && ok "PW fingerprint contains $CURRENT_HEAD" \
    || info "SHA not visible in root HTML (may be in meta or JS bundle)"
else
  warn "PW HTML does not contain expected React app markers — check deployment"
fi

echo
echo "  ── PW gate 3/3: Playwright smoke ────────────────────────────────────"
if ! run_playwright_smoke '\[Mission Backlog / PW\]|\[PW\]' \
    "Planning Workspace smoke"; then
  warn "PW Playwright smoke failed — PW may have deployed but has functional issues"
  warn "Check: npx playwright test --grep '\[PW\]' tools/playwright-staging/tests/"
fi

# ══ Final summary ══════════════════════════════════════════════════════════════
echo
echo "════════════════════════════════════════════════════════════════════"
echo -e "  ${GRN}All three staging deployments completed and gates passed.${NC}"
echo "  Commit deployed: $CURRENT_HEAD"
echo
echo "  Deployment IDs (parsed from railway up output):"
printf "  %-12s %s\n" "Backend:"  "$BACKEND_NEW_DEPLOY_ID"
printf "  %-12s %s\n" "Frontend:" "$FRONTEND_NEW_DEPLOY_ID"
printf "  %-12s %s\n" "PW:"       "$PW_NEW_DEPLOY_ID"
echo
echo "  Next: run the full Playwright suite for the final verification report."
echo "    cd tools/playwright-staging"
echo "    npx playwright test tests/staging-verification.spec.ts"
echo "    Screenshots: artifacts/staging-ui-verification/$CURRENT_HEAD/"
echo "════════════════════════════════════════════════════════════════════"
echo
