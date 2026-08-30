#!/usr/bin/env bash
# pre_alpha_check.sh — pre-alpha readiness checklist for AAFC TMS.
# Run from the project root before packaging or delivering to pilot users.
#
# Usage:
#   bash scripts/pre_alpha_check.sh

set -uo pipefail

PASS=0
FAIL=0
WARN=0

ok()   { echo "  [PASS] $1"; PASS=$((PASS+1)); }
fail() { echo "  [FAIL] $1"; FAIL=$((FAIL+1)); }
warn() { echo "  [WARN] $1"; WARN=$((WARN+1)); }

echo
echo "AAFC TMS — Pre-Alpha Readiness Check"
echo "=================================================="

# ── File structure ──
echo
echo "  File structure"
[ -f "backend/app/main.py" ] && ok "backend/app/main.py exists" || fail "backend/app/main.py missing"
[ -f "connected-frontend/index.html" ] && ok "connected-frontend/index.html exists" || fail "connected-frontend/index.html missing"
[ -f "CHANGELOG.md" ] && ok "CHANGELOG.md exists" || fail "CHANGELOG.md missing"
[ -f "CLAUDE.md" ] && ok "CLAUDE.md exists" || warn "CLAUDE.md missing (recommended)"
[ -f "docs/deployment_guide.md" ] && ok "docs/deployment_guide.md exists" || fail "docs/deployment_guide.md missing"
[ -f "docs/role_matrix.md" ] && ok "docs/role_matrix.md exists" || warn "docs/role_matrix.md missing"
[ -f "scripts/backup_sqlite_demo.sh" ] && ok "scripts/backup_sqlite_demo.sh exists" || warn "backup script missing"

# ── No access-code plaintext in frontend ──
echo
echo "  Security — access codes"
MATCHES=$(grep -cE "SYSADMIN2026|ADMIN703|ADMIN7WG|ADMINNATIONAL|703SQN2026|AUDITOR2026" connected-frontend/index.html 2>/dev/null || true)
[ "${MATCHES:-0}" -eq 0 ] && ok "No seeded access codes in frontend" || fail "Seeded access codes found in frontend (${MATCHES} matches)"

# localStorage is permitted only for UI preferences (displayDensity, navCollapsed).
# Operational data (tokens, role, session, access codes) must never go in localStorage.
MATCHES=$(grep -cE "localStorage\.(setItem|getItem)\(['\"]+(token|jwt|role|session|user|scope|access_code|squadron|wing)" connected-frontend/index.html 2>/dev/null || true)
[ "${MATCHES:-0}" -eq 0 ] && ok "No operational data in localStorage" || fail "Operational data found in localStorage (${MATCHES} matches)"

MATCHES=$(grep -cE "code_hash|plain_code" connected-frontend/index.html 2>/dev/null || true)
[ "${MATCHES:-0}" -eq 0 ] && ok "No hash/plaintext references in frontend" || fail "code_hash/plain_code found in frontend"

MATCHES=$(grep -cE "JWT_SECRET|SECRET_KEY" connected-frontend/index.html 2>/dev/null || true)
[ "${MATCHES:-0}" -eq 0 ] && ok "No JWT_SECRET in frontend" || fail "JWT_SECRET found in frontend"

# ── Backend security ──
echo
echo "  Security — backend config"
if [ -f "backend/app/config.py" ]; then
  grep -q "validate_for_production" backend/app/config.py && ok "Production config validation present" || fail "Production config validation missing"
  grep -q "COOKIE_SECURE" backend/app/config.py && ok "COOKIE_SECURE setting present" || fail "COOKIE_SECURE missing"
fi

# ── Migrations ──
echo
echo "  Database migrations"
LATEST_MIGRATION=$(ls backend/alembic/versions/*.py 2>/dev/null | sort | tail -1)
if [ -n "$LATEST_MIGRATION" ]; then
  ok "Alembic migrations directory has entries"
  CURRENT_HEAD=$(grep "revision = " "$LATEST_MIGRATION" | head -1 | grep -o "'[^']*'" | tr -d "'" || echo "unknown")
  echo "    Latest migration: $CURRENT_HEAD"
else
  fail "No Alembic migrations found"
fi

# ── Backend tests ──
echo
echo "  Backend tests"
if command -v python3 &>/dev/null && [ -d "backend" ]; then
  cd backend
  if source .venv/bin/activate 2>/dev/null; then
    RESULT=$(python -m pytest tests/ -q --tb=no 2>&1 | tail -1)
    if echo "$RESULT" | grep -q "passed"; then
      ok "pytest: $RESULT"
    else
      fail "pytest failed: $RESULT"
    fi
    deactivate 2>/dev/null || true
  else
    warn "Could not activate .venv — skipping pytest (run manually: cd backend && python -m pytest tests/ -q)"
  fi
  cd ..
fi

# ── Frontend size check ──
echo
echo "  Frontend"
if [ -f "connected-frontend/index.html" ]; then
  SIZE=$(wc -c < connected-frontend/index.html)
  SIZE_KB=$((SIZE/1024))
  [ "$SIZE_KB" -gt 50 ] && ok "Frontend has content (${SIZE_KB}KB)" || warn "Frontend suspiciously small (${SIZE_KB}KB)"
fi

# ── Scripts executable ──
echo
echo "  Scripts"
for s in scripts/backup_sqlite_demo.sh scripts/smoke_test_local.sh; do
  [ -f "$s" ] && ok "$s exists" || warn "$s missing"
done

# ── Docs ──
echo
echo "  Documentation"
for d in docs/deployment_guide.md docs/system_admin_console.md docs/pre_alpha_readiness_checklist.md; do
  [ -f "$d" ] && ok "$d exists" || warn "$d missing"
done

# ── Summary ──
echo
echo "=================================================="
echo "  Passed : $PASS"
echo "  Warnings: $WARN"
echo "  Failed : $FAIL"
echo
if [ "$FAIL" -eq 0 ] && [ "$WARN" -eq 0 ]; then
  echo "  All checks passed. System is pre-alpha ready."
elif [ "$FAIL" -eq 0 ]; then
  echo "  No failures. $WARN warning(s) — review before alpha delivery."
else
  echo "  $FAIL check(s) FAILED. Resolve before packaging."
  exit 1
fi
