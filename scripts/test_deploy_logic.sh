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
#
# Design notes:
# — _railway_deploy_list uses a file-based counter (DEPLOY_TEST_COUNTER_FILE) so
#   the call index survives across $() subshells.  Each $() creates a forked
#   subshell; in-memory variable changes inside $() are invisible to the parent.
#   Writing to a temp file is the standard fix.
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
_CTR_FILE=$(mktemp)   # call counter for _railway_deploy_list
_MSG_FILE=$(mktemp)   # message from die()
trap 'rm -f "$_CTR_FILE" "$_MSG_FILE"' EXIT

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

# ── Summary ───────────────────────────────────────────────────────────────────
echo
echo "════════════════════════════════════════════════════════════════════"
printf "  Tests run: %d   \033[0;32mPASS: %d\033[0m   \033[0;31mFAIL: %d\033[0m\n" \
  "$TESTS_RUN" "$TESTS_PASSED" "$TESTS_FAILED"
echo "════════════════════════════════════════════════════════════════════"
echo
[ "$TESTS_FAILED" -eq 0 ] || exit 1
