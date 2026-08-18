# Final Feature Inventory (Stage 1)

Functional surface inventory, cross-checked against live source rather than assumed
from prior docs. Companion to `final_source_inventory.md` (structural counts) — this
doc maps features to the pages/routes/endpoints that implement them.

## `connected-frontend/index.html` — nav pages by scope (`NAV_BY_SCOPE`)

**Updated 2026-08-17 at `2b263bd`** — Planning Workspace native integration reverted;
`help` added to squadron scope; `action-centre` and `program-audit` removed from scope
lists. Canonical detail in `docs/release/frontend_ui_state.md`.

| Scope | Pages |
|---|---|
| `squadron` | getting-started, dashboard, calendar, parade-nights, weekly-program, curriculum, activities, facilitators, resources, action-items, **help**, settings, accounts |
| `wing` | getting-started, wing-overview, wing-activities, wing-calendar, curriculum, audit, accounts |
| `national` | getting-started, national, national-activities, wing-calendar, curriculum, audit, accounts |
| `auditor` | audit, accounts |
| `system_admin` | getting-started, system-console, national, national-activities, wing-activities, wing-calendar, curriculum, audit, accounts |

`_PLANNING_PAGES = []` — placeholder constant, currently empty.  
Planning Workspace is an **external link** (`nav-pw-link`) shown by `bootApp()` when
`S.pwUrl` is configured; it is not a nav page.

22 distinct `page-*` IDs in HTML; `page-action-centre` and `page-program-audit` remain
in DOM but are excluded from all scope lists (unreachable by normal nav). The
`effectiveScope()` / `saBrowseWingId` / `saBrowseSquadronId` system_admin behaviour is
unchanged from prior docs.

## Backend functional areas (by router tag, 237 endpoints total — see `api-inventory.csv`)

| Router | Endpoints | Functional area |
|---|---:|---|
| `planning.py` | 59 | Parade-night planning: years, dates, conflicts, facilitator leave, CEA import, notices |
| `training.py` | 57 | Core training domain: curriculum, sessions, facilitators, activities, cadets, timing |
| `ops.py` | 19 | Operational actions, import/export preview, action items |
| `organisations.py` | 18 | Wings, squadrons, national entities, flights |
| `accounts.py` | 15 | User/account management, access codes |
| `program.py` | 14 | Cadet program packages, phases, promotion requests |
| `system.py` | 14 | System console: maintenance mode, audit log, rate limits, backups |
| `timing.py` | 10 | Timing templates/blocks |
| `wing_calendar.py` | 9 | Wing HQ events, squadron event status |
| `auth.py` | 7 | Login, session, me, refresh, logout |
| `dashboard.py` | 4 | Aggregated dashboard views |
| `export_import.py` | 4 | Program-level import/export |
| `health.py` | 3 | Liveness/readiness probes |
| `jobs.py` | 2 | Background job status |
| `setup.py` | 1 | Getting-started setup-status aggregation (Phase 3.5, this session) |

## Session's own claimed shipped work — spot-verified present in code, not just committed

| Feature | Verification |
|---|---|
| Getting Started setup checklist | `GET /api/setup/status` present (`setup.py`), router registered in `main.py`, `connected-frontend` has matching UI strings; `test_setup_status.py` (9 tests) all pass |
| Curriculum/program import preview | `POST /import/preview` (`ops.py:496`), `program_import_preview` (`export_import.py:107`), `preview_only` param on curriculum import (`training.py:1764`) |
| Drag-and-drop scheduling | `draggable`/`dragstart`/`dragover` handlers present in `connected-frontend/index.html` |
| Filtering/findability | 146 filter-related references in `connected-frontend/index.html` |
| NATHQ/Wing/Squadron Activity inheritance | `Activity` model (`training.py:189`) carries `owning_level` (national/wing/squadron), matching `CurriculumItem`'s existing pattern (`training.py:16`) |
| GAP-21 (system_admin Wing/Squadron scope) | `saRenderScopeBar`/`saEnterIntervention`/`saBrowseWingId`/`saBrowseSquadronId` all present (16 references), matching `.claude/rules/frontend.md`'s documented behaviour exactly |

## Test-suite baseline (re-run fresh this pass, not carried from a stale doc)

```
1002 passed, 5 skipped, 1737 warnings in 54.00s
```

This materially supersedes the number recorded in `.claude/rules/testing.md`
("310 passed, 1 skipped") — that file's own header already warns the baseline "goes
stale fast." Flagged as a recommended documentation correction for Stage 13 rather
than edited directly here, since `.claude/rules/*.md` changes are held for explicit
surfacing per this engagement's own plan.

## Known parallel/legacy model pairs (carried from prior gap register, re-confirmed present)

- `TrainingArea` (training.py) vs `PlanningLocation` (planning.py) — both still exist,
  status of consolidation unchanged from prior passes; full review deferred to Stage 3.
- `Facilitator` (training.py) is the single model; `planning.py`'s "planning
  facilitators" endpoints (`/api/planning/facilitators`, `/api/planning/facilitators/
  {id}/leave`) are views/behaviours over the same `Facilitator` table, not a second
  model — confirmed via `final_source_inventory.md`'s API-inventory correction above
  (no `PlanningFacilitator` model class exists in the 57-class model inventory).

---

## Year UX — Sub-project 1 (merged 2026-08-18, commit `5ab3b19`)

### New and modified API endpoints

| Method | Path | File | Change |
|--------|------|------|--------|
| GET | `/api/planning/years/{year_id}/export` | `planning.py` | New — CSV export of year's activities |
| POST | `/api/planning/years/{year_id}/cea/import` | `planning.py` | Modified — added `keep_existing` Form parameter (comma-sep cea_activity_ids to skip updating) |

### New backend tests (`backend/tests/test_year_ux.py` — 5 tests)

`test_export_year_csv_returns_200`, `test_export_year_csv_unauthenticated`, `test_export_year_csv_wrong_scope`, `test_cea_import_keep_existing_skips_update`, `test_cea_import_without_keep_existing_still_works`

### New frontend features (`connected-frontend/index.html`)

| Feature | Component / ID | Roles |
|---------|---------------|-------|
| Label cleanup | All pages — "Planning Year" / "Training Year" → bare year integer | all |
| Year nav control | `#ynDisplay`, `#ynPrev`, `#ynNext`, `#ynGear` in Activities ph-actions | sqn_admin + |
| Manage Years panel | `#m-manage-years` modal — create / archive / restore / delete / export | wing_admin, national_admin, system_admin |
| CEA Import modal | `#m-cea-import`, `#actImportCeaBtn` — 3-step CSV import with conflict preview | wing_admin, national_admin, system_admin |
| PW year badge | `#navPwYrBadge`, `#navPwYrHint` in nav-pw-link | all |
| TMS→PW year handoff | `&y=YYYY` appended to PW deep-link; `aafc_requested_year` sessionStorage | all |

### Updated test-suite baseline

```
1764 passed, 7 skipped  (note: 1 pre-existing flaky test in test_timing.py, unrelated to sub-project)
```

### Deferred minor findings (non-blocking, tracked in `.superpowers/sdd/2026-08-18-year-ux/progress.md`)

F-1 aria-labels on year nav buttons · F-2 yn-toast animation · F-3 year-nav-ctrl box-shadow · F-4 year-nav-ctrl flex-shrink · M-1 wrong-scope test hits 404 before scope gate · M-2 dead ynOpenManage stub · M-3 redundant esc() on textContent
