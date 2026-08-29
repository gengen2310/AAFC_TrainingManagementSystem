# Training Year — TMS ↔ Planning Workspace workflow

Date: 2026-08-29
Design: `docs/design/training-year-frontend-design.md` §7 · Spec §8

## The rule

**The handoff carries squadron and year INTEGER, never a `planning_year_id`.**

A year with no row is still a real, selectable year, so a UUID cannot express
the selection. Storing an id was the mechanism by which the two applications
disagreed about which year the user was looking at.

## The defect this replaced

```
TMS shows 2027  ──handoff──>  PW: years.find(y => y.year === 2027)
                              -> undefined (2027 has no row)
                              -> falls through to pickDefaultYear()
                              -> PW shows 2026
```

The user reported this as "the parade night from TMS still not showing up in
Planning Workspace". The two applications were looking at different years.

## How it works now

**TMS** opens PW with the token in the URL fragment plus the year integer —
fragments are never sent to the server and PW clears them before navigating:

```
{pwUrl}#t={token}&y={year}
```

**PW** stashes `y` as `aafc_requested_year`, then resolves the selection through
one pure function:

```ts
resolveYearSelection(years, requestedYear, storedYear)
  1. an explicit handover wins, EVEN when that year has no row   -> {year, id: null}
  2. otherwise keep the stored year while it is still on offer
  3. otherwise fall back to pickDefaultYear()
```

Rule 1 is the fix. It is a pure function precisely because this decision is what
let the two disagree: nine tests cover it, red-green verified — restoring the
old "only if matched" fall-through fails exactly the two that describe the bug.

## Storage

| key | holds | role |
|---|---|---|
| `aafc_pw_year` | year **number** | authoritative |
| `aafc_pw_year_id` | row id | **hint only** — lets year-scoped queries fire before `/years` arrives, always re-validated |

The hint preserves the ~1.6s waterfall saving the original code was written for,
without letting an id be the source of truth. A legacy id-only `localStorage`
falls back to the default year once rather than breaking.

## Type honesty

`PlanningYear.planning_year_id` is `string | null`, which is the truth as soon
as the API can return logical years. Making it honest immediately found two real
defects:

- `GuidedYearSetupModal` offered rollover from a year that might have no row.
- The PW year chips were keyed by `planning_year_id` **and** compared selection
  by it. Two null ids is a duplicate React key and — worse — `null === null`
  means every row-less year renders as selected at once. Keyed and compared by
  year now.

The second produces no console warning at all. Only the compiler found it.

## What the user sees

No second selection, no activation, no create prompt. PW renders the same
numeral in the same position as TMS, so the two read as one system rather than
two that happen to agree. Returning to TMS carries the year back the same way.

## Not yet done

- PW does not yet render the empty-future-year panel or the past-year read-only
  notice; TMS does. PW currently shows an empty workspace for a row-less year.
- `GuidedYearSetupModal` still opens with "new year or roll over?", which is the
  wrong framing under this model — both answers assume the year does not exist
  yet. Its rollover path was made safe; the redesign is its own change.
