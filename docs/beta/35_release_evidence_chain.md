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
| Release candidate commit | `e539d02c25b00bc11a197b3324eb52c71efdb093` |
| RC tag | `beta-2026-07-14-rc2` |
| Tag object | Annotated tag on `e539d02` |
| Tag status | Pushed to origin: COMPLETE (2026-07-14) |
| Commit message | `fix: replace useBlocker with useLocation in useProxyGuard; fix 35 Playwright E2E tests` |
| Prior RC (superseded) | `beta-2026-07-14-rc1` → `e918f3e` — superseded; rc2 includes all rc1 changes plus the useBlocker crash fix |
| Files changed (total) | 4 source files + documentation |
| Evidence file | `docs/beta/34_release_candidate_record.md` |

**DEFECT-001, DEFECT-003, DEFECT-005 fixes** are committed on this branch and included in `e918f3e`. They require a production deployment to take effect.

---

## Link 2 — Automated Tests

| Metric | Value |
|---|---|
| Test runner | pytest |
| Total tests | 541 |
| Test outcome | 541 passed, 1 skipped, 0 failures |
| Test files | `backend/tests/` — 23 test modules |
| Key regression tests | `test_lockout.py`, `test_planning_access.py`, `test_idor_prevention.py`, `test_audit.py`, `test_session_lifecycle.py` |
| `datetime.utcnow()` deprecations | 0 (fixed on this branch) |
| Playwright E2E | 35/35 passed (useBlocker crash fixed in rc2) |
| Test run commit | `e539d02` (rc2) |
| Test run timestamp | 2026-07-14T13:15:00+0800 |

---

## Link 3 — Staging Deployment

| Field | Value |
|---|---|
| Staging environment ID | `77a45568` |
| Staging backend URL | `aafc-tms-backend-staging.up.railway.app` |
| Staging frontend URL | `aafc-tms-frontend-staging.up.railway.app` (connected-frontend) |
| Staging Planning Workspace | `aafc-tms-planning-workspace-preview-staging.up.railway.app` |
| Commit deployed to staging | `3cc7650` (release branch HEAD; RC code `e539d02` + docs update) |
| Staging backend deployment ID | `72b45f4b-17ab-48ba-acd1-dbfa1760b123` (current after R5 re-deploy: `ac20386b`) |
| Deployment timestamp | 2026-07-14T14:38–14:39Z (D2) |
| Deployment method | `railway deployment up ./backend --path-as-root --service aafc-tms-backend` |

Staging deployment confirmation: **COMPLETE (2026-07-14)**

---

## Link 4 — Database Migration

| Field | Value |
|---|---|
| Alembic head revision | `x9y0z1a2b3c4` (v36) |
| Migration applied in staging | CONFIRMED — deploy logs show "Migrations complete" with no errors (2026-07-14T14:39Z) |
| Migration applied in production | PENDING (requires production deployment) |
| Migration verification command | `GET /api/system/status` → `"alembic_revision": "x9y0z1a2b3c4"` |
| Staging migration status | COMPLETE (no-op at head; schema current) |
| Production migration status | PENDING |
| Evidence | Railway deploy logs D2 and R2: "Migrations complete" (D3/R4 steps) |

---

## Link 5 — Backend Health

| Field | Value |
|---|---|
| Health endpoint | `GET /api/health/ready` |
| Expected response | `{"status":"ready","squadrons":16}` |
| Staging health status | CONFIRMED — `{"status":"ready","squadrons":16}` at D1, D4, R3, R5 (2026-07-14) |
| Production health status | PENDING (after production deployment) |
| Last confirmed staging health | 2026-07-14T14:47Z (post-R5 re-deploy) |
| Verification method | `curl -s https://[env]-backend.up.railway.app/api/health/ready` |

---

## Link 6 — Frontend Health

| Interface | URL | Status |
|---|---|---|
| Connected TMS frontend (staging) | `aafc-tms-frontend-staging.up.railway.app` | CONFIRMED 200 (2026-07-14, D5) |
| Planning Workspace (staging) | `aafc-tms-planning-workspace-preview-staging.up.railway.app/planning` | CONFIRMED 200 (2026-07-14, D6) |
| Connected TMS frontend (production) | `aafc-tms-frontend-[production].up.railway.app` | PENDING browser verification |
| Planning Workspace (production) | `aafc-tms-planning-workspace-preview-[production].up.railway.app/planning` | PENDING |

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
| Staging rollback rehearsal | COMPLETE — executed 2026-07-14; all automated steps PASS |
| Rehearsal report | `docs/beta/41_deployment_rehearsal.md` |
| Rollback commands verified | COMPLETE — Railway GraphQL `deploymentRedeploy` mutation confirmed working |
| Rollback deployment ID used | `a76198bf-b70b-41da-812d-ad4ad647f484` (rollback of `2ad00fec` → SUCCESS) |
| Post-rollback health | `{"status":"ready","squadrons":16}` PASS |
| D7 browser smoke steps | PENDING human tester execution |

---

## Link 12 — Final Approval

| Field | Value |
|---|---|
| GO/NO-GO gate document | `docs/beta/13_executive_go_no_go.md` |
| Current status | NO-GO (100-user load test not done; browser verification, UAT, governance pending) |
| Remaining gates to close | 100-user load test; browser verification; UAT; data governance; key custody; smoke test; production deployment approval |
| Final approval authority | Named person — PENDING |
| Approval method | ___________________  |
| Approval date | ___________  |

---

## Evidence Chain Summary

| Link | Description | Status |
|---|---|---|
| 1 | Git commit `e539d02` / tag `beta-2026-07-14-rc2` | COMPLETE (tag pushed to origin 2026-07-14) |
| 2 | Backend: 541 tests pass; Playwright E2E: 35/35 pass | COMPLETE on rc2 |
| 3 | Staging deployment of release branch HEAD (`3cc7650`) | COMPLETE — deployment `72b45f4b` SUCCESS 2026-07-14 |
| 4 | Database migration `x9y0z1a2b3c4` applied | COMPLETE — staging migration logs confirmed 2026-07-14 |
| 5 | Backend health `squadrons:16` | COMPLETE — confirmed at D1, D4, R3, R5 (2026-07-14) |
| 6 | Frontend HTML loading (staging) | COMPLETE — connected frontend + Planning Workspace: 200 |
| 7 | Browser login verification (2 squadrons, 2 roles) | PENDING human tester |
| 8 | Cross-interface data consistency | PENDING (UAT) |
| 9 | Security tests (IDOR, auth, role isolation) | PENDING test run |
| 10 | Performance / load test | PENDING — 100-user load test not yet run |
| 11 | Rollback rehearsal in staging | COMPLETE — D1–D7/R1–R5 executed 2026-07-14; all automated steps PASS |
| 12 | Final GO/NO-GO approval | PENDING |

**Links 1–6 and 11 are complete (automated gates). Links 7–10 and 12 remain pending human execution, approval, or load test.**

This document must be fully populated before the release is approved.
