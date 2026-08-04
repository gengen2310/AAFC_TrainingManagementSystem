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
`Training Area Capability`. **Update, Stage 1**: see the major finding below —
much of what Section 6 asks for may already exist, unreachable, as
`ProgramItem`/`ProgramItemDeployment`.

## Stage 1 major finding: `ProgramPackage`/`ProgramItem` — a second, complete curriculum-governance system, live but unreachable from either frontend

**Not previously found in this session's earlier research** (missed from the
original REM-01 duplicate-model list). Surfaced by reconciling against
`docs/beta/28_authoritative_data_model.md`, then verified directly against current
code (2026-08-04):

- `backend/app/models/program.py` defines 9 models: `Phase`, `ProgramPackage`,
  `ProgramItem`, `LearningHubResource`, `ProgramItemDeployment`, `SourceFile`,
  `SourceConflict`, `PromotionRequest`, `JobStatus`.
- `backend/app/routers/program.py` exposes 14 real, registered endpoints
  (`program.router` is mounted in `main.py`) — program-packages CRUD, program-items
  CRUD + retire, learning-hub-resources (+ "missing" report), program-coverage
  (squadron/wing), program-promotion (squadron→wing submit/list/approve).
- **Zero references to any of these endpoints in either frontend** — confirmed by
  grep across `connected-frontend/index.html` and `frontend/src/`. This is a fully
  built, presumably tested backend capability with no UI ever wired to it.
- `ProgramItem` has **no FK or code-level join to `CurriculumItem`** — confirmed by
  grep — they are entirely independent models covering the same real-world concept
  (a piece of curriculum content, its phase/element/duration/suitability, National→
  Wing→Squadron ownership and inheritance).
- **Strong evidence this is superseded, not parallel-and-current**: the migration
  that created these tables (`175e1c6e12f7_v9_1_cadet_program_jobs.py`) is the
  *first* migration in the entire chain — it predates `CurriculumItem`'s
  `owning_level` inheritance model and the 214-item national curriculum seed
  (`j5e6f7g8h9i0_v22_seed_national_curriculum.py`, much later). `CurriculumItem` is
  what's actually seeded with real data and used by every live feature (Mission
  Backlog, session scheduling, readiness, Getting Started). `program.py`'s tables
  have zero seeded/real data and zero UI reachability.
- **`ProgramItem.core_status` already has the exact value set Section 12 of the
  remediation instruction asks for**: `core|optional|extension|local|wing_required|
  national_required` — including `optional`, which `CurriculumItem.core_status`
  (`core|additional` only, displayed as "Foundation"/"Extension" in
  connected-frontend) does not have. `ProgramItemDeployment` also already models
  exactly the "inherited status", "can_schedule", "can_copy", "can_request_change"
  concepts Section 6 wants for scoped reference data.

**Working hypothesis, not yet confirmed with the user/product owner**: this is an
early (v9.1) design for curriculum governance that was superseded by
`CurriculumItem`'s simpler inheritance model as the project evolved, and never
removed. If confirmed, Section 6's "Program and Reference Data" capability request
may be substantially satisfiable by **building a frontend for existing,
already-correct backend infrastructure** rather than designing new tables — a much
smaller effort than assumed, but requires explicit confirmation this system was
truly abandoned (not, e.g., reserved for a not-yet-built import pipeline) before
committing to that plan. Tracked as REM-26 in the gap register.

## `core_status` terminology (Section 12)

`CurriculumItem.core_status` is still stored as `core`/`additional` in the
database and in most backend code — **this is a display-layer-only rename today**:
connected-frontend already renders `core`→"Foundation", `additional`→"Extension"
(`index.html:6468,6493`), and the curriculum CSV importer already accepts a
"Foundation or Extension" column, translating it back to `core`/`additional` for
storage (`training.py:2890-2892`). No backend/DB value migration is needed to
satisfy Section 12's *display* wording for the two existing categories. A genuine
gap remains: **no "Optional" category exists in `CurriculumItem` today** — Section
12 wants three categories (Foundation/Extension/Optional), and `CurriculumItem`
only has two. `ProgramItem.core_status` (see above) already has an `optional`
value, which is one more reason the two systems may be more directly related than
previously assumed.
