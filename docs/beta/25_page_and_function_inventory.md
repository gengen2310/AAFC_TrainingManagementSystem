# AAFC TMS — Page and Function Inventory

Phase 1 output. Every user-facing page, route, tab and major component.
Created: 2026-07-14. Update in place.

Allowed decisions: RETAIN | RETAIN AND IMPROVE | MERGE | REDIRECT | REMOVE FROM NAVIGATION | RETIRE | BACKEND ONLY | HISTORICAL READ-ONLY

---

## Connected-Frontend SPA (`connected-frontend/index.html`)

### Squadron Scope Pages

| Page | Route (nav id) | Roles | Purpose | Main action | Data source | Decision | Notes |
|---|---|---|---|---|---|---|---|
| Dashboard | `dashboard` | sqn_admin, sqn_general | Overview of planning year health, upcoming parades, facilitator readiness | Review training status | `/api/planning/*`, `/api/parade-nights`, `/api/training/*` | **RETAIN AND IMPROVE** | Central landing page; all drill-downs working |
| Calendar | `calendar` | sqn_admin, sqn_general | Monthly view of parade nights and activities | Navigate to parade night detail | `/api/parade-nights`, `/api/training/activities` | **RETAIN** | Clear single purpose |
| Parade Nights | `parade-nights` | sqn_admin, sqn_general | Manage and generate parade dates; view sessions | Create/edit parade nights | `/api/parade-nights` | **RETAIN** | Core workflow |
| Weekly Program | `weekly-program` | sqn_admin, sqn_general | Generate printable weekly program for a parade night | Print/export program | `/api/parade-nights/{id}` | **RETAIN** | Operational output |
| Curriculum | `curriculum` | sqn_admin, sqn_general | View and filter national/wing/local curriculum items | Review curriculum progress | `/api/training/curriculum` | **RETAIN** | — |
| Activities | `activities` | sqn_admin, sqn_general | Review imported CEA activities, wing/nat activities, local entries; classify | Import CEA, classify, add local | `/api/training/activities`, `/api/planning/years/{id}/cea/*` | **RETAIN AND IMPROVE** | CEA import now consolidated here |
| Facilitators | `facilitators` | sqn_admin, sqn_general | View and manage facilitator profiles and tags | Add/edit facilitator | `/api/planning/facilitators` | **RETAIN** | — |
| Resources (Training Areas) | `resources` | sqn_admin, sqn_general | Manage rooms and equipment | Add/edit room or equipment | `/api/training/rooms`, `/api/training/equipment` | **RETAIN** | — |
| Reports | `reports` | sqn_admin, sqn_general, wing_*, national_*, auditor | Training progress, coverage, risk reports | View reports | `/api/training/*`, `/api/ops/*` | **RETAIN** | — |
| Action Items | `action-items` | sqn_admin, sqn_general | Outstanding items requiring action | Review and act | `/api/planning/*` | **RETAIN** | — |
| Settings | `settings` | sqn_admin only | Unit configuration (training year, timing templates) | Configure unit settings | `/api/timing/*`, `/api/organisations/*` | **RETAIN** | Restricted to sqn_admin |
| Accounts | `accounts` | sqn_admin, wing_admin, wing_viewer, national_*, auditor, system_admin | User/account management within authorised scope | Create/reset access codes | `/api/accounts/*` | **RETAIN** | Role-gated correctly |

### Wing Scope Pages

| Page | Route | Roles | Purpose | Decision |
|---|---|---|---|---|
| Wing Overview | `wing-overview` | wing_admin, wing_viewer, national_*, system_admin | Overview of all squadrons in wing | **RETAIN** |
| Wing Calendar | `wing-calendar` | wing_admin, wing_viewer, national_*, system_admin | Wing-level and HQ event calendar | **RETAIN** |
| Curriculum Coverage | `curriculum-coverage` | wing_*, national_*, system_admin | Cross-squadron curriculum coverage matrix | **RETAIN** |
| Training Balance | `training-balance` | wing_*, national_*, system_admin | Subject-area distribution across squadrons | **RETAIN** |
| Facilitator Load | `facilitator-load` | wing_*, national_*, system_admin | Facilitator coverage and capability across squadrons | **RETAIN** |
| Risk & Bottlenecks | `risk-bottlenecks` | wing_*, national_*, system_admin | Units requiring attention | **RETAIN** |
| Audit | `audit` | wing_*, national_*, auditor, system_admin | Immutable audit log of all privileged actions | **RETAIN** |

### National Scope

| Page | Route | Roles | Purpose | Decision |
|---|---|---|---|---|
| National | `national` | national_*, system_admin | National HQ cross-wing assurance overview | **RETAIN** |

### System Admin

| Page | Route | Roles | Purpose | Decision |
|---|---|---|---|---|
| System Console | `system-console` | system_admin only | Platform administration, health, maintenance, backup, scope-map, audit | **RETAIN** |

### Hidden / Retired Pages (in HTML but not navigable)

These pages exist as `<div id="page-*">` in the HTML but have been removed from all nav scopes (`_PLANNING_PAGES=[]`) and from the sidebar. The `nav()` function redirects any programmatic access to operational equivalents.

| Page | Former route | Redirect | Decision | Reason |
|---|---|---|---|---|
| Annual Program | `planning-year` | → `activities` | **RETIRED** | Superseded by Planning Workspace; no operational purpose in connected-frontend |
| Training Planner | `planning-missions` | → `activities` | **RETIRED** | Mission Backlog is in Planning Workspace |
| Parade Night Program | `planning-builder` | → `parade-nights` | **RETIRED** | Session builder is in Planning Workspace |
| Planner Help | `planning-guide` | → `dashboard` | **RETIRED** | Static help content with no operational links |
| Key Activities | `planning-anchors` | Not redirected (unreachable) | **REMOVE FROM NAVIGATION** | Wing/HQ anchor events — data still accessible in Planning Workspace |
| Term Program | `planning-term` | Not redirected | **REMOVE FROM NAVIGATION** | Term planning in Planning Workspace |
| Long-Range View | `planning-longrange` | Not redirected | **REMOVE FROM NAVIGATION** | Year view in Planning Workspace |
| Locations/Facilitators | `planning-rooms` | Not redirected | **REMOVE FROM NAVIGATION** | Planning-specific resource view in Planning Workspace |
| Program Checks | `planning-checks` | Not redirected | **REMOVE FROM NAVIGATION** | Health monitoring in Planning Workspace |

**Recommendation**: The HTML for all 9 retired/hidden pages can be removed from `connected-frontend/index.html` to reduce file size (~400KB currently). The `nav()` redirects ensure no broken references. This is safe but not urgent.

---

## React Planning Workspace (`frontend/`)

### Registered Routes (App.tsx)

| Route | Component | Roles that see it | Purpose | Decision |
|---|---|---|---|---|
| `/` | Home (redirect) | All | Route to role-appropriate landing page | **RETAIN** |
| `/dashboard` | Dashboard | sqn_admin, sqn_general (in sqn scope); wing/nat in proxy mode | Training year health, progress, upcoming nights | **RETAIN AND IMPROVE** |
| `/calendar` | Calendar | sqn_*, proxy | Monthly parade night calendar | **RETAIN** |
| `/parade-nights` | ParadeNights | sqn_*, proxy | Parade night management | **RETAIN** |
| `/weekly-program` | WeeklyProgram | sqn_*, proxy | Printable weekly program | **RETAIN** |
| `/curriculum` | Curriculum | sqn_*, proxy | Curriculum list and progress | **RETAIN** |
| `/facilitators` | Facilitators | sqn_*, proxy | Facilitator profiles and stats | **RETAIN** |
| `/resources` | Resources | sqn_*, proxy | Rooms and equipment | **RETAIN** |
| `/cadets` | Cadets | sqn_admin, sqn_general (not sqn_general per roleGuards) | Cadet roll | **RETAIN** — operational, visible to sqn_admin |
| `/reports` | Reports | All | Training reports | **RETAIN** |
| `/report-catalogue` | ReportCatalogue | All | Report catalogue/index | **RETAIN** — complements Reports |
| `/action-items` | ActionItems | sqn_*, proxy | Outstanding action items | **RETAIN** |
| `/imports` | Imports | Admins only | CSV import utility | **RETAIN** — admin-only, gated |
| `/audit` | Audit | All (read-only for some) | Audit log | **RETAIN** |
| `/admin` | Admin | Admins only | Admin / settings | **RETAIN** |
| `/accounts` | Accounts | Admins, auditor | Account management | **RETAIN** |
| `/settings` | Settings | All | Access codes / personal settings | **RETAIN** |
| `/wing-overview` | WingOverview | wing_*, national_*, system_admin | Wing dashboard | **RETAIN** |
| `/national-overview` | NationalOverview | national_*, system_admin | National dashboard | **RETAIN** |
| `/planning` | PlanningWorkspace | All authenticated (module mode) | Full planning workspace | **RETAIN** |
| `*` (404) | Empty message | All | Page not found | **RETAIN** |

**Note**: The React frontend (`frontend/`) serves as the Planning Workspace preview at `/planning` in module mode. In full-app mode (if accessed standalone), it also provides the full squadron workflow. Both modes share the same codebase. In the current deployment, only module mode (`/planning` from connected-frontend) is production-authorised.

### Planning Workspace Internal Tabs (PlanningBottomDrawer)

| Tab | Key | Purpose | Decision |
|---|---|---|---|
| Activities | `activities` | CEA import, classification, review, duplicate detection, local additions | **RETAIN** — consolidated hub for activity workflow |
| Mission Backlog | `backlog` | Curriculum mission list with scheduling status, filters | **RETAIN** |
| Facilitators | `facilitators` | Facilitator assignment, workload, leave | **RETAIN** |
| Rooms | `rooms` | Room booking and conflict view | **RETAIN** |
| Equipment | `equipment` | Equipment management | **RETAIN** |
| Holidays | `holidays` | Holiday and stand-down dates | **RETAIN** |
| Notices | `notices` | Parade night notices (warnings, reminders) | **RETAIN** |

Retired tabs (removed in `e25343b`):
- Training Planner — removed; Mission Backlog covers this
- Import Review — removed; integrated into Activities tab

### Planning Workspace Views (PlanningContextBar + views/)

| View | Key | Purpose | Decision |
|---|---|---|---|
| Year view | `year` | Full planning year — all terms and parade nights | **RETAIN** |
| Term view | `term` | Single term view | **RETAIN** |
| 8-week view | `8week` | 8-week rolling window | **RETAIN** |
| 2-week view | `2week` | 2-week close-up | **RETAIN** |
| Parade Night | `parade-night` | Single parade night builder | **RETAIN** |
| Custom | `custom` | Date-range custom view | **RETAIN** |

Health chips (after `e25343b`): prep gaps, wing events to review, Healthy. Conflicts and unscheduled removed from header (data retained in underlying logic).

---

## Backend Endpoints by Router

### `planning.py` (58 endpoints) — Planning years, missions, CEA, parade builder

Key endpoint groups:
- Planning years CRUD
- Annual program (parade dates, terms, holidays)
- Missions (curriculum scheduling)
- Parade night builder (sessions, facilitator assignment, resources)
- Parade notices
- Facilitator planning (leave, workload)
- CEA activities (import, classify, batches)
- Planning activities (local overlay)
- Locations (planning-specific)
- Long-range view
- Term planner
- Program checks
- Command centre data (conflicts, unscheduled, prep gaps)

Decision: **RETAIN** — all endpoints actively used by Planning Workspace

### `training.py` (45 endpoints) — Core training data

Key endpoint groups:
- Curriculum items (CRUD, CSV import, national seeding)
- Parade nights (CRUD, session management)
- Sessions (CRUD, status lifecycle)
- Activities (CRUD, CEA import/classify)
- Facilitators (CRUD, tags, stats)
- Rooms (CRUD)
- Equipment (CRUD)
- Cadets (CRUD, risk flags, import)
- Reports (coverage, progress, risk)
- Action items

Decision: **RETAIN** — all actively used

### `ops.py` (17 endpoints) — Wing/national reporting

Key endpoint groups:
- Wing overview (squadron summaries)
- National overview (wing summaries)
- Curriculum coverage matrix
- Training balance
- Facilitator load
- Risk bottlenecks

Decision: **RETAIN** — wing/national oversight layer

### Other routers

| Router | Endpoints | Purpose | Decision |
|---|---|---|---|
| `accounts.py` | 12 | User/account management, access code reset | **RETAIN** |
| `organisations.py` | 14 | Squadron/wing/national CRUD | **RETAIN** |
| `system.py` | 13 | System console, maintenance, backup, scope-map | **RETAIN** |
| `auth.py` | 7 | Login, logout, session, proxy/intervention | **RETAIN** |
| `timing.py` | 10 | Timing templates (parade night slot configuration) | **RETAIN** |
| `wing_calendar.py` | 9 | Wing HQ event calendar | **RETAIN** |
| `program.py` | 14 | Weekly program generation, action items | **RETAIN** |
| `export_import.py` | 4 | CSV export/import | **RETAIN** |
| `health.py` | 3 | Health checks, readiness | **RETAIN** |

---

## Function Inventory — Duplicates and Consolidation Candidates

| Function | Locations | Duplication type | Decision |
|---|---|---|---|
| Curriculum display and filter | `connected-frontend/index.html` (curriculum page) + `frontend/src/routes/Curriculum.tsx` | Same data, different UIs, different scope (sqn-level) | **RETAIN BOTH** — different apps, different navigation contexts |
| Facilitator list | `connected-frontend` (facilitators page) + `frontend/src/routes/Facilitators.tsx` | Same data | **RETAIN BOTH** — same reason; Planning Workspace adds stats |
| Activity/CEA review | `connected-frontend` (activities page) + Planning Workspace (Activities tab) | Overlap — both show CEA and local activities | **RETAIN BOTH** — connected-frontend shows historical view; Planning Workspace adds classification workflow |
| Parade night view | `connected-frontend` (calendar, parade-nights) + Planning Workspace (parade night tab) | Overlap | **RETAIN BOTH** — different granularity and purpose |
| Reports (`page-reports` / "Training Summary") | `connected-frontend` | **[UPDATED 2026-07-24]** Not actually a live duplicate — `nav('reports')` always redirected away before this page could render, and its stats were never populated by any reachable code. **REMOVED** (master transformation plan Phase 6), not retained; `frontend/src/routes/Reports.tsx` (React full-app route table) is the only live "Reports" page now. That investigation also found and fixed a real bug: the Curriculum page's "N sess." drill-down silently failed for wing/national/auditor scope because it routed through this same dead page — see `docs/beta/15_known_limitations.md`. |
| Resource model | `TrainingArea`/`PlanningLocation` in backend | Two overlapping concepts for physical spaces | **[RESOLVED 2026-07-24]** — master transformation plan Phase 1; `/api/planning/locations` now reads/writes `training_areas` directly. See `docs/beta/15_known_limitations.md` DL-01. |
| `_all_sessions` in `ops.py` | Called twice in same function (double query) | N+1 | **FIX** (in stash — apply separately) |

---

## Error States and Empty States

| Page | Empty state | Error state | Loading state | Decision |
|---|---|---|---|---|
| Dashboard | Shows "no data" cards with guidance | ErrorNote component | Loading spinner | **RETAIN** — adequate |
| Curriculum | "No curriculum items" | ErrorNote | Loading | **RETAIN** |
| Parade Nights | "No parade nights yet" + guidance | ErrorNote | Loading | **RETAIN** |
| Mission Backlog | "No missions found" | Error div | Loading div | **RETAIN** |
| Activities tab | "No activities" | Error div | Loading div | **RETAIN** |
| Wing Overview | "No squadrons" | Error div | Loading | **RETAIN** |

---

## Route/Page Decision Summary

| Decision | Count | Items |
|---|---|---|
| RETAIN | 39 | Most production pages |
| RETAIN AND IMPROVE | 3 | Dashboard (both apps — Planning Workspace's rebuilt onto chart endpoints 2026-07-24), Activities (connected-frontend) |
| RETIRED | 4 | planning-year, planning-missions, planning-builder, planning-guide |
| REMOVE FROM NAVIGATION | 5 | planning-anchors, planning-term, planning-longrange, planning-rooms, planning-checks |
| REMOVED (dead code deleted) | 1 | `page-reports` / "Training Summary" (connected-frontend) — 2026-07-24 |
| MERGE — RESOLVED 2026-07-24 | 1 | TrainingArea + PlanningLocation resource model |
| No action needed | 9 | Hidden HTML divs for retired planning pages |

**Total pages classified**: 52 (30 connected-frontend + 22 React routes)
**Unclassified**: 0
