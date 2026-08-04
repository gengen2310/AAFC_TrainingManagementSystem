# Data Migration Plan — Stage 0 starting point

No destructive migration has been run or planned yet. This document records the
migration *decisions* as each domain-model consolidation (see
`domain_model_inventory.md`) actually gets designed — not a complete upfront plan
for work that hasn't started.

## Principles (from the remediation instruction + capability-preservation.md, restated for reference)

1. Normalise names only for comparison — never for storage.
2. Match by organisation + strong identifiers; auto-map only unambiguous matches.
3. Ambiguous records get a report, never an auto-merge.
4. Populate canonical foreign keys; preserve old IDs through a mapping table.
5. Add compatibility adapters before updating either frontend.
6. Verify historical schedules/records survive unchanged.
7. Destructive retirement of the old table/model is a separate, later,
   explicitly-authorised step — never bundled into the migration itself.

## Migrations actually run this session

**None required.** Every item shipped in the "TMS/Planning Workspace Integration"
pass and Stage 0 of this program was additive (new endpoints, new columns already
existed, or pure read-path changes) — confirmed via `alembic heads` staying at the
single existing head `b99b8f07eded` throughout. This is worth stating plainly: nine
distinct fixes landed without a single schema migration, which is itself evidence
the underlying data model was closer to sound than the remediation instruction's
framing assumed (see `master_remediation_plan.md`'s "Not a blank slate" section).

## Duplicate/near-duplicate migration designs (Section 4 format)

Design only — none of the rows below have been implemented. Each still needs an
explicit go/no-go decision (most require product input, not just engineering
judgement) before any code changes.

| Existing names | Meaning | Canonical name (proposed) | Compatibility plan | Migration |
|---|---|---|---|---|
| `TrainingArea` / `PlanningLocation` | A physical room/space | `TrainingArea` (already the de facto canonical — router-level reconciliation done) | None needed — both frontends already resolve to `training_areas` | **Retirement only**: drop the now-orphaned `planning_locations` table and `PlanningLocation` model once confirmed nothing reads it (grep-confirmed zero live query paths today). Zero data migration — no rows in the old table are the source of truth for anything live. Needs explicit authorisation per capability-preservation.md §1 before the drop (destructive, even though the table is unused). |
| `Session`/`TrainingSession` / `ScheduledSession` | A curriculum item scheduled into a parade-night slot | `Session` (already canonical) | None needed | **Retirement only**: same shape as above — `scheduled_sessions` table confirmed zero live writes. Authorisation required before drop. |
| `Activity` / `CeaActivity` | A training/administrative event on a date | Two real options, needs a decision: **(a)** keep split — `Activity` stays the operational/internally-created record, `CeaActivity` stays the external-feed staging/review record, permanently — this is closest to the instruction's own "Preferred outcome" wording ("a CEA import row or staging record may exist for review and provenance"); **(b)** fully merge into one `Activity` table with a `source` discriminator column and CEA-specific fields (`cea_activity_id`, `classification_status`, `is_removed_from_cea`) added to `Activity` itself | **This session already shipped the read-side compatibility path** regardless of which option is chosen later: Planning Workspace now reads canonical `Activity` rows (`GET /api/activities`) alongside its own `CeaActivity` rows, read-only, no write-path change. That satisfies "no second source of truth for viewing" today without committing to (a) or (b) | If (b) is chosen: backfill `Activity` rows from `CeaActivity` (mapping `cea_activity_id`→`Activity.cea_seq_nr`, already a column), keep `CeaActivity` as an immutable import-history/provenance table (rename conceptually, not necessarily physically), update Planning Workspace's CEA-import write path to create/update `Activity` rows instead. Real backfill migration, needs a decision first — **not scheduled** |
| `ParadeDate` / `ParadeNight` | "A parade night on a specific date" | Two real options: **(a)** keep split (current design) — `ParadeDate` is the planning-layer entry (can exist before any operational commitment), `ParadeNight` is the operational record (created once sessions are scheduled) — this split is **documented as intentional** in `docs/beta/28_authoritative_data_model.md` ("allowing planning without committing session slots"), not accidental drift; **(b)** merge into one table with a `planning_status` discriminator | Given (a) is explicitly documented as an intentional design (not found duplication), default recommendation is **keep split**, re-verify the FK-bridge behaviour (`ParadeDate.parade_night_id`) still matches this description rather than migrate | No migration recommended unless a concrete symptom (not just a naming-lint pass) shows the split causing real problems |
| `CurriculumItem` / `ProgramItem`+`ProgramPackage` | Curriculum content: phase/element/duration/suitability/ownership | `CurriculumItem` (the live, seeded, UI-reachable system) — `program.py`'s tables are very likely dead/superseded (see `domain_model_inventory.md`'s Stage 1 finding) | **Needs explicit product confirmation before any code change** — this is the biggest, most consequential finding this pass and must not be acted on unilaterally. If confirmed dead: no migration needed (zero real data in the `program_*` tables), just a retirement decision. If NOT dead (e.g. reserved for an unbuilt import pipeline): Section 6's "Program and Reference Data" capability could reuse `ProgramItemDeployment`'s inheritance model and `ProgramItem.core_status`'s richer value set (`core|optional|extension|local|wing_required|national_required`) as a head start, rather than designing new reference-data tables from scratch | Blocked on the product-confirmation question above |

## Anticipated future migrations (not yet started, additive-only, lower risk)

- **Reference-data tables** (Training Stage, Facilitator Type, Subject Area,
  Notice Type, etc., Section 6) — entirely new tables, additive, no existing data
  to migrate other than possibly backfilling free-text values into the new scoped
  records. Blocked on the `ProgramItem` question above — building these from
  scratch before that's resolved risks creating a *third* parallel system.
