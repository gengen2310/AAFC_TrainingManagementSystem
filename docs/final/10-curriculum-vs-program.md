# Part 41 — CurriculumItem vs ProgramItem

**Date:** 2026-08-30 · **Status:** DECIDED — `CurriculumItem` is canonical
(user decision, 2026-08-30). `ProgramItem`'s API surface is retired; its tables
are not yet dropped. Two follow-ups remain, both listed at the foot of this
document.

## What each one is

| | `CurriculumItem` | `ProgramItem` |
|---|---|---|
| table | `curriculum_items` | `program_items` |
| router references | ~117 | 16 |
| endpoints | throughout `training.py` | 14, in `program.py` |
| service layer | none dedicated | `services_program.py` |
| UI | the whole scheduling flow | **one link** — a CSV export |
| tests | extensive | `test_program.py` |
| seeded | 13 national items | 3 demo items |
| extras | — | packages, deployments, promotion workflow, Learning Hub resources, source-file ingestion, versioning/retirement |

`ProgramItem` is the richer model and the more considered design: it carries a
written visibility doctrine, a promotion workflow, and provenance back to the
source file each row came from. It is fully built, mounted and tested — and the
product never surfaced it. `CurriculumItem` is what the application actually
schedules against.

This is not dead code on either side. Both are live, both return 200.

## They disagree, and it is demonstrable

Both implement National → Wing → Squadron ownership. They do not agree on
**upward visibility**.

`services_program.py` states its rule in its own docstring, citing spec §7:

> Squadron-local items ... visible UPWARD to its Wing and to National for
> oversight. Peer Squadrons must NOT see them.

`routers/training.py`'s curriculum filter gives a wing user national + own-wing
items. A squadron-local item appears only if the caller names a squadron with
`?squadron_id=`.

Measured, as one wing admin against one installation:

```
GET /api/curriculum      wing sees 703's local item?        False
GET /api/program-items   wing sees squadron-local items?    True (1 of 15)
```

Same organisational question. Two live endpoints. Two different answers.

## Not a security fault

`_view_squadron_id` calls `require_can_view_squadron`, and
`Principal.can_view_squadron` resolves to `squadron_id == self.squadron_id` for a
squadron account. A squadron cannot read a peer's items through either surface;
a test pins this and must keep passing whichever doctrine wins.

The disagreement is about how much oversight a **wing** gets by default.

## Recorded, not fixed

`routers/training.py`'s squadron condition is
`CurriculumItem.squadron_id == sq_id`, without the paired
`owning_level == "squadron"` that the wing condition just above it has. It is
the same shape as the reference-data tag defect fixed in v60 — a scope tuple
tested as independent predicates.

Here it cannot leak: `sq_id` is always a squadron the caller has already been
authorised to view, so the worst case is including a row the caller can see
anyway. The seeded dataset contains no row with `squadron_id` set and
`owning_level <> 'squadron'`, but that proves the seed, not production. Adding
the pairing could therefore hide rows in a dataset that cannot be inspected from
here, to fix something that is not causing harm. Left alone deliberately.

## The decision — taken

`CurriculumItem` is canonical (option 2 below). What was done:

* Removed `routers/program.py` (14 endpoints), `services_program.py`,
  `tests/test_program.py`, and the `seed_program` block.
* Repointed the export. `program-items` was the **only** export type the
  CSV/XLSX/PDF endpoints supported, so deleting it would have left all three
  unable to export anything. They now serve curriculum items via
  `services.visible_curriculum_items`, which applies the same scope rules as
  `GET /api/curriculum` — an export with looser rules than the page it exports
  would be a quiet disclosure channel, and a test asserts 704 cannot see 703's
  local item through it. `program-items` remains as a deprecated alias so
  existing links keep working.
* Left the models and tables in place, marked retired in `models/program.py`.

### Follow-up 1 — the tables are still there

Dropping `program_items`, `program_packages`, `program_item_deployments`,
`phases`, `learning_hub_resources`, `promotion_requests` and `source_conflicts`
destroys whatever rows an environment holds, and no production data can be
inspected from here. Removing the API stops the duplicate entity being *used*;
dropping the tables is a separate, explicit step that needs a row count per
environment first. `JobStatus` and `SourceFile` live in the same module and are
**not** retired — background jobs and the workbook-preview endpoint still use
them.

### Follow-up 2 — spec §7 is now unimplemented

`ProgramItem` implemented upward oversight: a Wing seeing its squadrons' local
items without selecting a squadron. `CurriculumItem` does not. Retiring the
model that implemented a doctrine does not decide the doctrine, so this is still
open: **should a Wing Admin see a squadron's local curriculum without selecting
that squadron?** If yes, the change belongs in `routers/training.py`'s curriculum
filter, and `test_curriculum_hides_squadron_local_from_the_wing_by_default` is
the test to update.

## The options as they stood

1. **`ProgramItem` is canonical.** Migrate `curriculum_items` into it and retire
   the simpler model. The largest option, and it adopts the design that already
   has the doctrine, provenance and promotion workflow written down. ~117 call
   sites move.
2. **`CurriculumItem` is canonical.** Retire `program_items`, its 14 endpoints
   and its service layer. Smallest code change, but it discards a specified
   subsystem — including spec §7's upward-oversight rule, which would then need
   re-implementing on `CurriculumItem` if that oversight is wanted.
3. **Keep both with a stated boundary.** Only defensible if they mean different
   things. Today they do not, which is why they disagree.

Whichever is chosen, the upward-visibility question has to be answered
explicitly: **should a Wing Admin see a squadron's local curriculum without
selecting that squadron?** Spec §7 says yes. The shipped curriculum page says no.

`backend/tests/test_curriculum_program_doctrine.py` characterises both current
behaviours so the divergence stays visible and cannot widen while this is open.
When one doctrine wins, the losing test is the one to change — deliberately.
