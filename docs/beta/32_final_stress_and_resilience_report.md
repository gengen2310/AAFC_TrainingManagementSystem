# AAFC TMS — Final Stress and Resilience Report

Phase 16/32 output. Documents all resilience testing completed and pending.
Created: 2026-07-14.

---

## Completed Resilience Tests

### Backup and Restore (Phase 6 — PROVEN)

**Re-verified 2026-08-05 as Gate 5 of the formal 11-gate release process** (the July 14 run IDs
below are superseded — kept for history, current evidence is the 2026-08-05 rows):

| Test | Result | Evidence |
|---|---|---|
| Production backup (pg_dump → GPG-encrypted artifact) | PASS | Run [`31020353143`](https://github.com/gengen2310/AAFC_TrainingManagementSystem/actions/runs/31020353143), 2026-08-05 — artifact `postgresql-production-backup-20260805_152727` |
| SHA-256 integrity check on decrypted dump | PASS | Same run — computed hash matched stored checksum exactly |
| Production restore into ephemeral Postgres (schema + row counts) | PASS | Run [`31020333935`](https://github.com/gengen2310/AAFC_TrainingManagementSystem/actions/runs/31020333935), 2026-08-05 — 15/15 checks passed: `alembic_version` matched expected head, all 12 required tables present and readable (users=19, wings=1, squadrons=15, audit_logs=161, system_settings=7, access_codes=19, proxy_sessions=1, curriculum_items=214, planning_years=5), users≥1 confirmed |
| Application-level restore (real backend process against restored DB, real authenticated API reads) | PASS | Same run — spun up the actual FastAPI app against the restored database, logged in as a throwaway restore-test admin, then 8/8 authenticated reads succeeded: `/api/health/ready` (squadrons=15), `/api/auth/me`, `/api/wings` (1), `/api/squadrons` (15), `/api/users` (20), `/api/planning/years` (5), `/api/planning/facilitators` (0) |
| Daily backup schedule | ACTIVE | `.github/workflows/backup-postgresql.yml` |
| Weekly restore-test schedule | ACTIVE | `.github/workflows/test-restore-postgresql.yml` |

Recovery Time Objective (demonstrated): both workflows ran in under 2 minutes combined (restore-test
job 1m7s, backup job 31s) in a GitHub Actions runner.

**Note on timing relative to REM-77**: this backup/restore pair ran ~40 minutes before the REM-77
P0 migration (`5a195a98148a`) was deployed to production, so the restored database's
`alembic_version` reflects the prior head (`81734c0f34bf`), not a gap in the restore mechanism
itself — the check correctly compares against the dynamically-computed expected head at time of
run, not a hardcoded value. The mechanism is proven end-to-end regardless of which head is current;
the next scheduled daily/weekly run will naturally pick up the new head.

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
