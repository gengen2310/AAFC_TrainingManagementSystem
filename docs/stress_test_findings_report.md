# AAFC TMS — Full System Stress Test Findings Report
**Date:** 2026-07-06  
**Scope:** All backend API endpoints, frontend interactions, RBAC matrix, input validation, auth flows, security controls  
**Test environment:** Local SQLite (write/RBAC tests) + Live Railway/Supabase (auth/live tests)  
**Test baseline:** 358 tests passed, 1 skipped (pytest)

---

## Executive Summary

The system is broadly well-secured. All major RBAC boundaries hold, cross-tenant isolation is enforced, no SQL/command injection vectors were found, and all 22 security-specific tests pass. Two issues require attention before the system handles real brute-force scenarios:

| # | Severity | Finding |
|---|----------|---------|
| 1 | **CRITICAL** | IP rate limiter non-functional in production (multi-worker split-brain) |
| 2 | **BUG** | Migration expected-head hardcoded to wrong value → System Console shows false mismatch |
| 3 | Low | `require_role` 403 responses leak allowed roles to authenticated callers |
| 4 | Info | `/openapi.json` publicly accessible — 148 paths visible unauthenticated |

---

## Surface Area

| Component | Count |
|-----------|-------|
| API endpoint routes | 156 |
| Router files | 11 |
| Frontend pages/tabs | 21 |
| Defined roles | 8 |
| Public endpoints (no auth) | 5 (`/api/health`, `/api/health/db`, `/api/health/ready`, `/api/auth/login`, `/openapi.json`) |
| Protected endpoints | ~151 |

---

## FINDING 1 — CRITICAL: IP Rate Limiter Non-Functional in Production

### What was tested
6 consecutive login attempts with a wrong code from the same IP against the live Railway backend.

### What happened
All 6 attempts returned `401 invalid_code`. None triggered `429 locked_out`.

Expected: attempt 5 → `429 locked_out` (per `LOGIN_MAX_ATTEMPTS=5`).

### Root cause
`security.py` stores rate-limit state in two process-local dicts:
```python
_attempts: dict[str, list[float]] = {}
_lockouts: dict[str, float] = {}
```

Railway runs 2 gunicorn workers. Each has its own copy of these dicts. Login requests are load-balanced across workers, so each worker only sees ~half the attempts. With 2 workers and 6 attempts:

- Worker 1 sees attempts 1, 3, 5 → count = 3 (never reaches 5)
- Worker 2 sees attempts 2, 4, 6 → count = 3 (never reaches 5)

Neither worker ever reaches `LOGIN_MAX_ATTEMPTS=5`, so lockout never fires.

### Impact
The IP-based lockout — the only brute-force protection currently deployed — provides **zero protection** in production. An attacker can make unlimited login attempts at full speed.

### Fix options (in order of preference)

**Option A (recommended) — PostgreSQL-backed per-account lockout (task 8d)**  
Add `failed_attempts: int` and `locked_until: datetime | None` columns to `AccessCode`. Increment on each failed verify, lock when ≥ 5. Auto-reset after 15 min. Manual override by wing_admin. This works regardless of worker count because it uses the shared database. Task 8d is already planned — this finding makes it urgent.

**Option B — Redis-backed IP limiter**  
Replace `_attempts`/`_lockouts` dicts with Redis (`REDIS_URL` env var). Works across workers but requires adding Redis as a dependency. Not recommended unless there is already a Redis instance.

**Option C — Reduce gunicorn workers to 1**  
Immediate workaround but reduces throughput. Not recommended.

### Note on single-process behavior
The rate limiter works correctly in a single-process test environment (all 358 tests pass, including `test_login_rate_limit`). The failure is production-only.

---

## FINDING 2 — BUG: Migration Expected-Head Hardcoded to Wrong Value

### Location
`backend/app/routers/system.py:140`

```python
return {
    "expected_head": "h3c4d5e6f7g8",   # ← wrong: was correct at v21
    "current": _migration_head(),
}
```

### What's wrong
The `expected_head` was set at v21 (migration `h3c4d5e6f7g8`) and never updated as v22–v24 were added. The actual Alembic head in production is `l7g8h9i0j1k2` (v24).

The System Console (`GET /api/system/migrations`) will show a permanent "mismatch" warning to any system_admin who looks.

### Fix
One-line change: `"expected_head": "l7g8h9i0j1k2"`.

---

## FINDING 3 — LOW: `require_role` 403 Leaks Allowed Roles

### Location
`backend/app/permissions.py:97`

```python
def require_role(p: Principal, *roles: str):
    if p.role not in roles:
        raise HTTPException(403, detail={"error": "forbidden", "needs": list(roles)})
```

### What this means
An authenticated user who calls an endpoint they lack permission for receives the list of roles that can access it, e.g.:
```json
{"error": "forbidden", "needs": ["national_viewer", "national_admin", "system_admin", "auditor"]}
```

### Impact
Low. Only authenticated users encounter this. It does not expose data, enable privilege escalation, or help an attacker guess valid codes. In a single-tenant military context it is acceptable but slightly untidy.

### Fix (optional)
Remove the `needs` field from the 403 response, or restrict it to system_admin role only. No impact on functionality.

---

## FINDING 4 — INFO: `/openapi.json` Publicly Accessible

### What was found
`GET /openapi.json` returns HTTP 200 without authentication. It contains 148 paths, including all `/api/system/*` endpoints:
```
/api/system/audit-summary
/api/system/backups
/api/system/backups/pg-dump
/api/system/bootstrap-staging
/api/system/health
/api/system/maintenance
/api/system/maintenance/disable
/api/system/maintenance/enable
/api/system/migrations
/api/system/overview
/api/system/scope-map
/api/system/version
```

### Impact
Path names are visible without credentials. The endpoints themselves all require authentication and enforce RBAC, so an attacker who discovers the paths still cannot call them. This is a documentation disclosure, not an access control bypass.

### Decision needed
If the API is intended only for the frontend (not third-party integration), disable the docs:
```python
# backend/app/main.py
app = FastAPI(..., openapi_url=None)
```
If the OpenAPI spec is useful for the System Console or future integrations, restrict it to authenticated users with a custom middleware. No action required if exposure is acceptable.

---

## RBAC Matrix — All Verified Passing

| Test | Expected | Result |
|------|----------|--------|
| `sqn_general` GET /api/accounts | 403 | ✓ 403 |
| `sqn_general` GET /api/cadets | 403 | ✓ 403 |
| `sqn_general` POST /api/auth/change-code (other user) | 403 | ✓ 403 |
| `sqn_general` POST /api/accounts | 403 | ✓ 403 |
| `sqn_general` GET /api/reports/wing-overview | 403 | ✓ 403 |
| `sqn_general` GET /api/system/overview | 403 | ✓ 403 |
| `sqn_general` GET /api/parade-nights | 200 | ✓ 200 |
| `sqn_general` GET /api/curriculum | 200 | ✓ 200 |
| `sqn_general` GET /api/facilitators | 200 | ✓ 200 |
| `sqn_general` GET /api/training-areas | 200 | ✓ 200 |
| `sqn_general` GET /api/auth/me | 200 | ✓ 200 |
| Unauthenticated GET /api/auth/me | 401 | ✓ 401 |
| Unauthenticated GET /api/accounts | 401 | ✓ 401 |
| Unauthenticated GET /api/system/overview | 401 | ✓ 401 |
| Unauthenticated GET /api/system/backups | 401 | ✓ 401 |
| Unauthenticated GET /api/audit | 401 | ✓ 401 |
| Unauthenticated POST /api/auth/logout | 401 | ✓ 401 |
| Fake/expired JWT | 401 invalid_or_expired | ✓ 401 |
| Wrong HTTP method (GET /api/auth/login) | 405 | ✓ 405 |
| CORS from allowed origin | 200 + correct header | ✓ |
| CORS from disallowed origin | 400 no origin header | ✓ |
| SQL injection code | 401 (ORM, no injection) | ✓ 401 |
| Code as integer | 422 type error | ✓ 422 |
| Code as null | 422 type error | ✓ 422 |
| Empty body | 422 field required | ✓ 422 |
| 1000-char code | 401 invalid_code (no crash) | ✓ 401 |
| Extra JSON fields | Ignored + 401 | ✓ 401 |
| `GET /api/accounts/{uid}` scope (sqn_admin → other sqn user) | 403 | ✓ via `_can_read_account` |

---

## Auth Flow — Verified Passing

- Login with correct code → 200 + JWT + session object ✓
- Login with wrong code → 401 `invalid_code` ✓
- Login with valid code but inactive user → 401 `invalid_user` ✓
- Token refresh (valid token) → 200 + new token ✓
- Token refresh (no token) → 401 ✓
- Logout → 401 auth_required (no token) ✓
- JWT sliding refresh: works, bounds leaked-token exposure ✓

---

## Security Controls — All Clean

| Check | Result |
|-------|--------|
| SQL string concatenation | None found |
| Hardcoded secrets | None found |
| `shell=True` / `os.system` | None found |
| Unsafe deserialization (`pickle`, `yaml.load`) | None found |
| Debug endpoints | None found |
| pg_dump credentials | Passed via `PGPASSWORD` env (not CLI args) ✓ |
| DATABASE_URL in subprocess | Explicitly removed from subprocess env ✓ |
| Bootstrap-staging in production | Blocked by `ENVIRONMENT == "production"` check ✓ |
| File upload size limit | 5 MB enforced ✓ |
| Export type validation | Allowlist via `_rows_for()` before any header write ✓ |
| Formula injection in imports | `test_import_preview_and_formula_neutralisation` passes ✓ |
| Security headers | `test_security_headers_present` passes ✓ |

---

## Test Suite Coverage

```
358 passed, 1 skipped, 1 warning
```

Tests covering security scenarios: `test_hardening.py` (5), `test_core.py` (22).

Key tests:
- `test_squadron_cannot_read_other_squadron` — cross-tenant isolation
- `test_wing_admin_cannot_edit_without_proxy` — proxy mode enforcement
- `test_wing_admin_cannot_proxy_other_wing_scope` — cross-wing proxy blocked
- `test_login_rate_limit` — rate limiter (passes in single-process; does not cover multi-worker failure)
- `test_no_audit_delete_endpoint` — confirms audit log cannot be deleted via API

---

## Prioritized Action Items

### Must do before launch
1. **Implement per-account lockout (task 8d)**  
   Fixes the non-functional rate limiter. 5 wrong codes per account → `locked_until`. Auto-reset 15 min. Manual override by wing_admin. See Finding 1 above.

2. **Fix migration expected-head (1-line change)**  
   `system.py:140`: change `"h3c4d5e6f7g8"` → `"l7g8h9i0j1k2"`. See Finding 2.

### Optional / decide
3. **Decide on `/openapi.json` exposure**  
   Options: disable (`openapi_url=None`), require auth, or accept current state. See Finding 4.

4. **Remove `needs` from `require_role` 403 responses**  
   `permissions.py:97`: remove `, "needs": list(roles)` from the HTTPException. Low priority. See Finding 3.

### Already pending
5. **Switch DATABASE_URL to Transaction Pooler (port 6543)** — user must change in Railway dashboard.
