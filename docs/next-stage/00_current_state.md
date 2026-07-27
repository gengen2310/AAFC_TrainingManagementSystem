# AAFC TMS — Phase 0 Current State Verification

Next-Stage Development Program. Verified 2026-07-16.
Branch: `next-stage/v1-operational` (created from `release/beta-2026-07-14` @ `43b880c`).

---

## Repository

```
pwd:    /Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v17_1_source
root:   /Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v17_1_source
remote: origin → https://github.com/gengen2310/AAFC_TrainingManagementSystem.git
branch: next-stage/v1-operational  (created from 43b880c)
status: CLEAN
```

### Git Log (last 10)

```
43b880c (HEAD, origin/release/beta-2026-07-14) docs: record load test run 3 CONDITIONAL PASS
03cc7d5 docs: two 100-user load test runs collided — DEFECT-010, not release evidence
5182077 docs: update execution checkpoint — rc3, load test runs 1–3, DEFECT-007
f9408ad docs: update release gate docs for rc3, load test runs 1–3, DEFECT-007
d95e67d (tag: beta-2026-07-14-rc3) fix: scope sqn_general out of /api/planning/years list (DEFECT-007)
37e0d25 docs: resolve two stale checkpoint tasks, reconfirm backend test gate
8cec1c1 docs: add missing architecture.md/beta-release skill; record load-test findings
0ca4fe8 docs: execution checkpoint — corrected load test running (baw9zh1fw)
2e1f437 docs: record staging deployment and rollback rehearsal results (2026-07-14)
3cc7650 docs: update release gate docs to reflect rc2 state
```

### Tags

```
beta-2026-07-14-rc1  → e918f3e  (superseded)
beta-2026-07-14-rc2  → e539d02  (superseded)
beta-2026-07-14-rc3  → d95e67d  (current frozen RC — beta release candidate)
v17.1
```

### Worktrees

```
/Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v17_1_source          43b880c [release/beta-2026-07-14]
/Users/jennydv/Desktop/.../worktrees/agent-a384acc669dbfca9c                           96f2781 [worktree-agent-a384acc669dbfca9c]  ← orphaned; safe to prune
```

---

## Database / Migrations

| Field | Value |
|---|---|
| Alembic head | `x9y0z1a2b3c4` (v36 — cea_import_batch_created_by) |
| Local SQLite current | `v7w8x9y0z1a2` (v34) — **2 revisions behind** |
| Staging current | At head (Railway applies `alembic upgrade head` on deploy) |
| Production current | At head (Railway applies `alembic upgrade head` on deploy) |

Local SQLite is behind because v35 and v36 were written after the last local `alembic upgrade head`. This only affects local development; staging and production are current.

**Action: run `alembic upgrade head` locally before writing migration v37.**

---

## Services and Health

| Service | URL | Status | Response |
|---|---|---|---|
| Production backend | `https://aafc-tms-backend-production.up.railway.app` | ✅ UP | `{"status":"ready","squadrons":16}` |
| Production frontend (Main TMS) | `https://aafc-tms-frontend-production.up.railway.app` | Not verified by curl | |
| Production Planning Workspace | `https://aafc-tms-planning-workspace-preview-production.up.railway.app/planning` | Not verified by curl | |
| Staging backend | `https://aafc-tms-backend-staging.up.railway.app` | ✅ UP | `{"status":"ready","squadrons":16}` |
| Staging frontend | `https://aafc-tms-frontend-staging.up.railway.app` | Not verified | |
| Staging Planning Workspace | `https://aafc-tms-planning-workspace-preview-staging.up.railway.app/planning` | Not verified | |

**Note:** Production `/api/system/status` returns 404 (endpoint protected or removed). Deployed commit confirmed only from Railway deploy history in prior sessions.

---

## Deployed Commit State

| Environment | Last known deployed commit | What is missing |
|---|---|---|
| Production backend | ~`3cc7650` (rc2-era docs, pre-rc3) | DEFECT-001, -003, -005, -007 fixes |
| Staging backend | `ac20386b` deployment (rc2 code `e539d02`) | DEFECT-007 fix (rc3) |
| Production frontend | `ce2420c3` deployment | — |
| Staging frontend | `ce2420c3` | — |

**DEFECT-001 and DEFECT-007 (IDOR fixes) are NOT in production.** No sqn_general users should be activated until these are deployed.

---

## Beta Release Gate State

| Gate | Status |
|---|---|
| RC3 created and pushed | ✅ `d95e67d` / `beta-2026-07-14-rc3` |
| Backend tests: 544 pass | ✅ (`d95e67d`) |
| TypeScript: 0 errors | ✅ |
| Playwright E2E: 35/35 pass | ✅ (local backend, rc3) |
| Security greps: all clean | ✅ |
| DEFECT-007 fixed + 2 regression tests | ✅ |
| Post-load data integrity | ✅ |
| Load test — authoritative run 5 (clean solo): 106,151 req, P95=830ms, 0 real 5xx | ✅ PASS (runs 3/4 INVALID — concurrent collision DEFECT-010) |
| Staging deployment rehearsal (D1–D7) | ✅ |
| Staging rollback rehearsal (R1–R5) | ✅ |
| Backup/restore (production data) | ✅ |
| Browser verification (staging) | ⚠️ PENDING — human |
| UAT (4 testers × 20 tasks) | ⚠️ PENDING — human |
| Data governance (9 decisions) | ⚠️ PENDING — human |
| Backup key custody (5 actions) | ⚠️ PENDING — human |
| D7 browser smoke test | ⚠️ PENDING — human |
| Production DEFECT deploys | ⚠️ PENDING — approval required |
| Production smoke test | ⚠️ PENDING — after deployment |
| Explicit production approval | ⚠️ PENDING |
| **Overall** | **NO-GO** |

---

## Automated Test Counts

| Suite | Count | Files |
|---|---|---|
| Backend pytest | 544 collected | 23 test modules in `backend/tests/` |
| Playwright E2E | 35 tests | 7 spec files in `frontend/e2e/` |

### Playwright Spec Files

| File | Focus |
|---|---|
| `auth.spec.ts` | Login, logout, session handling |
| `cross-interface.spec.ts` | Cross-frontend data consistency |
| `dashboard.spec.ts` | Dashboard data display |
| `holiday-and-resources.spec.ts` | Holidays, rooms, equipment |
| `navigation.spec.ts` | Nav scope per role |
| `session-lifecycle.spec.ts` | Token expiry, refresh |
| `wing-proxy.spec.ts` | Proxy Mode, Intervention Mode |

**Not covered:** parade nights CRUD, scheduling (create/cancel/reschedule), facilitator assignment, leave conflicts, room/equipment conflicts, weekly program, reports, maintenance mode, year rollover, multi-Wing.

---

## Backend Routers (12)

| File | Prefix | Key areas |
|---|---|---|
| `accounts.py` | `/api/accounts` | User/account management |
| `auth.py` | `/api/auth` | Login, logout, me, refresh |
| `export_import.py` | `/api/export`, `/api/import` | CSV/XLSX/PDF export, program import |
| `health.py` | `/api/health` | Health checks |
| `ops.py` | `/api/` | Parade nights, activities, CEA, import |
| `organisations.py` | `/api/` | Wings, squadrons, flights |
| `planning.py` | `/api/planning` | Planning years, sessions, schedules |
| `program.py` | `/api/program` | Program packages, program items |
| `system.py` | `/api/system` | System admin, maintenance, bootstrap |
| `timing.py` | `/api/timing` | Timing templates, blocks |
| `training.py` | `/api/training` | Curriculum, facilitators, resources, activities |
| `wing_calendar.py` | `/api/wing-calendar` | Wing HQ calendar events |

---

## Models (7 files)

| File | Key models |
|---|---|
| `organisations.py` | `NationalEntity`, `Wing`, `Squadron`, `Flight`, `User`, `AccessCode`, `AuditLog`, `IpLoginAttempt`, `SystemSetting` |
| `operations.py` | `ParadeNight`, `ParadeDate`, `ActionItem`, `SystemSetting`, `JobStatus` |
| `planning.py` | `PlanningYear`, `AnchorPrepPlan`, `ParadeDateEntry`, `ScheduledSession`, `PlanningLocation`, `PlanningConflict`, `PlanningFacilitatorLeave`, `PlanningNotice`, `CeaImportBatch` |
| `training.py` | `CurriculumItem`, `Facilitator`, `FacilitatorRankHistory`, `TrainingArea`, `Equipment`, `Activity`, `Cadet`, `CEAActivity`, `WingActivity` |
| `program.py` | `ProgramPackage`, `ProgramItem`, `JobStatus` |
| `wing_calendar.py` | `WingCalendarEvent` |
| `operations.py` | `ActionItem`, `ImportRecord`, `ImportRow` |

---

## Frontend Structure

### Connected TMS (`connected-frontend/index.html`)

Single-file SPA, ~8,000 lines. Active page divs:

`dashboard`, `calendar`, `parade-nights`, `weekly-program`, `curriculum`, `activities`,
`facilitators`, `resources`, `reports`, `action-items`, `settings`, `accounts`,
`wing-overview`, `wing-calendar`, `national`, `curriculum-coverage`, `training-balance`,
`facilitator-load`, `risk-bottlenecks`, `audit`, `system-console`

**Legacy redirect:** `nav('planning-year')` → `'activities'` (line 2997)

**Stale text:** Line 6842 still says "Annual Program" linking to `nav('planning-year')` — functionally works (redirect exists) but misleading.

### Planning Workspace (`frontend/`)

React + Vite + TypeScript. Component structure:
- `src/components/` — DrilldownPanel, ErrorBoundary, Modal, Paginated, status/, ui.tsx
- `src/planning/` — Planning Workspace pages
- `src/routes/` — route definitions
- `src/auth/` — auth utilities
- `e2e/` — 7 Playwright spec files (35 tests)

---

## Overlapping Data Models

### A. Location/Space Models (CONFIRMED OVERLAP)

| Field | `TrainingArea` (`training.py`) | `PlanningLocation` (`planning.py`) |
|---|---|---|
| Table | `training_areas` | `planning_locations` |
| Squadron FK | `squadron_id` | `unit_id` (same table) |
| Name | `name` String(120) | `name` String(120) |
| Type | `type` String(40) | `location_type` String(30) |
| Capacity | `capacity` Integer | `capacity` Integer |
| Active | `active_status` Boolean | `active_status` Boolean |
| Soft delete | ✅ `SoftDeleteMixin` | ✗ none |
| Notes | `notes` Text | `notes` Text |
| Indoor/outdoor | `indoor_outdoor` String(20) | — |
| Avail. status | `availability_status` String(20) | — |
| Created by | — | `created_by` String(36) |

Planning Workspace resolves locations from EITHER table (planning.py:1205–1208 — checks PlanningLocation first, falls back to TrainingArea). Two sources of truth for the same physical concept.

### B. Facilitator Models (MINOR — less severe)

`Facilitator` is the ONE canonical model. `PlanningFacilitatorLeave` is a supplement (not a duplicate record). Both live under the same `facilitators.id`. Gap: leave records visible in Planning Workspace but not in Main TMS facilitator page.

---

## Identity and Concurrency State

**Identity:** Shared access codes only. `User.display_name` is a role name, not a person's name. No individual accountability. `created_by` fields identify the role user, not a person.

**Concurrency:** No optimistic locking. No `version`/`etag`/`revision` fields on any mutable model. All writes are last-write-wins.

---

## Multi-Wing State

**Core RBAC:** Multi-Wing capable — all tenancy checks use `wing_id` FK lookups.

**Hardcoded 7WG references (to remediate):**

| Location | Line | Content | Action |
|---|---|---|---|
| `auth.py` | 21 | "Contact 7 Wing SOCAD for access." | Generalise message |
| `system.py` | 413 | `Wing.code == "7WG"` | Make configurable |
| `system.py` | 417 | "7WG_not_found" error code | Generalise |
| `system.py` | 430 | "703 Squadron AAFC" hardcoded | Make configurable |
| `system.py` | 438 | "7WG Wing Admin" display_name | Make configurable |
| `seed_all.py` | passim | 7WG seed data | Intentional demo; keep |

---

## Installed Infrastructure (not fully connected)

| Component | State |
|---|---|
| Celery worker | File exists (`backend/app/workers/celery_app.py`); `generate_export` task is a placeholder stub; not running in production |
| Redis | `REDIS_URL` in config; not provisioned in Railway |
| `JobStatus` model | Exists (`program.py`); no API endpoint exposes job status to frontend |
| DB-backed rate limiter | Fully operational (`IpLoginAttempt` + `login_blocked_db`); covers login endpoint only |

---

## GitHub Workflows (4)

| Workflow | Schedule | Target |
|---|---|---|
| `backup-postgresql.yml` | Daily 18:00 UTC (02:00 AWST) | Production |
| `test-restore-postgresql.yml` | Weekly | Production backup artefacts |
| `backup-postgresql-staging.yml` | Manual/on-push | Staging |
| `test-restore-postgresql-staging.yml` | Manual | Staging backup artefacts |

---

## Open Defects

| ID | Description | Fixed | In Production |
|---|---|---|---|
| DEFECT-001 | sqn_general IDOR (parade-nights/general) | ✅ on branch | ❌ |
| DEFECT-003 | ENVIRONMENT=staging in production | ✅ code fix | ❌ (Railway var pending) |
| DEFECT-005 | Planning Workspace stale Dockerfile | ✅ on branch | ❌ |
| DEFECT-007 | sqn_general planning years IDOR | ✅ rc3 | ❌ |
| DEFECT-008 | Stash revision collision | ⚠️ deferred | — |

---

## Next-Stage Program Entry State

This document captures the exact state at program start. The next-stage program begins with:
- Beta RC3 frozen on `release/beta-2026-07-14` at `43b880c` — do not edit that branch
- All next-stage work on `next-stage/v1-operational`
- No production deployments until human gates complete
- All 25 gaps classified in `01_gap_matrix.md`
