# AAFC TMS — Release Evidence Chain

Phase 3 (Operational Release Gate). Proves every link in the chain from git commit to browser.
Created: 2026-07-14.

---

## Purpose

This document provides traceability from source code to production deployment. It is the single reference that answers "what was shipped, when, and with what evidence?"

---

## Link 1 — Git Commit

| Field | Value |
|---|---|
| Branch | `release/beta-2026-07-14` |
| Release candidate commit | `e918f3e654179355fe100fda285452844bdcbea0` |
| RC tag | `beta-2026-07-14-rc1` |
| Tag object | Lightweight tag on `e918f3e` |
| Tag status | Created locally; pushed to origin: PENDING |
| Commit message | `feat: remove 9 dead planning divs, simplify nav hook, fix ops N+1` |
| Files changed (total) | 4 source files + documentation |
| Evidence file | `docs/beta/34_release_candidate_record.md` |

**DEFECT-001, DEFECT-003, DEFECT-005 fixes** are committed on this branch and included in `e918f3e`. They require a production deployment to take effect.

---

## Link 2 — Automated Tests

| Metric | Value |
|---|---|
| Test runner | pytest |
| Total tests | 503 |
| Test outcome | PENDING re-run on clean RC (run before production deployment) |
| Test files | `backend/tests/` — 22 test modules |
| Key regression tests | `test_lockout.py`, `test_planning_access.py`, `test_idor_prevention.py`, `test_audit.py` |
| `datetime.utcnow()` deprecations | 0 (fixed on this branch) |
| Required evidence | pytest exit code 0 from `backend/` on commit `e918f3e` |

**Before production deployment**: run `cd backend && python -m pytest` and record the result in this document.

Actual test run result: **PENDING**
Test run timestamp: ___________
Test run commit: ___________

---

## Link 3 — Staging Deployment

| Field | Value |
|---|---|
| Staging environment ID | `77a45568` |
| Staging backend URL | `aafc-tms-backend-staging.up.railway.app` |
| Staging frontend URL | `aafc-tms-frontend-staging.up.railway.app` (connected-frontend) |
| Staging Planning Workspace | `aafc-tms-planning-workspace-preview-staging.up.railway.app` |
| Commit deployed to staging | `e918f3e` (to be confirmed) |
| Staging deployment ID | PENDING |
| Deployment timestamp | PENDING |
| Deployment method | `railway up` or Railway GitHub integration |

Staging deployment confirmation: **PENDING**

---

## Link 4 — Database Migration

| Field | Value |
|---|---|
| Alembic head revision | `x9y0z1a2b3c4` (v36) |
| Migration applied in staging | PENDING confirmation |
| Migration applied in production | PENDING (requires production deployment) |
| Migration verification command | `GET /api/system/status` → `"alembic_revision": "x9y0z1a2b3c4"` |
| Staging migration status | PENDING |
| Production migration status | PENDING |
| Evidence | Railway deploy logs; `system/status` response |

---

## Link 5 — Backend Health

| Field | Value |
|---|---|
| Health endpoint | `GET /api/health/ready` |
| Expected response | `{"status":"ready","squadrons":16}` |
| Staging health status | PENDING |
| Production health status | PENDING (after production deployment) |
| Last confirmed staging health | Not confirmed this session |
| Verification method | `curl -s https://[env]-backend.up.railway.app/api/health/ready` |

---

## Link 6 — Frontend Health

| Interface | URL | Status |
|---|---|---|
| Connected TMS frontend | `aafc-tms-frontend-[env].up.railway.app` | PENDING |
| Planning Workspace | `aafc-tms-planning-workspace-preview-[env].up.railway.app/planning` | PENDING |

Verification method: load each URL in Chrome; confirm HTML loads with status 200.

---

## Link 7 — Browser Verification

| Field | Value |
|---|---|
| Requirement | At least 2 squadron profiles verified across 2 roles in staging |
| Current status | PENDING — requires human tester with staging access |
| Full matrix | `docs/beta/26_squadron_verification_matrix.md` |
| Blocking for | Production deployment |

Minimum acceptable evidence before release:
- At least 1 sqn_admin login confirmed
- At least 1 sqn_general login confirmed
- Wing calendar visible for wing_admin
- National overview visible for national_admin

---

## Link 8 — Cross-Interface Data Verification

| Field | Value |
|---|---|
| Requirement | A training session created via connected TMS is visible in Planning Workspace, and vice versa |
| Test scope | At least 1 record round-trip per interface (UAT tasks 13–18 cover this) |
| Current status | PENDING — requires UAT |
| Evidence source | `docs/beta/38_user_acceptance_results.md` |

---

## Link 9 — Security Tests

| Test | Tool/Method | Status | Evidence |
|---|---|---|---|
| IDOR prevention | pytest `test_planning_access.py` | PENDING test run on RC | Exit code 0 |
| Authentication lockout | pytest `test_lockout.py` | PENDING test run on RC | Exit code 0 |
| Role isolation | pytest `test_role_isolation.py` | PENDING test run on RC | Exit code 0 |
| XSS input sanitisation | pytest (HTML encoding tests) | PENDING test run on RC | Exit code 0 |
| SQL injection | pytest (parameterised queries — no concatenated SQL) | PENDING test run on RC | Exit code 0 |
| CORS origin whitelist | Code review | COMPLETE | `backend/app/main.py` CORS config uses explicit origin list, not `*` |
| Secrets scan | `grep -r "sk-" backend/ frontend/` | COMPLETE | 0 matches |
| Rate limiting | `RATE_LIMIT_REQUESTS` env var | COMPLETE | Configured in Railway staging |

---

## Link 10 — Performance Tests

| Test | Status | Evidence |
|---|---|---|
| 100-user concurrent login simulation | NOT STARTED — requires staging environment | PENDING |
| Wing overview query time (<500ms at 16 sqn) | Code verified; N+1 documented but safe at 16 sqn | Documented in `29_code_inventory_and_review.md` |
| Backup/restore operation | Tested against staging database | `04_backup_restore_test_report.md` |

100-user load test gate: **PENDING — requires explicit approval to execute against staging**

---

## Link 11 — Rollback Rehearsal

| Field | Value |
|---|---|
| Rollback plan | `docs/beta/42_release_stop_and_rollback_plan.md` |
| Staging rollback rehearsal | PENDING — required before production deployment |
| Rehearsal report | `docs/beta/41_deployment_rehearsal.md` |
| Rollback commands verified | PENDING |

---

## Link 12 — Final Approval

| Field | Value |
|---|---|
| GO/NO-GO gate document | `docs/beta/13_executive_go_no_go.md` |
| Current status | CONDITIONAL GO |
| Remaining gates to close | Production deployment approval, browser verification, UAT, rollback rehearsal |
| Final approval authority | Named person — PENDING |
| Approval method | ___________________  |
| Approval date | ___________  |

---

## Evidence Chain Summary

| Link | Description | Status |
|---|---|---|
| 1 | Git commit `e918f3e` / tag `beta-2026-07-14-rc1` | COMPLETE (tag push pending) |
| 2 | Automated tests: 503 tests | PENDING re-run on RC |
| 3 | Staging deployment of `e918f3e` | PENDING |
| 4 | Database migration `x9y0z1a2b3c4` applied | PENDING |
| 5 | Backend health `squadrons:16` | PENDING |
| 6 | Frontend HTML loading | PENDING |
| 7 | Browser login verification (2 squadrons, 2 roles) | PENDING |
| 8 | Cross-interface data consistency | PENDING (UAT) |
| 9 | Security tests (IDOR, auth, role isolation) | PENDING test run |
| 10 | Performance / load test | PENDING approval |
| 11 | Rollback rehearsal in staging | PENDING |
| 12 | Final GO/NO-GO approval | PENDING |

**Links 1 is complete. Links 2–12 are pending human execution, approval, or external action.**

This document must be fully populated before the release is approved.
