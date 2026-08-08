# Data Integrity Report

Program: Final Remediation, Product Hardening and Public-Release Program, Section 8.
Consolidates and updates `docs/qualification/03_data_integrity_review.md` (Phase A Data Integrity
Auditor pass, 2026-08-08) against current state. Full per-finding evidence lives in that document and
`docs/qualification/data_relationship_inventory.csv` — not reproduced here in full; only status
changes and this program's own additions are detailed.

## P1 findings — status: CLOSED

Both P1 (silently wrong user-visible data) findings from the prior pass are fixed, tested, and
deployed to production as of this program's start:

1. `get_command_centre` reading the never-populated `scheduled_sessions` table for unscheduled-item
   and unstaffed-night counts — fixed `QUAL-001` (commit `e747d3b`), migrated to the
   `ParadeDate → ParadeNight → TrainingSession` join. 3 regression tests, verified fail-before/
   pass-after via `git stash`. Live-verified against staging: `unscheduled_required` went from "every
   core item" to a real count (7), `nights_missing_facilitator` from "always 0" to a real count (1).
2. `add_facilitator_leave`'s conflict-check computing "affected sessions" from the same dead table —
   same fix, same commit.

No new P1 (silently-wrong-data) findings were made in this pass.

## P2 findings — status: unchanged, tracked, not actioned

Per the prior review's own recommendation ("schedule after P1; needs a data audit before any
constraint change"), none of the following were actioned this pass — each still requires either a
live-data audit before a constraint could safely be added, or a Phase C/D architecture decision, not
a quick fix:

- **Orphan-row risk**: numerous tenancy (`wing_id`) and cross-model reference columns (see the prior
  review §2c/§4 for the full list) are plain `String` with no `ForeignKey()` declared, or are declared
  FKs with no `ON DELETE` behavior. No live orphan rows were queried or confirmed in either pass (both
  are read-only-of-schema reviews, not live-data audits) — the *pathways* are documented, not proven
  live incidents.
- **Missing uniqueness constraints**: `cadets.service_number` (indexed, not unique),
  `subject_area_tags`/`facilitator_type_tags` (no unique on `(normalised_name, scope, ...)`),
  `planning_years` (no unique on `(unit_id, year)`), `parade_nights` (no unique on
  `(squadron_id, date)`). Adding a constraint to a table that may already contain duplicates is itself
  risky without first auditing existing data — not attempted this pass.
- **Singleton data islands**: SITREP (`cadets.sitrep_part_1_status`/`_part_2_status` — two nullable
  strings, no table, no history, no dedicated write endpoint) and cadet promotion
  (`cadets.promotion_interest` — a single free-text field, no request/approval workflow) remain
  under-modelled relative to what a "Promotion requirement" entity would suggest. Product-scope
  questions, not engineering defects — routed to the personnel-information and UX review docs, not
  resolved here.
- `anchor_events.cea_activity_id` is declared `Integer` while `cea_activities.id` is a UUID string —
  this FK can never actually join. Confirmed still present, still almost certainly vestigial. Not
  removed this pass (needs the capability-preservation removal record, i.e. confirmation nothing reads
  it before deleting the column).

## This program's own additions

- Confirmed (§ `duplicate_concept_review.md`) that `scheduled_sessions`/`planning_locations` now have
  **zero** call sites of any kind (read or write) — stronger than the prior pass's finding, since the
  one remaining legacy read was removed by `QUAL-002` (commit `0170714`) shortly after the prior
  review was written.
- No new duplicate-table or missing-FK findings were made — the prior pass's coverage (25-entity
  `data_relationship_inventory.csv`) was treated as comprehensive and re-verified spot-checks (the
  headline `PlanningLocation` finding) confirmed its methodology was sound, so it was not re-run in
  full from scratch.

## What this report does NOT cover (honest scope boundary)

- No live database was queried for actual orphan rows or duplicate records in either this pass or the
  prior one — both are schema/code-level reviews. A genuine orphan-row audit requires running queries
  against a real (staging, never production) database and is recommended as a distinct follow-up if
  the P2 orphan-risk items are to be resolved rather than merely tracked.
- Personnel-information classification (SITREP, cadet promotion) is flagged here as a data-modelling
  gap but not classified for sensitivity — that is `docs/beta/`-track work, not repeated here.

*No application code, migration, or data was modified in the preparation of this document.*
