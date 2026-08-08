# Canonical Data Dictionary

Program: Final Remediation, Product Hardening and Public-Release Program, Section 8.

Source of truth: `docs/qualification/data_relationship_inventory.csv` (25 entities, full detail including duplication-risk notes per entity) -- this document is a readable summary over that CSV, not a re-derivation. Compiled during Phase A of the prior qualification program (2026-08-08) and re-verified for this program's headline finding (TrainingArea vs PlanningLocation -- see `duplicate_concept_review.md`).

## Entities

| Entity | Canonical table | Canonical ID | Owner scope | Parent |
|---|---|---|---|---|
| National | `national_entities` | id (UUID) | national | (root) |
| Wing | `wings` | id (UUID) | national | National (national_id FK->national_entities.id) |
| Squadron | `squadrons` | id (UUID) | squadron | Wing (wing_id FK->wings.id) |
| Specialist Unit | `squadrons (unit_type column)` | squadrons.id (UUID) | squadron | Wing |
| Flight grouping | `flights` | id (UUID) | squadron | Squadron (squadron_id FK->squadrons.id) |
| Account | `users (+ access_codes)` | users.id (UUID) | national/wing/squadron per role | org entity via national_id/wing_id/squadron_id FKs; flight_id FK |
| Cadet | `cadets` | id (UUID) | squadron | Squadron (squadron_id FK) |
| Facilitator | `facilitators` | id (UUID) | squadron | Squadron (squadron_id FK) |
| Facilitator Type | `facilitator_type_tags (+ facilitators.type free-text)` | facilitator_type_tags.id (UUID) | global/wing/squadron (scope column) | Squadron (squadron_id FK, nullable) |
| Subject Area | `subject_area_tags (+ facilitators.subject_areas JSON)` | subject_area_tags.id (UUID) | global/wing/squadron (scope column) | Squadron (squadron_id FK, nullable) |
| Training Stage | `(fragmented) phases / curriculum_phases / custom_phases + free-text phase columns` | phases.id / curriculum_phases.id / custom_phases.id (UUIDs) | global (phases); scoped (curriculum_phases); squadron (custom_phases) | varies (custom_phases.squadron_id FK) |
| Curriculum Item | `curriculum_items (+ program_items parallel model)` | curriculum_items.id (UUID) | national/wing/squadron (owning_level) | org via owning_level (wing_id/squadron_id plain String, no FK) |
| Activity | `activities (+ cea_activities parallel)` | activities.id (UUID) | national/wing/squadron (owning_level) | org (national_id/wing_id/squadron_id all plain String, no FK) |
| CEA import | `cea_import_batches (+ cea_activities rows)` | cea_import_batches.id (UUID) | wing (wing_id plain String) | PlanningYear (planning_year_id FK) |
| Holiday | `holiday_periods` | id (UUID) | (via planning year) | PlanningYear (planning_year_id FK) |
| Notice | `planning_notices` | id (UUID) | (via planning year/parade date) | ParadeDate (parade_date_id FK, NOT NULL) + PlanningYear (FK) |
| Planning Year | `planning_years` | id (UUID) | squadron (unit_id) / wing | Squadron (unit_id FK); wing_id plain String |
| Parade Night | `parade_nights (+ parade_dates parallel)` | parade_nights.id (UUID) | squadron | Squadron (squadron_id FK); wing_id plain String (no FK) |
| Session | `sessions (canonical) + scheduled_sessions (legacy, never written)` | sessions.id (UUID) | squadron | ParadeNight (parade_night_id FK) |
| Training Area | `training_areas (canonical) + planning_locations (legacy, never written)` | training_areas.id (UUID) | squadron | Squadron (squadron_id FK) |
| Equipment | `equipment` | id (UUID) | squadron | Squadron (squadron_id FK) |
| Conflict | `planning_conflicts (+ source_conflicts + computed resource clashes)` | planning_conflicts.id (UUID) | (via planning year) | PlanningYear (FK) / ParadeDate (FK) / ScheduledSession (FK) |
| SITREP | `cadets (sitrep_part_1_status, sitrep_part_2_status columns)` | (no own id — columns on cadets.id) | squadron | Cadet |
| Promotion requirement | `promotion_requests (program content) — NOT cadet promotion` | promotion_requests.id (UUID) | scope-to-scope (from_scope/to_scope) | ProgramItem (program_item_id, String, NO FK) |
| Audit event | `audit_logs` | id (UUID) | all (records role/scope/wing/squadron) | (references any object via object_type/object_id, unenforced) |

## Entities with a recorded duplication-risk note (see the CSV for full text)

| Entity | Risk classification (first words of the CSV note) |
|---|---|
| National | SAME CONCEPT single table. |
| Wing | SAME CONCEPT single canonical table. |
| Squadron | SAME CONCEPT single canonical table. |
| Specialist Unit | NOT A SEPARATE ENTITY. |
| Flight grouping | SAME CONCEPT single table. |
| Account | SAME CONCEPT. |
| Cadet | SAME CONCEPT single table. |
| Facilitator | SAME CONCEPT single canonical table read by both frontends. |
| Facilitator Type | SAME CONCEPT, INTENTIONAL DUAL REPRESENTATION. |
| Subject Area | SAME CONCEPT, same intentional dual shape as Facilitator Type. |
| Training Stage | THREE tables model the same 'phase/stage' concept: phases (cadet-program global catalogue), curriculum_phases (scoped catalogue mirroring elements), custom_phases (per-squadron). |
| Curriculum Item | curriculum_items is canonical for Main TMS training. |
| Activity | DIFFERENT-BUT-OVERLAPPING. |
| CEA import | SAME CONCEPT single batch table. |
| Holiday | SAME CONCEPT single table. |
| Notice | SAME CONCEPT single table. |
| Planning Year | SAME CONCEPT single table. |
| Parade Night | TWO PARALLEL MODELS of the parade evening: parade_nights (Main TMS, the delivery record) and parade_dates (Planning Workspace, the planning-calendar slot). |
| Session | TWO TABLES, ONE LIVE. |
| Training Area | TWO TABLES, ONE LIVE. |
| Equipment | SAME CONCEPT single table. |
| Conflict | THREE DIFFERENT CONCEPTS, SIMILAR NAME. |
| SITREP | SINGLETON DATA ISLAND. |
| Promotion requirement | NAMING COLLISION — needs human judgment. |
| Audit event | SAME CONCEPT single canonical immutable table. |

## Tenancy model (confirmed, not re-derived)

National -> Wing -> Squadron only. "Specialist Unit" is not a separate tenancy level -- it is `squadrons.unit_type` (`standard_squadron`, `specialist_squadron`, `specialist_flight`, `support_unit`), correctly reusing the Squadron tenancy model rather than a parallel entity. "Flight" (`flights` table) is a sub-squadron cadet-organisation grouping, not a tenancy level -- per `.claude/rules/architecture.md`, no Flight-scoped permission check should ever be added.

## Archive-behaviour inconsistency (recorded, not fixed this pass)

Archive semantics differ across entities: most training/org entities use `SoftDeleteMixin` (`is_archived` + `archived_at`); reference-tag tables use `is_active` only; `planning_notices`/`cea_activities` have `is_archived` without `archived_at`; `holiday_periods` has no archive at all (hard delete only); `planning_years` uses `active_status` + dependency-gated hard delete with no `is_archived`. This is a real inconsistency worth a deliberate design pass if archive/restore parity across entities becomes a priority -- not actioned in this pass since it is a cross-cutting schema decision, not a single fixable defect.

*No application code, migration, or data was modified in the preparation of this document.*
