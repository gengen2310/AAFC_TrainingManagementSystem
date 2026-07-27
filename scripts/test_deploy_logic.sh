#!/usr/bin/env bash
# test_deploy_logic.sh — Unit tests for deployment tracking logic in deploy-staging.sh
#
# Scenarios:
#   A. Active == Latest (clean state)        — correctly discovers next new deployment
#   B. Latest FAILED, active older           — ignores existing failed; waits for truly new ID
#   C. New deployment reaches SUCCESS        — sets VERIFIED_NEW_DEPLOY_ID; returns 0
#   D. New deployment reaches FAILED         — calls rollback check; aborts
#   E. Concurrent unexpected deployment      — aborts when another ID appears
#   F. No new deployment within timeout      — aborts on timeout
#   G. _capture_state parses LATEST != ACTIVE correctly
#   T1.  staging_acquire_credential — CI env var accepted
#   T2.  staging_acquire_credential — env var too short — die
#   T3.  staging_login — /api/auth/lookup 404 — die (bootstrap message)
#   T4.  staging_login — login 401 — die (invalid access code)
#   T5.  staging_login — login 429 — die (locked out)
#   T6.  staging_login — success — cookie stored; returns 0
#   T7.  staging_verify_session — 200 system_admin is_national=True — return 0
#   T8.  staging_verify_session — 200 wrong role — die
#   T9.  staging_verify_session — 401 — return 1 (no die)
#   T10. staging_reauth_if_needed — session still valid (200) — return 0
#   T11. staging_reauth_if_needed — session expired; reauth succeeds
#   T12. staging_login — LOGIN_PAYLOAD_FILE zeroed after use
#   T13. cleanup — files deleted; STAGING_SYSTEM_ADMIN_CODE unset
#
# Design notes:
# — _railway_deploy_list uses a file-based counter (DEPLOY_TEST_COUNTER_FILE) so
#   the call index survives across $() subshells.  Each $() creates a forked
#   subshell; in-memory variable changes inside $() are invisible to the parent.
#   Writing to a temp file is the standard fix.
# — curl() is similarly mocked with _CURL_CTR_FILE + MOCK_CURL_RESPONSES array.
# — die() is overridden to write the message to a file then exit 42. Exit 42 is
#   the sentinel that tells a test "die was called".  Each test subshell (...)
#   runs at most one scenario; when it exits 42 the parent checks the message.
# — POLL_INTERVAL=0 everywhere except Scenario F (which needs POLL_INTERVAL=1
#   with timeout=1 so the while-loop terminates after one iteration).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Load function definitions only (no main execution) ────────────────────────
DEPLOY_FUNCTIONS_ONLY=1 source "$SCRIPT_DIR/deploy-staging.sh"

# ── Shared test infrastructure files ─────────────────────────────────────────
_CTR_FILE=$(mktemp)      # call counter for _railway_deploy_list
_MSG_FILE=$(mktemp)      # message from die()
_CURL_CTR_FILE=$(mktemp) # call counter for curl mock
trap 'rm -f "$_CTR_FILE" "$_MSG_FILE" "$_CURL_CTR_FILE"' EXIT

# ── Override die() ────────────────────────────────────────────────────────────
# Writes the message to the shared file and exits the current subshell with 42.
die() {
  printf '%s' "$1" > "$_MSG_FILE"
  exit 42
}

# ── Override _railway_deploy_list (inherits from sourced script; we replace it) ──
# Uses the file-based counter so each $() call gets the next mock JSON entry.
# MOCK_DEPLOY_CALLS must be set as an array in the calling scope.
DEPLOY_TEST_MODE=1
DEPLOY_TEST_COUNTER_FILE="$_CTR_FILE"
export DEPLOY_TEST_MODE DEPLOY_TEST_COUNTER_FILE

# ── Mock curl function ────────────────────────────────────────────────────────
# Uses _CURL_CTR_FILE for cross-subshell call index.
# Reads responses from MOCK_CURL_RESPONSES[].
# Handles --cookie-jar by writing a fake aafc_session cookie to the jar file.
# Default when array exhausted: empty body + __STATUS__200.
MOCK_CURL_RESPONSES=()
curl() {
  local cf="${_CURL_CTR_FILE:-}"
  local idx=0
  [ -n "$cf" ] && [ -f "$cf" ] && idx=$(cat "$cf" 2>/dev/null || echo 0)
  [ -n "$cf" ] && echo $(( idx + 1 )) > "$cf"
  local prev="" jar="" arg
  for arg in "$@"; do
    [ "$prev" = "--cookie-jar" ] && jar="$arg"
    prev="$arg"
  done
  if [ -n "$jar" ] && [ -f "$jar" ]; then
    printf 'staging.up.railway.app\tFALSE\t/\tFALSE\t0\taafc_session\tfake-jwt\n' > "$jar"
  fi
  local resp=""
  resp="${MOCK_CURL_RESPONSES[$idx]:-}"
  [ -z "$resp" ] && resp=$'\n__STATUS__200'
  printf '%s\n' "$resp"
}

# ── Silence info/ok/fail noise ────────────────────────────────────────────────
info() { :; }
ok()   { :; }
fail() { :; }
PASS_COUNT=0
FAIL_COUNT=0

# ── Required globals ──────────────────────────────────────────────────────────
EXPECTED_PROJECT_ID="f5d9524f-8a57-44ff-86b7-ab66aec00e73"
ACTUAL_STAGING_ENV_ID="77a45568-5c16-46c2-9065-d5d339208b0e"
POLL_INTERVAL=0

# ── Helpers ───────────────────────────────────────────────────────────────────
TESTS_RUN=0; TESTS_PASSED=0; TESTS_FAILED=0

_pass() { echo -e "  \033[0;32m[PASS]\033[0m $1"; TESTS_PASSED=$((TESTS_PASSED+1)); }
_fail() { echo -e "  \033[0;31m[FAIL]\033[0m $1"; TESTS_FAILED=$((TESTS_FAILED+1)); }

_reset() {
  echo 0 > "$_CTR_FILE"
  : > "$_MSG_FILE"
}

_reset_auth() {
  echo 0 > "$_CURL_CTR_FILE"
  : > "$_MSG_FILE"
}

_die_msg() { cat "$_MSG_FILE" 2>/dev/null || true; }

# Compact single-deployment JSON
_J() { printf '[{"id":"%s","status":"%s","createdAt":"2026-07-22T%s"}]' "$1" "$2" "${3:-10:00:00Z}"; }
# Two-deployment JSON (latest first)
_J2() { printf '[{"id":"%s","status":"%s","createdAt":"2026-07-22T11:00:00Z"},{"id":"%s","status":"%s","createdAt":"2026-07-22T09:00:00Z"}]' "$1" "$2" "$3" "$4"; }

# ════════════════════════════════════════════════════════════════════════════════
# Scenario A: active == latest (clean state)
# Pre-state: latest == active == OLD-001 SUCCESS.
# Call sequence inside wait_for_new_deploy:
#   [0] limit=1, phase-1:  OLD-001 SUCCESS  → same as pre_latest, keep waiting
#   [1] limit=1, phase-1:  NEW-001 BUILDING → new ID discovered (new_deploy_id=NEW-001)
#   [2] limit=1, phase-2:  NEW-001 BUILDING → concurrent check OK
#   [3] limit=5, phase-2:  NEW-001 BUILDING → status BUILDING → wait
#   [4] limit=1, phase-2:  NEW-001 SUCCESS  → concurrent check OK
#   [5] limit=5, phase-2:  NEW-001 SUCCESS  → status SUCCESS → return 0
# ════════════════════════════════════════════════════════════════════════════════
echo
echo "══ A: active == latest (clean state) — discover next new deployment ════"
_reset
(
  MOCK_DEPLOY_CALLS=(
    "$(_J "OLD-001" "SUCCESS"  "10:00:00Z")"   # [0] phase-1: still pre_latest
    "$(_J "NEW-001" "BUILDING" "11:00:00Z")"   # [1] phase-1: new ID appears
    "$(_J "NEW-001" "BUILDING" "11:00:00Z")"   # [2] phase-2 concurrent check (limit=1)
    "$(_J "NEW-001" "BUILDING" "11:00:00Z")"   # [3] phase-2 wide status (limit=5)
    "$(_J "NEW-001" "SUCCESS"  "11:00:00Z")"   # [4] phase-2 concurrent check (limit=1)
    "$(_J "NEW-001" "SUCCESS"  "11:00:00Z")"   # [5] phase-2 wide status (limit=5) → done
  )
  VERIFIED_NEW_DEPLOY_ID="unknown"
  wait_for_new_deploy "SVC-A" "OLD-001" "OLD-001" 300 "ScenA"
  [ "$VERIFIED_NEW_DEPLOY_ID" = "NEW-001" ] && exit 0 || { echo "  VERIFIED=$VERIFIED_NEW_DEPLOY_ID"; exit 1; }
)
rc=$?
[ "$rc" -eq 0 ] && _pass "A: active==latest; NEW-001 discovered and confirmed SUCCESS" \
                || _fail "A: exit=$rc (expected 0); msg=$(_die_msg)"
TESTS_RUN=$((TESTS_RUN+1))

# ════════════════════════════════════════════════════════════════════════════════
# Scenario B: latest is FAILED, active is an older SUCCESS
# PRE_LATEST = FAILED-X, PRE_ACTIVE = SUCCESS-OLD.
# Phase-1 must wait for an ID different from FAILED-X (the pre_latest).
# It must NOT fire immediately on seeing FAILED-X again.
# Call sequence:
#   [0] limit=1: FAILED-X FAILED     → same as pre_latest, keep waiting
#   [1] limit=1: NEW-002 BUILDING    → new ID (different from FAILED-X) discovered
#   [2] limit=1: NEW-002 BUILDING    → concurrent check OK
#   [3] limit=5: NEW-002 BUILDING    → status BUILDING → wait
#   [4] limit=1: NEW-002 SUCCESS     → concurrent check OK
#   [5] limit=5: NEW-002 SUCCESS     → status SUCCESS → return 0
# ════════════════════════════════════════════════════════════════════════════════
echo
echo "══ B: latest=FAILED, active older — wait for truly new ID ═════════════"
_reset
(
  MOCK_DEPLOY_CALLS=(
    "$(_J "FAILED-X" "FAILED"   "09:00:00Z")"  # [0] pre_latest still returned
    "$(_J "NEW-002"  "BUILDING" "11:00:00Z")"  # [1] new ID appears
    "$(_J "NEW-002"  "BUILDING" "11:00:00Z")"  # [2] concurrent check
    "$(_J "NEW-002"  "BUILDING" "11:00:00Z")"  # [3] wide status
    "$(_J "NEW-002"  "SUCCESS"  "11:00:00Z")"  # [4] concurrent check
    "$(_J "NEW-002"  "SUCCESS"  "11:00:00Z")"  # [5] wide status → done
  )
  VERIFIED_NEW_DEPLOY_ID="unknown"
  # PRE_LATEST=FAILED-X, PRE_ACTIVE=SUCCESS-OLD
  wait_for_new_deploy "SVC-B" "FAILED-X" "SUCCESS-OLD" 300 "ScenB"
  [ "$VERIFIED_NEW_DEPLOY_ID" = "NEW-002" ] && exit 0 || { echo "  VERIFIED=$VERIFIED_NEW_DEPLOY_ID"; exit 1; }
)
rc=$?
[ "$rc" -eq 0 ] && _pass "B: pre-existing FAILED ignored; NEW-002 found and confirmed" \
                || _fail "B: exit=$rc (expected 0); msg=$(_die_msg)"
TESTS_RUN=$((TESTS_RUN+1))

# ════════════════════════════════════════════════════════════════════════════════
# Scenario C: new deployment reaches SUCCESS
# Verifies VERIFIED_NEW_DEPLOY_ID is set and function returns 0.
# Call sequence:
#   [0] limit=1: NEW-003 DEPLOYING   → different from OLD-003 → discovered
#   [1] limit=1: NEW-003 DEPLOYING   → concurrent check OK
#   [2] limit=5: NEW-003 DEPLOYING   → status DEPLOYING → wait
#   [3] limit=1: NEW-003 SUCCESS     → concurrent check OK
#   [4] limit=5: NEW-003 SUCCESS     → status SUCCESS → return 0
# ════════════════════════════════════════════════════════════════════════════════
echo
echo "══ C: new deployment → SUCCESS — VERIFIED_NEW_DEPLOY_ID set ════════════"
_reset
(
  MOCK_DEPLOY_CALLS=(
    "$(_J "NEW-003" "DEPLOYING" "11:00:00Z")"  # [0] phase-1: discovers NEW-003
    "$(_J "NEW-003" "DEPLOYING" "11:00:00Z")"  # [1] concurrent check
    "$(_J "NEW-003" "DEPLOYING" "11:00:00Z")"  # [2] wide status → DEPLOYING
    "$(_J "NEW-003" "SUCCESS"   "11:00:00Z")"  # [3] concurrent check
    "$(_J "NEW-003" "SUCCESS"   "11:00:00Z")"  # [4] wide status → SUCCESS
  )
  VERIFIED_NEW_DEPLOY_ID="unknown"
  wait_for_new_deploy "SVC-C" "OLD-003" "OLD-003" 300 "ScenC"
  [ "$VERIFIED_NEW_DEPLOY_ID" = "NEW-003" ] && exit 0 || exit 1
)
rc=$?
[ "$rc" -eq 0 ] && _pass "C: SUCCESS reached; VERIFIED_NEW_DEPLOY_ID=NEW-003; exit 0" \
                || _fail "C: exit=$rc; msg=$(_die_msg)"
TESTS_RUN=$((TESTS_RUN+1))

# ════════════════════════════════════════════════════════════════════════════════
# Scenario D: new deployment reaches FAILED
# Must call _check_rollback (which reads state via _railway_deploy_list) and
# then abort via die().  The rollback check should see OLD-004 as still active.
# Call sequence:
#   [0] limit=1:  NEW-004 FAILED     → phase-1 discovers NEW-004
#   [1] limit=1:  NEW-004 FAILED     → concurrent check OK
#   [2] limit=5:  NEW-004 FAILED     → status FAILED → abort path
#   [3] limit=20: [NEW-004 FAILED, OLD-004 SUCCESS]  → _check_rollback rollback query
# Then die("...FAILED...") → exit 42
# ════════════════════════════════════════════════════════════════════════════════
echo
echo "══ D: new deployment → FAILED — rollback check runs; abort ════════════"
_reset
(
  MOCK_DEPLOY_CALLS=(
    "$(_J "NEW-004" "FAILED" "11:00:00Z")"                      # [0] phase-1
    "$(_J "NEW-004" "FAILED" "11:00:00Z")"                      # [1] concurrent check
    "$(_J "NEW-004" "FAILED" "11:00:00Z")"                      # [2] wide status → FAILED
    "$(_J2 "NEW-004" "FAILED" "OLD-004" "SUCCESS")"             # [3] rollback check (limit=20)
  )
  VERIFIED_NEW_DEPLOY_ID="unknown"
  wait_for_new_deploy "SVC-D" "OLD-004" "OLD-004" 300 "ScenD"
  exit 1  # should not reach here
)
rc=$?
msg=$(_die_msg)
if [ "$rc" -eq 42 ] && echo "$msg" | grep -qiE "FAILED|HARD FAIL"; then
  _pass "D: FAILED deployment → die() called with FAILED message; rollback check ran"
elif [ "$rc" -eq 42 ]; then
  _fail "D: die() called but message doesn't mention FAILED: '$msg'"
else
  _fail "D: exit=$rc (expected 42); msg='$msg'"
fi
TESTS_RUN=$((TESTS_RUN+1))

# ════════════════════════════════════════════════════════════════════════════════
# Scenario E: concurrent unexpected deployment detected
# After NEW-005 is discovered in phase-1, the next limit=1 poll in phase-2
# returns a different ID (CONCURRENT-005).  This must abort immediately.
# Call sequence:
#   [0] limit=1: NEW-005 BUILDING     → phase-1 discovers NEW-005
#   [1] limit=1: CONCURRENT-005 BUILD → phase-2 concurrent check: ID ≠ NEW-005 → die()
# (limit=5 wide query is never reached because die() fires first)
# ════════════════════════════════════════════════════════════════════════════════
echo
echo "══ E: concurrent deployment detected — abort immediately ════════════════"
_reset
(
  MOCK_DEPLOY_CALLS=(
    "$(_J "NEW-005"        "BUILDING" "11:00:00Z")"   # [0] phase-1: discovers NEW-005
    "$(_J "CONCURRENT-005" "BUILDING" "11:30:00Z")"   # [1] phase-2 concurrent check → abort
  )
  VERIFIED_NEW_DEPLOY_ID="unknown"
  wait_for_new_deploy "SVC-E" "OLD-005" "OLD-005" 300 "ScenE"
  exit 1  # should not reach here
)
rc=$?
msg=$(_die_msg)
if [ "$rc" -eq 42 ] && echo "$msg" | grep -qi "concurrent"; then
  _pass "E: concurrent deployment detected; die() fired with 'concurrent' in message"
elif [ "$rc" -eq 42 ]; then
  _fail "E: die() called but no 'concurrent' in message: '$msg'"
else
  _fail "E: exit=$rc (expected 42); msg='$msg'"
fi
TESTS_RUN=$((TESTS_RUN+1))

# ════════════════════════════════════════════════════════════════════════════════
# Scenario F: no new deployment appears — timeout
# Phase-1 never sees a new ID.  With POLL_INTERVAL=1 and timeout=1, the loop
# runs once (elapsed=0 < 1), calls sleep 1, elapsed becomes 1, then 1 < 1 is
# false → loop exits → die("no new deployment appeared within...")
# Call sequence:
#   [0] limit=1: OLD-006 SUCCESS   → same as pre_latest, still waiting
# Then sleep 1, elapsed=1 ≥ timeout=1 → exit loop → die()
# ════════════════════════════════════════════════════════════════════════════════
echo
echo "══ F: no new deployment within timeout — abort ══════════════════════════"
_reset
(
  MOCK_DEPLOY_CALLS=(
    "$(_J "OLD-006" "SUCCESS" "09:00:00Z")"   # [0] always the same pre_latest
    "$(_J "OLD-006" "SUCCESS" "09:00:00Z")"   # [1] safety extra
  )
  VERIFIED_NEW_DEPLOY_ID="unknown"
  POLL_INTERVAL=1
  wait_for_new_deploy "SVC-F" "OLD-006" "OLD-006" 1 "ScenF"
  exit 1  # should not reach here
)
rc=$?
msg=$(_die_msg)
if [ "$rc" -eq 42 ] && echo "$msg" | grep -qiE "appeared|timeout|HARD FAIL"; then
  _pass "F: timeout abort triggered; die() called with timeout message"
elif [ "$rc" -eq 42 ]; then
  _fail "F: die() called but message unexpected: '$msg'"
else
  _fail "F: exit=$rc (expected 42); msg='$msg'"
fi
TESTS_RUN=$((TESTS_RUN+1))

# ════════════════════════════════════════════════════════════════════════════════
# Scenario G: _capture_state — LATEST and ACTIVE parsed correctly
# Input: FAILED-X is newest (latest), OLD-G is older SUCCESS (active/serving).
# Expects: latest=FAILED-X, active=OLD-G
# ════════════════════════════════════════════════════════════════════════════════
echo
echo "══ G: _capture_state — LATEST and ACTIVE correctly distinguished ════════"
_reset
(
  MOCK_DEPLOY_CALLS=(
    "$(_J2 "FAILED-X" "FAILED" "OLD-G" "SUCCESS")"  # limit=20 returns both
  )
  result=$(_capture_state "SOME-SVC")
  latest="${result%%|*}"
  rest="${result#*|}"
  lat_status="${rest%%|*}"
  rest="${rest#*|}"
  active="${rest%%|*}"

  ok_=0
  [ "$latest"     = "FAILED-X" ] && ok_=$((ok_+1)) || echo "    FAIL: latest='$latest' (expected FAILED-X)"
  [ "$lat_status" = "FAILED"   ] && ok_=$((ok_+1)) || echo "    FAIL: lat_status='$lat_status' (expected FAILED)"
  [ "$active"     = "OLD-G"    ] && ok_=$((ok_+1)) || echo "    FAIL: active='$active' (expected OLD-G)"
  [ "$ok_" -eq 3 ] && exit 0 || exit 1
)
rc=$?
[ "$rc" -eq 0 ] && _pass "G: _capture_state: latest=FAILED-X(FAILED), active=OLD-G(SUCCESS)" \
                || _fail "G: _capture_state returned unexpected values"
TESTS_RUN=$((TESTS_RUN+1))

# ═══════════════════════════════════════════════════════════════════════════════
# AUTH TESTS T1–T13
# These tests mock the curl binary. staging_acquire_credential, staging_login,
# staging_verify_session, staging_reauth_if_needed, and cleanup are tested
# with controlled responses from MOCK_CURL_RESPONSES[].
# Each test uses _reset_auth (resets curl counter + die message file) and sets
# up its own COOKIE_JAR / LOGIN_PAYLOAD_FILE temp files in the parent shell
# so file contents are visible after the subshell exits.
# ═══════════════════════════════════════════════════════════════════════════════

# ── T1: staging_acquire_credential — CI env var accepted ──────────────────────
# STAGING_SYSTEM_ADMIN_CODE is long enough → returns 0 (no prompt, no die)
echo
echo "══ T1: staging_acquire_credential — CI env var accepted ════════════════"
_reset_auth
(
  STAGING_SYSTEM_ADMIN_CODE="myvalidcode99"
  staging_acquire_credential
)
rc=$?
[ "$rc" -eq 0 ] && _pass "T1: CI env var (≥6 chars) accepted; returns 0" \
                || _fail "T1: exit=$rc (expected 0); msg=$(_die_msg)"
TESTS_RUN=$((TESTS_RUN+1))

# ── T2: staging_acquire_credential — env var too short — die ──────────────────
# STAGING_SYSTEM_ADMIN_CODE shorter than 6 chars → die("too short")
echo
echo "══ T2: staging_acquire_credential — too-short env var — die ════════════"
_reset_auth
(
  STAGING_SYSTEM_ADMIN_CODE="abc"
  staging_acquire_credential
  exit 1  # should not reach
)
rc=$?
msg=$(_die_msg)
if [ "$rc" -eq 42 ] && echo "$msg" | grep -qi "short\|placeholder"; then
  _pass "T2: short env var → die() with 'short/placeholder' in message"
elif [ "$rc" -eq 42 ]; then
  _fail "T2: die() called but message unexpected: '$msg'"
else
  _fail "T2: exit=$rc (expected 42); msg='$msg'"
fi
TESTS_RUN=$((TESTS_RUN+1))

# ── T3: staging_login — lookup returns 404 — die with bootstrap message ───────
# /api/auth/lookup returns 404 → die mentions "bootstrap"
echo
echo "══ T3: staging_login — lookup 404 — die (bootstrap) ════════════════════"
_reset_auth
_TCJAR=$(mktemp); chmod 600 "$_TCJAR"
_TPLF=$(mktemp); chmod 600 "$_TPLF"
COOKIE_JAR="$_TCJAR"; LOGIN_PAYLOAD_FILE="$_TPLF"
(
  MOCK_CURL_RESPONSES=(
    $'\n__STATUS__404'   # [0] lookup → 404
  )
  STAGING_SYSTEM_ADMIN_CODE="validcode99"
  staging_login
  exit 1
)
rc=$?
rm -f "$_TCJAR" "$_TPLF"
msg=$(_die_msg)
if [ "$rc" -eq 42 ] && echo "$msg" | grep -qi "bootstrap\|not found"; then
  _pass "T3: lookup 404 → die() with bootstrap/not-found message"
elif [ "$rc" -eq 42 ]; then
  _fail "T3: die() called but message unexpected: '$msg'"
else
  _fail "T3: exit=$rc (expected 42); msg='$msg'"
fi
TESTS_RUN=$((TESTS_RUN+1))

# ── T4: staging_login — lookup success + login 401 — die (invalid code) ───────
echo
echo "══ T4: staging_login — login 401 — die (invalid access code) ══════════"
_reset_auth
_TCJAR=$(mktemp); chmod 600 "$_TCJAR"
_TPLF=$(mktemp); chmod 600 "$_TPLF"
COOKIE_JAR="$_TCJAR"; LOGIN_PAYLOAD_FILE="$_TPLF"
(
  MOCK_CURL_RESPONSES=(
    $'{"user_id":"u1","display_name":"Sys"}\n__STATUS__200'  # [0] lookup → 200
    $'\n__STATUS__401'                                        # [1] login → 401
  )
  STAGING_SYSTEM_ADMIN_CODE="wrongcode"
  staging_login
  exit 1
)
rc=$?
rm -f "$_TCJAR" "$_TPLF"
msg=$(_die_msg)
if [ "$rc" -eq 42 ] && echo "$msg" | grep -qi "invalid\|401\|access code"; then
  _pass "T4: login 401 → die() with 'invalid/401/access code' in message"
elif [ "$rc" -eq 42 ]; then
  _fail "T4: die() called but message unexpected: '$msg'"
else
  _fail "T4: exit=$rc (expected 42); msg='$msg'"
fi
TESTS_RUN=$((TESTS_RUN+1))

# ── T5: staging_login — login 429 — die (locked out) ─────────────────────────
echo
echo "══ T5: staging_login — login 429 — die (locked out) ════════════════════"
_reset_auth
_TCJAR=$(mktemp); chmod 600 "$_TCJAR"
_TPLF=$(mktemp); chmod 600 "$_TPLF"
COOKIE_JAR="$_TCJAR"; LOGIN_PAYLOAD_FILE="$_TPLF"
(
  MOCK_CURL_RESPONSES=(
    $'{"user_id":"u1","display_name":"Sys"}\n__STATUS__200'  # [0] lookup → 200
    $'\n__STATUS__429'                                        # [1] login → 429
  )
  STAGING_SYSTEM_ADMIN_CODE="validcode99"
  staging_login
  exit 1
)
rc=$?
rm -f "$_TCJAR" "$_TPLF"
msg=$(_die_msg)
if [ "$rc" -eq 42 ] && echo "$msg" | grep -qi "locked\|429\|attempts"; then
  _pass "T5: login 429 → die() with 'locked/429/attempts' in message"
elif [ "$rc" -eq 42 ]; then
  _fail "T5: die() called but message unexpected: '$msg'"
else
  _fail "T5: exit=$rc (expected 42); msg='$msg'"
fi
TESTS_RUN=$((TESTS_RUN+1))

# ── T6: staging_login — success — cookie stored; returns 0 ────────────────────
# Lookup 200 → login 200 (mock writes fake cookie to jar) → returns 0
# After call, COOKIE_JAR must contain cookie data (non-empty).
echo
echo "══ T6: staging_login — success — cookie stored; returns 0 ══════════════"
_reset_auth
_TCJAR=$(mktemp); chmod 600 "$_TCJAR"
_TPLF=$(mktemp); chmod 600 "$_TPLF"
COOKIE_JAR="$_TCJAR"; LOGIN_PAYLOAD_FILE="$_TPLF"
(
  MOCK_CURL_RESPONSES=(
    $'{"user_id":"test-uuid","display_name":"Sys"}\n__STATUS__200'                   # [0] lookup
    $'{"token":"fake-jwt","session":{"role":"system_admin"}}\n__STATUS__200'         # [1] login
  )
  STAGING_SYSTEM_ADMIN_CODE="validcode99"
  staging_login
)
rc=$?
cookie_size=$(wc -c < "$_TCJAR" 2>/dev/null || echo 0)
rm -f "$_TCJAR" "$_TPLF"
if [ "$rc" -eq 0 ] && [ "$cookie_size" -gt 0 ]; then
  _pass "T6: login succeeded (exit 0); cookie jar non-empty (${cookie_size} bytes)"
elif [ "$rc" -ne 0 ]; then
  _fail "T6: staging_login returned $rc (expected 0); msg=$(_die_msg)"
else
  _fail "T6: staging_login returned 0 but cookie jar is empty"
fi
TESTS_RUN=$((TESTS_RUN+1))

# ── T7: staging_verify_session — 200 system_admin is_national=True — return 0 ─
echo
echo "══ T7: staging_verify_session — system_admin is_national=True — return 0"
_reset_auth
_TCJAR=$(mktemp); chmod 600 "$_TCJAR"
COOKIE_JAR="$_TCJAR"
(
  MOCK_CURL_RESPONSES=(
    $'{"session":{"role":"system_admin","is_national":true,"user_id":"u1"}}\n__STATUS__200'
  )
  staging_verify_session "T7"
)
rc=$?
rm -f "$_TCJAR"
[ "$rc" -eq 0 ] && _pass "T7: /api/auth/me 200 system_admin is_national → return 0" \
                || _fail "T7: exit=$rc (expected 0); msg=$(_die_msg)"
TESTS_RUN=$((TESTS_RUN+1))

# ── T8: staging_verify_session — 200 wrong role — die ────────────────────────
echo
echo "══ T8: staging_verify_session — 200 wrong role — die ══════════════════"
_reset_auth
_TCJAR=$(mktemp); chmod 600 "$_TCJAR"
COOKIE_JAR="$_TCJAR"
(
  MOCK_CURL_RESPONSES=(
    $'{"session":{"role":"wing_admin","is_national":false}}\n__STATUS__200'
  )
  staging_verify_session "T8"
  exit 1
)
rc=$?
rm -f "$_TCJAR"
msg=$(_die_msg)
if [ "$rc" -eq 42 ] && echo "$msg" | grep -qiE "wing_admin|not system_admin|Authorisation"; then
  _pass "T8: wrong role → die() with role/authorisation message"
elif [ "$rc" -eq 42 ]; then
  _fail "T8: die() called but message unexpected: '$msg'"
else
  _fail "T8: exit=$rc (expected 42); msg='$msg'"
fi
TESTS_RUN=$((TESTS_RUN+1))

# ── T9: staging_verify_session — 401 — returns 1 (no die) ────────────────────
# 401 must return 1, not call die(). The caller decides whether to reauth.
echo
echo "══ T9: staging_verify_session — 401 — returns 1 (no die) ══════════════"
_reset_auth
_TCJAR=$(mktemp); chmod 600 "$_TCJAR"
COOKIE_JAR="$_TCJAR"
(
  MOCK_CURL_RESPONSES=(
    $'\n__STATUS__401'
  )
  staging_verify_session "T9"
)
rc=$?
rm -f "$_TCJAR"
if [ "$rc" -eq 1 ]; then
  _pass "T9: /api/auth/me 401 → return 1 (not die)"
elif [ "$rc" -eq 42 ]; then
  _fail "T9: die() was called on 401 — should return 1; msg=$(_die_msg)"
elif [ "$rc" -eq 0 ]; then
  _fail "T9: returned 0 on 401 — expected 1"
else
  _fail "T9: exit=$rc (expected 1); msg=$(_die_msg)"
fi
TESTS_RUN=$((TESTS_RUN+1))

# ── T10: staging_reauth_if_needed — session still valid — returns 0 ───────────
# /api/auth/me → 200 system_admin → verify succeeds → no reauth needed
echo
echo "══ T10: staging_reauth_if_needed — valid session — return 0 ════════════"
_reset_auth
_TCJAR=$(mktemp); chmod 600 "$_TCJAR"
_TPLF=$(mktemp); chmod 600 "$_TPLF"
COOKIE_JAR="$_TCJAR"; LOGIN_PAYLOAD_FILE="$_TPLF"
(
  MOCK_CURL_RESPONSES=(
    $'{"session":{"role":"system_admin","is_national":true}}\n__STATUS__200'  # [0] verify → OK
  )
  staging_reauth_if_needed "T10"
)
rc=$?
rm -f "$_TCJAR" "$_TPLF"
[ "$rc" -eq 0 ] && _pass "T10: session valid (200) → returns 0, no relogin" \
                || _fail "T10: exit=$rc (expected 0); msg=$(_die_msg)"
TESTS_RUN=$((TESTS_RUN+1))

# ── T11: staging_reauth_if_needed — session expired; reauth succeeds ──────────
# [0] /api/auth/me 401 (verify → expired, return 1)
# [1] /api/auth/lookup 200 → user_id
# [2] /api/auth/login 200 → cookie
# [3] /api/auth/me 200 system_admin (reauth verify → OK)
echo
echo "══ T11: staging_reauth_if_needed — expired; reauth succeeds ════════════"
_reset_auth
_TCJAR=$(mktemp); chmod 600 "$_TCJAR"
_TPLF=$(mktemp); chmod 600 "$_TPLF"
COOKIE_JAR="$_TCJAR"; LOGIN_PAYLOAD_FILE="$_TPLF"
(
  MOCK_CURL_RESPONSES=(
    $'\n__STATUS__401'                                                                   # [0] initial verify → 401
    $'{"user_id":"u1","display_name":"Sys"}\n__STATUS__200'                             # [1] lookup → 200
    $'{"token":"jwt","session":{"role":"system_admin"}}\n__STATUS__200'                 # [2] login → 200
    $'{"session":{"role":"system_admin","is_national":true}}\n__STATUS__200'            # [3] reauth verify → OK
  )
  STAGING_SYSTEM_ADMIN_CODE="validcode99"
  staging_reauth_if_needed "T11"
)
rc=$?
rm -f "$_TCJAR" "$_TPLF"
[ "$rc" -eq 0 ] && _pass "T11: 401 → relogin → re-verify system_admin → returns 0" \
                || _fail "T11: exit=$rc (expected 0); msg=$(_die_msg)"
TESTS_RUN=$((TESTS_RUN+1))

# ── T12: staging_login — LOGIN_PAYLOAD_FILE zeroed after login curl returns ───
# The access code is written to LOGIN_PAYLOAD_FILE then immediately zeroed.
# After staging_login succeeds, the payload file must be empty.
echo
echo "══ T12: staging_login — payload file zeroed after use ══════════════════"
_reset_auth
_TCJAR=$(mktemp); chmod 600 "$_TCJAR"
_TPLF=$(mktemp); chmod 600 "$_TPLF"
COOKIE_JAR="$_TCJAR"; LOGIN_PAYLOAD_FILE="$_TPLF"
(
  MOCK_CURL_RESPONSES=(
    $'{"user_id":"u1","display_name":"Sys"}\n__STATUS__200'               # [0] lookup
    $'{"token":"jwt","session":{"role":"system_admin"}}\n__STATUS__200'   # [1] login
  )
  STAGING_SYSTEM_ADMIN_CODE="SUPERSECRET123"
  staging_login
)
rc=$?
payload_size=$(wc -c < "$_TPLF" 2>/dev/null || echo -1)
rm -f "$_TCJAR" "$_TPLF"
if [ "$rc" -eq 0 ] && [ "$payload_size" -eq 0 ]; then
  _pass "T12: login succeeded; LOGIN_PAYLOAD_FILE zeroed (0 bytes) immediately after use"
elif [ "$rc" -ne 0 ]; then
  _fail "T12: staging_login returned $rc (expected 0); msg=$(_die_msg)"
else
  _fail "T12: LOGIN_PAYLOAD_FILE not zeroed — ${payload_size} bytes remain"
fi
TESTS_RUN=$((TESTS_RUN+1))

# ── T13: cleanup — deletes temp files; unsets STAGING_SYSTEM_ADMIN_CODE ───────
# Write content to COOKIE_JAR (triggers logout curl call), then call cleanup.
# After cleanup: files must not exist; credential must be unset (within subshell).
echo
echo "══ T13: cleanup — files deleted; credential unset ══════════════════════"
_reset_auth
_TCJAR=$(mktemp); chmod 600 "$_TCJAR"
_TPLF=$(mktemp); chmod 600 "$_TPLF"
COOKIE_JAR="$_TCJAR"; LOGIN_PAYLOAD_FILE="$_TPLF"
printf 'staging.example.com\tFALSE\t/\tFALSE\t0\taafc_session\tfake-jwt\n' > "$_TCJAR"
(
  MOCK_CURL_RESPONSES=(
    $'{"ok":true}\n__STATUS__200'   # [0] logout call → 200
  )
  STAGING_SYSTEM_ADMIN_CODE="shouldbeunset"
  cleanup
  # Credential must be unset within the subshell
  [ -z "${STAGING_SYSTEM_ADMIN_CODE:-}" ] || exit 1
  # Files must be gone (removed by cleanup)
  [ ! -f "$COOKIE_JAR" ] && [ ! -f "$LOGIN_PAYLOAD_FILE" ] && exit 0 || exit 1
)
rc=$?
files_gone=0
[ ! -f "$_TCJAR" ] && [ ! -f "$_TPLF" ] && files_gone=1
rm -f "$_TCJAR" "$_TPLF" 2>/dev/null || true  # safety
if [ "$rc" -eq 0 ] && [ "$files_gone" -eq 1 ]; then
  _pass "T13: cleanup deleted temp files; STAGING_SYSTEM_ADMIN_CODE unset"
elif [ "$rc" -ne 0 ]; then
  _fail "T13: subshell exit=$rc — credential not unset or files not deleted"
elif [ "$files_gone" -eq 0 ]; then
  _fail "T13: cleanup ran but files still exist from parent shell perspective"
else
  _fail "T13: exit=$rc files_gone=$files_gone"
fi
TESTS_RUN=$((TESTS_RUN+1))

# ── Summary ───────────────────────────────────────────────────────────────────
echo
echo "════════════════════════════════════════════════════════════════════"
printf "  Tests run: %d   \033[0;32mPASS: %d\033[0m   \033[0;31mFAIL: %d\033[0m\n" \
  "$TESTS_RUN" "$TESTS_PASSED" "$TESTS_FAILED"
echo "  (A–G: deployment tracking · T1–T13: auth/cookie/cleanup)"
echo "════════════════════════════════════════════════════════════════════"
echo
[ "$TESTS_FAILED" -eq 0 ] || exit 1
