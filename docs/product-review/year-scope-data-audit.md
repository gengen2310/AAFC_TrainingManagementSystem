# Year-scope data audit

Date: 2026-08-29
Spec: `docs/superpowers/specs/2026-08-28-training-year-context-model.md`

What is actually scoped to a Training Year, measured from the models and from
the live staging database — not from recollection.

## 1. Foreign keys to `planning_years`

Nine, four of them NOT NULL. The NOT NULL ones are what make a year container
load-bearing: those rows cannot exist without one.

| nullable | model.column |
|---|---|
| **NOT NULL** | `ParadeDate.planning_year_id` |
| **NOT NULL** | `HolidayPeriod.planning_year_id` |
| **NOT NULL** | `AnchorEvent.planning_year_id` |
| **NOT NULL** | `TrainingClass.training_year_id` |
| NULL-able | `PlanningConflict.planning_year_id` |
| NULL-able | `PlanningFacilitatorLeave.planning_year_id` |
| NULL-able | `PlanningNotice.planning_year_id` |
| NULL-able | `CeaImportBatch.planning_year_id` |
| NULL-able | `CeaActivity.planning_year_id` |

Counted with `grep -c 'ForeignKey("planning_years.id")' app/models/*.py`, and
each classified by whether its column carries `nullable=True`.

**Consequence for the context model.** A year that nobody has written to needs
no row, because nothing points at it yet. The moment any of these four is
written, the container must exist — which is exactly where
`ensure_year_context()` sits, and nowhere else.

## 2. What is NOT year-scoped

Facilitators, training areas, equipment, subject areas and timing templates are
squadron-scoped and carry no year. They therefore need no copying, migrating or
duplicating when the year changes — a point the copy-setup design depends on,
because it is why copy-setup can be small.

`Activity` is squadron-scoped and **not** year-scoped at all. The Activities
page's "Inherited Activities" card consequently shows the same rows whatever
year is selected. Pre-existing; recorded in
`docs/design/training-year-frontend-design.md` §11.

## 3. Live data findings

### Staging, 2026-08-28/29 (read-only queries)

| finding | value |
|---|---|
| wings | **15** — 7WG, 9WG, ten `LVW*` load-test wings (12 squadrons each), QA1WG, TW1, ZZW1 |
| wings with NULL timezone, before the fix | **14** |
| wings with NULL timezone, after v57 | **0** |
| squadrons holding more than one active year | **0** |
| 708's target container `b482b6ed-…` | **absent** |
| materialised year rows for 703 | 13, including load-test years as far out as 3107 |

The 15-wing figure is the whole reason `v57` had to backfill by
`timezone IS NULL` rather than by `code = '7WG'`. A wing left NULL makes
`wing_timezone()` raise, and that raise surfaces as a 500 on every endpoint
that resolves a year — for every squadron in that wing. See
`training-year-migration-impact.md` §3.

### Production

Not queried. Instruction §58 forbids altering production data, and nothing here
required a production read. Two production facts are carried from the earlier
baseline (`docs/product-review/training-year-current-model.md`) and are
**unverified in this pass**:

- 7WG is the only wing.
- 708's container is numbered 2027 while holding 15 parade dates in 2026 —
  the case `v58` exists to correct.

Both must be re-checked against a production dump before that migration runs.
`tools/data-quality/year_container_audit.py` is the read-only tool for it.

## 4. Ambiguity register

Instruction §41: ambiguous historical data stops and asks rather than being
guessed at.

| item | status |
|---|---|
| 708 numbered 2027, dates in 2026 | **Decided by the user 2026-08-28**: the dates are authoritative, renumber the container. Implemented as `v58`, guarded so it refuses any other state. |
| Squadron 718's two orphaned parade nights (no planning year at all) | **Still open.** Not touched by this program. |
| Load-test years on staging (2501, 2645, 2651, 2665, 2666, 3107) | Test debris, not real data. Left alone; they exercise the far-future path harmlessly. |
