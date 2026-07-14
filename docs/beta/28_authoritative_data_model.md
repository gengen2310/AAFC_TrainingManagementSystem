# AAFC TMS — Authoritative Data Model

Phase 8 output. Every shared concept mapped to its authoritative source.
Created: 2026-07-14.

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
| Training session | `training_sessions` | `Session` | via `parade_night_id` → `squadron_id` | — |

### Activities and CEA

| Concept | Authoritative table | Model class | Owning level | Dedup |
|---|---|---|---|---|
| Activity (general) | `activities` | `Activity` | `owning_level`: national/wing/squadron | `national_id` links to national source |
| CEA activity (import) | `cea_activities` | `CeaActivity` | via `planning_year_id` | `external_id` is the CEA reference; duplicate detection by `external_id` per year |
| CEA import batch | `cea_import_batches` | `CeaImportBatch` | via `planning_year_id` | — |
| Local hide (sqn overlay) | `cea_local_hides` | `CeaLocalHide` | `squadron_id` | Hides an inherited activity for one sqn; does not delete the source record |

### Facilitators and Leave

| Concept | Authoritative table | Model class | Owning org | Archive |
|---|---|---|---|---|
| Facilitator (planning) | `planning_facilitators` | `Facilitator` (planning) | `squadron_id` | `is_archived` |
| Facilitator (training) | `facilitators` | `Facilitator` (training) | `squadron_id` | — |
| Facilitator leave | `facilitator_leave` | `FacilitatorLeave` | via `facilitator_id` → `squadron_id` | — |
| Scheduled session assignment | `scheduled_sessions.facilitator_id` | — | via `scheduled_session_id` | — |

**Duplication flag**: `planning_facilitators` (planning module) and `facilitators` (training module) are separate tables with separate records. A user must add a facilitator in both places for full functionality. This is the primary outstanding duplication in the data model. Merging requires: (1) deciding which FK the planning module uses, (2) migrating `planning_facilitators` records to reference `facilitators`, (3) updating all planning callers. Deferred to post-beta.

### Physical Spaces — KNOWN DUPLICATION

| Concept | Authoritative table | Model class | Used by |
|---|---|---|---|
| Training area / room | `training_areas` | `TrainingArea` | connected-frontend Resources page; `training.py` router |
| Planning location | `planning_locations` | `PlanningLocation` | Planning Workspace Rooms tab; `planning.py` router |

**Both represent physical spaces** (rooms, outdoor areas, training facilities) owned by a squadron. They are separate tables with overlapping fields:

| Field | `training_areas` | `planning_locations` |
|---|---|---|
| Squadron FK | `squadron_id` | `unit_id` |
| Name | `name` | `name` |
| Type | `type` + `indoor_outdoor` | `location_type` |
| Capacity | `capacity` | `capacity` |
| Notes | `notes` | `notes` |
| Active | `active_status` | `active_status` |
| Soft delete | `is_archived` (SoftDeleteMixin) | None |

**Decision**: `training_areas` is the **canonical** source (older, more complete, has soft-delete, serves the primary connected-frontend). `planning_locations` is a secondary overlay used only by Planning Workspace's session scheduling UI.

**Planned merger (post-beta)**: Migration to add `training_area_id FK` on `planning_locations` and deprecate redundant fields. Callers in `planning.py` router updated to join through `training_areas`. UI in Planning Workspace updated to read from unified `training_areas` endpoint. Risk: medium (two routers, two frontends, existing session assignment references).

**For this release**: Both tables remain operational independently. A squadron that creates rooms via the connected-frontend Resources page will NOT automatically see them in the Planning Workspace Rooms tab (and vice versa). This is a documented limitation.

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
| Scheduled session | `scheduled_sessions` | `ScheduledSession` | Curriculum assigned to a parade date slot |
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
| CEA activities | `external_id` (from CEA system) | Per `planning_year_id` |
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

| Priority | Duplication | Effort | Risk |
|---|---|---|---|
| HIGH | Facilitator split (`facilitators` vs `planning_facilitators`) | Medium | Migration + 2 router callers |
| MEDIUM | Physical spaces (`training_areas` vs `planning_locations`) | Medium | Migration + 2 routers + 2 frontend UIs |
| LOW | `core_status` value rename (`core`→`foundation`, `additional`→`extension`) | Low | Already in stash; needs migration ID fix |
| LOW | `TrainingArea.squadron_id` vs `PlanningLocation.unit_id` naming inconsistency | Trivial | Can be addressed in merger |
