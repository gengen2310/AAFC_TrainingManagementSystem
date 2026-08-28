# Training year model, and merging ParadeNight with ParadeDate

Date: 2026-08-27
Status: design, reviewed 2026-08-28 — one blocking defect found and resolved; see REVIEW notes

## Why

A squadron admin reported, more than once, that a parade night created in TMS
does not appear in Planning Workspace. It was treated as a sync bug and patched
twice (REM-129, REM-139). It is not a sync bug.

TMS writes a `ParadeNight`, keyed by squadron and date. Planning Workspace reads
a `ParadeDate`, keyed by `planning_year_id`. They are two rows for one real
night, joined by a nullable FK. Nothing in a `ParadeNight` says which training
year it belongs to, so `_year_for_date()` infers it. When the inference picks a
different year than the one Planning Workspace is displaying, the night is
created successfully, reports success, and is invisible.

Measured on production, read-only, 2026-08-27:

| | |
|---|---|
| parade_nights | 154 |
| parade_dates | 146 |
| linked pairs | 146 |
| ParadeDate with no night | 0 |
| ParadeNight with no date | 8 |
| — of those, a year spans the date | 2 |
| — of those, a year matches the calendar year | 4 |
| — of those, squadron has no active year at all | 2 |
| **squadrons with more than one active year** | **6** |

That last row is the live cause. Six squadrons are in the state where the
inference has more than one defensible answer.

The same query against staging returns 577 nights and 67 dates — 510 orphans.
Staging carries automated-test debris and is not representative; the migration
is sized against production.

## Decisions taken

Recorded because they were the user's calls, not derived:

1. A squadron has **one active training year, plus optionally a next year in
   draft**. Not "exactly one", not "several freely".
2. **TMS is for setup and administration; Planning Workspace is where planning
   happens.**
3. Within that, the split is **"TMS adds dates, PW plans them"** — TMS says
   which nights exist, PW says what happens on them.
4. **Merge the two tables** rather than re-pointing the writers and leaving both.
   Recommended against initially on migration risk; production's numbers made it
   tractable and the decision stands.
5. **Phase A before Phase B, as one project.** Discovered during design: merging
   does not fix the six multi-active squadrons, because a merged row still has
   to name one year. The year rule is a prerequisite for the merge, not an
   alternative to it.

## Phase A — the year model

### Schema

`PlanningYear.active_status: bool` becomes `status: str` with values
`draft | active | archived`. The boolean cannot express "next year, being
prepared", which decision 1 requires.

`active_status` is retained as a generated/derived value for one release so
existing queries keep working; see Compatibility below.

### Invariant

At most one `active` year per squadron.

The current index is unique on `(unit_id, year)` where `active_status` — it
prevents two active *2026* rows but permits an active 2026 **and** an active
2027. That is exactly how the six squadrons reached their present state. The
index becomes unique on `(unit_id)` where `status = 'active'`.

Wing- and national-scoped years have `unit_id IS NULL` and both SQLite and
PostgreSQL treat NULLs as distinct, so they remain unconstrained. That is
correct and is preserved from the existing index.

### Behaviour

- A parade night attaches to the squadron's active year. Never inferred.
- A draft year is never a candidate unless deliberately targeted.
- TMS and Planning Workspace both default to the active year, so they cannot
  disagree about which year is "current".

### Data to resolve

Six squadrons hold more than one active year. One stays active; the others
become draft or archived. **This is a per-squadron human decision and the
migration must not guess it.** The deliverable is a report listing, per
squadron, each active year with its date span and dependent-row counts, for the
user to adjudicate before Phase A ships.

## Phase B — the merge

### Which table survives

`parade_nights` survives; `parade_dates` folds into it.

Chosen on repointing cost measured on production: 86 sessions FK
`parade_nights`, while 30 rows FK `parade_dates` (28 conflicts, 2 notices, 0
prep plans). Keeping the nights table moves 30 rows instead of 86.

### Columns

`parade_nights` gains `planning_year_id` (NOT NULL, FK `planning_years.id`),
and `term`, `week_number`, `is_active`, `cancellation_reason` carried over from
the date row.

**REVIEW 2026-08-28 — this contradicted the orphan handling below, and the spec
could not have been implemented as written.** `parade_nights` is the surviving
table, so all 154 nights — including the 8 orphans — are *already rows in it*.
"Not migrated" is meaningless for a row that is already there, and a NOT NULL
column cannot be added while two rows have no value for it.

Resolved by making it a **precondition rather than a migration branch**, the same
treatment the six multi-active squadrons already get: the migration refuses to run
while any parade night lacks a resolvable year. The two unresolvable nights are
reported and fixed by a human *before* Phase B starts, not during it. That keeps
the spec's rule — nothing invents a year — and removes the impossible state.

`ParadeNight.training_year` (a bare integer) is superseded by
`planning_year_id` and is dropped in the same migration. Keeping both would
reintroduce the ambiguity this design exists to remove.

### Foreign keys to repoint

Into `parade_dates`, all repointed to the merged row:

- `PlanningNotice.parade_date_id` — NOT NULL
- `PlanningConflict.parade_date_id` — nullable
- `AnchorPrepPlan.planned_parade_date_id` — nullable, 0 rows on production

Already pointing at `parade_nights`, unchanged:

- `Session.parade_night_id`
- `ParadeNightTimingOverride`

`ParadeDate.parade_night_id` — the join itself — ceases to exist.

The 146 linked pairs map one-to-one, so the repointing is exact and needs no
resolution logic.

**`PlanningNotice` already carries its own nullable `planning_year_id`.** After
the merge it would reach a year two ways: directly, and through the parade night
it FKs. Two paths to one fact will drift. The notice's own column is dropped and
the year is read through the night, so there is one answer. Found during spec
review, not during design — worth stating because the same shape may exist on
other planning tables and was not audited.

### The eight orphans

| resolution | count | action |
|---|---|---|
| a year's parade dates span the date | 2 | attach to that year |
| a year matches the date's calendar year | 4 | attach to that year |
| squadron has no active year at all | 2 | **blocks the migration; fixed by a human first** |

The final two are reported for a human decision **before Phase B runs at all**
(see the REVIEW note under Columns — they cannot be "skipped" mid-migration,
because they are already rows in the surviving table). Guessing a year for them
would be the same inference this design removes, run once over historical data
where nobody can check the answer.

### Rollback

`parade_dates` is **renamed, not dropped**, and retained for one release. A
dropped table cannot be inspected when something turns out wrong three weeks
later. It is dropped in a follow-up migration once the merged model has run in
production for a release.

### Code removed

`_year_for_date()` in `backend/app/routers/training.py`, and
`_find_or_create_parade_date_for_night()` which calls it. The question they
exist to answer is answered at creation time instead.

The `linked_to_planning_year: false` warning toast in connected-frontend
(added 2026-08-25) also becomes unreachable and is removed with them.

## After it ships

- **TMS** — "Add parade date": pick a date, the year is the squadron's active
  year and is shown, not inferred.
- **Planning Workspace** — plans what happens on that night: sessions, phases,
  facilitators, timing.

One record. One year. No inference between the two applications.

## Compatibility

Phase A changes a column that many queries filter on. **REVIEW 2026-08-28: "many"
was doing far too much work.** Measured on main, `active_status` is referenced
**296 times** — 156 in `backend/app`, 63 in tests, 31 in migrations, 24 in
connected-frontend and 22 in the React app.

The last two matter most: **46 of those references are in two independently
deployed frontends**, so there is a window where an old frontend talks to a new
backend. The API must keep returning `active_status` alongside `status` until both
frontends have shipped and been verified. The sequence below is correct but step 3
is not one step; it is the bulk of Phase A.

Sequence:

1. Add `status`, backfill from `active_status`, keep `active_status` derived.
2. Ship. Both columns readable; nothing reads `status` yet.
3. Migrate readers to `status`.
4. Ship. Adjudicate the six squadrons.
5. Tighten the index to one active year per squadron.
6. Drop `active_status`.

Phase B begins only after step 5 holds in production.

## Testing

- Backend: a squadron cannot hold two active years; a parade night attaches to
  the active year and never to a draft; the eight orphan resolutions each
  produce the documented outcome; and the migration REFUSES TO RUN while any
  night lacks a resolvable year, rather than skipping those rows.
- Migration: run forward and backward against a disposable PostgreSQL restored
  from a production dump, asserting row counts and FK integrity per table before
  and after. Never against production directly.
- Frontend: creating a date in TMS makes it visible in Planning Workspace for
  the same year, verified in a browser rather than by API round-trip.
- Regression: the REM-139 tests are rewritten against the new model rather than
  deleted, so the original reported symptom stays covered.

## Integrity assumptions, now verified

The first draft assumed these and did not check them. Re-verified read-only
against production on 2026-08-28, all clean:

| assumption | result |
|---|---|
| every `parade_date` links to a night | 0 unlinked |
| no night has two `parade_date` rows | 0 duplicates |
| paired rows agree on the date | 0 mismatches |
| paired rows agree on the squadron | 0 mismatches |
| no notice points at a date whose night is missing | 0 |

The migration should **assert** these rather than trust this table: they were true
on 2026-08-28, not necessarily on the day it runs.

## Risks

- **Production is 23 migrations behind before this adds more.** This work must
  not be the thing that first exercises that backlog. Catching production up is
  a prerequisite, not part of this spec.
- Phase A step 5 will fail loudly if any squadron still holds two active years.
  That is intended, but it means step 4's adjudication must be complete.
- `PlanningNotice.parade_date_id` is NOT NULL. If any notice references a
  parade date whose night is one of the two unresolvable orphans, the repoint
  fails. Production has 2 notices and 0 such conflicts today; the migration must
  check this rather than assume it holds at deploy time.

## Out of scope

Raised in the same conversation, deliberately not designed here:

- **Session Structure and Default Training Periods wording.** Easier after this
  lands, because "Training Period" stops competing with "session" and "phase".
- **Session-to-phase allocation UX** in Planning Workspace.
- **A screen the user wants moved out of a panel and onto a normal page** — not
  yet identified; the user is describing it.
- **REM-155**, the unscoped read of promotion requests.

## Open questions

1. Which year stays active for each of the six squadrons?
2. What happens to the two parade nights whose squadrons have no active year —
   create a year, attach to an archived one, or leave them out of the merge?
3. Should a draft year be visible in Planning Workspace at all, or only in TMS
   until it becomes active?
4. **REVIEW 2026-08-28 — the draft lifecycle is undefined and the spec depends on
   it.** "draft" appears throughout, but nothing here says how a year *becomes*
   draft (created that way? demoted from active?), who may promote draft to
   active, or what happens to the outgoing active year at rollover — archived
   automatically, or left for someone to archive? Decision 1 cannot be
   implemented without answers. This is the largest remaining gap.
