# AAFC TMS — Authoritative Data Model

Phase 8 output. Every shared concept mapped to its authoritative source.
Created: 2026-07-14.

**⚠️ Corrected 2026-07-24** (master transformation plan review): several claims below
were checked directly against `backend/app/models/*.py` and found wrong — a
facilitator-duplication claim that doesn't exist, and several table/class names that
don't match the current schema. Corrections are inline, marked with **[CORRECTED]**.
Treat this whole document as a hypothesis to re-verify against the actual model files
before trusting it, not as ground truth — that is exactly the mistake this correction
pass is fixing.

---

## Model Inventory and Authority Map

### Core Planning Hierarchy

| Concept | Authoritative table | Model class | Owning org field | Archive behaviour | Canonical ID field |
|---|---|---|---|---|---|
| Planning year | `planning_years` | `PlanningYear` | `unit_id` (squadron) or `wing_id` | `active_status` bool | `planning_year_id` (UUID) |
| Term | Embedded in `planning_years.terms` (JSON) or derived from `parade_dates.term` | — | via `planning_year_id` | N/A | `term` string (e.g. "Term 1") |
| Parade date (planning) | `parade_dates` | `ParadeDate` | via `planning_year_id` | `is_active` bool | `parade_date_id` (UUID) |
| Parade night (operational) | `parade_nights` | `ParadeNight` | `squadron_id` | `is_archived` bool | `id` (UUID) |

**Note on parade date vs parade night**: these are two separate concepts. A `ParadeDate` is a planning entry within a planning year. A `ParadeNight` is an operational record created when sessions are scheduled. They are linked via `ParadeDate.parade_night_id`. This join is intentional — the planning layer and the operational layer are separate, allowing planning without committing session slots.

### Curriculum

| Concept | Authoritative table | Model class | Owning level | Inheritance |
|---|---|---|---|---|
| Curriculum item | `curriculum_items` | `CurriculumItem` | `owning_level` (national/wing/squadron) | National items visible to all; wing items visible to wing+sqn; sqn items local only |
| Program type | `core_status` field on `CurriculumItem` | — | Set at creation | Values: `foundation`, `extension`, `optional` (migrated from `core`/`additional`) |
| Training session | `sessions` **[CORRECTED — was `training_sessions`]** | `Session` (imported as `TrainingSession` in `planning.py`) | via `parade_night_id` → `squadron_id` | — |

**[NEW, 2026-07-24]** A second, parallel curriculum/publishing model exists —
`ProgramPackage`/`ProgramItem` (`backend/app/models/program.py`), a National→Wing→Squadron
publishing workflow (draft→review→approved→published→retired→archived) served by its own
router (`routers/program.py`). No FK or code-level join was found between `ProgramItem` and
`CurriculumItem` — they appear to be entirely independent data models for an overlapping
concern. **Open question, not resolved by this pass**: is `ProgramItem` a governance/publishing
layer intended to feed or replace `CurriculumItem`, or a genuinely separate concept? Do not
assume either direction before this is confirmed directly.

### Activities and CEA

| Concept | Authoritative table | Model class | Owning level | Dedup |
|---|---|---|---|---|
| Activity (general) | `activities` | `Activity` | `owning_level`: national/wing/squadron | `cea_seq_nr` links to a legacy-pipeline CEA import (see DL-04 below) |
| CEA activity (import) | `cea_activities` | `CeaActivity` | via `planning_year_id` | `cea_activity_id` **[CORRECTED — was `external_id`]** is the CEA reference; duplicate detection by `cea_activity_id` per year, with a name+date-key fallback |
| CEA import batch | `cea_import_batches` | `CeaImportBatch` | via `planning_year_id` | — |
| Local hide (sqn overlay) | `activity_local_hides` **[CORRECTED — was `cea_local_hides`]** | `ActivityLocalHide` **[CORRECTED — was `CeaLocalHide`]** | `squadron_id` | Hides an inherited activity for one sqn; does not delete the source record |

**[NEW, 2026-07-24] — see `docs/beta/15_known_limitations.md` DL-04 for full detail**: CEA
import is actually **two separate pipelines**, not one. The `Activity`/`cea_seq_nr` row above
describes the older, `sqn_admin`-permissioned pipeline (`POST /api/activities/import-cea`,
`training.py`) with no review workflow. The `CeaActivity`/`CeaImportBatch` rows describe the
newer, `wing_admin`+-only pipeline (`POST /api/planning/years/{id}/cea/import`, `planning.py`)
with a full review/classification workflow. They were not previously documented as two
separate systems in this table.

### Facilitators and Leave

| Concept | Authoritative table | Model class | Owning org | Archive |
|---|---|---|---|---|
| Facilitator | `facilitators` | `Facilitator` | `squadron_id` | `is_archived` (`SoftDeleteMixin`) |
| Facilitator leave | `planning_facilitator_leave` **[CORRECTED — was `facilitator_leave`]** | `PlanningFacilitatorLeave` **[CORRECTED — was `FacilitatorLeave`]** | via `facilitator_id` → `squadron_id` | — |
| Scheduled session assignment (dead code — see note) | `scheduled_sessions.facilitator_id` | — | via `scheduled_session_id` | — |

**[CORRECTED, 2026-07-24] — no facilitator duplication exists.** This section previously
claimed a separate `planning_facilitators` table/`Facilitator` (planning) model requiring
double data entry. **That claim is false**, confirmed by direct inspection: only one
`Facilitator` model/table exists anywhere in `backend/app/models/` or any Alembic migration.
Planning Workspace's `/api/planning/facilitators` endpoint (`list_planning_facilitators`)
reads the *same* `facilitators` table via a different router function — a read-only overlay,
not a second data source. **Do not plan or attempt a facilitator merger migration; there is
nothing to merge.** (Corresponding correction also made in
`docs/beta/15_known_limitations.md` DL-02.)

**Separately — real, dead code found in this same area (2026-07-24)**: `scheduled_sessions`
(model `ScheduledSession`) has no live create/update path anywhere in the codebase — confirmed
zero `ScheduledSession(...)` instantiations exist. The one endpoint that queried it for
facilitator workload stats (`GET /years/{id}/facilitators/{id}/workload`) always silently
returned zero regardless of real workload; this has been fixed to query `TrainingSession`
instead (see `docs/beta/15_known_limitations.md` DL-01). The `scheduled_sessions` table and
`ScheduledSession` model are left in place, unused, rather than dropped in that fix — a later,
purely cosmetic cleanup could remove them, but nothing depends on them today.

### Physical Spaces — RESOLVED 2026-07-24

| Concept | Authoritative table | Model class | Used by |
|---|---|---|---|
| Training area / room | `training_areas` | `TrainingArea` | connected-frontend Resources page (`training.py` router) **and** Planning Workspace Rooms tab (`planning.py` router — now reads/writes the same table) |

**[CORRECTED, 2026-07-24]** This section previously described `planning_locations`/
`PlanningLocation` as a separate, actively-used table requiring a future migration. That
migration has been done: `/api/planning/locations` (`planning.py`) now reads and writes
`training_areas` directly instead of the separate `planning_locations` table, following the
same pattern already used correctly for facilitators. Response JSON shape is unchanged
(`location_id`/`unit_id`/`name`/`location_type`/`capacity`/`notes`/`active_status`), so no
frontend changes were needed. Verified live: a room created in either app now appears
immediately in the other.

**Bonus finding from this fix**: `create_session`/`update_session`'s room-resolution logic
(`db.get(TrainingArea, body.location_id)`) only ever looked up `TrainingArea` rows — a
`location_id` from the old `PlanningLocation`-backed endpoint silently failed to resolve, so a
room picked in Planning Workspace would not actually attach to the session (no error, just an
unassigned room). This is now fixed as a direct side effect of the merge.

**Not touched**: the `planning_locations` table and `PlanningLocation` model are left in place
(no migration, no drop) — nothing in any live, reachable code path depends on them, so this
avoids any data-loss or FK-constraint risk. A later, purely cosmetic cleanup pass could drop
the now-orphaned table.

### Notices and Announcements

| Concept | Table | Model | Scope |
|---|---|---|---|
| Parade notice | `parade_notices` | `ParadeNotice` | Per `parade_date_id` |
| Action item | `action_items` | `ActionItem` | Per squadron or wing |

### Holidays and Schedules

| Concept | Table | Model | Scope |
|---|---|---|---|
| Planning holiday | `planning_holidays` | `PlanningHoliday` | Per `planning_year_id` |
| Anchor event (Wing HQ) | `anchor_events` | `AnchorEvent` | Per `planning_year_id` or wing |
| Wing HQ event | `wing_hq_events` | `WingHQEvent` | Per wing; squadron overlay via `squadron_event_status` |

### Scheduled Sessions

| Concept | Table | Model | Notes |
|---|---|---|---|
| Scheduled session **[CORRECTED — dead code]** | `scheduled_sessions` | `ScheduledSession` | **Not live.** No `ScheduledSession(...)` is instantiated anywhere in the codebase — the real, live create/update path for a curriculum item assigned to a parade date slot is `TrainingSession` (`sessions` table, see Curriculum section above), created via `assign_mission`/`create_session`/`update_session`. `ScheduledSession` and this table are unused; left in place rather than dropped since removing them carries no functional benefit and a table drop is unnecessary risk for a purely cosmetic cleanup. |
| Planning conflict | `planning_conflicts` | `PlanningConflict` | Detected during run-checks; can be overridden |
| Prep rule | `prep_rules` | (query only) | Configures lead-time requirements |

---

## Audit Trail

All privileged mutations are written to `audit_logs` via the `audit()` service. The audit log is:
- Append-only (no update/delete endpoint exists)
- Scoped to the calling user and organisation
- Indexed on `(object_type, object_id)` for efficient drilldown

No model or endpoint bypasses the audit service for privileged write operations.

---

## Import Identity and Duplicate Prevention

| Import type | Dedup key | Scope |
|---|---|---|
| CEA activities (reviewed pipeline, `planning.py`) | `cea_activity_id` **[CORRECTED — was `external_id`]**, with a name+date-key fallback | Per `planning_year_id` |
| CEA activities (legacy pipeline, `training.py`) | `cea_seq_nr` only, no fallback, no review step — see `docs/beta/15_known_limitations.md` DL-04 | Per squadron |
| Curriculum CSV import | `code` (LEAFlet code) | Per `owning_level` + `squadron_id` |
| Wing HQ calendar | `event_id` from Wing HQ | Per wing |

---

## Cache Keys (React frontend)

React Query is the client cache. Key patterns:

| Data | Query key | Stale time |
|---|---|---|
| Planning years | `["planning-years"]` | default |
| Annual program | `["planning-annual", yearId]` | 5 min |
| Missions | `["planning-missions", yearId, "backlog"]` | 3 min |
| CEA activities | `["cea-activities"]` | 2 min |
| CEA batches | `["cea-batches", yearId]` | 2 min |
| Command centre | `["command-centre", yearId]` | 90 sec |
| Night summaries | `["night-summaries", yearId]` | not set (default) |

No cross-squadron data sharing via cache. All query keys are derived from the authenticated user's planning year, which is already scope-restricted by the backend.

---

## Outstanding Consolidations (Post-Beta)

**[CORRECTED, 2026-07-24]**: two of the four items below were already resolved or never real;
see `docs/beta/15_known_limitations.md` for the up-to-date DL-01 through DL-04 entries.

| Priority | Duplication | Status |
|---|---|---|
| ~~HIGH~~ | ~~Facilitator split~~ | **Not real — corrected 2026-07-24.** No `planning_facilitators` table ever existed. |
| ~~MEDIUM~~ | ~~Physical spaces~~ | **Resolved 2026-07-24.** `/api/planning/locations` now reads/writes `training_areas` directly. |
| MEDIUM | CEA import — two pipelines, different role gates (`sqn_admin` vs `wing_admin`+) | **Open, blocked on a product decision** — see DL-04. Not a technical-only fix; redirecting one to the other removes a real capability or loosens a real permission gate without confirmation either is intended. |
| LOW | `core_status` value rename (`core`→`foundation`, `additional`→`extension`) | Not independently re-verified in the 2026-07-24 pass — check current migration state before assuming this is still pending. |
