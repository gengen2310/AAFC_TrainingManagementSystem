#!/usr/bin/env bash
# smoke_test_local.sh — quick smoke test of the local running server.
# Requires: curl, jq (optional)
#
# Usage:
#   bash scripts/smoke_test_local.sh
#
# Expects backend at http://localhost:8000 and frontend at http://localhost:8080.

set -euo pipefail

BASE="http://localhost:8000"
FRONTEND="http://localhost:8080"
PASS=0
FAIL=0

check() {
  local label="$1"
  local status="$2"
  local expected="$3"
  if [ "$status" -eq "$expected" ]; then
    echo "  [PASS] $label"
    PASS=$((PASS+1))
  else
    echo "  [FAIL] $label — expected $expected, got $status"
    FAIL=$((FAIL+1))
  fi
}

echo
echo "AAFC TMS — Local Smoke Test"
echo "=================================================="

# Health
echo
echo "  Health"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/health")
check "GET /api/health → 200" "$STATUS" 200

STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/health/db")
check "GET /api/health/db → 200" "$STATUS" 200

# Frontend
echo
echo "  Frontend"
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$FRONTEND/")
check "GET frontend/ → 200" "$STATUS" 200

# Auth
echo
echo "  Authentication"
COOKIE_FILE=$(mktemp)
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -c "$COOKIE_FILE" \
  -X POST "$BASE/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"code":"ADMIN703"}')
check "Login ADMIN703 → 200" "$STATUS" 200

STATUS=$(curl -s -o /dev/null -w "%{http_code}" -b "$COOKIE_FILE" "$BASE/api/auth/me")
check "GET /api/auth/me (authenticated) → 200" "$STATUS" 200

# Bad login
STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST "$BASE/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"code":"WRONG"}')
check "Login bad code → 401" "$STATUS" 401

# Unauthenticated protected route
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/accounts")
check "GET /api/accounts unauthenticated → 401" "$STATUS" 401

# System admin
echo
echo "  System Admin"
SYS_COOKIE_FILE=$(mktemp)
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -c "$SYS_COOKIE_FILE" \
  -X POST "$BASE/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"code":"SYSADMIN2026"}')
check "Login SYSADMIN2026 → 200" "$STATUS" 200

STATUS=$(curl -s -o /dev/null -w "%{http_code}" -b "$SYS_COOKIE_FILE" "$BASE/api/system/overview")
check "GET /api/system/overview (system_admin) → 200" "$STATUS" 200

STATUS=$(curl -s -o /dev/null -w "%{http_code}" -b "$COOKIE_FILE" "$BASE/api/system/overview")
check "GET /api/system/overview (sqn_admin) → 403" "$STATUS" 403

rm -f "$COOKIE_FILE" "$SYS_COOKIE_FILE"

# Summary
echo
echo "=================================================="
echo "  Passed: $PASS  Failed: $FAIL"
echo

if [ "$FAIL" -eq 0 ]; then
  echo "  All smoke tests passed."
else
  echo "  $FAIL test(s) FAILED."
  exit 1
fi
