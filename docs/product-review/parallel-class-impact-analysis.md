# Parallel Training Class — impact analysis

Required by the whole-system hardening program addendum §85 before any schema
change. Findings below are from direct inspection of
`backend/app/models/training.py`, `backend/app/models/program.py`,
`backend/app/models/planning.py`, `backend/app/models/organisations.py` at
commit `4c5e384` — grep for `stage_id`, `phase_id`, `training_stage`, `cohort`,
`class`, `audience`, `year_group`, `group`, `session.stage`, `curriculum.stage`.

## Finding 1 — there is no Training Class (cohort) concept anywhere in the schema

Confirmed by full-text inspection of every model file. The closest existing
concepts are:

- `CurriculumPhase` (`training.py:346`) — a properly scoped
  (system/national/wing/squadron) reference-data catalogue of phase/stage
  *names* (Orientation, Initial, Junior, Intermediate, Senior, Bronze, Silver,
  Gold, plus locally-created ones). This already satisfies the addendum's
  §32.1 definition of **Training Stage** almost exactly as specified — no new
  table is needed for the Stage half of the model.
- `CustomPhase` (`training.py:42`) — an older, squadron-scoped phase-name
  table, narrower than `CurriculumPhase`. Needs a follow-up check for whether
  it is still live or superseded (out of scope for this pass; flagged as
  CLASS-14's migration surface, not investigated further here).

Neither of these, nor anything else in the schema, represents a **local group
of cadets undertaking a stage** — the addendum's §32.2 **Training Class**
concept. This confirms addendum §33 ("Do not impose one class per stage")
describes a real, currently-unimplemented requirement, not an existing gap in
an existing feature.

## Finding 2 — the "ONE STAGE = ONE COLUMN = ONE CLASS" anti-pattern the addendum warns about is real, in two places

1. `Session.cadet_group` (`training.py:112`) — a single plain-text nullable
   string column: `orientation/initial/junior/intermediate/senior`. A Session
   can record exactly one audience value, as free text, with no FK, no
   many-to-many relationship, and no way to distinguish "Senior 1" from
   "Senior 3" — both would be stored as the identical string `senior`. This is
   the direct root cause blocking addendum §40/§41 (Session ↔ Training Class
   many-to-many) and §69 (per-class facilitator/resource conflict detection).
2. `Cadet.phase` (`training.py:242`) — also a single plain-text nullable
   string column, one value per cadet. This cannot represent a cadet
   concurrently enrolled in, e.g., a Senior class (Foundation) and a Bronze
   class (Extension) at the same time — the exact scenario addendum §38/§92
   requires (CLASS-09). `Cadet.flight` (`training.py:243`) is a separate,
   unrelated free-text field for sub-squadron grouping — per
   `.claude/rules/architecture.md`, Flight is not a tenancy level and must not
   be conflated with Training Class; confirmed no overlap in the schema today.

Neither field is a foreign key to any catalogue table — both are informal,
uncontrolled strings. This also explains why `Session.phase_at_time` exists
alongside `cadet_group`: `phase_at_time` snapshots the *curriculum item's*
phase (for historical accuracy if the curriculum catalogue changes later),
which is a different concept from *which class attended* — the addendum's
distinction between "what was taught" and "who attended" (§42) is already
partially honoured for curriculum, but the "who" side has no structured
representation at all.

## Finding 3 — `program.py` (Phase/ProgramPackage/ProgramItem) is off-limits and is not the right place for this anyway

`Phase` in `program.py` is part of the `ProgramItem`/`ProgramPackage` system
that an earlier explicit user instruction this program marked off-limits (see
`docs/product-review/current-system-map.md`). It is also architecturally the
wrong layer for Training Class: `ProgramItem`/`ProgramPackage` model
*curriculum content packaging*, not *cadet cohort membership*. The new
Training Class model belongs alongside `CurriculumPhase`/`Session`/`Cadet` in
`training.py`, not in `program.py`. This program's Training Class work will
not touch `program.py`.

## Finding 4 — reusable patterns already proven in this codebase

- **Scoped reference data**: `CurriculumPhase`/`CurriculumElement`/
  `SubjectAreaTag`/`FacilitatorTypeTag` all share one proven shape
  (`scope_level` + nullable `wing_id`/`squadron_id`, visibility = national +
  own-wing + own-squadron). A `TrainingClass` row itself is squadron-and-year
  scoped (addendum §37, "year-specific"), not national/wing-inheritable like
  these — closer in shape to `PlanningYear` (`squadron_id` + `year`-scoped,
  `active_status`, `version` for optimistic locking) than to the
  national-inheritance pattern. Use `PlanningYear`'s shape as the closer
  template; reuse `CurriculumPhase`'s shape only for the Training Stage
  catalogue, which already exists.
- **Optimistic locking**: `ParadeNight`, `PlanningYear`, `Session` all carry a
  `version` integer column with the same "two concurrent PATCHes silently
  last-write-win" rationale documented in `ParadeNight`'s own model comment.
  `TrainingClass` needs the same, since class renames/archives are exactly
  the kind of low-frequency-but-real-conflict edit this pattern protects.
- **Soft delete / archive**: `SoftDeleteMixin` is used throughout
  (`CurriculumItem`, `ParadeNight`, `Session`, `Facilitator`, `TrainingArea`,
  `Equipment`, `Activity`, `Cadet`). `TrainingClass` should use it too —
  addendum §62/§63 (split/merge) explicitly require historical classes to
  survive, not be hard-deleted.
- **Many-to-many with metadata**: no existing exact precedent for a
  Session↔TrainingClass audience table in this schema; closest shape is
  `ParadeNightTimingOverride`'s explicit join-row-with-reason pattern
  (`training.py:304`) — worth following for the audience table's own
  "combined vs split, with an optional per-class outcome exception" needs
  (addendum §48, §59.1/§59.2).

## Proposed target shape (design only — not yet implemented)

```
TrainingClass (training.py, alongside CurriculumPhase/Session/Cadet)
  id, squadron_id (FK squadrons), training_year_id (FK planning_years),
  training_stage_id (FK curriculum_phases), display_name, sequence,
  active_status (SoftDeleteMixin), start_date/end_date (nullable),
  expected_count (nullable), notes (nullable),
  version (optimistic locking), created_by/updated_by, TimestampMixin

SessionAudience (join table, training.py)
  id, session_id (FK sessions), training_class_id (FK training_classes),
  outcome_override (nullable — addendum §48's per-class exception),
  outcome_override_reason (nullable)

CadetClassMembership (training.py) — ONLY if individual cadet tracking is
  in current approved scope; addendum §39 explicitly permits class-level
  planning without named cadets. Needs a product decision, not an engineering
  default. Not designed further in this pass.
  id, cadet_id (FK cadets), training_class_id (FK training_classes),
  start_date, end_date (nullable), active_status, source, created_by
```

`Session.cadet_group` and `Cadet.phase` are NOT dropped in the same
migration — per `.claude/rules/capability-preservation.md` and this program's
own §86/§87 (safe migration, backward compatibility), the existing
single-string fields stay in place as a read compatibility path while every
new planning surface moves to `SessionAudience`. A follow-up migration to
formally deprecate them is a separate, later, explicitly-flagged step once
every consumer (Mission Backlog, Weekly Program, dashboards, both frontends)
has been migrated and verified — not attempted in this pass.

## What this pass did NOT do

This document is analysis only, per addendum §85's own instruction to
document impact *before* touching schema. No migration, model, or API change
has been made yet. The backend model/migration/API implementation is tracked
as follow-up work (see the program status note in
`docs/release/final_release_program_2026.md`).

## Status

Confirms: CLASS-01 through CLASS-14 (per addendum §103) are real, currently
unaddressed gaps, not already-solved problems. Recorded in
`docs/remediation/master_gap_register.csv`.
