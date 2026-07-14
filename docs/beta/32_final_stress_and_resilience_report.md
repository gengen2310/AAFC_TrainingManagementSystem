# AAFC TMS — Final Stress and Resilience Report

Phase 16/32 output. Documents all resilience testing completed and pending.
Created: 2026-07-14.

---

## Completed Resilience Tests

### Backup and Restore (Phase 6 — PROVEN)

| Test | Result | Evidence |
|---|---|---|
| Production backup (pg_dump → GPG-encrypted artifact) | PASS | Run `29281190414` — 432,758-byte dump |
| Production restore (PostgreSQL schema + row counts) | PASS | Run `29281292666` — schema verified |
| Application-level restore (API read from restored DB) | PASS | Run `29297143467` — 8 authenticated API reads: wings=8, squadrons=16, users=39, audit_logs=441, curriculum_items=217, planning_years=10 |
| Alembic revision check post-restore | PASS | Revision `x9y0z1a2b3c4` confirmed in restored environment |
| Daily backup schedule | ACTIVE | `.github/workflows/backup-postgresql.yml` |
| Weekly restore-test schedule | ACTIVE | `.github/workflows/test-restore-postgresql.yml` |

Recovery Time Objective (demonstrated): ~8 minutes for dump + restore + verification in GitHub Actions runner.

### Security Resilience

| Test | Result | Commit |
|---|---|---|
| Rate limiting (IP lockout after 5 failures) | PASS — `test_db_ip_lockout_fires_after_five_wrong_codes` | Existing |
| Per-account lockout | PASS — `test_account_lockout_blocks_correct_code` | Existing |
| Lockout persistence in DB | PASS — `test_db_ip_lockout_persists_in_table` | Existing |
| Admin unlock endpoint | PASS — `test_wing_admin_can_unlock_sqn_account` | Existing |
| IDOR cross-squadron read (sqn_admin) | PASS — `test_planning_idor.py` (all 50 scenarios) | Existing |
| IDOR cross-squadron read (sqn_general) | PASS — 4 new tests in `test_planning.py` | `67e8f13` |
| Code isolation (admin code rejected for viewer account) | PASS — `test_admin_code_rejected_for_viewer_account` | Existing |
| Maintenance mode enforcement | PASS — `test_maintenance_enforcement.py` (30 scenarios) | Existing |
| Access code not returned in API responses | PASS — security grep + test_hardening.py | Verified |

### Migration Chain Resilience

| Test | Result |
|---|---|
| Alembic migration chain validates (CI) | PASS — `test_compute_alembic_head.py` |
| All 3 environments on same revision | PASS — `x9y0z1a2b3c4` confirmed local, staging, production |
| `seed_all.py` safety guard (no prod destruction) | PASS — `test_reset_db_safety.py` |

---

## Pending Resilience Tests

### 100-User Concurrent Load Test (BLOCKED — Phase 15)

**Status**: Not executed. Requires:
- Staging environment confirmed available (✓)
- Load test runner (Locust or k6) installed and configured
- Explicit approval to run against staging
- Test scenario designed for representative squadron workflow (login → parade night load → CEA import → session schedule)

**Target criteria** (from mission spec):
- P95 response time ≤ 2000ms under 100 concurrent users
- Zero 5xx errors during sustained load
- Auth token/cookie invalidation under load does not cascade

**Risk**: None to production (staging only). Risk to staging data: synthetic data only.

### Chaos Testing (BLOCKED — Phase 16)

**Status**: Not executed. Requires Railway infrastructure access to simulate:
- Backend container restart mid-request
- Database connection pool exhaustion
- Network partition between frontend and backend

**Planned scenarios**:
- Restart backend during active session → client receives 503, reconnects on retry
- DB connection pool exhausted → requests queue or return 503, not 500
- Maintenance mode activation during active sessions → all non-admin requests receive 503

**Risk**: Medium to staging (temporary outage). No production action.

### Penetration Testing (PARTIAL)

| Area | Status |
|---|---|
| Authentication bypass | Tested via lockout and scope tests — no bypass found |
| IDOR (cross-squadron data access) | Tested for sqn_admin and sqn_general — all blocked correctly |
| XSS via API response values | `esc()` usage verified (182 calls, 180 innerHTML usages); not browser-tested |
| SQL injection via query params | FastAPI/SQLAlchemy parameterised queries used throughout; no raw SQL in user paths |
| JWT tampering | HS256 with 256-bit key; `python-jose` enforces signature; no test for alg=none attack |
| Access code brute force | Rate limiting proven; 5-failure lockout proven |
| Privilege escalation | Role checks in `permissions.py`; require_* pattern enforced; no test for parameter injection of role field |

**Gaps requiring follow-up (post-beta)**:
- Browser-level XSS test with `<script>` payload in a field value
- alg=none JWT header attack test
- HTTP verb override (X-HTTP-Method-Override) header test

---

## Resilience Summary

| Category | Complete | Pending |
|---|---|---|
| Backup/restore | ✓ Fully proven | — |
| Authentication resilience | ✓ Proven | — |
| IDOR/scope enforcement | ✓ Proven | — |
| SQL injection surface | ✓ Verified (parameterised) | — |
| XSS surface | ✓ Verified (esc()) | Browser test pending |
| Concurrent load | — | 100-user test pending (approval required) |
| Chaos/restart resilience | — | Pending (approval required) |
| Penetration (full) | Partial | JWT alg, verb override, XSS browser test |

**Release gate**: Backup/restore, authentication resilience, and IDOR enforcement are all proven. Load test and chaos test are pending but not blocking — beta release can proceed with documented gaps. Full penetration test is recommended before general availability.
