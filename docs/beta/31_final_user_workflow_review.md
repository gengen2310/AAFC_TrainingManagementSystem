# AAFC TMS — Final User Workflow Review

Phase 31 output. Functional assessment of every primary user workflow.
Created: 2026-07-14. All workflows verified against code; browser verification is flagged where it differs.

---

## Verification Method

Workflows verified by:
1. Code path tracing (router endpoints + connected-frontend JS functions)
2. Backend integration test coverage (where test names correspond to workflow steps)
3. Browser: marked [BROWSER NEEDED] where code tracing cannot substitute

---

## Squadron Admin Workflows

### WF-01: First-Time Setup

| Step | Mechanism | Verified |
|---|---|---|
| Login with sqn_admin code | `POST /api/auth/login` → session cookie | Test: `test_lookup_then_login_full_flow` |
| Configure training year dates | `POST /api/timing/templates` + `GET /api/timing/templates` | Test: `test_timing.py` |
| Add facilitators | `POST /api/planning/facilitators` | Test: `test_planning.py::test_facilitator_workload_*` |
| Add rooms (Resources) | `POST /api/training/rooms` | Test coverage in `test_planner_v14.py` |
| Create planning year | `POST /api/planning/years` | Test: `test_planning.py::test_can_create_planning_year` |
| Generate parade dates | `POST /api/planning/years/{id}/parade-dates/generate` | Test: `test_planning.py` |
| **Status** | Code-verified | [BROWSER NEEDED] for UX flow |

### WF-02: Weekly Parade Night Operation

| Step | Mechanism | Verified |
|---|---|---|
| View upcoming parade nights | `GET /api/parade-nights` | Connected-frontend calendar page |
| Open parade night detail | `GET /api/parade-nights/{id}` | `loadParadeNightDetail()` in SPA |
| Assign sessions | `PUT /api/parade-nights/{id}/sessions` | Training module |
| Assign facilitators to sessions | `POST /api/training/sessions/{id}/assign` | `test_planning.py` |
| Mark session complete | `PUT /api/training/sessions/{id}/status` | `test_core.py` |
| Generate weekly program | `GET /api/program/weekly/{id}` | `test_program.py` |
| **Status** | Code-verified | [BROWSER NEEDED] for visual review |

### WF-03: CEA Activity Import and Classification

| Step | Mechanism | Verified |
|---|---|---|
| Navigate to Activities tab | Connected-frontend `nav('activities')` | Code-verified |
| Upload CEA file | `POST /api/planning/years/{id}/cea/import` | Code path traced |
| Review import batch | `GET /api/planning/years/{id}/cea/batches` | Test: `test_planning.py::test_cea_*` |
| Classify activities | `PUT /api/planning/years/{id}/cea/activities/{id}/classify` | Test: `test_planning.py` |
| View classified activities | `GET /api/planning/years/{id}/cea/activities` | Test: `test_sqn_general_cannot_read_other_sqn_cea` |
| Hide unwanted activity | `POST /api/planning/years/{id}/cea/activities/{id}/hide` | Code path traced |
| **Status** | Code-verified | [BROWSER NEEDED] for CEA file upload UX |

### WF-04: Curriculum Progress Review

| Step | Mechanism | Verified |
|---|---|---|
| View curriculum items | `GET /api/training/curriculum` | Connected-frontend Curriculum page + React Curriculum route |
| Filter by phase/subject | Client-side filter in `filterCurriculum()` | Code-verified |
| View coverage status | Derived from `GET /api/planning/years/{id}/annual-program` | Test: `test_planning.py::test_annual_program_*` |
| Mark curriculum complete | Session completion → curriculum progress update | Test: session status tests |
| **Status** | Code-verified | [BROWSER NEEDED] for progress bar rendering |

### WF-05: Planning Workspace

| Step | Mechanism | Verified |
|---|---|---|
| Open Planning Workspace | `nav('planning-workspace')` → iframe loads React app | Code-verified |
| Select planning year | `GET /api/planning/years` → year selector | Test: `test_planning.py` |
| View year calendar | Year view component | TypeScript: 0 errors |
| Drag curriculum to date | `POST /api/planning/years/{id}/scheduled-sessions` | Code path traced |
| Check command centre | `GET /api/planning/years/{id}/command-centre` | Test: `test_planning.py` |
| View night summaries | `GET /api/planning/years/{id}/night-summaries` | Test: `test_night_summaries_*` |
| View facilitator workload | `GET /api/planning/years/{id}/facilitators/workload` | Test: `test_facilitator_workload_*` |
| **Status** | Code-verified | [BROWSER NEEDED] for drag-and-drop interaction |

---

## Wing Admin Workflows

### WF-06: Squadron Oversight

| Step | Mechanism | Verified |
|---|---|---|
| Login as wing_admin | `POST /api/auth/login` | Test: `test_accounts.py` |
| View wing overview | `GET /api/ops/wing/overview` | Test: `test_wing_coverage.py` |
| Check curriculum coverage | `GET /api/ops/wing/curriculum-coverage` | Test coverage in ops tests |
| View risk bottlenecks | `GET /api/ops/wing/risk-bottlenecks` | Code path traced |
| View Wing HQ calendar | `GET /api/wing-calendar/events` | Test: `test_wing_calendar.py` |
| Manage squadron accounts | `GET/POST /api/accounts` (wing-scoped) | Test: `test_accounts.py` |
| **Status** | Code-verified | [BROWSER NEEDED] for visual review |

### WF-07: Wing HQ Calendar Import

| Step | Mechanism | Verified |
|---|---|---|
| Run import script | `scripts/import_wing_hq_calendar.py --dry-run` then commit | Code-verified; datetime deprecation fixed `2026-07-14` |
| View imported events | `GET /api/wing-calendar/events` | Test: `test_wing_calendar.py` |
| Squadron confirms/declines | `PUT /api/wing-calendar/events/{id}/status/{sqn_id}` | Test: `test_wing_calendar.py` |
| **Status** | Code-verified | [BROWSER NEEDED] for squadron confirmation UX |

---

## Auditor Workflows

### WF-08: Audit Log Review

| Step | Mechanism | Verified |
|---|---|---|
| Login as auditor | `POST /api/auth/login` | Test: `test_accounts.py` (auditor role) |
| View audit log | `GET /api/training/audit` (wing/national scope) | Test: `test_system_admin.py` |
| Filter by object type / date | Query params | Code path traced |
| Export audit log | Via reports or manual API | Code path traced |
| **Status** | Code-verified | [BROWSER NEEDED] |

---

## System Admin Workflows

### WF-09: System Console Operations

| Step | Mechanism | Verified |
|---|---|---|
| Login as system_admin | `POST /api/auth/login` | Test: `test_system_admin.py` |
| View system health | `GET /api/system/health` | Test: `test_system_admin.py` |
| Enable maintenance mode | `POST /api/system/maintenance` | Test: `test_maintenance_enforcement.py` |
| Trigger backup | `POST /api/system/backup` | Test: `test_system_admin.py::test_trigger_backup_*` |
| Run scope map | `GET /api/system/scope-map` | Test: `test_system_admin.py` |
| Bootstrap staging | `POST /api/system/bootstrap-staging` (staging only) | Blocked in production when `ENVIRONMENT=production` |
| **Status** | Code-verified | [BROWSER NEEDED] for system console UI |

---

## Workflow Gap Analysis

| Workflow | Code-verified | Browser-verified | Gap |
|---|---|---|---|
| First-time setup | ✓ | ✗ | [BROWSER NEEDED] |
| Weekly parade operation | ✓ | ✗ | [BROWSER NEEDED] |
| CEA import | ✓ | ✗ | [BROWSER NEEDED] |
| Curriculum review | ✓ | ✗ | [BROWSER NEEDED] |
| Planning Workspace | ✓ | ✗ | [BROWSER NEEDED] — drag-and-drop not testable in code |
| Wing oversight | ✓ | ✗ | [BROWSER NEEDED] |
| Wing HQ calendar | ✓ | ✗ | [BROWSER NEEDED] |
| Audit log | ✓ | ✗ | [BROWSER NEEDED] |
| System console | ✓ | ✗ | [BROWSER NEEDED] |

All 9 primary workflows are code-verified. Browser verification for all workflows is pending and required before general availability. For the beta release with known test squadrons, browser verification should be completed by the beta coordinator using the squadron verification matrix (`26_squadron_verification_matrix.md`).
