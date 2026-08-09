# Data quality register

Status: initial pass, 2026-08-09. Per §10/§29 — orphans, shadow records,
duplicate business objects, free-text values that should be canonical
references, and other data-integrity risks. This is a design-time register
(what the schema *permits* to go wrong), not a live data audit of staging/
production row counts — that is separate follow-up work.

## Confirmed structural risks (schema allows these; not yet measured how often they occur in real data)

1. **`Facilitator.subject_areas` is a denormalized string list, not an FK to
   `SubjectAreaTag`** (see `canonical-data-map.md`). A tag can be renamed or
   archived in the catalogue while stale copies of its old name remain on
   facilitator records indefinitely. Root cause of REM-128. Structural risk
   remains even after REM-128's test-hygiene fix — the underlying schema
   shape is unchanged.
2. **`Session.cadet_group` and `Cadet.phase` are free-text strings, not FKs**
   (see `parallel-class-impact-analysis.md`). No canonical constraint means
   two different spellings/casings of the same intended value can silently
   diverge without any database-level detection.
3. **Dead `PlanningLocation`/`ScheduledSession` models** (`planning.py`) —
   zero live call sites, confirmed in an earlier pass this program. Not a
   live risk (nothing writes to them), but their continued presence in the
   schema is a source of confusion for anyone reading the model file cold —
   candidate for a cheap, low-risk deletion (§9's "no unexplained duplicate
   data systems").
4. **Two facilitator-list read paths with independently maintained
   scoping logic** (`training.py`'s `_view_squadron_id()` pattern vs
   `planning.py`'s own ad hoc filter) — not a data-quality risk in the
   traditional sense, but a "same concept, two code paths" risk that already
   produced one real defect (REM-130) and could silently regress again if
   only one path is fixed in a future change.

## Not yet measured this pass (needs a live data query, not schema inspection)

- Orphaned Sessions (no matching ParadeNight).
- Sessions referencing a soft-deleted Facilitator/TrainingArea by ID.
- HolidayPeriod rows with no matching PlanningYear (shouldn't be possible via
  the API, but worth a direct row-count check given the FK is not itself
  enforced at the SQLite level in local/test environments).
- Duplicate-named Squadrons/Facilitators/TrainingAreas.
- Stale CEA import batches with no corresponding live Activity.

Recorded as open rather than fabricated — running these as real queries
against a staging snapshot is the next concrete step, not attempted in this
documentation-only pass.
