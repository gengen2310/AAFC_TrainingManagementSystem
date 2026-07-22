#!/usr/bin/env bash
# deploy-staging.sh — Hardened staging deployment guard for AAFC TMS (v4).
#
# Gate order:
#   PRE-DEPLOY  : token presence + /api/auth/me role check (stable, v39-safe endpoint)
#   PREFLIGHT   : Railway IDs, UUID proof, git, tests, Alembic code head
#   POST-AUTH   : capture PRE_LATEST and PRE_ACTIVE deployment IDs for all services
#   BACKEND GATE: health, new-deployment ID confirmed, DB revision, subject-area-tags CRUD
#   FRONTEND GATE: HTTP 200, new-deployment ID confirmed, build fingerprint, Playwright
#   PW GATE     : HTTP 200/healthz, new-deployment ID confirmed, fingerprint, Playwright
#
# Deployment tracking (fixes the LATEST vs ACTIVE distinction):
#   PRE_LATEST_DEPLOY_ID  = --limit 1 result before railway up (may be FAILED)
#   PRE_ACTIVE_DEPLOY_ID  = first SUCCESS in --limit 20 list (what's serving traffic)
#   After railway up: wait until --limit 1 returns an ID != PRE_LATEST to discover NEW_DEPLOY_ID
#   Then poll NEW_DEPLOY_ID specifically. Abort on concurrent deployment (another ID appears).
#
# Subject-area-tags CRUD runs only after backend v40 is confirmed active.
# /api/auth/me is used for pre-deploy token validation (not subject-area-tags).
#
# REQUIRED: STAGING_AUTH_TOKEN  (system_admin bearer token; never printed)
# OPTIONAL: DRY_RUN=1           (validate token + preflight + show commands; no writes; exit 0)
#
# USAGE:
#   STAGING_AUTH_TOKEN=<token> bash scripts/deploy-staging.sh
#   STAGING_AUTH_TOKEN=<token> DRY_RUN=1 bash scripts/deploy-staging.sh
#
# TESTING (source functions without running main):
#   DEPLOY_FUNCTIONS_ONLY=1 source scripts/deploy-staging.sh

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

# ── Testable Railway deployment list wrapper ───────────────────────────────────
# In test mode (DEPLOY_TEST_MODE=1) returns entries from MOCK_DEPLOY_CALLS[].
# The call index is persisted to DEPLOY_TEST_COUNTER_FILE (a temp file) so that
# the index survives across $() subshells, which would otherwise lose in-memory
# variable changes.  The test script must set DEPLOY_TEST_COUNTER_FILE and
# initialise it to "0" before each test.

_railway_deploy_list() {
  local svc_id="$1" env_id="$2" limit="${3:-5}"
  if [ "${DEPLOY_TEST_MODE:-0}" = "1" ]; then
    local cf="${DEPLOY_TEST_COUNTER_FILE:-}"
    local idx=0
    [ -n "$cf" ] && [ -f "$cf" ] && idx=$(cat "$cf")
    [ -n "$cf" ] && echo $(( idx + 1 )) > "$cf"
    printf '%s\n' "${MOCK_DEPLOY_CALLS[$idx]:-[]}"
    return 0
  fi
  railway deployment list \
    --project "$EXPECTED_PROJECT_ID" \
    --service "$svc_id" \
    --environment "$env_id" \
    --limit "$limit" --json 2>/dev/null || echo "[]"
}

# ── Pre-deployment state capture ───────────────────────────────────────────────
# Outputs: "LATEST_ID|LATEST_STATUS|ACTIVE_ID|ACTIVE_CREATED"
# LATEST  = first row from --limit 20 (newest regardless of status)
# ACTIVE  = first SUCCESS row from --limit 20 (currently serving traffic)
_capture_state() {
  local svc_id="$1"
  local json
  json=$(_railway_deploy_list "$svc_id" "${ACTUAL_STAGING_ENV_ID:-}" 20)
  echo "$json" | python3 -c '
import json, sys
data = json.load(sys.stdin)
latest_id      = data[0]["id"]        if data else "none"
latest_status  = data[0]["status"]    if data else "none"
active_id      = "none"
active_created = "none"
for d in data:
    if d["status"] == "SUCCESS":
        active_id      = d["id"]
        active_created = d["createdAt"]
        break
print(f"{latest_id}|{latest_status}|{active_id}|{active_created}")
' 2>/dev/null || echo "none|none|none|none"
}

# ── New deployment tracking ────────────────────────────────────────────────────
# Usage: wait_for_new_deploy <svc_id> <pre_latest_id> <pre_active_id> <timeout_s> <label>
# Sets VERIFIED_NEW_DEPLOY_ID on success.
# Phase 1: wait until --limit 1 returns ID != pre_latest_id  → that is NEW_DEPLOY_ID
# Phase 2: poll until NEW_DEPLOY_ID reaches SUCCESS
#   - Abort on FAILED/CRASHED/REMOVED
#   - Abort if yet another deployment appears (concurrent activity)
#   - Abort on timeout
# On failure: runs check_rollback against pre_active_id
VERIFIED_NEW_DEPLOY_ID="unknown"

wait_for_new_deploy() {
  local svc_id="$1" pre_latest_id="$2" pre_active_id="$3" timeout="$4" label="$5"
  local elapsed=0
  VERIFIED_NEW_DEPLOY_ID="unknown"
  local new_deploy_id="discovering"

  info "$label: watching for deployment newer than $pre_latest_id (timeout ${timeout}s)"

  while [ "$elapsed" -lt "$timeout" ]; do
    local json1
    json1=$(_railway_deploy_list "$svc_id" "${ACTUAL_STAGING_ENV_ID:-}" 1)
    local latest_id latest_status
    latest_id=$(echo "$json1" | python3 -c "
import json,sys; d=json.load(sys.stdin); print(d[0]['id'] if d else 'none')" 2>/dev/null || echo "none")
    latest_status=$(echo "$json1" | python3 -c "
import json,sys; d=json.load(sys.stdin); print(d[0]['status'] if d else 'none')" 2>/dev/null || echo "none")

    if [ "$new_deploy_id" = "discovering" ]; then
      # Phase 1: wait for the list to change
      if [ "$latest_id" = "$pre_latest_id" ]; then
        echo "    [${elapsed}s] Latest is still pre-deploy ($pre_latest_id) — upload in progress"
      elif [ "$latest_id" = "none" ]; then
        echo "    [${elapsed}s] No deployments returned — retrying"
      else
        new_deploy_id="$latest_id"
        info "$label: new deployment discovered: $new_deploy_id (status: $latest_status)"
      fi
    else
      # Phase 2: poll specific deployment; detect concurrent activity
      if [ "$latest_id" != "$new_deploy_id" ] && [ "$latest_id" != "none" ]; then
        die "$label: concurrent deployment detected — $latest_id appeared after our deployment $new_deploy_id. Investigate before retrying."
      fi
      # Get specific status from wider query
      local json5
      json5=$(_railway_deploy_list "$svc_id" "${ACTUAL_STAGING_ENV_ID:-}" 5)
      local our_status
      our_status=$(echo "$json5" | python3 -c "
import json,sys
d=json.load(sys.stdin)
for dep in d:
    if dep['id']=='$new_deploy_id':
        print(dep['status']); break
else: print('not_found')" 2>/dev/null || echo "not_found")
      case "$our_status" in
        SUCCESS)
          ok "$label deployment $new_deploy_id reached SUCCESS after ${elapsed}s"
          VERIFIED_NEW_DEPLOY_ID="$new_deploy_id"
          return 0
          ;;
        FAILED|CRASHED|REMOVED)
          echo
          echo -e "  ${RED}$label deployment $new_deploy_id reached $our_status${NC}"
          _check_rollback "$svc_id" "$pre_active_id" "$new_deploy_id" "$label"
          die "$label deployment $new_deploy_id → $our_status — HARD FAIL."
          ;;
        not_found)
          echo "    [${elapsed}s] $label $new_deploy_id not in recent list — retrying"
          ;;
        *)
          echo "    [${elapsed}s] $label $new_deploy_id status: $our_status — waiting"
          ;;
      esac
    fi

    sleep "$POLL_INTERVAL"
    elapsed=$((elapsed + POLL_INTERVAL))
  done

  if [ "$new_deploy_id" = "discovering" ]; then
    die "$label: no new deployment appeared within ${timeout}s — HARD FAIL."
  else
    die "$label: deployment $new_deploy_id did not reach SUCCESS within ${timeout}s — HARD FAIL."
  fi
}

# ── Rollback verification ──────────────────────────────────────────────────────
# Usage: _check_rollback <svc_id> <pre_active_id> <failed_new_id> <label>
_check_rollback() {
  local svc_id="$1" pre_active_id="$2" failed_new_id="$3" label="$4"
  local state
  state=$(_capture_state "$svc_id")
  local current_latest current_active
  current_latest="${state%%|*}"
  # active_id is the third field
  current_active=$(echo "$state" | cut -d'|' -f3)

  info "$label rollback check:"
  info "  Pre-deploy active: $pre_active_id"
  info "  Failed new deploy: $failed_new_id"
  info "  Current active:    $current_active"
  info "  Current latest:    $current_latest"

  if [ "$current_active" = "$pre_active_id" ]; then
    ok "$label rollback confirmed — prior deployment $pre_active_id is still active"
  elif [ "$current_active" = "$failed_new_id" ]; then
    echo -e "  ${YLW}[WARN]${NC} $label active deployment is the failed ID $failed_new_id — unexpected state"
  elif [ "$current_active" = "none" ]; then
    echo -e "  ${YLW}[WARN]${NC} $label has no active SUCCESS deployment — service may be down"
  else
    echo -e "  ${YLW}[WARN]${NC} $label active deployment $current_active is neither pre-deploy nor failed — concurrent deployment activity suspected"
  fi
}

# ── HTTP health gate ───────────────────────────────────────────────────────────
# Usage: poll_health <url> <timeout_s> <description>
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
    echo "    [${elapsed}s] HTTP $code — waiting"
    sleep "$POLL_INTERVAL"
    elapsed=$((elapsed + POLL_INTERVAL))
  done
  die "$desc did not return HTTP 200 within ${timeout}s — HARD FAIL."
}

# ── Authenticated staging API call ────────────────────────────────────────────
# Sets STAGING_API_CODE and STAGING_API_BODY. Token is never echoed.
STAGING_API_CODE="000"
STAGING_API_BODY=""
staging_api_call() {
  local method="$1" path="$2" body="${3:-}"
  local url="https://$EXPECTED_STAGING_BACKEND_DOMAIN$path"
  local raw
  if [ -n "$body" ]; then
    raw=$(curl -s -w "\n__STATUS__%{http_code}" \
      --connect-timeout 10 --max-time 20 \
      -X "$method" \
      -H "Authorization: Bearer $STAGING_AUTH_TOKEN" \
      -H "Content-Type: application/json" \
      -d "$body" "$url" 2>/dev/null)
  else
    raw=$(curl -s -w "\n__STATUS__%{http_code}" \
      --connect-timeout 10 --max-time 20 \
      -X "$method" \
      -H "Authorization: Bearer $STAGING_AUTH_TOKEN" \
      "$url" 2>/dev/null)
  fi
  STAGING_API_CODE=$(echo "$raw" | grep -o '__STATUS__[0-9]*' | grep -o '[0-9]*' || echo "000")
  STAGING_API_BODY=$(echo "$raw" | sed 's/__STATUS__[0-9]*$//')
}

# ── Playwright smoke (hard gate) ──────────────────────────────────────────────
# Usage: require_playwright_smoke <grep_pattern> <description>
require_playwright_smoke() {
  local pattern="$1" desc="$2"
  local spec="tools/playwright-staging/tests/staging-verification.spec.ts"
  if ! command -v npx &>/dev/null || [ ! -f "$spec" ]; then
    die "Playwright not available — required gate cannot run: $desc. Install dependencies."
  fi
  info "Running required Playwright gate: $desc"
  npx playwright test \
      --project=chromium \
      --grep "$pattern" \
      --reporter=line \
      --timeout=60000 \
      "$spec" 2>&1 \
    && ok "Playwright gate PASSED: $desc" \
    || die "Playwright gate FAILED: $desc — HARD FAIL."
}

# ── Subject-area-tags CRUD workflow ───────────────────────────────────────────
# Runs only after backend v40 is confirmed active. Never prints the token.
run_subject_area_tags_crud() {
  echo
  echo "  ── Subject-area-tags CRUD workflow ──────────────────────────────────"

  staging_api_call GET "/api/subject-area-tags"
  [ "$STAGING_API_CODE" = "200" ] \
    || die "/api/subject-area-tags GET → $STAGING_API_CODE (expected 200) — HARD FAIL."
  echo "$STAGING_API_BODY" | python3 -c "import json,sys; assert isinstance(json.load(sys.stdin),list)" 2>/dev/null \
    || die "/api/subject-area-tags response is not a JSON array — HARD FAIL."
  ok "GET /api/subject-area-tags → 200 JSON array"

  local tag_name="Deployment Verification $(date -u '+%Y%m%dT%H%M%SZ')"
  staging_api_call POST "/api/subject-area-tags" \
    "{\"display_name\": \"$tag_name\", \"scope\": \"squadron\"}"
  [ "$STAGING_API_CODE" = "201" ] \
    || die "POST /api/subject-area-tags → $STAGING_API_CODE (expected 201) — HARD FAIL."
  local tag_id
  tag_id=$(echo "$STAGING_API_BODY" | python3 -c "
import json,sys; print(json.load(sys.stdin).get('id','MISSING'))" 2>/dev/null || echo "MISSING")
  [ "$tag_id" = "MISSING" ] || [ -z "$tag_id" ] \
    && die "POST response missing stable ID — HARD FAIL." || true
  ok "POST /api/subject-area-tags → 201, id=$tag_id"

  staging_api_call GET "/api/subject-area-tags"
  [ "$STAGING_API_CODE" = "200" ] \
    || die "GET (after create) → $STAGING_API_CODE — HARD FAIL."
  local found
  found=$(echo "$STAGING_API_BODY" | python3 -c "
import json,sys; print('yes' if any(t.get('id')=='$tag_id' for t in json.load(sys.stdin)) else 'no')" 2>/dev/null || echo "no")
  [ "$found" = "yes" ] \
    && ok "Created tag $tag_id present in active list" \
    || die "Created tag $tag_id NOT found in active list — HARD FAIL."

  staging_api_call DELETE "/api/subject-area-tags/$tag_id"
  [ "$STAGING_API_CODE" = "200" ] \
    || die "DELETE /api/subject-area-tags/$tag_id → $STAGING_API_CODE (expected 200) — HARD FAIL."
  ok "DELETE /api/subject-area-tags/$tag_id → 200"

  staging_api_call GET "/api/subject-area-tags"
  [ "$STAGING_API_CODE" = "200" ] \
    || die "GET (after archive) → $STAGING_API_CODE — HARD FAIL."
  local still
  still=$(echo "$STAGING_API_BODY" | python3 -c "
import json,sys; print('yes' if any(t.get('id')=='$tag_id' for t in json.load(sys.stdin)) else 'no')" 2>/dev/null || echo "yes")
  [ "$still" = "no" ] \
    && ok "Archived tag $tag_id absent from active list — CRUD PASS" \
    || die "Archived tag $tag_id still in active list — HARD FAIL."
}

# ── FUNCTIONS_ONLY guard (allows sourcing for tests) ──────────────────────────
[[ "${DEPLOY_FUNCTIONS_ONLY:-0}" = "1" ]] && return 0 2>/dev/null || true

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN EXECUTION BEGINS HERE
# ═══════════════════════════════════════════════════════════════════════════════

echo
echo "════════════════════════════════════════════════════════════════════"
echo "  AAFC TMS — Hardened Staging Deployment Guard (v4)"
echo "  All gates: HARD FAIL. UUIDs enforced. CRUD after backend only."
echo "════════════════════════════════════════════════════════════════════"
echo

# ══ PRE-0: Token presence and non-placeholder check ══════════════════════════
echo "  [PRE-0] Staging auth token presence…"
if [ -z "${STAGING_AUTH_TOKEN:-}" ]; then
  die "STAGING_AUTH_TOKEN is not set.
  Export a valid system_admin bearer token for staging:
    export STAGING_AUTH_TOKEN=<token>
  Deployment is blocked without it."
fi
# Minimum plausible length for a JWT (header.payload.signature)
if [ "${#STAGING_AUTH_TOKEN}" -lt 100 ]; then
  die "STAGING_AUTH_TOKEN is too short (${#STAGING_AUTH_TOKEN} chars; JWT expected >100). Appears to be a placeholder."
fi
ok "STAGING_AUTH_TOKEN present and non-trivial length (not printed)"

# ══ STEP 1: Fetch Railway project state ═══════════════════════════════════════
echo
echo "  [1/12] Fetching Railway project state…"
RAILWAY_JSON=$(railway status --json 2>&1)
echo "$RAILWAY_JSON" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null \
  && ok "Railway JSON fetched" \
  || die "Failed to parse Railway JSON. Run: railway login"

# ══ STEP 2: Project ID ════════════════════════════════════════════════════════
echo
echo "  [2/12] Verifying project ID…"
ACTUAL_PROJECT_ID=$(echo "$RAILWAY_JSON" | python3 -c "
import json,sys; print(json.load(sys.stdin).get('id','MISSING'))" 2>/dev/null || echo "ERROR")
info "Expected: $EXPECTED_PROJECT_ID"
info "Actual:   $ACTUAL_PROJECT_ID"
[ "$ACTUAL_PROJECT_ID" = "$EXPECTED_PROJECT_ID" ] \
  && ok "Project ID matches" || die "Project ID mismatch."

# ══ STEP 3: Staging environment ID ════════════════════════════════════════════
echo
echo "  [3/12] Verifying staging environment ID…"
ACTUAL_STAGING_ENV_ID=$(echo "$RAILWAY_JSON" | python3 -c "
import json,sys
data=json.load(sys.stdin)
for e in data.get('environments',{}).get('edges',[]):
    if e['node']['name']=='staging': print(e['node']['id']); break
else: print('MISSING')" 2>/dev/null || echo "ERROR")
info "Expected: $EXPECTED_STAGING_ENV_ID"
info "Actual:   $ACTUAL_STAGING_ENV_ID"
[ "$ACTUAL_STAGING_ENV_ID" = "$EXPECTED_STAGING_ENV_ID" ] \
  && ok "Staging env ID matches" || die "Staging env ID mismatch."
[ "$ACTUAL_STAGING_ENV_ID" = "$PRODUCTION_ENV_ID" ] \
  && die "CRITICAL: staging env ID equals production!" \
  || ok "Staging env ID distinct from production ($PRODUCTION_ENV_ID)"

# ══ STEP 4: Service IDs ═══════════════════════════════════════════════════════
echo
echo "  [4/12] Verifying service IDs…"
_svc_id() {
  local name="$1"
  echo "$RAILWAY_JSON" | python3 -c "
import json,sys; data=json.load(sys.stdin)
for s in data.get('services',{}).get('edges',[]):
    if s['node']['name']=='$name': print(s['node']['id']); break
else: print('MISSING')" 2>/dev/null || echo "ERROR"
}
ACTUAL_BACKEND_SVC_ID=$(_svc_id "$EXPECTED_BACKEND_SVC_NAME")
ACTUAL_FRONTEND_SVC_ID=$(_svc_id "$EXPECTED_FRONTEND_SVC_NAME")
ACTUAL_PW_SVC_ID=$(_svc_id "$EXPECTED_PW_SVC_NAME")
info "Backend  expected=$EXPECTED_BACKEND_SVC_ID  actual=$ACTUAL_BACKEND_SVC_ID"
info "Frontend expected=$EXPECTED_FRONTEND_SVC_ID  actual=$ACTUAL_FRONTEND_SVC_ID"
info "PW       expected=$EXPECTED_PW_SVC_ID  actual=$ACTUAL_PW_SVC_ID"
[ "$ACTUAL_BACKEND_SVC_ID"  = "$EXPECTED_BACKEND_SVC_ID"  ] && ok "Backend  svc ID" || fail "Backend  svc ID MISMATCH"
[ "$ACTUAL_FRONTEND_SVC_ID" = "$EXPECTED_FRONTEND_SVC_ID" ] && ok "Frontend svc ID" || fail "Frontend svc ID MISMATCH"
[ "$ACTUAL_PW_SVC_ID"       = "$EXPECTED_PW_SVC_ID"       ] && ok "PW       svc ID" || fail "PW svc ID MISMATCH"
[ "$FAIL_COUNT" -gt 0 ] && die "Service ID verification failed."

# ══ STEP 5: UUID read-only proof ══════════════════════════════════════════════
echo
echo "  [5/12] UUID read-only resolution proof…"
_uuid_proof() {
  local label="$1" svc_id="$2"
  local json
  json=$(railway deployment list \
    --project "$EXPECTED_PROJECT_ID" \
    --service "$svc_id" \
    --environment "$ACTUAL_STAGING_ENV_ID" \
    --limit 1 --json 2>&1)
  if echo "$json" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
    ok "$label UUID $svc_id accepted by railway deployment list"
    echo "$json" | python3 -c "
import json,sys; d=json.load(sys.stdin)
if d: print(f'    id={d[0][\"id\"]}  status={d[0][\"status\"]}  created={d[0][\"createdAt\"]}')" 2>/dev/null || true
  else
    die "$label UUID $svc_id NOT accepted: $json"
  fi
}
_uuid_proof "Backend"  "$ACTUAL_BACKEND_SVC_ID"
_uuid_proof "Frontend" "$ACTUAL_FRONTEND_SVC_ID"
_uuid_proof "PW"       "$ACTUAL_PW_SVC_ID"

# ══ STEP 6: Staging domains ═══════════════════════════════════════════════════
echo
echo "  [6/12] Verifying staging target domains…"
STAGING_DOMAINS=$(echo "$RAILWAY_JSON" | python3 -c "
import json,sys; data=json.load(sys.stdin)
for env in data.get('environments',{}).get('edges',[]):
    if env['node']['id']=='$EXPECTED_STAGING_ENV_ID':
        for si in env['node'].get('serviceInstances',{}).get('edges',[]):
            for d in si['node'].get('domains',{}).get('serviceDomains',[]):
                print(d['domain'])" 2>/dev/null || echo "ERROR")
echo "  Staging domains:"
echo "$STAGING_DOMAINS" | while read -r d; do [ -n "$d" ] && echo "    $d"; done
echo "$STAGING_DOMAINS" | grep -q "production.up.railway.app" \
  && die "Production domain in staging targets!" \
  || ok "No production domains"
echo "$STAGING_DOMAINS" | grep -qF "$EXPECTED_STAGING_BACKEND_DOMAIN"  && ok "Backend  domain" || fail "Backend  staging domain NOT found"
echo "$STAGING_DOMAINS" | grep -qF "$EXPECTED_STAGING_FRONTEND_DOMAIN" && ok "Frontend domain" || fail "Frontend staging domain NOT found"
echo "$STAGING_DOMAINS" | grep -qF "$EXPECTED_STAGING_PW_DOMAIN"       && ok "PW       domain" || fail "PW staging domain NOT found"

# ══ STEP 7: Git state ═════════════════════════════════════════════════════════
echo
echo "  [7/12] Git state…"
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "UNKNOWN")
[ "$CURRENT_BRANCH" = "$EXPECTED_BRANCH" ] \
  && ok "Branch: $CURRENT_BRANCH" || die "Branch '$CURRENT_BRANCH' ≠ '$EXPECTED_BRANCH'."
[[ "$CURRENT_BRANCH" =~ ^(main|master)$|production ]] && die "Protected branch."
CURRENT_HEAD=$(git rev-parse --short HEAD 2>/dev/null || echo "UNKNOWN")
info "HEAD: $CURRENT_HEAD — $(git log -1 --format='%s')"
git merge-base --is-ancestor "$REQUIRED_ANCESTOR" HEAD 2>/dev/null \
  && ok "Fix commit $REQUIRED_ANCESTOR is ancestor of $CURRENT_HEAD" \
  || die "Fix commit $REQUIRED_ANCESTOR NOT in HEAD's history."
git diff-index --quiet HEAD -- 2>/dev/null && ok "Working tree clean" || die "Uncommitted changes."
UNPUSHED=$(git log "origin/${EXPECTED_BRANCH}..HEAD" --oneline 2>/dev/null || echo "ERROR")
[ -n "$UNPUSHED" ] && die "Unpushed commits — push to origin/$EXPECTED_BRANCH first."
ok "HEAD pushed to origin/$EXPECTED_BRANCH"

# ══ STEP 8: Security greps ════════════════════════════════════════════════════
echo
echo "  [8/12] Security greps…"
_check_grep() {
  local label="$1" pattern="$2" path="$3"
  local c; c=$(grep -rc "$pattern" "$path" 2>/dev/null | awk -F: '{s+=$2}END{print s+0}')
  [ "$c" -eq 0 ] && ok "$label" || { fail "$label ($c match(es))"; grep -rn "$pattern" "$path"|head -3; }
}
_check_grep "No seeded codes"         "SYSADMIN2026\|ADMIN703\|ADMIN7WG\|ADMINNATIONAL" "connected-frontend"
_check_grep "No localStorage"          "localStorage"                                     "connected-frontend"
_check_grep "No access-code hashes"    "code_hash\|plain_code"                           "connected-frontend"
_check_grep "No JWT_SECRET/SECRET_KEY" "JWT_SECRET\|SECRET_KEY"                           "connected-frontend"
_check_grep "No DB connection strings" "postgresql://\|postgres://\|sqlite:///"           "connected-frontend"

# ══ STEP 9: Backend tests ═════════════════════════════════════════════════════
echo
echo "  [9/12] Backend test suite…"
[ -d "backend" ] || die "backend/ not found."
pushd backend > /dev/null
source .venv/bin/activate 2>/dev/null || die ".venv not found."
TEST_OUT=$(python -m pytest tests/ -q --tb=no 2>&1)
LAST=$(echo "$TEST_OUT" | tail -1)
echo "$LAST" | grep -q "passed" && ! echo "$LAST" | grep -q "failed" \
  && ok "Tests: $LAST" || { fail "Tests: $LAST"; echo "$TEST_OUT"|tail -8; }
deactivate 2>/dev/null || true
popd > /dev/null

# ══ STEP 10: Alembic code head ════════════════════════════════════════════════
echo
echo "  [10/12] Alembic code head…"
pushd backend > /dev/null
source .venv/bin/activate 2>/dev/null || true
ALEMBIC_CODE_HEAD=$(python -m alembic heads 2>/dev/null | grep -oE '[a-f0-9]{12}' | head -1 || echo "unknown")
info "Alembic code head: $ALEMBIC_CODE_HEAD"
[ "$ALEMBIC_CODE_HEAD" = "$REQUIRED_ALEMBIC_HEAD" ] \
  && ok "Code head is $REQUIRED_ALEMBIC_HEAD (v40)" \
  || die "Code head is $ALEMBIC_CODE_HEAD, expected $REQUIRED_ALEMBIC_HEAD."
deactivate 2>/dev/null || true
popd > /dev/null

# ══ STEP 11: Railway CLI ══════════════════════════════════════════════════════
echo
echo "  [11/12] Railway CLI…"
command -v railway &>/dev/null || die "railway CLI not found."
ok "railway CLI: $(railway --version 2>/dev/null)"

# ══ STEP 12: Token validation via /api/auth/me ═══════════════════════════════
# /api/auth/me is stable against v39 DB (reads JWT + users table only).
# Does NOT depend on subject_area_tags or the v40 migration.
echo
echo "  [12/12] Validating STAGING_AUTH_TOKEN via /api/auth/me…"
staging_api_call GET "/api/auth/me"
if [ "$STAGING_API_CODE" = "200" ]; then
  TOKEN_ROLE=$(echo "$STAGING_API_BODY" | python3 -c "
import json,sys; d=json.load(sys.stdin); print(d.get('session',{}).get('role','unknown'))" 2>/dev/null || echo "unknown")
  TOKEN_IS_NATIONAL=$(echo "$STAGING_API_BODY" | python3 -c "
import json,sys; d=json.load(sys.stdin); print(d.get('session',{}).get('is_national',False))" 2>/dev/null || echo "False")
  info "Token role: $TOKEN_ROLE  is_national: $TOKEN_IS_NATIONAL"
  if [ "$TOKEN_ROLE" = "system_admin" ]; then
    ok "STAGING_AUTH_TOKEN is valid — role: system_admin"
  else
    die "Token valid but role='$TOKEN_ROLE', not system_admin — HARD FAIL."
  fi
elif [ "$STAGING_API_CODE" = "401" ]; then
  die "STAGING_AUTH_TOKEN is invalid or expired (HTTP 401) — obtain a fresh system_admin token."
else
  die "/api/auth/me returned $STAGING_API_CODE — staging backend may be unreachable or token is corrupt."
fi

# ══ Preflight summary ═════════════════════════════════════════════════════════
echo
echo "════════════════════════════════════════════════════════════════════"
echo -e "  Preflight: ${GRN}PASS: $PASS_COUNT${NC}   ${RED}FAIL: $FAIL_COUNT${NC}"
echo "════════════════════════════════════════════════════════════════════"
[ "$FAIL_COUNT" -gt 0 ] && die "$FAIL_COUNT preflight check(s) failed."
echo

# ══ Pre-deployment state capture ══════════════════════════════════════════════
# Captures BOTH latest deployment ID (regardless of status) and active SUCCESS ID.
# The new-deployment tracker waits for latest to CHANGE from PRE_*_LATEST.
echo "  PRE-DEPLOYMENT STATE (both LATEST and ACTIVE captured per service)"
echo

_capture_and_report() {
  local svc_id="$1" label="$2"
  local state
  state=$(_capture_state "$svc_id")
  local latest="${state%%|*}"
  local rest="${state#*|}"
  local lat_status="${rest%%|*}"
  rest="${rest#*|}"
  local active="${rest%%|*}"
  local active_created="${rest#*|}"
  printf "  %-12s LATEST=%-44s (%s)\n" "$label" "$latest" "$lat_status"
  printf "  %-12s ACTIVE=%-44s (%s)\n" ""          "$active"  "$active_created"
  echo "${latest}|${active}"
}

_BACKEND_PRE=$(_capture_and_report "$ACTUAL_BACKEND_SVC_ID"  "Backend:")
PRE_BACKEND_LATEST="${_BACKEND_PRE%%|*}";  PRE_BACKEND_ACTIVE="${_BACKEND_PRE#*|}"

_FRONTEND_PRE=$(_capture_and_report "$ACTUAL_FRONTEND_SVC_ID" "Frontend:")
PRE_FRONTEND_LATEST="${_FRONTEND_PRE%%|*}"; PRE_FRONTEND_ACTIVE="${_FRONTEND_PRE#*|}"

_PW_PRE=$(_capture_and_report "$ACTUAL_PW_SVC_ID" "PW:")
PRE_PW_LATEST="${_PW_PRE%%|*}";            PRE_PW_ACTIVE="${_PW_PRE#*|}"

echo
echo "  The new-deployment tracker waits for --limit 1 to return an ID"
echo "  different from PRE_LATEST before declaring a new deployment found."
echo

# ══ Resolved targets display ══════════════════════════════════════════════════
echo "  RESOLVED TARGETS (verified against immutable allowlist)"
echo
printf "  %-30s %s\n" "Project ID:"         "$ACTUAL_PROJECT_ID"
printf "  %-30s %s\n" "Staging env ID:"      "$ACTUAL_STAGING_ENV_ID"
printf "  %-30s %s\n" "Production env ID:"   "$PRODUCTION_ENV_ID  (NOT targeted)"
echo
printf "  %-30s %s / UUID: %s\n" "Service 1:" "$EXPECTED_BACKEND_SVC_NAME"  "$ACTUAL_BACKEND_SVC_ID"
printf "  %-30s %s / UUID: %s\n" "Service 2:" "$EXPECTED_FRONTEND_SVC_NAME" "$ACTUAL_FRONTEND_SVC_ID"
printf "  %-30s %s / UUID: %s\n" "Service 3:" "$EXPECTED_PW_SVC_NAME"       "$ACTUAL_PW_SVC_ID"
echo
printf "  %-30s %s\n" "Branch:"  "$CURRENT_BRANCH"
printf "  %-30s %s\n" "HEAD:"    "$CURRENT_HEAD — $(git log -1 --format='%s')"
echo

# ══ Authorization gate ════════════════════════════════════════════════════════
REQUIRED_PHRASE="DEPLOY TO STAGING ${CURRENT_HEAD}"
echo -e "  ${YLW}══ AUTHORIZATION REQUIRED ══${NC}"
echo
echo "  All preflight checks passed. Authorize deployment of $CURRENT_HEAD:"
echo -e "  ${BLU}${REQUIRED_PHRASE}${NC}"
echo
read -r CONFIRM
[ -z "$CONFIRM" ]                      && die "Empty input."
[ "$CONFIRM" != "$REQUIRED_PHRASE" ]   && die "Phrase mismatch.\n  Typed:    '$CONFIRM'\n  Required: '$REQUIRED_PHRASE'"
RECHECK_HEAD=$(git rev-parse --short HEAD 2>/dev/null)
[ "$RECHECK_HEAD" != "$CURRENT_HEAD" ] && die "HEAD changed during prompt."
echo
echo -e "  ${GRN}Authorization accepted.${NC} Deploying $CURRENT_HEAD."
echo

# ══ DRY RUN ══════════════════════════════════════════════════════════════════
if [ "${DRY_RUN:-0}" = "1" ]; then
  echo -e "  ${YLW}DRY RUN — commands that would execute (no writes made):${NC}"
  echo
  echo "  [1/3] Backend  (UUID: $ACTUAL_BACKEND_SVC_ID)"
  echo "    railway up --project $EXPECTED_PROJECT_ID \\"
  echo "               --service $ACTUAL_BACKEND_SVC_ID \\"
  echo "               --environment $ACTUAL_STAGING_ENV_ID --detach"
  echo "    Gate 1: poll /api/health/ready HTTP 200 (${BACKEND_GATE_TIMEOUT}s)"
  echo "    Gate 2: wait for NEW deployment (newer than PRE_BACKEND_LATEST=$PRE_BACKEND_LATEST)"
  echo "    Gate 3: /api/system/migrations revision == $REQUIRED_ALEMBIC_HEAD"
  echo "    Gate 4: subject-area-tags CRUD (POST→GET→DELETE→GET)"
  echo "    [DRY RUN: gates 3-4 not executed; staging DB unchanged]"
  echo
  echo "  [2/3] Frontend (UUID: $ACTUAL_FRONTEND_SVC_ID)"
  echo "    railway up --project $EXPECTED_PROJECT_ID \\"
  echo "               --service $ACTUAL_FRONTEND_SVC_ID \\"
  echo "               --environment $ACTUAL_STAGING_ENV_ID --detach"
  echo "    Gate 1: poll / HTTP 200 (${FRONTEND_GATE_TIMEOUT}s)"
  echo "    Gate 2: wait for NEW deployment (newer than PRE_FRONTEND_LATEST=$PRE_FRONTEND_LATEST)"
  echo "    Gate 3: root HTML contains app-build meta with SHA $CURRENT_HEAD"
  echo "    Gate 4: Playwright — [Dashboard], [Nav] Mobile, [Network]"
  echo
  echo "  [3/3] PW       (UUID: $ACTUAL_PW_SVC_ID)"
  echo "    railway up --project $EXPECTED_PROJECT_ID \\"
  echo "               --service $ACTUAL_PW_SVC_ID \\"
  echo "               --environment $ACTUAL_STAGING_ENV_ID --detach"
  echo "    Gate 1: poll /healthz HTTP 200 (${PW_GATE_TIMEOUT}s)"
  echo "    Gate 2: wait for NEW deployment (newer than PRE_PW_LATEST=$PRE_PW_LATEST)"
  echo "    Gate 3: root HTML contains React markers + SHA $CURRENT_HEAD"
  echo "    Gate 4: Playwright — [Mission Backlog / PW], [PW]"
  echo
  echo "  Token validated via /api/auth/me (read-only, no staging data changed)."
  echo "  Subject-area-tags CRUD: runs only post-backend in live mode."
  echo
  echo "  DRY RUN complete. Exit 0. No deployments. No staging writes."
  exit 0
fi

# ══════════════════════════════════════════════════════════════════════════════
# DEPLOYMENT 1/3 — BACKEND
# ══════════════════════════════════════════════════════════════════════════════
echo "────────────────────────────────────────────────────────────────────"
echo "  [Deploy 1/3] $EXPECTED_BACKEND_SVC_NAME"
info "  Service UUID:      $ACTUAL_BACKEND_SVC_ID"
info "  Env UUID:          $ACTUAL_STAGING_ENV_ID"
info "  PRE_LATEST:        $PRE_BACKEND_LATEST"
info "  PRE_ACTIVE:        $PRE_BACKEND_ACTIVE"
info "  Migration:         a1b2c3d4e5f6 → $REQUIRED_ALEMBIC_HEAD"
echo

railway up \
  --project "$EXPECTED_PROJECT_ID" \
  --service "$ACTUAL_BACKEND_SVC_ID" \
  --environment "$ACTUAL_STAGING_ENV_ID" \
  --detach 2>&1

echo
echo "  ── Backend gate 1/4: health ──────────────────────────────────────────"
poll_health \
  "https://$EXPECTED_STAGING_BACKEND_DOMAIN/api/health/ready" \
  "$BACKEND_GATE_TIMEOUT" "Backend /api/health/ready"

READY_JSON=$(curl -s --connect-timeout 10 --max-time 15 \
  "https://$EXPECTED_STAGING_BACKEND_DOMAIN/api/health/ready" 2>/dev/null || echo '{}')
echo "$READY_JSON" | python3 -c "
import json,sys; d=json.load(sys.stdin); assert d.get('status')=='ready'" 2>/dev/null \
  && ok "Readiness: status=ready" \
  || die "Backend /api/health/ready did not return status:ready — HARD FAIL."

echo
echo "  ── Backend gate 2/4: new deployment ID ──────────────────────────────"
wait_for_new_deploy \
  "$ACTUAL_BACKEND_SVC_ID" \
  "$PRE_BACKEND_LATEST" \
  "$PRE_BACKEND_ACTIVE" \
  "$BACKEND_GATE_TIMEOUT" \
  "Backend"
BACKEND_NEW_DEPLOY_ID="$VERIFIED_NEW_DEPLOY_ID"
info "Backend: new=$BACKEND_NEW_DEPLOY_ID  pre_latest=$PRE_BACKEND_LATEST  pre_active=$PRE_BACKEND_ACTIVE"

echo
echo "  ── Backend gate 3/4: database revision ──────────────────────────────"
staging_api_call GET "/api/system/migrations"
[ "$STAGING_API_CODE" = "200" ] \
  || die "/api/system/migrations → $STAGING_API_CODE (expected 200) — HARD FAIL."
DB_REVISION=$(echo "$STAGING_API_BODY" | python3 -c "
import json,sys; print(json.load(sys.stdin).get('revision','MISSING'))" 2>/dev/null || echo "ERROR")
IS_SINGLE=$(echo "$STAGING_API_BODY" | python3 -c "
import json,sys; print(json.load(sys.stdin).get('is_single_head',False))" 2>/dev/null || echo "False")
info "is_single_head: $IS_SINGLE  revision: $DB_REVISION"
[ "$IS_SINGLE" = "True" ] || die "Multiple Alembic heads — HARD FAIL."
[ "$DB_REVISION" = "$REQUIRED_ALEMBIC_HEAD" ] \
  && ok "DB revision: $DB_REVISION — exact match (v40 applied)" \
  || die "DB revision '$DB_REVISION' ≠ '$REQUIRED_ALEMBIC_HEAD' — HARD FAIL."

run_subject_area_tags_crud

ok "Backend gate PASSED."

# Re-verify backend service ID
_recheck=$(_svc_id "$EXPECTED_BACKEND_SVC_NAME")
[ "$_recheck" = "$EXPECTED_BACKEND_SVC_ID" ] || die "Backend service ID changed!"

# ══════════════════════════════════════════════════════════════════════════════
# DEPLOYMENT 2/3 — MAIN TMS FRONTEND
# ══════════════════════════════════════════════════════════════════════════════
echo
echo "────────────────────────────────────────────────────────────────────"
echo "  [Deploy 2/3] $EXPECTED_FRONTEND_SVC_NAME"
info "  Service UUID:      $ACTUAL_FRONTEND_SVC_ID"
info "  PRE_LATEST:        $PRE_FRONTEND_LATEST"
info "  PRE_ACTIVE:        $PRE_FRONTEND_ACTIVE"
echo

railway up \
  --project "$EXPECTED_PROJECT_ID" \
  --service "$ACTUAL_FRONTEND_SVC_ID" \
  --environment "$ACTUAL_STAGING_ENV_ID" \
  --detach 2>&1

echo
echo "  ── Frontend gate 1/4: HTTP 200 ──────────────────────────────────────"
poll_health "https://$EXPECTED_STAGING_FRONTEND_DOMAIN/" "$FRONTEND_GATE_TIMEOUT" "Frontend /"

echo
echo "  ── Frontend gate 2/4: new deployment ID ─────────────────────────────"
wait_for_new_deploy \
  "$ACTUAL_FRONTEND_SVC_ID" \
  "$PRE_FRONTEND_LATEST" \
  "$PRE_FRONTEND_ACTIVE" \
  "$FRONTEND_GATE_TIMEOUT" \
  "Frontend"
FRONTEND_NEW_DEPLOY_ID="$VERIFIED_NEW_DEPLOY_ID"
info "Frontend: new=$FRONTEND_NEW_DEPLOY_ID  pre_latest=$PRE_FRONTEND_LATEST"

echo
echo "  ── Frontend gate 3/4: build fingerprint ─────────────────────────────"
FRONTEND_HTML=$(curl -s --connect-timeout 10 --max-time 20 \
  "https://$EXPECTED_STAGING_FRONTEND_DOMAIN/" 2>/dev/null || echo "")
echo "$FRONTEND_HTML" | grep -q 'name="app-build"' \
  || die 'Build fingerprint meta (name="app-build") NOT found — HARD FAIL.'
ok "Build fingerprint meta present"
echo "$FRONTEND_HTML" | grep -q "$CURRENT_HEAD" \
  || die "Root HTML does not contain SHA $CURRENT_HEAD — HARD FAIL."
ok "Root HTML contains SHA: $CURRENT_HEAD"

echo
echo "  ── Frontend gate 4/4: Playwright smoke ──────────────────────────────"
require_playwright_smoke \
  '\[Dashboard\]|\[Nav\] Mobile|\[Network\]' \
  "Dashboard + Mobile nav + Network"

ok "Frontend gate PASSED."

# ══════════════════════════════════════════════════════════════════════════════
# DEPLOYMENT 3/3 — PLANNING WORKSPACE
# ══════════════════════════════════════════════════════════════════════════════
echo
echo "────────────────────────────────────────────────────────────────────"
echo "  [Deploy 3/3] $EXPECTED_PW_SVC_NAME"
info "  Service UUID:      $ACTUAL_PW_SVC_ID"
info "  PRE_LATEST:        $PRE_PW_LATEST"
info "  PRE_ACTIVE:        $PRE_PW_ACTIVE"
echo

railway up \
  --project "$EXPECTED_PROJECT_ID" \
  --service "$ACTUAL_PW_SVC_ID" \
  --environment "$ACTUAL_STAGING_ENV_ID" \
  --detach 2>&1

echo
echo "  ── PW gate 1/4: HTTP 200 ────────────────────────────────────────────"
poll_health "https://$EXPECTED_STAGING_PW_DOMAIN/healthz" "$PW_GATE_TIMEOUT" "PW /healthz"

echo
echo "  ── PW gate 2/4: new deployment ID ───────────────────────────────────"
wait_for_new_deploy \
  "$ACTUAL_PW_SVC_ID" \
  "$PRE_PW_LATEST" \
  "$PRE_PW_ACTIVE" \
  "$PW_GATE_TIMEOUT" \
  "PW"
PW_NEW_DEPLOY_ID="$VERIFIED_NEW_DEPLOY_ID"
info "PW: new=$PW_NEW_DEPLOY_ID  pre_latest=$PRE_PW_LATEST"

echo
echo "  ── PW gate 3/4: build fingerprint ───────────────────────────────────"
PW_HTML=$(curl -s --connect-timeout 10 --max-time 20 \
  "https://$EXPECTED_STAGING_PW_DOMAIN/" 2>/dev/null || echo "")
echo "$PW_HTML" | grep -qiE 'react|vite|__vite_|data-reactroot' \
  || die "PW HTML lacks React app markers — HARD FAIL."
ok "PW HTML contains React app markers"
echo "$PW_HTML" | grep -q "$CURRENT_HEAD" \
  || die "PW root HTML does not contain SHA $CURRENT_HEAD — HARD FAIL."
ok "PW root HTML contains SHA: $CURRENT_HEAD"

echo
echo "  ── PW gate 4/4: Playwright smoke ────────────────────────────────────"
require_playwright_smoke \
  '\[Mission Backlog / PW\]|\[PW\]' \
  "Planning Workspace smoke"

ok "PW gate PASSED."

# ══ Final audit: active deployment IDs ══════════════════════════════════════
echo
echo "  POST-DEPLOYMENT ACTIVE DEPLOYMENT VERIFICATION"
echo
_final_check() {
  local svc_id="$1" pre_active="$2" expected_new="$3" label="$4"
  local state; state=$(_capture_state "$svc_id")
  local current_active; current_active=$(echo "$state" | cut -d'|' -f3)
  if [ "$current_active" = "$expected_new" ]; then
    ok "$label active deployment: $current_active (new deployment confirmed active)"
  elif [ "$current_active" = "$pre_active" ]; then
    die "$label active deployment is still pre-deploy ID — new deployment may not be serving."
  else
    info "$label active deployment: $current_active (different from both pre-deploy and expected new)"
  fi
}
_final_check "$ACTUAL_BACKEND_SVC_ID"  "$PRE_BACKEND_ACTIVE"  "$BACKEND_NEW_DEPLOY_ID"  "Backend:"
_final_check "$ACTUAL_FRONTEND_SVC_ID" "$PRE_FRONTEND_ACTIVE" "$FRONTEND_NEW_DEPLOY_ID" "Frontend:"
_final_check "$ACTUAL_PW_SVC_ID"       "$PRE_PW_ACTIVE"       "$PW_NEW_DEPLOY_ID"       "PW:"

echo
echo "════════════════════════════════════════════════════════════════════"
echo -e "  ${GRN}All three staging deployments completed. All hard gates passed.${NC}"
echo "  Commit deployed: $CURRENT_HEAD"
echo
printf "  %-12s pre_latest=%-44s  new=%s\n" "Backend:"  "$PRE_BACKEND_LATEST"  "$BACKEND_NEW_DEPLOY_ID"
printf "  %-12s pre_latest=%-44s  new=%s\n" "Frontend:" "$PRE_FRONTEND_LATEST" "$FRONTEND_NEW_DEPLOY_ID"
printf "  %-12s pre_latest=%-44s  new=%s\n" "PW:"       "$PRE_PW_LATEST"       "$PW_NEW_DEPLOY_ID"
echo
echo "  Next: run the full Playwright suite."
echo "    npx playwright test tools/playwright-staging/tests/staging-verification.spec.ts"
echo "    Screenshots: artifacts/staging-ui-verification/$CURRENT_HEAD/"
echo "════════════════════════════════════════════════════════════════════"
echo
