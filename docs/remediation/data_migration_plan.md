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

## Anticipated future migrations (not yet started)

- **`PlanningLocation` retirement** — once the router-level reconciliation
  (confirmed complete) is trusted long enough, the dead table itself could be
  dropped. Requires separate explicit authorisation per capability-preservation.md
  §1 — not scheduled.
- **`Activity`/`CeaActivity` consolidation** (if a single-table outcome is chosen
  over the current dual-pipeline-with-shared-read design) — would need a real
  backfill/mapping-table migration. Not designed yet; REM-01 is currently tracking
  the *design decision*, not an implementation.
- **`ParadeDate`/`ParadeNight` consolidation** — not designed yet.
- **Reference-data tables** (Training Stage, Facilitator Type, Subject Area,
  Notice Type, etc., Section 6) — entirely new tables, additive, no existing data
  to migrate other than possibly backfilling free-text values into the new scoped
  records. Not designed yet.
