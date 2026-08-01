# Final Feature Inventory (Stage 1)

Functional surface inventory, cross-checked against live source rather than assumed
from prior docs. Companion to `final_source_inventory.md` (structural counts) — this
doc maps features to the pages/routes/endpoints that implement them.

## `connected-frontend/index.html` — nav pages by scope (`NAV_BY_SCOPE`, line 3356)

| Scope | Pages |
|---|---|
| `squadron` | getting-started, dashboard, calendar, parade-nights, weekly-program, curriculum, activities, facilitators, resources, action-items, settings, accounts, + shared planning pages |
| `wing` | getting-started, wing-overview, wing-activities, wing-calendar, curriculum, audit, accounts, + shared planning pages |
| `national` | getting-started, national, national-activities, wing-calendar, curriculum, audit, accounts, + shared planning pages |
| `auditor` | audit, accounts, + shared planning pages |
| `system_admin` | getting-started, system-console, national, national-activities, wing-activities, wing-calendar, curriculum, audit, accounts, + shared planning pages |

22 distinct `page-*` IDs found in the file — matches `.claude/rules/frontend.md`'s
documented `nav()`/`NAV_BY_SCOPE` model exactly, including the `effectiveScope()`
system_admin widen-not-narrow behaviour and the `saBrowseWingId`/`saBrowseSquadronId`
helpers described there (re-read directly from source at
`connected-frontend/index.html:3372-3385`, not taken on the doc's word).

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
