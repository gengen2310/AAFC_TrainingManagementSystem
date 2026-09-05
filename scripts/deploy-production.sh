#!/usr/bin/env bash
# deploy-production.sh — Hardened production deployment guard for AAFC TMS (v1).
#
# ┌─────────────────────────────────────────────────────────────────────────┐
# │  PRODUCTION DEPLOY — RUNS LIVE MIGRATIONS AGAINST PRODUCTION DATABASE  │
# │  Irreversible until a manual rollback is triggered in Railway dashboard │
# └─────────────────────────────────────────────────────────────────────────┘
#
# Authentication:
#   Two-step cookie login against production backend.
#   Credential via env var or hidden interactive prompt. Never in args.
#
# Gate order:
#   CREDENTIAL  : hidden prompt or PRODUCTION_SYSTEM_ADMIN_CODE env var
#   PREFLIGHT   : Railway IDs, UUIDs, git, security greps, backend tests, Alembic head
#   AUTH        : login + /api/auth/me role=system_admin
#   PRE-DEPLOY  : capture PRE_LATEST and PRE_ACTIVE for all three services
#   AUTHZ       : deployment phrase (DEPLOY TO PRODUCTION <sha>)
#   BACKEND     : railway up → health/ready → new-deploy ID → DB revision → CRUD
#   FRONTEND    : railway up → HTTP 200 → new-deploy ID → build fingerprint
#   PW          : railway up → HTTP 200 → new-deploy ID → React markers
#   CLEANUP     : logout, delete cookie jar, unset credential
#
# USAGE:
#   bash scripts/deploy-production.sh                                  # interactive
#   PRODUCTION_SYSTEM_ADMIN_CODE=xxx bash scripts/deploy-production.sh # CI
#   PRODUCTION_SYSTEM_ADMIN_CODE=xxx DRY_RUN=1 bash scripts/deploy-production.sh
#
# TESTING (source functions without running main):
#   DEPLOY_FUNCTIONS_ONLY=1 source scripts/deploy-production.sh

set -uo pipefail

# ── Immutable allowlist ────────────────────────────────────────────────────────
EXPECTED_PROJECT_ID="f5d9524f-8a57-44ff-86b7-ab66aec00e73"
EXPECTED_PRODUCTION_ENV_ID="571a8028-3640-4542-a4ab-7a1ee6b1f693"
STAGING_ENV_ID="77a45568-5c16-46c2-9065-d5d339208b0e"  # MUST NEVER BE TARGETED

EXPECTED_BACKEND_SVC_ID="deb53faa-ca8d-4291-aa2e-9ff3029c50f8"
EXPECTED_FRONTEND_SVC_ID="2b5e6359-2523-4209-be5b-bdf7f5273ec5"
EXPECTED_PW_SVC_ID="253cf237-1836-43bc-9ee4-0e4eefd447b4"

EXPECTED_BACKEND_SVC_NAME="aafc-tms-backend"
EXPECTED_FRONTEND_SVC_NAME="aafc-tms-frontend"
EXPECTED_PW_SVC_NAME="aafc-tms-planning-workspace-preview"

EXPECTED_PRODUCTION_BACKEND_DOMAIN="aafc-tms-backend-production.up.railway.app"
EXPECTED_PRODUCTION_FRONTEND_DOMAIN="aafc-tms-frontend-production.up.railway.app"
EXPECTED_PRODUCTION_PW_DOMAIN="aafc-tms-planning-workspace-preview-production.up.railway.app"

EXPECTED_BRANCH="main"
REQUIRED_ANCESTOR="de27c42"
REQUIRED_ALEMBIC_HEAD="b1c2d3e4f5a6"

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

# ── Temp-file globals ─────────────────────────────────────────────────────────
COOKIE_JAR=""
LOGIN_PAYLOAD_FILE=""
PROD_API_CODE="000"
PROD_API_BODY=""
VERIFIED_NEW_DEPLOY_ID="unknown"
ACTUAL_TARGET_ENV_ID=""

# ── Cleanup ────────────────────────────────────────────────────────────────────
cleanup() {
  if [ -n "${COOKIE_JAR:-}" ] && [ -f "${COOKIE_JAR:-}" ] && [ -s "${COOKIE_JAR:-}" ]; then
    curl -s -X POST \
      --connect-timeout 5 --max-time 10 \
      --cookie "$COOKIE_JAR" \
      "https://$EXPECTED_PRODUCTION_BACKEND_DOMAIN/api/auth/logout" \
      >/dev/null 2>&1 || true
    info "Production logout called."
  fi
  [ -n "${LOGIN_PAYLOAD_FILE:-}" ] && : > "${LOGIN_PAYLOAD_FILE:-}" 2>/dev/null || true
  rm -f "${COOKIE_JAR:-}" "${LOGIN_PAYLOAD_FILE:-}" 2>/dev/null || true
  unset PRODUCTION_SYSTEM_ADMIN_CODE 2>/dev/null || true
  info "Temporary files deleted; credential unset."
}

# ── Railway deployment list wrapper ───────────────────────────────────────────
_railway_deploy_list() {
  local svc_id="$1" env_id="$2" limit="${3:-5}"
  railway deployment list \
    --project "$EXPECTED_PROJECT_ID" \
    --service "$svc_id" \
    --environment "$env_id" \
    --limit "$limit" --json 2>/dev/null || echo "[]"
}

# ── Pre-deployment state capture ───────────────────────────────────────────────
_capture_state() {
  local svc_id="$1"
  local json
  json=$(_railway_deploy_list "$svc_id" "${ACTUAL_TARGET_ENV_ID:-}" 20)
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

# ── New deployment tracker ─────────────────────────────────────────────────────
wait_for_new_deploy() {
  local svc_id="$1" pre_latest_id="$2" pre_active_id="$3" timeout="$4" label="$5"
  local elapsed=0
  VERIFIED_NEW_DEPLOY_ID="unknown"
  local new_deploy_id="discovering"

  info "$label: watching for deployment newer than $pre_latest_id (timeout ${timeout}s)"

  while [ "$elapsed" -lt "$timeout" ]; do
    local json1
    json1=$(_railway_deploy_list "$svc_id" "${ACTUAL_TARGET_ENV_ID:-}" 1)
    local latest_id latest_status
    latest_id=$(echo "$json1" | python3 -c "
import json,sys; d=json.load(sys.stdin); print(d[0]['id'] if d else 'none')" 2>/dev/null || echo "none")
    latest_status=$(echo "$json1" | python3 -c "
import json,sys; d=json.load(sys.stdin); print(d[0]['status'] if d else 'none')" 2>/dev/null || echo "none")

    if [ "$new_deploy_id" = "discovering" ]; then
      if [ "$latest_id" = "$pre_latest_id" ]; then
        echo "    [${elapsed}s] Latest is still pre-deploy ($pre_latest_id) — upload in progress"
      elif [ "$latest_id" = "none" ]; then
        echo "    [${elapsed}s] No deployments returned — retrying"
      else
        new_deploy_id="$latest_id"
        info "$label: new deployment discovered: $new_deploy_id (status: $latest_status)"
      fi
    else
      if [ "$latest_id" != "$new_deploy_id" ] && [ "$latest_id" != "none" ]; then
        die "$label: concurrent deployment detected — $latest_id appeared after our deployment $new_deploy_id. Investigate before retrying."
      fi
      local json5
      json5=$(_railway_deploy_list "$svc_id" "${ACTUAL_TARGET_ENV_ID:-}" 5)
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
          echo -e "\n  ${RED}$label deployment $new_deploy_id reached $our_status${NC}"
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

# ── Rollback check ─────────────────────────────────────────────────────────────
_check_rollback() {
  local svc_id="$1" pre_active_id="$2" failed_new_id="$3" label="$4"
  local state; state=$(_capture_state "$svc_id")
  local current_active; current_active=$(echo "$state" | cut -d'|' -f3)
  info "$label rollback check: pre_active=$pre_active_id  failed=$failed_new_id  now_active=$current_active"
  if [ "$current_active" = "$pre_active_id" ]; then
    ok "$label rollback confirmed — prior deployment $pre_active_id is still active"
  elif [ "$current_active" = "none" ]; then
    echo -e "  ${YLW}[WARN]${NC} $label has no active SUCCESS deployment — service may be down"
  else
    echo -e "  ${YLW}[WARN]${NC} $label active deployment is $current_active (neither pre-deploy nor failed)"
  fi
}

# ── HTTP health gate ───────────────────────────────────────────────────────────
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

# ── Credential acquisition ─────────────────────────────────────────────────────
acquire_credential() {
  if [ -n "${PRODUCTION_SYSTEM_ADMIN_CODE:-}" ]; then
    if [ "${#PRODUCTION_SYSTEM_ADMIN_CODE}" -lt 6 ]; then
      die "PRODUCTION_SYSTEM_ADMIN_CODE is too short — appears to be a placeholder."
    fi
    info "Credential loaded from PRODUCTION_SYSTEM_ADMIN_CODE (CI mode; value not printed)"
    return 0
  fi
  read -r -s -p "  Production System Admin access code: " PRODUCTION_SYSTEM_ADMIN_CODE
  printf "\n"
  if [ -z "${PRODUCTION_SYSTEM_ADMIN_CODE:-}" ]; then
    die "No access code entered — authentication blocked."
  fi
}

# ── Production login ───────────────────────────────────────────────────────────
prod_login() {
  local lookup_raw lookup_code lookup_body user_id
  lookup_raw=$(curl -s -w "\n__STATUS__%{http_code}" \
    --connect-timeout 10 --max-time 20 \
    -X POST \
    -H "Content-Type: application/json" \
    -d '{"unit_type":"national","role":"system_admin"}' \
    "https://$EXPECTED_PRODUCTION_BACKEND_DOMAIN/api/auth/lookup" 2>/dev/null)
  lookup_code=$(echo "$lookup_raw" | grep -o '__STATUS__[0-9]*' | grep -o '[0-9]*' || echo "000")
  lookup_body=$(echo "$lookup_raw" | sed 's/__STATUS__[0-9]*$//')

  case "$lookup_code" in
    200) ;;
    404) die "Production auth lookup: no system_admin found — bootstrap not complete." ;;
    *)   die "Production auth lookup failed (HTTP $lookup_code)." ;;
  esac

  user_id=$(echo "$lookup_body" | python3 -c "
import json,sys; print(json.load(sys.stdin).get('user_id','MISSING'))" 2>/dev/null || echo "MISSING")
  [ "$user_id" = "MISSING" ] || [ -z "$user_id" ] \
    && die "Production auth lookup: response missing user_id."

  printf '{"user_id":"%s","code":"%s"}' "$user_id" "$PRODUCTION_SYSTEM_ADMIN_CODE" \
    > "$LOGIN_PAYLOAD_FILE"

  local login_raw login_code
  login_raw=$(curl -s -w "\n__STATUS__%{http_code}" \
    --connect-timeout 10 --max-time 20 \
    -X POST \
    -H "Content-Type: application/json" \
    --cookie-jar "$COOKIE_JAR" \
    -d @"$LOGIN_PAYLOAD_FILE" \
    "https://$EXPECTED_PRODUCTION_BACKEND_DOMAIN/api/auth/login" 2>/dev/null)

  : > "$LOGIN_PAYLOAD_FILE"

  login_code=$(echo "$login_raw" | grep -o '__STATUS__[0-9]*' | grep -o '[0-9]*' || echo "000")
  case "$login_code" in
    200) ok "Production login: HTTP 200, session cookie stored" ;;
    401) die "Production login: invalid access code (HTTP 401)." ;;
    429) die "Production login: locked out (HTTP 429) — too many failed attempts." ;;
    *)   die "Production login: unexpected HTTP $login_code." ;;
  esac
}

# ── Session verification ───────────────────────────────────────────────────────
prod_verify_session() {
  local label="${1:-Auth}"
  local resp code body role is_national
  resp=$(curl -s -w "\n__STATUS__%{http_code}" \
    --connect-timeout 10 --max-time 20 \
    --cookie "$COOKIE_JAR" \
    "https://$EXPECTED_PRODUCTION_BACKEND_DOMAIN/api/auth/me" 2>/dev/null)
  code=$(echo "$resp" | grep -o '__STATUS__[0-9]*' | grep -o '[0-9]*' || echo "000")
  body=$(echo "$resp" | sed 's/__STATUS__[0-9]*$//')

  case "$code" in
    200)
      role=$(echo "$body" | python3 -c "
import json,sys; print(json.load(sys.stdin).get('session',{}).get('role','unknown'))" 2>/dev/null || echo "unknown")
      is_national=$(echo "$body" | python3 -c "
import json,sys; print(json.load(sys.stdin).get('session',{}).get('is_national',False))" 2>/dev/null || echo "False")
      if [ "$role" = "system_admin" ] && [ "$is_national" = "True" ]; then
        ok "$label /api/auth/me → role=system_admin is_national=True"
        return 0
      else
        die "$label /api/auth/me: role='$role' is_national='$is_national' — not system_admin national. Auth denied."
      fi
      ;;
    401) return 1 ;;
    *) die "$label /api/auth/me returned HTTP $code — production backend unreachable?" ;;
  esac
}

prod_reauth_if_needed() {
  local label="${1:-Post-deploy}"
  if prod_verify_session "$label (session check)"; then
    return 0
  fi
  info "$label: session expired — reauthenticating..."
  : > "$COOKIE_JAR"
  prod_login
  prod_verify_session "$label (reauth)"
}

# ── Authenticated production API call ──────────────────────────────────────────
prod_api_call() {
  local method="$1" path="$2" body="${3:-}"
  local url="https://$EXPECTED_PRODUCTION_BACKEND_DOMAIN$path"
  local raw
  if [ -n "$body" ]; then
    raw=$(curl -s -w "\n__STATUS__%{http_code}" \
      --connect-timeout 10 --max-time 20 \
      -X "$method" -H "Content-Type: application/json" \
      --cookie "$COOKIE_JAR" --cookie-jar "$COOKIE_JAR" \
      -d "$body" "$url" 2>/dev/null)
  else
    raw=$(curl -s -w "\n__STATUS__%{http_code}" \
      --connect-timeout 10 --max-time 20 \
      -X "$method" \
      --cookie "$COOKIE_JAR" --cookie-jar "$COOKIE_JAR" \
      "$url" 2>/dev/null)
  fi
  PROD_API_CODE=$(echo "$raw" | grep -o '__STATUS__[0-9]*' | grep -o '[0-9]*' || echo "000")
  PROD_API_BODY=$(echo "$raw" | sed 's/__STATUS__[0-9]*$//')
}

# ── CRUD smoke: subject-area-tags (self-cleaning) ──────────────────────────────
run_crud_smoke() {
  echo
  echo "  ── Subject-area-tags CRUD smoke (self-cleaning) ─────────────────────"

  prod_api_call GET "/api/subject-area-tags"
  [ "$PROD_API_CODE" = "200" ] \
    || die "/api/subject-area-tags GET → $PROD_API_CODE (expected 200) — HARD FAIL."
  echo "$PROD_API_BODY" | python3 -c "import json,sys; assert isinstance(json.load(sys.stdin),list)" 2>/dev/null \
    || die "Response is not a JSON array — HARD FAIL."
  ok "GET /api/subject-area-tags → 200 JSON array"

  local tag_name="Deployment Verification $(date -u '+%Y%m%dT%H%M%SZ')"
  prod_api_call POST "/api/subject-area-tags" \
    "{\"display_name\": \"$tag_name\", \"scope\": \"global\"}"
  [ "$PROD_API_CODE" = "201" ] \
    || die "POST /api/subject-area-tags → $PROD_API_CODE (expected 201) — HARD FAIL."
  local tag_id
  tag_id=$(echo "$PROD_API_BODY" | python3 -c "
import json,sys; print(json.load(sys.stdin).get('tag_id','MISSING'))" 2>/dev/null || echo "MISSING")
  [ "$tag_id" = "MISSING" ] || [ -z "$tag_id" ] \
    && die "POST response missing tag_id — HARD FAIL." || true
  ok "POST /api/subject-area-tags → 201, id=$tag_id"

  prod_api_call DELETE "/api/subject-area-tags/$tag_id"
  [ "$PROD_API_CODE" = "200" ] \
    || die "DELETE /api/subject-area-tags/$tag_id → $PROD_API_CODE — HARD FAIL."
  ok "DELETE /api/subject-area-tags/$tag_id → 200"

  prod_api_call GET "/api/subject-area-tags"
  [ "$PROD_API_CODE" = "200" ] || die "GET (after archive) → $PROD_API_CODE — HARD FAIL."
  local still
  still=$(echo "$PROD_API_BODY" | python3 -c "
import json,sys; print('yes' if any(t.get('tag_id')=='$tag_id' for t in json.load(sys.stdin)) else 'no')" 2>/dev/null || echo "yes")
  [ "$still" = "no" ] \
    && ok "Archived tag absent from active list — CRUD PASS" \
    || die "Archived tag $tag_id still in active list — HARD FAIL."
}

# ── FUNCTIONS_ONLY guard ───────────────────────────────────────────────────────
[[ "${DEPLOY_FUNCTIONS_ONLY:-0}" = "1" ]] && return 0 2>/dev/null || true

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN EXECUTION BEGINS HERE
# ═══════════════════════════════════════════════════════════════════════════════

echo
echo -e "  ${RED}████████████████████████████████████████████████████████████████████${NC}"
echo -e "  ${RED}██  AAFC TMS — PRODUCTION DEPLOYMENT GUARD (v1)                  ██${NC}"
echo -e "  ${RED}██  THIS WILL MIGRATE THE LIVE PRODUCTION DATABASE                ██${NC}"
echo -e "  ${RED}██  All gates: HARD FAIL · UUIDs enforced · Staging blocked       ██${NC}"
echo -e "  ${RED}████████████████████████████████████████████████████████████████████${NC}"
echo

# ── Init temp files and cleanup trap ──────────────────────────────────────────
COOKIE_JAR=$(mktemp)
chmod 600 "$COOKIE_JAR"
LOGIN_PAYLOAD_FILE=$(mktemp)
chmod 600 "$LOGIN_PAYLOAD_FILE"
trap cleanup EXIT INT TERM

# ══ CREDENTIAL ════════════════════════════════════════════════════════════════
echo "  [CRED] Production System Admin credential…"
acquire_credential
echo

# ══ STEP 1: Railway project state ════════════════════════════════════════════
echo "  [1/11] Fetching Railway project state…"
RAILWAY_JSON=$(railway status --json 2>&1)
echo "$RAILWAY_JSON" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null \
  && ok "Railway JSON fetched" \
  || die "Failed to parse Railway JSON. Run: railway login"

# ══ STEP 2: Project ID ═══════════════════════════════════════════════════════
echo
echo "  [2/11] Verifying project ID…"
ACTUAL_PROJECT_ID=$(echo "$RAILWAY_JSON" | python3 -c "
import json,sys; print(json.load(sys.stdin).get('id','MISSING'))" 2>/dev/null || echo "ERROR")
info "Expected: $EXPECTED_PROJECT_ID"
info "Actual:   $ACTUAL_PROJECT_ID"
[ "$ACTUAL_PROJECT_ID" = "$EXPECTED_PROJECT_ID" ] \
  && ok "Project ID matches" || die "Project ID mismatch."

# ══ STEP 3: Production environment ID ════════════════════════════════════════
echo
echo "  [3/11] Verifying production environment ID…"
ACTUAL_TARGET_ENV_ID=$(echo "$RAILWAY_JSON" | python3 -c "
import json,sys
data=json.load(sys.stdin)
for e in data.get('environments',{}).get('edges',[]):
    if e['node']['name']=='production': print(e['node']['id']); break
else: print('MISSING')" 2>/dev/null || echo "ERROR")
info "Expected: $EXPECTED_PRODUCTION_ENV_ID"
info "Actual:   $ACTUAL_TARGET_ENV_ID"
[ "$ACTUAL_TARGET_ENV_ID" = "$EXPECTED_PRODUCTION_ENV_ID" ] \
  && ok "Production env ID matches" || die "Production env ID mismatch."
[ "$ACTUAL_TARGET_ENV_ID" = "$STAGING_ENV_ID" ] \
  && die "CRITICAL: resolved env ID is staging — ABORT." \
  || ok "Target env is NOT staging — safe to proceed"

# ══ STEP 4: Service IDs ══════════════════════════════════════════════════════
echo
echo "  [4/11] Verifying service IDs…"
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

# ══ STEP 5: UUID read-only proof (production env) ════════════════════════════
echo
echo "  [5/11] UUID read-only resolution proof (production env)…"
_uuid_proof() {
  local label="$1" svc_id="$2"
  local json
  json=$(railway deployment list \
    --project "$EXPECTED_PROJECT_ID" \
    --service "$svc_id" \
    --environment "$ACTUAL_TARGET_ENV_ID" \
    --limit 1 --json 2>&1)
  if echo "$json" | python3 -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
    ok "$label UUID $svc_id accepted"
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

# ══ STEP 6: Production domains guard ════════════════════════════════════════
echo
echo "  [6/11] Verifying production domains are targeted (not staging)…"
PROD_DOMAINS=$(echo "$RAILWAY_JSON" | python3 -c "
import json,sys; data=json.load(sys.stdin)
for e in data.get('environments',{}).get('edges',[]):
    if e['node']['id']=='$EXPECTED_PRODUCTION_ENV_ID':
        for si in e['node'].get('serviceInstances',{}).get('edges',[]):
            for d in si['node'].get('domains',{}).get('serviceDomains',[]):
                print(d['domain'])" 2>/dev/null || echo "ERROR")
echo "  Production domains:"
echo "$PROD_DOMAINS" | while read -r d; do [ -n "$d" ] && echo "    $d"; done
echo "$PROD_DOMAINS" | grep -q "staging.up.railway.app" \
  && die "Staging domain found in production targets — ABORT." \
  || ok "No staging domains in production targets"
echo "$PROD_DOMAINS" | grep -qF "$EXPECTED_PRODUCTION_BACKEND_DOMAIN"  && ok "Backend  production domain" || fail "Backend  production domain NOT found"
echo "$PROD_DOMAINS" | grep -qF "$EXPECTED_PRODUCTION_FRONTEND_DOMAIN" && ok "Frontend production domain" || fail "Frontend production domain NOT found"
echo "$PROD_DOMAINS" | grep -qF "$EXPECTED_PRODUCTION_PW_DOMAIN"       && ok "PW       production domain" || fail "PW production domain NOT found"
[ "$FAIL_COUNT" -gt 0 ] && die "Domain verification failed."

# ══ STEP 7: Git state ════════════════════════════════════════════════════════
echo
echo "  [7/11] Git state…"
CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || echo "UNKNOWN")
[ "$CURRENT_BRANCH" = "$EXPECTED_BRANCH" ] \
  && ok "Branch: $CURRENT_BRANCH" || die "Branch '$CURRENT_BRANCH' ≠ '$EXPECTED_BRANCH'."
CURRENT_HEAD=$(git rev-parse --short HEAD 2>/dev/null || echo "UNKNOWN")
info "HEAD: $CURRENT_HEAD — $(git log -1 --format='%s')"
git merge-base --is-ancestor "$REQUIRED_ANCESTOR" HEAD 2>/dev/null \
  && ok "Fix commit $REQUIRED_ANCESTOR is ancestor of $CURRENT_HEAD" \
  || die "Fix commit $REQUIRED_ANCESTOR NOT in HEAD's history."
git diff-index --quiet HEAD -- 2>/dev/null && ok "Working tree clean" || die "Uncommitted changes."
UNPUSHED=$(git log "origin/${EXPECTED_BRANCH}..HEAD" --oneline 2>/dev/null || echo "ERROR")
[ -n "$UNPUSHED" ] && die "Unpushed commits — push to origin/$EXPECTED_BRANCH first."
ok "HEAD pushed to origin/$EXPECTED_BRANCH"

# ══ STEP 8: Security greps ═══════════════════════════════════════════════════
echo
echo "  [8/11] Security greps…"
_check_grep() {
  local label="$1" pattern="$2" path="$3"
  local c; c=$(grep -rcE "$pattern" "$path" 2>/dev/null | awk -F: '{s+=$2}END{print s+0}')
  [ "$c" -eq 0 ] && ok "$label" || { fail "$label ($c match(es))"; grep -rnE "$pattern" "$path"|head -3; }
}
_check_grep "No seeded codes"         "SYSADMIN2026|ADMIN703|ADMIN7WG|ADMINNATIONAL" "connected-frontend"
_check_grep "No localStorage"          "localStorage"                                  "connected-frontend"
_check_grep "No access-code hashes"   "code_hash|plain_code"                          "connected-frontend"
_check_grep "No JWT_SECRET/SECRET_KEY" "JWT_SECRET|SECRET_KEY"                         "connected-frontend"
_check_grep "No DB connection strings" "postgresql://|postgres://|sqlite:///"          "connected-frontend"
[ "$FAIL_COUNT" -gt 0 ] && die "Security grep failed — do not deploy."

# ══ STEP 9: Backend tests ════════════════════════════════════════════════════
echo
echo "  [9/11] Backend test suite…"
[ -d "backend" ] || die "backend/ not found."
pushd backend > /dev/null
source .venv/bin/activate 2>/dev/null || die ".venv not found."
TEST_OUT=$(python -m pytest tests/ -q --tb=no 2>&1)
LAST=$(echo "$TEST_OUT" | tail -1)
echo "$LAST" | grep -q "passed" && ! echo "$LAST" | grep -q "failed" \
  && ok "Tests: $LAST" || { fail "Tests: $LAST"; echo "$TEST_OUT"|tail -8; die "Test suite failed — do not deploy."; }
deactivate 2>/dev/null || true
popd > /dev/null

# ══ STEP 10: Alembic code head ═══════════════════════════════════════════════
echo
echo "  [10/11] Alembic code head…"
pushd backend > /dev/null
source .venv/bin/activate 2>/dev/null || true
ALEMBIC_CODE_HEAD=$(python -m alembic heads 2>/dev/null | grep -oE '[a-f0-9]{12}' | head -1 || echo "unknown")
info "Alembic code head: $ALEMBIC_CODE_HEAD"
[ "$ALEMBIC_CODE_HEAD" = "$REQUIRED_ALEMBIC_HEAD" ] \
  && ok "Code head is $REQUIRED_ALEMBIC_HEAD (v51)" \
  || die "Code head is $ALEMBIC_CODE_HEAD, expected $REQUIRED_ALEMBIC_HEAD — ABORT."
deactivate 2>/dev/null || true
popd > /dev/null

# ══ STEP 11: Login + session verification ════════════════════════════════════
echo
echo "  [11/11] Authenticating to production…"
prod_login
prod_verify_session "Step 11"

# ══ Preflight summary ═════════════════════════════════════════════════════════
echo
echo -e "  ${RED}════════════════════════════════════════════════════════════════════${NC}"
echo -e "  Preflight: ${GRN}PASS: $PASS_COUNT${NC}   ${RED}FAIL: $FAIL_COUNT${NC}"
echo -e "  ${RED}════════════════════════════════════════════════════════════════════${NC}"
[ "$FAIL_COUNT" -gt 0 ] && die "$FAIL_COUNT preflight check(s) failed."
echo

# ══ Pre-deployment state capture ══════════════════════════════════════════════
echo "  PRE-DEPLOYMENT STATE"
echo
_capture_and_report() {
  local svc_id="$1" label="$2"
  local state; state=$(_capture_state "$svc_id")
  local latest="${state%%|*}"
  local rest="${state#*|}"
  local lat_status="${rest%%|*}"
  rest="${rest#*|}"
  local active="${rest%%|*}"
  local active_created="${rest#*|}"
  printf "  %-12s LATEST=%-44s (%s)\n" "$label" "$latest" "$lat_status" >&2
  printf "  %-12s ACTIVE=%-44s (%s)\n" ""        "$active"  "$active_created" >&2
  echo "${latest}|${active}"
}

_BACKEND_PRE=$(_capture_and_report "$ACTUAL_BACKEND_SVC_ID"  "Backend:")
PRE_BACKEND_LATEST="${_BACKEND_PRE%%|*}";  PRE_BACKEND_ACTIVE="${_BACKEND_PRE#*|}"

_FRONTEND_PRE=$(_capture_and_report "$ACTUAL_FRONTEND_SVC_ID" "Frontend:")
PRE_FRONTEND_LATEST="${_FRONTEND_PRE%%|*}"; PRE_FRONTEND_ACTIVE="${_FRONTEND_PRE#*|}"

_PW_PRE=$(_capture_and_report "$ACTUAL_PW_SVC_ID" "PW:")
PRE_PW_LATEST="${_PW_PRE%%|*}";            PRE_PW_ACTIVE="${_PW_PRE#*|}"

echo
echo "  RESOLVED TARGETS"
echo
printf "  %-30s %s\n" "Project ID:"         "$ACTUAL_PROJECT_ID"
printf "  %-30s %s\n" "Production env ID:"  "$ACTUAL_TARGET_ENV_ID"
printf "  %-30s %s  (NOT TARGETED)\n" "Staging env ID:"    "$STAGING_ENV_ID"
echo
printf "  %-30s %s / UUID: %s\n" "Service 1:" "$EXPECTED_BACKEND_SVC_NAME"  "$ACTUAL_BACKEND_SVC_ID"
printf "  %-30s %s / UUID: %s\n" "Service 2:" "$EXPECTED_FRONTEND_SVC_NAME" "$ACTUAL_FRONTEND_SVC_ID"
printf "  %-30s %s / UUID: %s\n" "Service 3:" "$EXPECTED_PW_SVC_NAME"       "$ACTUAL_PW_SVC_ID"
echo
printf "  %-30s %s\n" "Branch:" "$CURRENT_BRANCH"
printf "  %-30s %s\n" "HEAD:"   "$CURRENT_HEAD — $(git log -1 --format='%s')"
echo

# ══ Authorization gate ════════════════════════════════════════════════════════
REQUIRED_PHRASE="DEPLOY TO PRODUCTION ${CURRENT_HEAD}"
echo -e "  ${RED}══ PRODUCTION AUTHORIZATION REQUIRED ══${NC}"
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
echo -e "  ${GRN}Authorization accepted.${NC} Deploying $CURRENT_HEAD to production."
echo

# ══ DRY RUN ═══════════════════════════════════════════════════════════════════
if [ "${DRY_RUN:-0}" = "1" ]; then
  echo -e "  ${YLW}DRY RUN — no deployments, no migrations, no production writes:${NC}"
  echo
  echo "  [1/3] Backend  → --environment $ACTUAL_TARGET_ENV_ID (production)"
  echo "    Gates: /api/health/ready HTTP 200 → new deploy ID → DB revision $REQUIRED_ALEMBIC_HEAD → CRUD smoke"
  echo "  [2/3] Frontend → --environment $ACTUAL_TARGET_ENV_ID (production)"
  echo "    Gates: / HTTP 200 → new deploy ID → build fingerprint meta tag"
  echo "  [3/3] PW       → --environment $ACTUAL_TARGET_ENV_ID (production)"
  echo "    Gates: / HTTP 200 → new deploy ID → React markers"
  echo
  echo "  DRY RUN complete. Exit 0. No deployment. No production writes."
  exit 0
fi

# ══════════════════════════════════════════════════════════════════════════════
# DEPLOYMENT 1/3 — BACKEND
# ══════════════════════════════════════════════════════════════════════════════
echo "────────────────────────────────────────────────────────────────────"
echo "  [Deploy 1/3] $EXPECTED_BACKEND_SVC_NAME  → PRODUCTION"
info "  Service UUID: $ACTUAL_BACKEND_SVC_ID"
info "  PRE_LATEST:   $PRE_BACKEND_LATEST"
info "  PRE_ACTIVE:   $PRE_BACKEND_ACTIVE"
echo

railway up ./backend --path-as-root \
  --project "$EXPECTED_PROJECT_ID" \
  --service "$ACTUAL_BACKEND_SVC_ID" \
  --environment "$ACTUAL_TARGET_ENV_ID" \
  --detach 2>&1 || die "Backend: railway up command failed — HARD FAIL."

echo
echo "  ── Backend gate 1/4: new deployment ID ──────────────────────────────"
wait_for_new_deploy \
  "$ACTUAL_BACKEND_SVC_ID" "$PRE_BACKEND_LATEST" "$PRE_BACKEND_ACTIVE" \
  "$BACKEND_GATE_TIMEOUT" "Backend"
BACKEND_NEW_DEPLOY_ID="$VERIFIED_NEW_DEPLOY_ID"
info "Backend: new=$BACKEND_NEW_DEPLOY_ID"

echo
echo "  ── Backend gate 2/4: health/ready (new container) ───────────────────"
poll_health \
  "https://$EXPECTED_PRODUCTION_BACKEND_DOMAIN/api/health/ready" \
  "$BACKEND_GATE_TIMEOUT" "Backend /api/health/ready"

READY_JSON=$(curl -s --connect-timeout 10 --max-time 15 \
  "https://$EXPECTED_PRODUCTION_BACKEND_DOMAIN/api/health/ready" 2>/dev/null || echo '{}')
echo "$READY_JSON" | python3 -c "
import json,sys; d=json.load(sys.stdin); assert d.get('status')=='ready'" 2>/dev/null \
  && ok "Readiness: status=ready" \
  || die "Backend /api/health/ready did not return status:ready — HARD FAIL."

echo
echo "  ── Backend gate 3/4: database revision ──────────────────────────────"
prod_reauth_if_needed "Backend gate 3"
prod_api_call GET "/api/system/migrations"
[ "$PROD_API_CODE" = "200" ] \
  || die "/api/system/migrations → $PROD_API_CODE — HARD FAIL."
DB_REVISION=$(echo "$PROD_API_BODY" | python3 -c "
import json,sys; print(json.load(sys.stdin).get('revision','MISSING'))" 2>/dev/null || echo "ERROR")
IS_SINGLE=$(echo "$PROD_API_BODY" | python3 -c "
import json,sys; print(json.load(sys.stdin).get('is_single_head',False))" 2>/dev/null || echo "False")
info "is_single_head: $IS_SINGLE  revision: $DB_REVISION"
[ "$IS_SINGLE" = "True" ] || die "Multiple Alembic heads — HARD FAIL."
[ "$DB_REVISION" = "$REQUIRED_ALEMBIC_HEAD" ] \
  && ok "DB revision: $DB_REVISION (v51) — exact match" \
  || die "DB revision '$DB_REVISION' ≠ '$REQUIRED_ALEMBIC_HEAD' — HARD FAIL."

echo
echo "  ── Backend gate 4/4: CRUD smoke ─────────────────────────────────────"
prod_reauth_if_needed "Backend gate 4"
run_crud_smoke
ok "Backend gate PASSED."

# ══════════════════════════════════════════════════════════════════════════════
# DEPLOYMENT 2/3 — MAIN TMS FRONTEND
# ══════════════════════════════════════════════════════════════════════════════
echo
echo "────────────────────────────────────────────────────────────────────"
echo "  [Deploy 2/3] $EXPECTED_FRONTEND_SVC_NAME  → PRODUCTION"
info "  Service UUID: $ACTUAL_FRONTEND_SVC_ID"
info "  PRE_LATEST:   $PRE_FRONTEND_LATEST"
echo

railway up ./connected-frontend --path-as-root \
  --project "$EXPECTED_PROJECT_ID" \
  --service "$ACTUAL_FRONTEND_SVC_ID" \
  --environment "$ACTUAL_TARGET_ENV_ID" \
  --detach 2>&1 || die "Frontend: railway up command failed — HARD FAIL."

echo
echo "  ── Frontend gate 1/3: new deployment ID ─────────────────────────────"
wait_for_new_deploy \
  "$ACTUAL_FRONTEND_SVC_ID" "$PRE_FRONTEND_LATEST" "$PRE_FRONTEND_ACTIVE" \
  "$FRONTEND_GATE_TIMEOUT" "Frontend"
FRONTEND_NEW_DEPLOY_ID="$VERIFIED_NEW_DEPLOY_ID"
info "Frontend: new=$FRONTEND_NEW_DEPLOY_ID"

echo
echo "  ── Frontend gate 2/3: HTTP 200 (new container) ──────────────────────"
poll_health "https://$EXPECTED_PRODUCTION_FRONTEND_DOMAIN/" "$FRONTEND_GATE_TIMEOUT" "Frontend /"

echo
echo "  ── Frontend gate 3/3: build fingerprint ─────────────────────────────"
FRONTEND_BUILD=""
_fp_elapsed=0
while [ "$_fp_elapsed" -lt 180 ]; do
  _fb=$(curl -s --connect-timeout 10 --max-time 30 \
    "https://$EXPECTED_PRODUCTION_FRONTEND_DOMAIN/" 2>/dev/null \
    | grep -o 'name="app-build" content="[^"]*"' | head -1 2>/dev/null || true)
  if [ -n "$_fb" ] && ! echo "$_fb" | grep -q '__APP_BUILD__'; then
    FRONTEND_BUILD="$_fb"
    break
  fi
  info "Frontend fingerprint not ready yet (${_fp_elapsed}s) — retrying in 15s…"
  sleep 15
  _fp_elapsed=$((_fp_elapsed + 15))
done
[ -z "$FRONTEND_BUILD" ] && die 'Build fingerprint meta NOT found after 180s — HARD FAIL.'
ok "Frontend build fingerprint: $FRONTEND_BUILD"
ok "Frontend gate PASSED."

# ══════════════════════════════════════════════════════════════════════════════
# DEPLOYMENT 3/3 — PLANNING WORKSPACE
# ══════════════════════════════════════════════════════════════════════════════
echo
echo "────────────────────────────────────────────────────────────────────"
echo "  [Deploy 3/3] $EXPECTED_PW_SVC_NAME  → PRODUCTION"
info "  Service UUID: $ACTUAL_PW_SVC_ID"
info "  PRE_LATEST:   $PRE_PW_LATEST"
echo

railway up ./frontend --path-as-root \
  --project "$EXPECTED_PROJECT_ID" \
  --service "$ACTUAL_PW_SVC_ID" \
  --environment "$ACTUAL_TARGET_ENV_ID" \
  --detach 2>&1 || die "PW: railway up command failed — HARD FAIL."

echo
echo "  ── PW gate 1/3: new deployment ID ───────────────────────────────────"
wait_for_new_deploy \
  "$ACTUAL_PW_SVC_ID" "$PRE_PW_LATEST" "$PRE_PW_ACTIVE" \
  "$PW_GATE_TIMEOUT" "PW"
PW_NEW_DEPLOY_ID="$VERIFIED_NEW_DEPLOY_ID"
info "PW: new=$PW_NEW_DEPLOY_ID"

echo
echo "  ── PW gate 2/3: HTTP 200 (new container) ────────────────────────────"
poll_health "https://$EXPECTED_PRODUCTION_PW_DOMAIN/" "$PW_GATE_TIMEOUT" "PW /"

echo
echo "  ── PW gate 3/3: React markers ───────────────────────────────────────"
_pw_ready=0; _pw_elapsed=0
while [ "$_pw_elapsed" -lt 180 ]; do
  if curl -s --connect-timeout 10 --max-time 30 \
    "https://$EXPECTED_PRODUCTION_PW_DOMAIN/" 2>/dev/null \
    | grep -qiE 'id="root"|type="module"|/assets/'; then
    _pw_ready=1; break
  fi
  info "PW not ready yet (${_pw_elapsed}s) — retrying in 15s…"
  sleep 15
  _pw_elapsed=$((_pw_elapsed + 15))
done
[ "$_pw_ready" -eq 0 ] && die "PW HTML lacks React app markers after 180s — HARD FAIL."
ok "PW HTML contains React app markers"
PW_BUILD=$(curl -s --connect-timeout 15 --max-time 60 \
  "https://$EXPECTED_PRODUCTION_PW_DOMAIN/" 2>/dev/null \
  | grep -o 'name="app-build" content="[^"]*"' | head -1 || echo "no fingerprint")
ok "PW build fingerprint: $PW_BUILD"
ok "PW gate PASSED."

# ══ Final audit ══════════════════════════════════════════════════════════════
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
    die "$label still serving pre-deploy ID — new may not be active."
  else
    info "$label active deployment: $current_active"
  fi
}
_final_check "$ACTUAL_BACKEND_SVC_ID"  "$PRE_BACKEND_ACTIVE"  "$BACKEND_NEW_DEPLOY_ID"  "Backend:"
_final_check "$ACTUAL_FRONTEND_SVC_ID" "$PRE_FRONTEND_ACTIVE" "$FRONTEND_NEW_DEPLOY_ID" "Frontend:"
_final_check "$ACTUAL_PW_SVC_ID"       "$PRE_PW_ACTIVE"       "$PW_NEW_DEPLOY_ID"       "PW:"

echo
echo -e "  ${GRN}════════════════════════════════════════════════════════════════════${NC}"
echo -e "  ${GRN}All three production deployments completed. All gates passed.${NC}"
echo "  Commit deployed: $CURRENT_HEAD"
echo
printf "  %-12s pre_latest=%-44s  new=%s\n" "Backend:"  "$PRE_BACKEND_LATEST"  "$BACKEND_NEW_DEPLOY_ID"
printf "  %-12s pre_latest=%-44s  new=%s\n" "Frontend:" "$PRE_FRONTEND_LATEST" "$FRONTEND_NEW_DEPLOY_ID"
printf "  %-12s pre_latest=%-44s  new=%s\n" "PW:"       "$PRE_PW_LATEST"       "$PW_NEW_DEPLOY_ID"
echo
echo "  Next: run the D7 smoke test checklist (docs/beta/D7_smoke_test_checklist.md)"
echo "        Record deployment IDs in docs/release/final_release_program_2026.md"
echo -e "  ${GRN}════════════════════════════════════════════════════════════════════${NC}"
