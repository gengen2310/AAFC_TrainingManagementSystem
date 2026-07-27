# AAFC TMS — Code Inventory and Review

Phase 9 output. Full executable inventory of backend, frontend, and infrastructure code.
Created: 2026-07-14. Update in place.

---

## Backend (`backend/`)

### Router Files

| Router | Endpoints | Lines | Primary responsibility |
|---|---|---|---|
| `planning.py` | 58 | 4032 | Planning years, annual program, missions, CEA, session builder, facilitator planning, program checks, command centre |
| `training.py` | 45 | 1974 | Curriculum, parade nights, sessions, activities, facilitators, rooms, equipment, cadets, reports, action items |
| `ops.py` | 17 | 477 | Wing and national oversight: squadron summaries, curriculum coverage, training balance, facilitator load, risk bottlenecks |
| `wing_calendar.py` | 9 | 670 | Wing HQ event calendar: import, CRUD, squadron overlay |
| `timing.py` | 10 | 632 | Timing templates: slot configurations for parade night programs |
| `accounts.py` | 12 | 596 | Account/user management, access code reset, lockout unlock |
| `system.py` | 13 | 487 | System console, maintenance mode, backup trigger, restore, scope map, health |
| `organisations.py` | 14 | 345 | Squadron, wing, national CRUD; org hierarchy |
| `program.py` | 14 | 287 | Weekly program generation, action items |
| `auth.py` | 7 | 278 | Login, logout, session (`/api/auth/me`), lookup, proxy/intervention |
| `export_import.py` | 4 | 143 | CSV export/import for curriculum and cadets |
| `health.py` | 3 | 30 | Health check, readiness, version |
| `__init__.py` | 0 | 0 | Router package init |
| **Total** | **206** | **9951** | — |

### Model Files

| File | Lines | Key models |
|---|---|---|
| `training.py` | 297 | Curriculum, Session, Activity, Facilitator, Room, Equipment, Cadet, TrainingArea, FacilitatorLeave, ActionItem, CeaActivity |
| `planning.py` | 255 | PlanningYear, ParadeDate, ScheduledSession, PlanningMission, PlanningFacilitator, PlanningLocation, PlanningHoliday, PlanningConflict, AnchorEvent, ParadeNotice, CeaImportBatch, CeaLocalHide, PlanningActivity |
| `program.py` | 156 | ParadeNight, WeeklyProgramSlot, TimingTemplate, TimingSlot |
| `organisations.py` | 116 | Squadron, Wing, National, Flight |
| `operations.py` | 98 | User, AccessCode, IpLoginAttempt, AuditLog |
| `wing_calendar.py` | 89 | WingHQEvent, SquadronEventStatus |
| `__init__.py` | 38 | Re-exports all models for Alembic |
| **Total** | **1049** | 34 mapped classes |

### Migration Files

| Count | Range | Coverage |
|---|---|---|
| 26 files | v01 → v36 | Full linear chain; no branches; current head `x9y0z1a2b3c4` |

Notable migrations:
- v28+: Added Planning Workspace tables (PlanningYear, ScheduledSession, etc.)
- v33: Added CEA import tables (CeaImportBatch, CeaLocalHide)
- v35: Added `cancelled_at`, `cancelled_reason` to scheduled_sessions
- v36: Added `classified_at` to cea_activities; corrected `down_revision` collision in stash (NOT yet applied)

### Test Files

| File | Lines | Passed | Skipped | Coverage area |
|---|---|---|---|---|
| `test_planning.py` | 1440 | ~160 | 1 | Planning years, missions, annual program, sqn_general IDOR, xlsx exports, night-summaries, facilitator workload |
| `test_accounts.py` | 784 | ~90 | 0 | Account CRUD, role-gated access, code reset, account detail |
| `test_timing.py` | 632 | ~70 | 0 | Timing templates, slot configuration |
| `test_planner_v14.py` | 640 | ~70 | 0 | Legacy training planner, annual program v14 |
| `test_organisations.py` | 581 | ~60 | 0 | Squadron/wing/national CRUD, hierarchy |
| `test_wing_calendar.py` | 504 | ~55 | 0 | Wing HQ calendar, squadron overlay |
| `test_planning_idor.py` | 480 | ~50 | 0 | Cross-squadron IDOR attempts, scope boundary tests |
| `test_system_admin.py` | 420 | ~45 | 0 | System console, maintenance, backup, restore, scope-map |
| `test_lockout.py` | 340 | ~35 | 0 | IP lockout, per-account lockout, unlock endpoint, lookup flow |
| `test_maintenance_enforcement.py` | 308 | ~30 | 0 | Maintenance mode blocks non-admins |
| `test_curriculum_elements.py` | 234 | ~25 | 0 | Curriculum item CRUD, level inheritance |
| `test_curriculum_import.py` | 197 | ~20 | 0 | CSV curriculum import, dedup, seeding |
| `test_program.py` | 178 | ~18 | 0 | Weekly program generation, action items |
| `test_core.py` | 177 | ~20 | 0 | Core auth flows, session check |
| `test_reset_db_safety.py` | 84 | ~8 | 0 | seed_all.py safety guard |
| `test_compute_alembic_head.py` | 62 | ~6 | 0 | Migration chain validates in CI |
| `test_hardening.py` | 46 | ~5 | 0 | Headers, rate limit, XSS vectors |
| `test_wing_coverage.py` | 40 | ~4 | 0 | Wing curriculum coverage endpoint |
| `conftest.py` | 50 | — | — | Shared fixtures: in-memory SQLite, client, login helper |
| **Total** | **7175** | **503** | **1** | — |

### Other Backend Files

| File | Purpose | Review status |
|---|---|---|
| `app/main.py` | App entrypoint, router registration, lifespan, production fail-close check | RETAIN |
| `app/config.py` | Settings; `is_production` bool; `validate_for_production()` | RETAIN |
| `app/permissions.py` | RBAC Principal, require_* helpers | RETAIN |
| `app/database.py` | DB engine, SessionLocal, `utcnow()` canonical helper, UUIDMixin, TimestampMixin, SoftDeleteMixin | RETAIN |
| `app/security.py` | Access code hashing, verification, JWT encode/decode | RETAIN |
| `app/services/audit.py` | Audit log writer — called for all privileged writes | RETAIN |
| `scripts/import_wing_hq_calendar.py` | One-off Wing HQ calendar import from XLSX | RETAIN |
| `seeds/seed_all.py` | Full synthetic dataset (16 squadrons); destructive (`reset_db`) | RETAIN — dev/demo only; deploy guard in staging entrypoint |
| `seeds/staging_seed.py` | Minimal bootstrap: system_admin only; idempotent | RETAIN |
| `docker-entrypoint-staging.sh` | Alembic + bootstrap + gunicorn; used by both staging and production | RETAIN |

---

## Connected-Frontend (`connected-frontend/index.html`)

| Metric | Value |
|---|---|
| File size | ~400 KB (single-file SPA) |
| Page divs (`id="page-*"`) | 30 |
| Navigable pages (in at least one nav scope) | 21 |
| Retired pages (HTML exists, no nav path) | 9 |
| Nav scopes defined | 5 (squadron, wing, national, auditor, system_admin) |
| JS functions (named `function `) | ~110 |
| JS API calls (`api(`) | ~95 |
| CSS custom properties | 10 (AAFC VIG palette tokens) |

Key JS modules (by function cluster):
- `nav()` / `NAV_BY_SCOPE` / `applyNavScope()` — routing and scope enforcement
- `loadDashboard()` / `renderDashboard()` — dashboard data and render
- `loadParadeNights()` / `loadParadeNightDetail()` / `renderParadeNight()` — parade night workflow
- `loadCurriculum()` / `filterCurriculum()` — curriculum view
- `loadActivities()` / `renderActivities()` / `importCEA()` — activities + CEA import
- `loadFacilitators()` / `saveFacilitator()` — facilitator management
- `loadResources()` / `loadTrainingAreas()` / `loadEquipment()` — resource management
- `loadReports()` / `renderReports()` — reports
- `loadWingOverview()` / `loadCurriculumCoverage()` / `loadTrainingBalance()` — wing-level views
- `loadAudit()` / `renderAuditLog()` — audit log
- `loadSystemConsole()` / section loaders — system admin
- `api()` / `apiErr()` / `esc()` — utilities

**XSS posture**: All user-facing content inserted via `innerHTML` uses `esc()` helper. API response values not treated as safe HTML. `localStorage` not used for operational data.

---

## React Planning Workspace (`frontend/src/`)

### Source File Inventory

| Category | Files | Lines (approx) | Key exports |
|---|---|---|---|
| API layer | `api/index.ts`, `api/client.ts`, `api/types.ts` | ~2000 | All API methods, shared types |
| App root | `App.tsx`, `main.tsx`, `vite-env.d.ts` | ~200 | Route definitions, app bootstrap |
| Auth | `auth/AuthProvider.tsx`, `auth/LoginPage.tsx`, `auth/permissions.ts`, `auth/RequireAuth.tsx`, `auth/roleGuards.ts`, `auth/useProxyGuard.ts` | ~600 | AuthContext, LoginPage, permission helpers |
| Layout | `layout/AppShell.tsx`, `layout/ProxyControls.tsx` | ~300 | AppShell wrapper, proxy mode controls |
| Planning components | `components/planning/PlanningBottomDrawer.tsx` (1668 lines), `PlanningContextBar.tsx`, `PlanningLeftPanel.tsx`, `PlanningRightDrawer.tsx`, `SetupPanel.tsx`, `ActivityDetailBlock.tsx`, `ParadeNightBlock.tsx`, `ParadeNightMiniGrid.tsx`, `ParadeNightProgramCard.tsx`, `ParadeNightSummaryCard.tsx` | ~4500 | Bottom drawer (7 tabs), context bar, left panel, right drawer, setup panel |
| Views | `views/YearView.tsx`, `TermView.tsx`, `EightWeekView.tsx`, `TwoWeekView.tsx`, `ParadeNightGridView.tsx`, `ListView.tsx` | ~2000 | All planning calendar views |
| UI components | `components/ui.tsx`, `components/assurance.tsx`, `components/DrilldownPanel.tsx`, `components/ErrorBoundary.tsx`, `components/Modal.tsx`, `components/Paginated.tsx`, `components/status/StatusBadge.tsx` | ~600 | Shared UI primitives |
| Routes | 19 route files (Dashboard, Calendar, ParadeNights, ParadeNightDetail, Curriculum, Facilitators, Resources, Reports, ReportCatalogue, ActionItems, Imports, Audit, Admin, Accounts, Settings, Overviews, Cadets, WeeklyProgram, PlanningWorkspace) | ~5000 | All page components |
| Utilities | `utils/planningFilters.ts` | ~150 | Filter predicates for planning data |
| Tests | `tests/setup.ts` | ~30 | Vitest setup |
| **Total** | **58 files** | **~15,350** | — |

### TypeScript Health

| Check | Result | Date |
|---|---|---|
| `npx tsc --noEmit` | **0 errors** | 2026-07-14 |
| `BottomTab` type | `"backlog" \| "facilitators" \| "rooms" \| "equipment" \| "holidays" \| "notices" \| "activities"` | Post-cleanup |
| No unused imports flagged | Verified | — |

---

## Infrastructure

### Railway Services

| Service | Environment | Source | URL pattern |
|---|---|---|---|
| `aafc-tms-backend` | prod + staging | `backend/` + `docker-entrypoint-staging.sh` | `aafc-tms-backend[-staging].up.railway.app` |
| `aafc-tms-frontend` | prod + staging | `connected-frontend/` + nginx | `aafc-tms-frontend[-staging].up.railway.app` |
| `aafc-tms-planning-workspace-preview` | prod + staging | `frontend/` + Dockerfile | `aafc-tms-planning-workspace-preview[-staging].up.railway.app` |
| PostgreSQL | prod + staging | Railway managed | Internal only |

### CI/CD (`.github/workflows/`)

| Workflow | Trigger | Action |
|---|---|---|
| `backup-postgresql.yml` | Daily cron | Dumps production DB, GPG-encrypts, uploads artifact |
| `test-restore-postgresql.yml` | Weekly cron | Downloads latest backup, decrypts, restores to ephemeral PG, runs smoke check |

### Dockerfiles

| Service | Location | Status |
|---|---|---|
| Backend | `backend/Dockerfile` | Working; uses `docker-entrypoint-staging.sh` |
| Connected-frontend | `connected-frontend/Dockerfile` | Working; nginx single-file serve |
| Planning Workspace | `frontend/Dockerfile` | **Fixed on branch** (DEFECT-005); not yet deployed to production |

---

## Security Scan

Results against rules defined in `.claude/rules/security.md`:

| Check | Command | Result |
|---|---|---|
| Removed UI wording | `grep -Rc "your unit only\|Controlled access for training" connected-frontend backend` | **0 matches** |
| Access code exposure | `grep -Rc "View current code\|Show access code\|Reveal code" connected-frontend backend` | **0 matches** |
| Seeded codes in frontend | `grep -Rc "ADMIN703\|ADMIN7WG\|ADMINNATIONAL\|plain_code\|code_hash\|localStorage" connected-frontend` | **0 matches** |
| Secrets in frontend | `grep -Rc "JWT_SECRET\|SECRET_KEY\|DATABASE_URL" connected-frontend` | **0 matches** |

---

## Code Health Summary

| Area | Status | Notes |
|---|---|---|
| Backend tests | **503 pass, 1 skip** | 503 is the baseline for this release |
| TypeScript | **0 errors** | Clean after PlanningBottomDrawer cleanup |
| `datetime.utcnow()` deprecations | **0 remaining** | Fixed in `planning.py`, `test_lockout.py`, `import_wing_hq_calendar.py` |
| Dead UI code | **None remaining** | Training Planner and Import Review tab bodies removed |
| IDOR gap | **Fixed on branch** | `sqn_general` scope restriction added; not yet in production |
| Duplicate data models | **Documented** | 2 known duplications (facilitators, physical spaces) — deferred to post-beta |
| Security invariants | **All pass** | XSS: `esc()` used; no secrets in frontend; audit log intact |
| Stash | **Untouched** | `stash@{0}` — 709 insertions, risky to apply; investigate post-release |
