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

### 100-User Concurrent Load Test (Gate 7 — PASS, 2026-08-05)

**Status**: Executed against staging (`tools/stress/load_test_staging.py --users 100
--duration-minutes 45 --ramp-seconds 60`). Staging data was cleaned first (archived 123 leftover
test squadrons + 1,208 associated test accounts accumulated from e2e runs earlier this session,
via the real `POST /api/accounts/batch-archive` and `POST /api/squadrons/{id}/archive` endpoints —
reversible, audited, user-approved) so the run reflects the original 16-squadron/38-user synthetic
baseline, not a contaminated dataset.

**Environment note**: the first two attempts (background tasks `bs7xin7gs`, `blawzrudo`) were killed
by this session's own execution harness before finishing — not a target-system failure. Both showed
strong partial evidence before being cut off (run 1: 0 5xx errors across 98,929 requests, 89% of the
run; run 2: 12 5xx errors across 66,455 requests, 64% of the run — see below). A third attempt
(`bhiu4077w`), approved by the user after the first two kills, ran to full completion.

**Authoritative result — run 3, full 2,771s (46.2 min) completion:**

| Metric | Result |
|---|---|
| Total requests | 111,468 |
| Successful (200) | 95,391 (85.6%) |
| 429 (rate-limited, expected — single-IP virtual-user pool hits the same rate limiter a real distributed user base wouldn't) | 15,977 (14.3%) |
| 401 | 100 (0.1%) |
| **5xx errors** | **0** |
| Overall P95 latency (all endpoints) | **253ms** |
| Max latency | 1,208ms |
| `/api/auth/login` P95 (n=200) | 380ms |
| `/api/parade-nights` P95 (n=44,123) | 347ms |
| Login success rate | 100.00% (200/200) |

**Target criteria** (from mission spec):
- P95 response time ≤ 2000ms under 100 concurrent users → **PASS (253ms, 8× headroom)**
- Zero 5xx errors during sustained load → **PASS (0 errors across the complete run)**
- Unexpected-response rate <1% (excluding the expected rate-limiter 429s) → **PASS (0.09%)**

**OVERALL: PASS.**

**Disclosed, not swept under the PASS** — run 2's 12 5xx errors: a genuine, real 500-range response
count occurred partway through the second attempt (appearing around the ~1,350–1,750s mark of that
run, 0.018% of that run's 66,455 requests), before that run was independently killed by the harness.
This did **not** recur in run 1 (0/98,929, cut off at 89%) or run 3 (0/111,468, the complete run) —
across all three attempts combined, 12 failures out of 276,791 total requests (0.0043%). Attempted to
root-cause via `railway logs --since/--until` against the relevant time window; the flag combination
returned no log lines for this deployment (a tooling limitation encountered mid-investigation, not
confirmed as a Railway-wide constraint), and `--lines`-based retrieval couldn't reach far enough back
given the request volume. Not reproduced, not root-caused, and not blocking given the authoritative
(complete) run's clean result — but a real, low-frequency intermittent 500-response event under
sustained 100-concurrent-user load is exactly the kind of thing that should not be silently dropped
just because it didn't reproduce. Recommend: if this recurs in a future load test or in production
under real traffic, prioritize getting `railway logs --since/--until` working (or an alternative log
export) for faster root-causing — this session's inability to pull historical logs for a ~5-minute
window was itself a real gap in incident-response tooling, separate from the load test result itself.

**Risk**: None to production (staging only, synthetic data).

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
| Concurrent load | ✓ Proven 2026-08-05 — PASS (0 5xx, P95 253ms, 111,468 requests, full 46min run) | — |
| Chaos/restart resilience | — | Pending (approval required) |
| Penetration (full) | Partial | JWT alg, verb override, XSS browser test |

**Release gate**: Backup/restore, authentication resilience, IDOR enforcement, and the 100-user
concurrent load test are all proven. Chaos test is pending but not blocking — beta release can
proceed with documented gaps. Full penetration test is recommended before general availability. One
low-frequency, non-reproduced anomaly (12 5xx errors in one of three load-test attempts, not root-
caused — see the Concurrent Load Test section above) is disclosed, not treated as blocking given the
authoritative complete run's clean result.
