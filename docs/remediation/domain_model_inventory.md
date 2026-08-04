# Domain Model Inventory — canonical vs. duplicate/legacy

First-pass inventory, built from real code inspection (three-agent research during
the immediately-prior "TMS/Planning Workspace Integration" plan, this same session,
plus direct grep verification below). Not yet a complete audit of all ~57 backend
models (see `capability_manifest_before.json` for the full list) — this covers the
pairs/triples with a genuine duplicate-concept risk, per Section 4 of the
remediation instruction.

## Already-canonical (one source of truth, verified)

| Domain | Canonical model | Notes |
|---|---|---|
| Parade Nights / sessions | `Session` (aliased `TrainingSession`), `backend/app/models/training.py` | `ScheduledSession` (below) is confirmed dead legacy |
| Mission Backlog | Built from `CurriculumItem` + `Session` join | No separate storage |
| Facilitators + leave | `Facilitator`, `PlanningFacilitatorLeave` | Both frontends use the same endpoints |
| Rooms | `TrainingArea`, `backend/app/models/training.py` | See below — `PlanningLocation` reconciled at router level |
| Equipment | `Equipment` | |
| Holidays | `HolidayPeriod` | |
| Planning Year | `PlanningYear` | create/list/rollover/rename/archive/restore/delete all wired now (this session) |

## Confirmed dead/legacy (do not build on, but not yet removed — needs authorisation per capability-preservation.md)

- **`ScheduledSession`** (`backend/app/models/planning.py`) — explicit code comment
  confirms "never populated by any live create/update path... predates the v14
  rewrite" (`backend/app/routers/planning.py:3608-3613, 3722`). Real writes go
  through `Session`/`TrainingSession` via `ParadeDate → ParadeNight → Session`.
- **`PlanningLocation`** (`backend/app/models/planning.py`) — model still exists,
  but `GET/POST/PATCH /api/planning/locations` already reads/writes the
  `training_areas` table, not `planning_locations` (explicit code comment,
  `backend/app/routers/planning.py:329-341`, describes this as a completed "Rooms
  merger"). The table itself is vestigial.

## Genuine, still-open duplication (needs a design decision, not yet consolidated)

- **`Activity` vs `CeaActivity`** (REM-01 in the gap register) — `Activity`
  (`backend/app/routers/training.py`, inheritance-aware, `/api/activities`) is what
  connected-frontend's Activities pages read/write. `CeaActivity`
  (`backend/app/routers/planning.py`, `/api/planning/years/{id}/cea/*`) is what
  Planning Workspace's CEA import tooling reads/writes. The merge was previously
  one-directional (CEA → legacy view, read-only). **This session closed the
  visibility half**: Planning Workspace's Activities/CEA tab now also reads
  canonical `Activity` rows via the same session-scoped `GET /api/activities`
  endpoint connected-frontend uses (`frontend/src/api/index.ts::canonicalActivities`,
  wired into `PlanningBottomDrawer.tsx`'s `unified` list as a new `tms_activity`
  source, read-only). The write side is deliberately still split: CEA import
  continues to own `CeaActivity` as its own external-feed pipeline; `Activity`
  continues to be the internally-created record. A full single-table consolidation
  (per the instruction's "Preferred outcome: Activity is the operational canonical
  record; a CEA import row may exist for review/provenance") is a genuine data
  migration, not attempted this pass.
- **`ParadeDate` vs `ParadeNight`** — two live models for "a parade night on a given
  date", bridged by `ParadeDate.parade_night_id` FK rather than being one table.
  Not consolidated.
- **`AnchorEvent` / `WingHQEvent` / `Activity(owning_level in wing,national)`** — an
  undocumented three-way overlap around "organisation-level event". No
  reconciliation comment found anywhere (unlike the Rooms merger, which is
  explicitly documented). Needs its own design pass before touching.

## Reference-data concepts that don't exist yet (Section 6)

`Training Stage`, `Facilitator Type` (partially exists as free text), `Subject
Area` (exists as `subject_area_tags`, not scoped/inherited the way Section 6
wants), `Session Status Reason`, `Activity Type` (free text today), `Notice Type`,
`Training Area Capability`. Building the full scoped-reference-data model with
national/wing/squadron inheritance is net-new work (REM-23).
