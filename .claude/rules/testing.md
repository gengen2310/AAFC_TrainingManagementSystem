# Testing Rules — AAFC TMS

## Running tests

```bash
cd backend
source .venv/bin/activate
python -m pytest tests/ -q        # quick pass/fail
python -m pytest tests/ -v        # verbose
python -m pytest tests/test_system_admin.py -q  # single file
```

Current baseline (2026-08-09, commit 5a6932b): 1231 passed, 5 skipped.

## Test patterns

- Use `login(client, code)` from `tests/conftest.py` to get auth headers
- Each endpoint needs: happy-path, forbidden (403), unauthenticated (401)
- For system_admin endpoints: also test that national_admin, sqn_admin, auditor are denied
- For state-changing endpoints: verify audit log entry is created
- For access-code endpoints: verify no plaintext or hash in response body

## Test file naming

- `test_system_admin.py` — system console, maintenance, backup, scope-map, audit
- `test_planner_v14.py` — training planner, annual program
- `test_planning.py` — parade nights, curriculum, accounts
- `test_accounts.py` — account management RBAC
- New feature tests go in `test_{feature_area}.py`

## What NOT to test

- Do not test that the database schema matches models (covered by Alembic)
- Do not mock the database — use the real SQLite test DB from conftest.py
- Do not test third-party library behaviour (SQLAlchemy, FastAPI)

## Stress test scripts (against live server)

```bash
# Smoke test (requires server running)
python tools/stress/smoke_test.py

# Security scope test (requires server running)
python tools/stress/security_scope_test.py

# Load test auth
python tools/stress/load_test_auth.py --concurrency 20 --requests 100
```

## Pre-packaging test run

Always run the full test suite with no failures before packaging:
```bash
cd backend && python -m pytest tests/ -q --tb=short
```
