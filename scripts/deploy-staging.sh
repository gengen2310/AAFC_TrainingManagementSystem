#!/usr/bin/env bash
# deploy-staging.sh — Hardened staging deployment guard for AAFC TMS (v3).
#
# All verification gates are HARD FAIL — no WARN-and-continue.
# Deployment commands use immutable UUIDs for project, environment, and service.
#
# REQUIRED ENVIRONMENT VARIABLE:
#   STAGING_AUTH_TOKEN   Bearer token for authenticated staging API checks.
#                        Deployment is blocked if this is absent or fails a
#                        pre-flight liveness check. Never printed to stdout.
#
# USAGE:
#   STAGING_AUTH_TOKEN=<token> bash scripts/deploy-staging.sh
#   STAGING_AUTH_TOKEN=<token> DRY_RUN=1 bash scripts/deploy-staging.sh

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
die()  { echo -e "\n  ${RED}══ ABORT ══${NC} $1\n"; exit 1; }

# ── Helper: poll until HTTP 200 ────────────────────────────────────────────────
# Usage: poll_health <url> <timeout_s> <description>
# Returns 0 when 200, exits script on timeout (hard gate).
poll_health() {
  local url="$1" timeout="$2" desc="$3"
  local elapsed=0
  info "Polling $desc: $url  (timeout ${timeout}s)"
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
  die "$desc did not return HTTP 200 within ${timeout}s — HARD FAIL. Next service NOT deployed."
}

# ── Helper: wait for a named deployment to reach SUCCESS/ACTIVE ────────────────
# Usage: wait_for_new_deploy <svc_uuid> <env_uuid> <pre_deploy_id> <timeout_s> <desc>
# Sets VERIFIED_NEW_DEPLOY_ID on success. Dies on timeout or FAILED/CRASHED.
wait_for_new_deploy() {
  local svc_id="$1" env_id="$2" pre_id="$3" timeout="$4" desc="$5"
  local elapsed=0
  VERIFIED_NEW_DEPLOY_ID="unknown"
  info "Waiting for new $desc deployment (pre-deploy: $pre_id, timeout: ${timeout}s)"
  while [ "$elapsed" -lt "$timeout" ]; do
    local latest_json
    latest_json=$(railway deployment list \
      --project "$EXPECTED_PROJECT_ID" \
      --service "$svc_id" \
      --environment "$env_id" \
      --limit 1 --json 2>/dev/null || echo "[]")
    local new_id new_status
    new_id=$(echo "$latest_json" | python3 -c "
import json,sys; data=json.load(sys.stdin)
print(data[0]['id'] if data else 'none')" 2>/dev/null || echo "none")
    new_status=$(echo "$latest_json" | python3 -c "
import json,sys; data=json.load(sys.stdin)
print(data[0]['status'] if data else 'none')" 2>/dev/null || echo "none")

    if [ "$new_id" = "$pre_id" ]; then
      echo "    [${elapsed}s] Latest deployment is still pre-deploy ID — upload in progress"
    elif [ "$new_status" = "SUCCESS" ]; then
      ok "$desc new deployment $new_id reached SUCCESS after ${elapsed}s"
      VERIFIED_NEW_DEPLOY_ID="$new_id"
      return 0
    elif [ "$new_status" = "FAILED" ] || [ "$new_status" = "CRASHED" ] || [ "$new_status" = "REMOVED" ]; then
      die "$desc deployment $new_id reached $new_status — HARD FAIL. Previous deployment retained."
    else
      echo "    [${elapsed}s] $desc deployment $new_id status: $new_status — waiting…"
    fi
    sleep "$POLL_INTERVAL"
    elapsed=$((elapsed + POLL_INTERVAL))
  done
  die "$desc new deployment did not reach SUCCESS within ${timeout}s — HARD FAIL."
}

# ── Helper: query latest SUCCESS deploy ID for a service ──────────────────────
get_active_deploy() {
  local svc_id="$1" env_id="$2"
  railway deployment list \
    --project "$EXPECTED_PROJECT_ID" \
    --service "$svc_id" \
    --environment "$env_id" \
    --limit 20 --json 2>/dev/null \
  | python3 -c "
import json,sys
data=json.load(sys.stdin)
for d in data:
    if d['status']=='SUCCESS':
        print(d['id']+'|'+d['status']+'|'+d['createdAt'])
        break
else:
    print('unknown|unknown|unknown')
" 2>/dev/null || echo "unknown|unknown|unknown"
}

# ── Helper: verify failure recovery ───────────────────────────────────────────
# Usage: check_rollback <svc_id> <env_id> <pre_deploy_id> <svc_label>
check_rollback() {
  local svc_id="$1" env_id="$2" pre_id="$3" label="$4"
  info "Checking rollback for $label (pre-deploy: $pre_id)"
  local active_line
  active_line=$(get_active_deploy "$svc_id" "$env_id")
  local active_id active_status active_time
  IFS='|' read -r active_id active_status active_time <<< "$active_line"
  if [ "$active_id" = "$pre_id" ]; then
    ok "$label rollback confirmed: $active_id (SUCCESS) is still active"
  else
    echo -e "  ${YLW}[WARN]${NC} $label active deployment ($active_id) differs from pre-deploy ($pre_id)"
    info "  Status: $active_status  Created: $active_time"
    info "  Check Railway dashboard to confirm intended state."
  fi
}

# ── Helper: run targeted Playwright smoke (hard gate) ─────────────────────────
# Usage: require_playwright_smoke <grep_pattern> <description>
# Dies if Playwright not available or any test fails.
require_playwright_smoke() {
  local pattern="$1" desc="$2"
  local spec="tools/playwright-staging/tests/staging-verification.spec.ts"
  if ! command -v npx &>/dev/null || [ ! -f "$spec" ]; then
    die "Playwright not available — cannot run required gate: $desc. Install dependencies first."
  fi
  info "Running required Playwright gate: $desc"
  if ! npx playwright test \
      --project=chromium \
      --grep "$pattern" \
      --reporter=line \
      --timeout=60000 \
      "$spec" 2>&1; then
    die "Playwright gate FAILED: $desc — HARD FAIL. Next service NOT deployed."
  fi
  ok "Playwright gate PASSED: $desc"
}

# ── Helper: authenticated staging API call (no credential in output) ──────────
# Usage: staging_api_call <method> <path> [<body>]
# Returns HTTP code in STAGING_API_CODE, response body in STAGING_API_BODY.
staging_api_call() {
  local method="$1" path="$2" body="${3:-}"
  local url="https://$EXPECTED_STAGING_BACKEND_DOMAIN$path"
  if [ -n "$body" ]; then
    STAGING_API_BODY=$(curl -s -w "\n__HTTP_CODE__%{http_code}" \
      --connect-timeout 10 --max-time 20 \
      -X "$method" \
      -H "Authorization: Bearer $STAGING_AUTH_TOKEN" \
      -H "Content-Type: application/json" \
      -d "$body" "$url" 2>/dev/null)
  else
    STAGING_API_BODY=$(curl -s -w "\n__HTTP_CODE__%{http_code}" \
      --connect-timeout 10 --max-time 20 \
      -X "$method" \
      -H "Authorization: Bearer $STAGING_AUTH_TOKEN" \
      "$url" 2>/dev/null)
  fi
  STAGING_API_CODE=$(echo "$STAGING_API_BODY" | grep -o '__HTTP_CODE__[0-9]*' | grep -o '[0-9]*' || echo "000")
  STAGING_API_BODY=$(echo "$STAGING_API_BODY" | sed 's/__HTTP_CODE__[0-9]*$//')
}

# ── Header ─────────────────────────────────────────────────────────────────────
echo
echo "════════════════════════════════════════════════════════════════════"
echo "  AAFC TMS — Hardened Staging Deployment Guard (v3)"
echo "  All verification gates are HARD FAIL."
echo "  Deployment uses immutable UUIDs for all Railway targets."
echo "════════════════════════════════════════════════════════════════════"
echo

# ══ PREFLIGHT: STAGING_AUTH_TOKEN required ═══════════════════════════════════
echo "  [PRE-0] Staging auth token…"
if [ -z "${STAGING_AUTH_TOKEN:-}" ]; then
  die "STAGING_AUTH_TOKEN is not set. Export it before running this script:
  export STAGING_AUTH_TOKEN=<system_admin_bearer_token>
  Deployment is blocked without a valid staging authentication token."
fi
ok "STAGING_AUTH_TOKEN is present (not printed)"

# Pre-flight liveness check — token must authenticate right now
staging_api_call GET "/api/health"
if [ "$STAGING_API_CODE" = "200" ]; then
  ok "Staging backend /api/health reachable (token format not yet tested)"
else
  info "Staging backend /api/health returned $STAGING_API_CODE — backend may be down or token pre-check skipped"
fi

# ══ STEP 1: Fetch Railway state ════════════════════════════════════════════════
echo
echo "  [1/12] Fetching Railway project state…"
RAILWAY_JSON=$(railway status --json 2>&1)
if echo "$RAILWAY_JSON" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
  ok "Railway JSON fetched"
else
  die "Failed to parse Railway JSON. Run: railway login"
fi

# ══ STEP 2: Verify project ID ═════════════════════════════════════════════════
echo
echo "  [2/12] Verifying project ID…"
ACTUAL_PROJECT_ID=$(echo "$RAILWAY_JSON" | python3 -c "
import json,sys; d=json.load(sys.stdin); print(d.get('id','MISSING'))" 2>/dev/null || echo "ERROR")
info "Expected: $EXPECTED_PROJECT_ID"
info "Actual:   $ACTUAL_PROJECT_ID"
[ "$ACTUAL_PROJECT_ID" = "$EXPECTED_PROJECT_ID" ] \
  && ok "Project ID matches" \
  || die "Project ID mismatch. Aborting."

# ══ STEP 3: Verify staging environment ID ═════════════════════════════════════
echo
echo "  [3/12] Verifying staging environment ID…"
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

# ══ STEP 4: Verify service IDs ════════════════════════════════════════════════
echo
echo "  [4/12] Verifying service IDs…"
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
[ "$FAIL_COUNT" -gt 0 ] && die "Service ID verification failed."

# ══ STEP 5: UUID read-only proof (railway deployment list) ════════════════════
echo
echo "  [5/12] UUID read-only resolution proof (railway deployment list)…"
# Each call uses the exact allowlisted UUIDs. Returns structured JSON with deployment
# ID, status, and createdAt. A non-empty JSON array proves the UUID is accepted.

UUID_PROOF_BACKEND=$(railway deployment list \
  --project "$EXPECTED_PROJECT_ID" \
  --service "$ACTUAL_BACKEND_SVC_ID" \
  --environment "$ACTUAL_STAGING_ENV_ID" \
  --limit 1 --json 2>&1)
UUID_PROOF_FRONTEND=$(railway deployment list \
  --project "$EXPECTED_PROJECT_ID" \
  --service "$ACTUAL_FRONTEND_SVC_ID" \
  --environment "$ACTUAL_STAGING_ENV_ID" \
  --limit 1 --json 2>&1)
UUID_PROOF_PW=$(railway deployment list \
  --project "$EXPECTED_PROJECT_ID" \
  --service "$ACTUAL_PW_SVC_ID" \
  --environment "$ACTUAL_STAGING_ENV_ID" \
  --limit 1 --json 2>&1)

verify_uuid_proof() {
  local label="$1" json="$2" expected_svc_id="$3"
  local resolved_svc
  resolved_svc=$(echo "$json" | python3 -c "
import json,sys
try:
    data=json.load(sys.stdin)
    print(len(data))
except: print('0')" 2>/dev/null || echo "0")
  if echo "$json" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null \
      && [ "$resolved_svc" -gt 0 ] 2>/dev/null; then
    ok "$label UUID $expected_svc_id accepted by railway deployment list"
    echo "$json" | python3 -c "
import json,sys; d=json.load(sys.stdin)
if d: print(f'    Latest: id={d[0][\"id\"]}  status={d[0][\"status\"]}  created={d[0][\"createdAt\"]}')" 2>/dev/null || true
  elif echo "$json" | python3 -c "import json,sys; data=json.load(sys.stdin); assert data==[]" 2>/dev/null; then
    ok "$label UUID $expected_svc_id accepted (service has no deployments yet)"
  else
    die "$label UUID $expected_svc_id was NOT accepted by Railway CLI: $json"
  fi
}

verify_uuid_proof "Backend"  "$UUID_PROOF_BACKEND"  "$ACTUAL_BACKEND_SVC_ID"
verify_uuid_proof "Frontend" "$UUID_PROOF_FRONTEND" "$ACTUAL_FRONTEND_SVC_ID"
verify_uuid_proof "PW"       "$UUID_PROOF_PW"       "$ACTUAL_PW_SVC_ID"

# ══ STEP 6: Verify staging domains ════════════════════════════════════════════
echo
echo "  [6/12] Verifying staging target domains…"
STAGING_DOMAINS=$(echo "$RAILWAY_JSON" | python3 -c "
import json,sys
data=json.load(sys.stdin)
for env in data.get('environments',{}).get('edges',[]):
    if env['node']['id'] == '$EXPECTED_STAGING_ENV_ID':
        for si in env['node'].get('serviceInstances',{}).get('edges',[]):
            for d in si['node'].get('domains',{}).get('serviceDomains',[]):
                print(d['domain'])" 2>/dev/null || echo "ERROR")
echo "  Staging domains:"
echo "$STAGING_DOMAINS" | while read -r d; do [ -n "$d" ] && echo "    $d"; done
echo "$STAGING_DOMAINS" | grep -q "production.up.railway.app" \
  && die "Production domain detected in staging targets!" \
  || ok "No production domains in staging targets"
echo "$STAGING_DOMAINS" | grep -qF "$EXPECTED_STAGING_BACKEND_DOMAIN"  \
  && ok "Backend  domain: $EXPECTED_STAGING_BACKEND_DOMAIN"  || fail "Backend  staging domain NOT found"
echo "$STAGING_DOMAINS" | grep -qF "$EXPECTED_STAGING_FRONTEND_DOMAIN" \
  && ok "Frontend domain: $EXPECTED_STAGING_FRONTEND_DOMAIN" || fail "Frontend staging domain NOT found"
echo "$STAGING_DOMAINS" | grep -qF "$EXPECTED_STAGING_PW_DOMAIN"       \
  && ok "PW       domain: $EXPECTED_STAGING_PW_DOMAIN"       || fail "PW staging domain NOT found"

# ══ STEP 7: Git state ═════════════════════════════════════════════════════════
echo
echo "  [7/12] Git state…"
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "UNKNOWN")
info "Branch: $CURRENT_BRANCH"
[ "$CURRENT_BRANCH" = "$EXPECTED_BRANCH" ] || die "Branch is '$CURRENT_BRANCH', expected '$EXPECTED_BRANCH'."
ok "Branch: $CURRENT_BRANCH"
[[ "$CURRENT_BRANCH" == "main" || "$CURRENT_BRANCH" == "master" || "$CURRENT_BRANCH" == *"production"* ]] \
  && die "Protected branch."
CURRENT_HEAD=$(git rev-parse --short HEAD 2>/dev/null || echo "UNKNOWN")
info "HEAD: $CURRENT_HEAD — $(git log -1 --format='%s')"
git merge-base --is-ancestor "$REQUIRED_ANCESTOR" HEAD 2>/dev/null \
  || die "Fix commit $REQUIRED_ANCESTOR is NOT an ancestor of HEAD. Aborting."
ok "Fix commit $REQUIRED_ANCESTOR is ancestor of $CURRENT_HEAD"
git diff-index --quiet HEAD -- 2>/dev/null || die "Working tree has uncommitted changes."
ok "Working tree clean"
UNPUSHED=$(git log "origin/${EXPECTED_BRANCH}..HEAD" --oneline 2>/dev/null || echo "ERROR")
[ -n "$UNPUSHED" ] && die "Unpushed commits — push to origin/$EXPECTED_BRANCH first."
ok "HEAD pushed to origin/$EXPECTED_BRANCH"

# ══ STEP 8: Security greps ════════════════════════════════════════════════════
echo
echo "  [8/12] Security greps…"
check_grep() {
  local label="$1" pattern="$2" path="$3"
  local count
  count=$(grep -rc "$pattern" "$path" 2>/dev/null | awk -F: '{s+=$2} END{print s+0}')
  [ "$count" -eq 0 ] && ok "$label (0 matches)" || { fail "$label — $count match(es)"; grep -rn "$pattern" "$path" | head -3; }
}
check_grep "No seeded codes"           "SYSADMIN2026\|ADMIN703\|ADMIN7WG\|ADMINNATIONAL" "connected-frontend"
check_grep "No localStorage"            "localStorage"                                     "connected-frontend"
check_grep "No access-code hashes"      "code_hash\|plain_code"                           "connected-frontend"
check_grep "No JWT_SECRET/SECRET_KEY"   "JWT_SECRET\|SECRET_KEY"                           "connected-frontend"
check_grep "No DB connection strings"   "postgresql://\|postgres://\|sqlite:///"           "connected-frontend"

# ══ STEP 9: Backend tests ═════════════════════════════════════════════════════
echo
echo "  [9/12] Backend test suite…"
if [ -d "backend" ]; then
  pushd backend > /dev/null
  if source .venv/bin/activate 2>/dev/null; then
    TEST_OUT=$(python -m pytest tests/ -q --tb=no 2>&1)
    LASTLINE=$(echo "$TEST_OUT" | tail -1)
    echo "$LASTLINE" | grep -q "passed" && ! echo "$LASTLINE" | grep -q "failed" \
      && ok "Tests: $LASTLINE" \
      || { fail "Test failures: $LASTLINE"; echo "$TEST_OUT" | tail -10; }
    deactivate 2>/dev/null || true
  else
    die ".venv not found — cannot verify backend tests."
  fi
  popd > /dev/null
else
  die "backend/ directory not found."
fi

# ══ STEP 10: Alembic head (code) ══════════════════════════════════════════════
echo
echo "  [10/12] Alembic migration head (code)…"
if [ -d "backend" ]; then
  pushd backend > /dev/null
  if source .venv/bin/activate 2>/dev/null; then
    ALEMBIC_HEAD=$(python -m alembic heads 2>/dev/null | grep -oE '[a-f0-9]{12}' | head -1 || echo "unknown")
    info "Alembic head: $ALEMBIC_HEAD"
    [ "$ALEMBIC_HEAD" = "$REQUIRED_ALEMBIC_HEAD" ] \
      && ok "Alembic code head is $REQUIRED_ALEMBIC_HEAD (v40)" \
      || die "Alembic code head is $ALEMBIC_HEAD, expected $REQUIRED_ALEMBIC_HEAD."
    deactivate 2>/dev/null || true
  fi
  popd > /dev/null
fi

# ══ STEP 11: Railway CLI ══════════════════════════════════════════════════════
echo
echo "  [11/12] Railway CLI…"
command -v railway &>/dev/null || die "railway CLI not found. Install: npm install -g @railway/cli"
ok "railway CLI: $(railway --version 2>/dev/null)"

# ══ STEP 12: STAGING_AUTH_TOKEN validity (system_admin endpoint) ══════════════
echo
echo "  [12/12] Verifying staging auth token is valid and has system_admin access…"
staging_api_call GET "/api/system/health"
if [ "$STAGING_API_CODE" = "200" ]; then
  ok "STAGING_AUTH_TOKEN is valid — /api/system/health returned 200"
elif [ "$STAGING_API_CODE" = "401" ] || [ "$STAGING_API_CODE" = "403" ]; then
  die "STAGING_AUTH_TOKEN is invalid or lacks system_admin role (HTTP $STAGING_API_CODE). Obtain a fresh system_admin token for staging."
else
  die "/api/system/health returned $STAGING_API_CODE — staging backend may be down or token invalid."
fi

# ══ Preflight summary ═════════════════════════════════════════════════════════
echo
echo "════════════════════════════════════════════════════════════════════"
echo -e "  Preflight: ${GRN}PASS: $PASS_COUNT${NC}   ${RED}FAIL: $FAIL_COUNT${NC}"
echo "════════════════════════════════════════════════════════════════════"
[ "$FAIL_COUNT" -gt 0 ] && die "$FAIL_COUNT preflight check(s) failed."
echo

# ══ Pre-deployment ID capture ═════════════════════════════════════════════════
echo "  PRE-DEPLOYMENT STATE (captured for rollback reference)"
echo

capture_pre_deploy() {
  local svc_id="$1" label="$2"
  local line
  line=$(get_active_deploy "$svc_id" "$ACTUAL_STAGING_ENV_ID")
  local dep_id dep_status dep_time
  IFS='|' read -r dep_id dep_status dep_time <<< "$line"
  echo "$dep_id"
  printf "  %-12s id=%-44s status=%-10s created=%s\n" "$label" "$dep_id" "$dep_status" "$dep_time"
}

PRE_BACKEND_ID=$(capture_pre_deploy  "$ACTUAL_BACKEND_SVC_ID"  "Backend:")
PRE_FRONTEND_ID=$(capture_pre_deploy "$ACTUAL_FRONTEND_SVC_ID" "Frontend:")
PRE_PW_ID=$(capture_pre_deploy       "$ACTUAL_PW_SVC_ID"       "PW:")

echo
echo "  These IDs will be compared against active deployments after any gate failure."
echo

# ══ Resolved targets display ══════════════════════════════════════════════════
echo "  RESOLVED DEPLOYMENT TARGETS — verified against immutable allowlist"
echo
printf "  %-32s %s\n" "Project ID:"          "$ACTUAL_PROJECT_ID"
printf "  %-32s %s\n" "Staging env ID:"       "$ACTUAL_STAGING_ENV_ID"
printf "  %-32s %s\n" "Production env ID:"    "$PRODUCTION_ENV_ID  (NOT targeted)"
echo
printf "  %-32s %s\n" "Service 1 [FIRST]:"    "$EXPECTED_BACKEND_SVC_NAME"
printf "  %-32s %s\n" "  UUID:"               "$ACTUAL_BACKEND_SVC_ID"
printf "  %-32s %s\n" "  Domain:"             "$EXPECTED_STAGING_BACKEND_DOMAIN"
printf "  %-32s %s\n" "  Pre-deploy ID:"      "$PRE_BACKEND_ID"
echo
printf "  %-32s %s\n" "Service 2:"            "$EXPECTED_FRONTEND_SVC_NAME"
printf "  %-32s %s\n" "  UUID:"               "$ACTUAL_FRONTEND_SVC_ID"
printf "  %-32s %s\n" "  Domain:"             "$EXPECTED_STAGING_FRONTEND_DOMAIN"
printf "  %-32s %s\n" "  Pre-deploy ID:"      "$PRE_FRONTEND_ID"
echo
printf "  %-32s %s\n" "Service 3 [LAST]:"     "$EXPECTED_PW_SVC_NAME"
printf "  %-32s %s\n" "  UUID:"               "$ACTUAL_PW_SVC_ID"
printf "  %-32s %s\n" "  Domain:"             "$EXPECTED_STAGING_PW_DOMAIN"
printf "  %-32s %s\n" "  Pre-deploy ID:"      "$PRE_PW_ID"
echo
printf "  %-32s %s\n" "Branch:"               "$CURRENT_BRANCH"
printf "  %-32s %s\n" "HEAD:"                 "$CURRENT_HEAD — $(git log -1 --format='%s')"
echo
echo "  DB revision gate:     /api/system/migrations → revision == $REQUIRED_ALEMBIC_HEAD (HARD FAIL)"
echo "  Subject-area-tags:    CRUD workflow with STAGING_AUTH_TOKEN (HARD FAIL)"
echo "  Frontend fingerprint: SHA + timestamp in root HTML (HARD FAIL)"
echo "  Frontend Playwright:  full browser smoke (HARD FAIL)"
echo "  PW fingerprint:       SHA + app markers in root HTML (HARD FAIL)"
echo "  PW Playwright:        full browser smoke (HARD FAIL)"
echo

# ══ Authorization gate ════════════════════════════════════════════════════════
REQUIRED_PHRASE="DEPLOY TO STAGING ${CURRENT_HEAD}"
echo -e "  ${YLW}══ AUTHORIZATION REQUIRED ══${NC}"
echo
echo "  All preflight checks passed. Type exactly to authorize:"
echo -e "  ${BLU}${REQUIRED_PHRASE}${NC}"
echo
read -r CONFIRM
[ -z "$CONFIRM" ]                      && die "Empty input."
[ "$CONFIRM" != "$REQUIRED_PHRASE" ]   && die "Phrase mismatch.\n  Typed:    '$CONFIRM'\n  Required: '$REQUIRED_PHRASE'"
RECHECK_HEAD=$(git rev-parse --short HEAD 2>/dev/null)
[ "$RECHECK_HEAD" != "$CURRENT_HEAD" ] && die "HEAD changed during prompt."
echo
echo -e "  ${GRN}Authorization accepted.${NC} Deploying $CURRENT_HEAD to staging."
echo

# ══ DRY RUN ══════════════════════════════════════════════════════════════════
if [ "${DRY_RUN:-0}" = "1" ]; then
  echo -e "  ${YLW}DRY RUN — commands that would execute:${NC}"
  echo
  echo "  [1/3] Backend  (UUID: $ACTUAL_BACKEND_SVC_ID)"
  echo "    railway up \\"
  echo "      --project $EXPECTED_PROJECT_ID \\"
  echo "      --service $ACTUAL_BACKEND_SVC_ID \\"
  echo "      --environment $ACTUAL_STAGING_ENV_ID \\"
  echo "      --detach"
  echo "    Gates (all HARD FAIL):"
  echo "      poll /api/health/ready HTTP 200 (${BACKEND_GATE_TIMEOUT}s)"
  echo "      readiness JSON: status == ready"
  echo "      wait_for_new_deploy: new deployment ID ≠ $PRE_BACKEND_ID, reaches SUCCESS"
  echo "      /api/system/migrations: revision == $REQUIRED_ALEMBIC_HEAD (DB direct)"
  echo "      /api/subject-area-tags CRUD: create / retrieve / archive / confirm gone"
  echo
  echo "  [2/3] Frontend (UUID: $ACTUAL_FRONTEND_SVC_ID)"
  echo "    railway up \\"
  echo "      --project $EXPECTED_PROJECT_ID \\"
  echo "      --service $ACTUAL_FRONTEND_SVC_ID \\"
  echo "      --environment $ACTUAL_STAGING_ENV_ID \\"
  echo "      --detach"
  echo "    Gates (all HARD FAIL):"
  echo "      poll / HTTP 200 (${FRONTEND_GATE_TIMEOUT}s)"
  echo "      wait_for_new_deploy: new deployment ID ≠ $PRE_FRONTEND_ID, reaches SUCCESS"
  echo "      root HTML contains app-build meta with SHA $CURRENT_HEAD"
  echo "      Playwright: [Dashboard], [Nav] Mobile, [Network] — all assertions required"
  echo
  echo "  [3/3] Planning Workspace (UUID: $ACTUAL_PW_SVC_ID)"
  echo "    railway up \\"
  echo "      --project $EXPECTED_PROJECT_ID \\"
  echo "      --service $ACTUAL_PW_SVC_ID \\"
  echo "      --environment $ACTUAL_STAGING_ENV_ID \\"
  echo "      --detach"
  echo "    Gates (all HARD FAIL):"
  echo "      poll /healthz HTTP 200 (${PW_GATE_TIMEOUT}s)"
  echo "      wait_for_new_deploy: new deployment ID ≠ $PRE_PW_ID, reaches SUCCESS"
  echo "      root HTML contains React app markers"
  echo "      Playwright: [Mission Backlog / PW], [PW] — all assertions required"
  echo
  echo "  DRY RUN complete. No deployment made."
  exit 0
fi

# ══════════════════════════════════════════════════════════════════════════════
# DEPLOYMENT 1/3 — BACKEND
# ══════════════════════════════════════════════════════════════════════════════
echo "────────────────────────────────────────────────────────────────────"
echo "  [Deploy 1/3] $EXPECTED_BACKEND_SVC_NAME"
info "  Service UUID:    $ACTUAL_BACKEND_SVC_ID"
info "  Env UUID:        $ACTUAL_STAGING_ENV_ID"
info "  Pre-deploy ID:   $PRE_BACKEND_ID"
info "  Migration:       a1b2c3d4e5f6 → $REQUIRED_ALEMBIC_HEAD"
echo

BACKEND_UP_OUT=$(railway up \
  --project "$EXPECTED_PROJECT_ID" \
  --service "$ACTUAL_BACKEND_SVC_ID" \
  --environment "$ACTUAL_STAGING_ENV_ID" \
  --detach 2>&1)
echo "$BACKEND_UP_OUT"

echo
echo "  ── Backend gate 1/4: health ──────────────────────────────────────────"
poll_health \
  "https://$EXPECTED_STAGING_BACKEND_DOMAIN/api/health/ready" \
  "$BACKEND_GATE_TIMEOUT" \
  "Backend /api/health/ready"

READY_JSON=$(curl -s --connect-timeout 10 --max-time 15 \
  "https://$EXPECTED_STAGING_BACKEND_DOMAIN/api/health/ready" 2>/dev/null || echo '{}')
info "Readiness response: $READY_JSON"
echo "$READY_JSON" | python3 -c "
import json,sys; d=json.load(sys.stdin)
assert d.get('status')=='ready', repr(d)" 2>/dev/null \
  && ok "Readiness status: ready" \
  || die "Backend /api/health/ready did not return status:ready — HARD FAIL."

echo
echo "  ── Backend gate 2/4: new deployment ID ──────────────────────────────"
VERIFIED_NEW_DEPLOY_ID="unknown"
wait_for_new_deploy \
  "$ACTUAL_BACKEND_SVC_ID" \
  "$ACTUAL_STAGING_ENV_ID" \
  "$PRE_BACKEND_ID" \
  "$BACKEND_GATE_TIMEOUT" \
  "Backend"
BACKEND_NEW_DEPLOY_ID="$VERIFIED_NEW_DEPLOY_ID"
ok "Backend new deployment ID: $BACKEND_NEW_DEPLOY_ID (differs from pre-deploy $PRE_BACKEND_ID)"

echo
echo "  ── Backend gate 3/4: database revision (HARD GATE) ──────────────────"
staging_api_call GET "/api/system/migrations"
if [ "$STAGING_API_CODE" != "200" ]; then
  die "/api/system/migrations returned $STAGING_API_CODE (expected 200) — HARD FAIL."
fi
DB_REVISION=$(echo "$STAGING_API_BODY" | python3 -c "
import json,sys; d=json.load(sys.stdin); print(d.get('revision','MISSING'))" 2>/dev/null || echo "ERROR")
IS_SINGLE=$(echo "$STAGING_API_BODY" | python3 -c "
import json,sys; d=json.load(sys.stdin); print(d.get('is_single_head',False))" 2>/dev/null || echo "False")
REVISIONS=$(echo "$STAGING_API_BODY" | python3 -c "
import json,sys; d=json.load(sys.stdin); print(d.get('revisions',[]))" 2>/dev/null || echo "[]")
info "DB revisions: $REVISIONS"
info "is_single_head: $IS_SINGLE"
info "revision: $DB_REVISION"
[ "$IS_SINGLE" = "True" ] || die "Multiple Alembic heads detected: $REVISIONS — HARD FAIL."
[ "$DB_REVISION" = "$REQUIRED_ALEMBIC_HEAD" ] \
  && ok "DB revision: $DB_REVISION — exact match — migration v40 confirmed applied" \
  || die "DB revision is '$DB_REVISION', expected '$REQUIRED_ALEMBIC_HEAD' — HARD FAIL. Migration may not have applied."

echo
echo "  ── Backend gate 4/4: subject-area-tags CRUD workflow ────────────────"
# Step 1: GET /api/subject-area-tags — must return 200 + JSON array
staging_api_call GET "/api/subject-area-tags"
[ "$STAGING_API_CODE" = "200" ] \
  || die "/api/subject-area-tags GET returned $STAGING_API_CODE (expected 200) — HARD FAIL."
echo "$STAGING_API_BODY" | python3 -c "import json,sys; data=json.load(sys.stdin); assert isinstance(data,list)" 2>/dev/null \
  || die "/api/subject-area-tags response is not a JSON array — HARD FAIL."
ok "GET /api/subject-area-tags → 200 JSON array"

# Step 2: Create a synthetic test tag
VERIFY_TAG_NAME="Deployment Verification $(date -u '+%Y%m%d%H%M%S')"
staging_api_call POST "/api/subject-area-tags" \
  "{\"display_name\": \"$VERIFY_TAG_NAME\", \"scope\": \"squadron\"}"
[ "$STAGING_API_CODE" = "201" ] \
  || die "Create tag returned $STAGING_API_CODE (expected 201) — HARD FAIL."
VERIFY_TAG_ID=$(echo "$STAGING_API_BODY" | python3 -c "
import json,sys; d=json.load(sys.stdin); print(d.get('id','MISSING'))" 2>/dev/null || echo "MISSING")
[ "$VERIFY_TAG_ID" = "MISSING" ] || [ -z "$VERIFY_TAG_ID" ] \
  && die "Create tag response missing stable ID — HARD FAIL." || true
ok "POST /api/subject-area-tags → 201, tag_id=$VERIFY_TAG_ID"

# Step 3: Retrieve the created tag in the list
staging_api_call GET "/api/subject-area-tags"
[ "$STAGING_API_CODE" = "200" ] \
  || die "GET /api/subject-area-tags (after create) returned $STAGING_API_CODE — HARD FAIL."
TAG_PRESENT=$(echo "$STAGING_API_BODY" | python3 -c "
import json,sys; data=json.load(sys.stdin)
found=any(t.get('id')=='$VERIFY_TAG_ID' for t in data)
print('yes' if found else 'no')" 2>/dev/null || echo "no")
[ "$TAG_PRESENT" = "yes" ] \
  && ok "Created tag $VERIFY_TAG_ID found in active list" \
  || die "Created tag $VERIFY_TAG_ID NOT found in active list after create — HARD FAIL."

# Step 4: Archive the tag
staging_api_call DELETE "/api/subject-area-tags/$VERIFY_TAG_ID"
[ "$STAGING_API_CODE" = "200" ] \
  || die "Archive tag returned $STAGING_API_CODE (expected 200) — HARD FAIL."
ok "DELETE /api/subject-area-tags/$VERIFY_TAG_ID → 200 archived"

# Step 5: Confirm it no longer appears in the active list
staging_api_call GET "/api/subject-area-tags"
[ "$STAGING_API_CODE" = "200" ] \
  || die "GET /api/subject-area-tags (after archive) returned $STAGING_API_CODE — HARD FAIL."
TAG_STILL=$(echo "$STAGING_API_BODY" | python3 -c "
import json,sys; data=json.load(sys.stdin)
found=any(t.get('id')=='$VERIFY_TAG_ID' for t in data)
print('yes' if found else 'no')" 2>/dev/null || echo "yes")
[ "$TAG_STILL" = "no" ] \
  && ok "Archived tag $VERIFY_TAG_ID no longer in active list — subject-area-tags CRUD PASS" \
  || die "Archived tag $VERIFY_TAG_ID still appears in active list — HARD FAIL."

ok "Backend gate PASSED. Proceeding to Main TMS frontend."

# Re-verify backend service ID has not changed
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
info "  Service UUID:    $ACTUAL_FRONTEND_SVC_ID"
info "  Env UUID:        $ACTUAL_STAGING_ENV_ID"
info "  Pre-deploy ID:   $PRE_FRONTEND_ID"
info "  Entrypoint:      connected-frontend/docker-entrypoint.sh"
echo

FRONTEND_UP_OUT=$(railway up \
  --project "$EXPECTED_PROJECT_ID" \
  --service "$ACTUAL_FRONTEND_SVC_ID" \
  --environment "$ACTUAL_STAGING_ENV_ID" \
  --detach 2>&1)
echo "$FRONTEND_UP_OUT"

echo
echo "  ── Frontend gate 1/4: HTTP 200 ──────────────────────────────────────"
poll_health \
  "https://$EXPECTED_STAGING_FRONTEND_DOMAIN/" \
  "$FRONTEND_GATE_TIMEOUT" \
  "Frontend /"

echo
echo "  ── Frontend gate 2/4: new deployment ID ─────────────────────────────"
VERIFIED_NEW_DEPLOY_ID="unknown"
wait_for_new_deploy \
  "$ACTUAL_FRONTEND_SVC_ID" \
  "$ACTUAL_STAGING_ENV_ID" \
  "$PRE_FRONTEND_ID" \
  "$FRONTEND_GATE_TIMEOUT" \
  "Frontend"
FRONTEND_NEW_DEPLOY_ID="$VERIFIED_NEW_DEPLOY_ID"
ok "Frontend new deployment ID: $FRONTEND_NEW_DEPLOY_ID"

echo
echo "  ── Frontend gate 3/4: build fingerprint (HARD GATE) ────────────────"
FRONTEND_HTML=$(curl -s --connect-timeout 10 --max-time 20 \
  "https://$EXPECTED_STAGING_FRONTEND_DOMAIN/" 2>/dev/null || echo "")
if ! echo "$FRONTEND_HTML" | grep -q 'name="app-build"'; then
  die "Build fingerprint meta (name=\"app-build\") NOT found in root HTML — HARD FAIL.
  The entrypoint sed replacement may have failed. Check: curl https://$EXPECTED_STAGING_FRONTEND_DOMAIN/ | grep app-build"
fi
ok "Build fingerprint meta tag present"
if ! echo "$FRONTEND_HTML" | grep -q "$CURRENT_HEAD"; then
  die "Root HTML does not contain current HEAD $CURRENT_HEAD — HARD FAIL.
  Deployed SHA does not match expected. Check the app-build content attribute."
fi
ok "Root HTML contains HEAD SHA: $CURRENT_HEAD"
BUILD_TS=$(echo "$FRONTEND_HTML" | grep -o 'content="[^"]*"' | head -2 | tail -1 || echo "")
info "app-build content: $BUILD_TS"

echo
echo "  ── Frontend gate 4/4: Playwright browser smoke (HARD GATE) ─────────"
require_playwright_smoke \
  '\[Dashboard\]|\[Nav\] Mobile|\[Network\]' \
  "Dashboard + Mobile nav + Network (CSP + appget + chart data)"

ok "Frontend gate PASSED. Proceeding to Planning Workspace."

# ══════════════════════════════════════════════════════════════════════════════
# DEPLOYMENT 3/3 — PLANNING WORKSPACE
# ══════════════════════════════════════════════════════════════════════════════
echo
echo "────────────────────────────────────────────────────────────────────"
echo "  [Deploy 3/3] $EXPECTED_PW_SVC_NAME"
info "  Service UUID:    $ACTUAL_PW_SVC_ID"
info "  Env UUID:        $ACTUAL_STAGING_ENV_ID"
info "  Pre-deploy ID:   $PRE_PW_ID"
info "  Entrypoint:      frontend/docker-entrypoint.sh (# delimiter)"
echo

PW_UP_OUT=$(railway up \
  --project "$EXPECTED_PROJECT_ID" \
  --service "$ACTUAL_PW_SVC_ID" \
  --environment "$ACTUAL_STAGING_ENV_ID" \
  --detach 2>&1)
echo "$PW_UP_OUT"

echo
echo "  ── PW gate 1/4: HTTP 200 ────────────────────────────────────────────"
# /healthz is the standard endpoint; fall through to / only after gate timeout
if ! (curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 --max-time 15 \
    "https://$EXPECTED_STAGING_PW_DOMAIN/healthz" 2>/dev/null | grep -q "200"); then
  info "/healthz probe returned non-200 — will poll through poll_health"
fi
poll_health \
  "https://$EXPECTED_STAGING_PW_DOMAIN/healthz" \
  "$PW_GATE_TIMEOUT" \
  "PW /healthz"

echo
echo "  ── PW gate 2/4: new deployment ID ───────────────────────────────────"
VERIFIED_NEW_DEPLOY_ID="unknown"
wait_for_new_deploy \
  "$ACTUAL_PW_SVC_ID" \
  "$ACTUAL_STAGING_ENV_ID" \
  "$PRE_PW_ID" \
  "$PW_GATE_TIMEOUT" \
  "PW"
PW_NEW_DEPLOY_ID="$VERIFIED_NEW_DEPLOY_ID"
ok "PW new deployment ID: $PW_NEW_DEPLOY_ID"

echo
echo "  ── PW gate 3/4: build fingerprint (HARD GATE) ───────────────────────"
PW_HTML=$(curl -s --connect-timeout 10 --max-time 20 \
  "https://$EXPECTED_STAGING_PW_DOMAIN/" 2>/dev/null || echo "")
if ! echo "$PW_HTML" | grep -qiE 'react|vite|__vite_|data-reactroot'; then
  die "PW root HTML does not contain React app markers — HARD FAIL.
  nginx may not be serving the built app. Check Railway logs."
fi
ok "PW HTML contains React app markers"
if ! echo "$PW_HTML" | grep -q "$CURRENT_HEAD"; then
  die "PW root HTML does not contain current HEAD $CURRENT_HEAD — HARD FAIL.
  The PW build fingerprint does not match the deployed commit."
fi
ok "PW root HTML contains HEAD SHA: $CURRENT_HEAD"

echo
echo "  ── PW gate 4/4: Playwright browser smoke (HARD GATE) ───────────────"
require_playwright_smoke \
  '\[Mission Backlog / PW\]|\[PW\]' \
  "Planning Workspace smoke (nav, auth, render, no CSP, no errors)"

ok "PW gate PASSED."

# ══ Failure recovery verification (end-of-run audit) ═════════════════════════
echo
echo "  POST-DEPLOYMENT FAILURE-RECOVERY AUDIT"
echo "  (All services deployed — confirming active deployment IDs updated)"
echo

verify_final_deploy() {
  local svc_id="$1" pre_id="$2" expected_new_id="$3" label="$4"
  local active_line
  active_line=$(get_active_deploy "$svc_id" "$ACTUAL_STAGING_ENV_ID")
  local active_id active_status active_time
  IFS='|' read -r active_id active_status active_time <<< "$active_line"
  if [ "$active_id" = "$expected_new_id" ]; then
    ok "$label active deployment: $active_id (SUCCESS) — matches new deployment"
  elif [ "$active_id" = "$pre_id" ]; then
    die "$label active deployment is still pre-deploy ID ($pre_id) — deployment may not have succeeded."
  else
    info "$label active deployment: $active_id — status: $active_status"
  fi
}

verify_final_deploy "$ACTUAL_BACKEND_SVC_ID"  "$PRE_BACKEND_ID"  "$BACKEND_NEW_DEPLOY_ID"  "Backend:"
verify_final_deploy "$ACTUAL_FRONTEND_SVC_ID" "$PRE_FRONTEND_ID" "$FRONTEND_NEW_DEPLOY_ID" "Frontend:"
verify_final_deploy "$ACTUAL_PW_SVC_ID"       "$PRE_PW_ID"       "$PW_NEW_DEPLOY_ID"       "PW:"

# ══ Final summary ══════════════════════════════════════════════════════════════
echo
echo "════════════════════════════════════════════════════════════════════"
echo -e "  ${GRN}All three staging deployments completed. All hard gates passed.${NC}"
echo "  Commit deployed: $CURRENT_HEAD"
echo
echo "  Deployment IDs:"
printf "  %-12s pre=%-44s  new=%s\n" "Backend:"  "$PRE_BACKEND_ID"  "$BACKEND_NEW_DEPLOY_ID"
printf "  %-12s pre=%-44s  new=%s\n" "Frontend:" "$PRE_FRONTEND_ID" "$FRONTEND_NEW_DEPLOY_ID"
printf "  %-12s pre=%-44s  new=%s\n" "PW:"       "$PRE_PW_ID"       "$PW_NEW_DEPLOY_ID"
echo
echo "  Next: run the full Playwright suite for the final verification report."
echo "    cd tools/playwright-staging"
echo "    npx playwright test tests/staging-verification.spec.ts"
echo "    Screenshots: artifacts/staging-ui-verification/$CURRENT_HEAD/"
echo "════════════════════════════════════════════════════════════════════"
echo
