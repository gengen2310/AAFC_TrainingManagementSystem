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

### Lifecycle

Decided by the user, 2026-08-28: **one active year; the next year is drafted
manually; the draft is promoted automatically on rollover, and the outgoing year
is archived in the same moment.**

**There is no scheduler on this system, so "automatic" cannot mean a cron job.**
Verified: `workers/celery_app.py` configures a broker but declares no
`beat_schedule`, there are no periodic tasks, and Railway has no Redis service —
so `dispatcher.py` always takes its documented fallback and runs work
synchronously in-process. Nothing exists that can fire at midnight on 1 January.

Implemented instead as **lazy evaluation on read**. The helper that resolves "the
active year for this squadron" performs the rollover itself, the first time it is
called on or after the rollover date:

    resolve_active_year(squadron):
        active = the squadron's active year
        draft  = the squadron's draft year, if any
        if draft and today >= rollover_date(draft):
            promote draft -> active, archive the outgoing year   # one transaction
        return the active year

The user-visible behaviour is exactly what was asked for — nobody presses
anything, the year changes by itself — with no new infrastructure.

Three consequences that must be handled, not assumed:

**The `year` number does not reliably describe the dates the year contains.**
Found 2026-08-28 while listing the six squadrons, and it undermines the rollover
rule. Three of them hold a year numbered **2027** whose parade dates are all in
2026:

    704  2027  "2026 Training Year -> 2027"   5 dates, 2026-08-07 .. 2026-09-04
    708  2027  "2026 Training Year -> 2027"  15 dates, 2026-08-21 .. 2026-12-04
    702  2027  "2026 Training Year -> 2027"   0 dates

The names suggest a rollover or copy feature that renumbered the year without
re-dating its contents. If such a row is the draft, "promote on 1 January of the
draft's year" activates it on 1 Jan 2027 holding parade nights that finished in
2026 — an active year whose entire programme is in the past.

**This must be settled before the rollover rule can be implemented.** Either the
rollover date comes from the year's own dates rather than its number, or these
rows are corrected first and the number is made authoritative. The second is
cleaner but needs the same per-squadron adjudication as everything else here.

**Timezone — and the system does not currently know it.** Rollover is
**1 January of the draft year's own `year`, in squadron-local time** (decided
2026-08-28).

Checked, not assumed: there is **no timezone field on `Squadron`, `Wing` or
`NationalEntity`**, and the only timezone-aware code in the backend is
`UTCDateTime` in `database.py`. So squadron-local time is not expressible today
and **this is a prerequisite, not a detail**.

**Decided 2026-08-28: `Australia/Perth` on 7WG. Squadrons cannot override it.**

An IANA `timezone` string on `Wing`, and nothing on `Squadron` — the override I
originally proposed is dropped, which removes a fallback chain and a column.
`zoneinfo` is in the standard library on Python 3.13, so this adds no dependency.

**Scope check, and a correction to the earlier framing in this section.** I
argued this mattered because AAFC spans Australian states, with Perth on UTC+8
against Sydney's UTC+11 on 1 January. That is true of AAFC as an organisation but
**not of this deployment**: production has exactly one wing, 7 Wing – Western
Australia, holding all 18 squadrons with none unassigned. So a single value
covers 100% of production and the multi-state daylight-saving hazard is
**latent, not live**.

It stays on `Wing` rather than becoming one global constant precisely because it
is latent. Adding a second wing then becomes a data change instead of a schema
change plus a migration.

**And this makes the fail-loudly rule more important, not less.** With one wing,
a missing-timezone bug is invisible — every lookup finds Perth. It first bites
when wing two is created, which is exactly when nobody is watching for it. An
unset `timezone` must raise, never silently fall back to UTC or to Perth.

Same defect class as the naive-UTC timestamps fixed on 2026-08-25.

**It mutates on a read.** Two concurrent requests can both see an un-promoted
draft. The promotion must run in one transaction and rely on the
one-active-year-per-squadron unique index to make the loser fail and retry,
rather than on checking first and writing after.

**It is silent.** The active year changing under a user mid-session is the same
class of surprise as the original defect this spec exists to remove. Both
frontends already display the year; they should additionally notice that it
changed since the page loaded and say so, rather than swapping the data
underneath. This is a requirement, not a nicety.

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

**CORRECTED 2026-08-28.** The first breakdown counted overlapping categories: the
"span" nights also have an active year numbered 2026, so they were counted twice
and "calendar year" was inflated from 2 to 4. The mutually exclusive breakdown,
from the per-row listing:

| resolution | count | action |
|---|---|---|
| a year's parade dates span the date | 2 | attach to that year (704, 708) |
| a year matches the date's calendar year | 2 | attach to that year (713 x2) |
| squadron has **no planning year at all** | 2 | **blocks the migration** (718 x2) |
| active years exist but none span or match | 2 | **blocks the migration** (TEST x2) |

So **four nights need a human decision, not two.** All eight carry zero sessions,
so nothing is lost either way. 718 has no planning years whatsoever — not merely
no active one — and its two nights are real events ("Exec and Band Night",
"708SQN Grad Parade"), not test debris.

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

1. ~~Which year stays active for each of the six squadrons?~~ **ANSWERED AND DONE
   2026-08-28 — see REM-156.** Resolved directly on production rather than by
   migration: 703 and 721 had an empty duplicate archived; 704 kept the row
   holding its 16 parade dates, was renamed "2026 test 1.0" → "2026 Training
   Year", and had its two empties plus its 2027 row archived; 708 had both empty
   2026 rows archived, leaving the row that actually holds its 15 dates. 702 and
   TEST were reviewed and need no change — each is already a populated current
   year plus an empty next year, which is this spec's own model rather than a
   duplicate.

   **This removes a Phase A precondition.** The per-squadron adjudication that
   had to happen before the one-active-year index could be tightened is complete.
   Production now holds at most one active year per squadron except 702 and TEST,
   whose second year becomes the *draft* under the new `status` column rather
   than needing to be archived at all. Phase A no longer waits on a data cleanup;
   it waits on question 6.
2. What happens to the two parade nights whose squadrons have no active year —
   create a year, attach to an archived one, or leave them out of the merge?
3. Should a draft year be visible in Planning Workspace at all, or only in TMS
   until it becomes active?
4. ~~The draft lifecycle is undefined.~~ **ANSWERED 2026-08-28:** one active year,
   next year drafted manually, promoted automatically on rollover with the
   outgoing year archived in the same transaction. Written up under Lifecycle.
5. ~~What date is "rollover"?~~ **ANSWERED 2026-08-28: 1 January of the draft
   year's own `year`, in squadron-local time.** Consistent with the data, where a
   seeded training year spans a calendar year — note the Session Structure help
   text claimed July–June and was found wrong on 2026-08-25.
6. ~~Who sets the timezones, and what are they?~~ **ANSWERED 2026-08-28:
   `Australia/Perth` on 7WG; squadrons cannot override.** 7WG is production's only
   wing and holds all 18 squadrons, so that one value covers everything. The
   per-squadron override is dropped from the design.

   **Nothing now blocks implementation of Phase A.** Questions 2 and 3 remain but
   neither gates it: 2 concerns two orphaned parade nights at a squadron with no
   planning year, which is a Phase B precondition; 3 is a UI decision that can be
   made while Phase A is built.
