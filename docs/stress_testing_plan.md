# AAFC TMS — Stress Testing Plan

## Purpose

Find where the system breaks before alpha. Establish baseline performance, identify capacity limits, and verify security controls hold under load.

## Scripts

| Script | Purpose |
|---|---|
| `tools/stress/smoke_test.py` | Quick end-to-end functional verification |
| `tools/stress/load_test_auth.py` | Concurrent login throughput |
| `tools/stress/security_scope_test.py` | RBAC and IDOR enforcement under varied inputs |
| `tools/stress/data_volume_seed.py` | Generate larger data volumes for volume testing |

## A. Smoke Test (functional)

Run before and after every deployment.

```bash
python tools/stress/smoke_test.py
```

Expected: all checks PASS. Any FAIL blocks deployment.

## B. Load Test — Authentication

```bash
python tools/stress/load_test_auth.py --concurrency 20 --requests 100
```

Measures login throughput and latency. Reports:
- Success count, rate-limited count, error count
- Average, median, p95, max latency
- Requests per second

**Target for alpha:** ≥10 req/s with p95 < 500ms at concurrency=10.

To test rate limiting:
```bash
python tools/stress/load_test_auth.py --concurrency 10 --requests 50
# Use a bad code to trigger lockout:
# Edit load_test_auth.py and change CODE="BADCODE" — expect 429s after 5 attempts/IP
```

## C. Load Test — Planning Endpoints

Manual load test using curl or Python requests against planning endpoints. Not scripted in V17 but can be added with:

```python
import concurrent.futures, requests, time
# ... follow pattern from load_test_auth.py
```

Endpoints to test:
- `GET /api/planning/years`
- `GET /api/planning/years/{id}/missions`
- `GET /api/planning/years/{id}/annual-program`

## D. Security Scope Test

```bash
python tools/stress/security_scope_test.py
```

Checks:
- Unauthenticated access to all protected routes
- Invalid JWT token
- Read-only roles attempting writes
- system_admin endpoints denied to non-system roles
- Cross-scope IDOR attempts
- Wing admin cross-wing access
- Oversized request body handling
- Unexpected enum values
- Rate limiting after bad login attempts
- No secrets in API responses

All checks must PASS before alpha delivery.

## E. Data Volume Test

```bash
# Create a separate test database
cd backend
DATABASE_URL=sqlite:///./test_volume.db python ../tools/stress/data_volume_seed.py \
  --wings 8 --sqns-per-wing 6 --users-per-sqn 3 --curriculum 50
```

Then start the backend with the test DB and re-run smoke test:
```bash
DATABASE_URL=sqlite:///./test_volume.db uvicorn app.main:app --port 8001
BASE=http://localhost:8001 python tools/stress/smoke_test.py
```

Measure response times for list endpoints with larger data.

**Warning:** Never use `data_volume_seed.py` against the demo or production database.

## F. Failure Testing (manual)

| Test | Method | Expected |
|---|---|---|
| Backend down | Stop uvicorn, reload frontend | Frontend shows connection error |
| Database missing | Remove .db file while backend running | 500 error on first DB call |
| Invalid JWT | Send malformed cookie | 401 |
| Expired session | Wait past TTL or modify exp claim | 401, must re-login |
| Short JWT secret in production | Set ENVIRONMENT=production with short secret | Backend refuses to start |
| Port already in use | Start two backends on 8000 | Second fails cleanly |

## G. Browser Testing

| Browser | Version | Test scope |
|---|---|---|
| Chrome | Latest | Full golden path + system_admin |
| Safari | Latest | Login, navigation, planning |
| Edge | Latest | Login, curriculum, audit |

For each browser:
1. Hard refresh (Cmd+Shift+R)
2. Login as ADMIN703
3. Navigate through: Dashboard → Training Planner → Annual Program → Parade Night Program
4. Login as SYSADMIN2026
5. Check System Console loads all sections
6. Enable and disable maintenance mode

## H. Usability Stress (manual)

| Scenario | Test |
|---|---|
| Empty annual program | Create new planning year with no data |
| No timing template | Delete timing template and open PN builder |
| No curriculum | Create parade night with no curriculum in DB |
| Long mission name | Create curriculum item with 200-char title |
| Many facilitators | Add 20+ facilitators and open builder |
| Empty audit log | Login as auditor before any other actions |

## Results Template

| Test | Date | Result | Avg Latency | Max Latency | Notes |
|---|---|---|---|---|---|
| Smoke test | | | | | |
| Auth load (c=20, n=100) | | | | | |
| Security scope test | | | | | |
| Volume seed (8 wings, 48 sqns) | | | | | |
| Browser: Chrome | | | | | |
| Browser: Safari | | | | | |

## V17 Alpha Stress Test Results

| Test | Result |
|---|---|
| Backend tests (310) | 310 passed, 1 skipped |
| Smoke test | Run against live server to confirm |
| Security scope test | Run against live server to confirm |
| Auth load test | Run against live server to confirm |

Full live stress test results should be recorded before beta delivery.
