# Training Year as calendar context

Date: 2026-08-28
Status: design, awaiting review

**Supersedes in part** `2026-08-27-year-model-and-parade-night-merge-design.md`
and `2026-08-18-year-ux-design.md`. See §10 for exactly which decisions fall.

Baseline this argues from: `docs/product-review/training-year-current-model.md`.

---

## 1. The reframe

A Training Year is **a calendar context for grouping year-specific training
information**. It is not a document, a plan requiring approval, a draft, an
activated record, or an archived record.

The current model treats it as a workflow object, and every defect in the
REM-134 / 139 / 145 / 156 family follows from that. `active_status` carries three
unrelated jobs — archive state, default-year selection, and setup completion
(`setup.py:71`) — and none of them is "current", because nothing in the codebase
compares a year to today's date.

The evidence says the calendar model is already how the data behaves. Of 12
production year-rows holding parade dates, **10 match their year integer
exactly**: a 2026 year holds only 2026 dates. The two exceptions are legacy rows
named `2026 Training Year → 2027`, produced by `rollover_year`.

## 2. Decisions taken

The user's, on 2026-08-28. Recorded because they are decisions, not derivations.
**Two deliberately override the instruction's own recommendations**; they are
marked, so the doc and the decision cannot drift apart.

1. **Year selection is capped at current + 2 future years.** Past years are not
   capped. ⚠️ *Overrides §28 Q1's "do not impose a product cap".*
2. **An unconfigured future year opens empty and offers setup.** Nothing is
   copied unless the user explicitly asks.
3. **Copy-forward is limited to the §28 list**, confirmed exactly: Training Class
   structure and parade recurrence, both optional. Never sessions, outcomes,
   progress, attendance, audit history or published status. Facilitators,
   training areas, equipment, subject areas and timing templates are not
   year-scoped, so there is nothing to copy. Holidays are re-imported, never
   date-shifted by 365 days.
4. **Past years are read-only by default**, with correction available through an
   authorised, audited path.
5. **The wing/national year capability is retained, unused.** ⚠️ *Overrides §27's
   lean toward removing it.* Production holds **zero** wing- or national-scoped
   planning years — all 21 are squadron-scoped — so this costs nothing today and
   removes nothing that exists.
6. **A calendar year is 1 January to 31 December.** Not asked; confirmed from
   data (§1).
7. **Copying class structure creates new canonical classes for the target year**,
   optional, reviewed before commit. No cadets, progress or sessions carry over.
8. **A year can be browsed before any row exists.** The canonical row is
   materialised on the first year-specific **write**.
9. **708's year numbered 2027, holding all 15 of its dates in 2026, is renumbered
   to 2026.** The dates are authoritative.

## 3. Logical year versus materialised row

The user sees a year. The database needs a row because nine foreign keys point
at `planning_years`, **four** of them NOT NULL.

```
  read   GET  /…/704/2028/…        -> 200, empty context, NO row created
  write  POST /…/704/2028/classes  -> ensure_year_context(704, 2028)
                                      materialises the canonical row, then writes
```

`ensure_year_context(db, squadron_id, year) -> PlanningYear` is the only function
that creates a `PlanningYear`. It is called from write paths, never from reads.

**Reads must not mutate.** The instruction is explicit and the reasoning is
sound: browsing years would otherwise litter the table with empty rows, and a GET
that writes is the kind of surprise this whole exercise is removing. Reads that
find no row return an empty context, not a 404.

This retires `_get_year_or_404` as the universal gate for reads. Writes still
404 on a malformed or out-of-scope request; they simply do not require the row to
pre-exist.

## 4. Derived context, not stored state

```
current_year = wing_local_date().year          # Australia/Perth for 7WG
```

- `year < current` → **previous**
- `year == current` → **current**
- `year > current` → **future**

Nothing is persisted. On 1 January the derived default changes and **no database
write occurs** — no promotion, no archival, no status rewrite, no scheduler. This
is the single largest simplification against the superseded design, which needed
a lazy-promotion resolver, a mutation-on-read, and a concurrency argument to
achieve the same user-visible outcome.

`Wing.timezone` (IANA, `Australia/Perth` for 7WG) is still required and is
salvaged from the superseded Phase A plan. An unset timezone must raise, never
default: with one wing a missing value is invisible, and first bites when a
second wing is created.

## 5. One canonical container per squadron and year

```sql
UNIQUE (unit_id, year) WHERE <not retired>
```

This replaces `uq_planning_years_unit_year_active`, which was scoped to
`active_status` and therefore permitted an active 2026 **and** an active 2027 —
the mechanism behind REM-156.

`ensure_year_context` must be idempotent: concurrent callers resolve to the same
row, relying on the unique index rather than check-then-write.

Retirement survives only as **technical remediation** — duplicate suppression and
SysAdmin correction of erroneous empty rows — not as a lifecycle a Training Cell
performs. Existing archived rows are preserved for audit.

## 6. The year has no name

`PlanningYear.name` stops being a user-editable identity. Display is derived:

```
2026                      (selector, chips, headings)
2026 Training Year        (where a noun is needed)
```

`2026–2027 Training Year` disappears — and note it was **generated, not typed**:
`SetupPanel.tsx:75` pre-fills `` `${year}–${year+1} Training Year` ``. So does
`2026 test 1.0`, which is what 704's real year was called until 2026-08-28.

The column may persist for compatibility, derived on write. Nothing may branch on
its value; the integer `year` is authoritative.

## 7. Rollover becomes copy-setup

`POST /years/{id}/rollover` currently creates a year with `active_status=True`
and names it `f"{name} → {target_year}"` (`planning.py:3643,3658`). That single
behaviour produced both the multi-active state and the `→ 2027` naming.

It is replaced by an explicit, reviewed **Copy setup from `<year>`** action that
copies only what §2.3 permits into an already-existing year context. Creating the
year is no longer part of it, because the year already exists.

## 8. TMS and Planning Workspace share one context

PW persists `aafc_pw_year_id` — a UUID (`PlanningWorkspace.tsx:3`). It should
persist **squadron + year integer**, so that a year needing no row is still a
valid context and the two apps cannot disagree.

TMS showing `704 · 2027` and opening PW must land on `704 · 2027`: no second
selection, no activation, no create prompt.

## 9. Migration

Per the instruction's §40–41: **audit first, stop on ambiguity, never silently
reinterpret.**

A read-only audit must report, per `PlanningYear`: squadron, year integer, name,
retirement state, parade-date count and span, training-class count, holiday
count, session count, and every other dependent. It must flag child dates outside
the year integer, duplicate live rows, retired rows with dependents, and rows
with no dependents at all.

Known now:

| case | disposition |
|---|---|
| 10 of 12 populated rows match their year integer | migrate unchanged |
| 704's 2027 row holding 2026 dates | already archived 2026-08-28 (REM-156) |
| **708's 2027 row holding all 15 of its 2026 dates** | **renumber the container to 2026** (§2.9) |
| 702, TEST — populated current + empty next | the empty next year simply stops needing a row |

No parade night may be reassigned to a different calendar year by inference. A
2026 night belongs to 2026 regardless of what its container is called.

## 10. What is superseded

From `2026-08-27-year-model-and-parade-night-merge-design.md`:

- the `draft | active | archived` status column — **superseded**; no lifecycle
- promotion of a draft on rollover — **superseded**; context is derived
- lazy promotion, the mutation-on-read and its concurrency design — **superseded**
- the one-*active*-year index — **superseded** by one canonical row per
  `(unit_id, year)`
- active-year defaulting — **superseded** by wing-local calendar year
- archive as a normal lifecycle transition — **superseded**; remediation only
- rollover as year creation — **superseded** by copy-setup

**Not superseded, and carried forward:**

- `Wing.timezone`, IANA, no squadron override, fail-loud
- the ParadeNight/ParadeDate merge objective (Phase B), reworked per §9
- the REM-156 production consolidation, which stands
- the integrity assumptions verified against production on 2026-08-28

From `2026-08-18-year-ux-design.md`: any create/manage/rename/archive year UX.

## 11. Open questions

1. **Does `ensure_year_context` need a scope check beyond the caller's?** A
   squadron admin writing to their own squadron's 2028 is clearly fine. A
   wing_admin acting through Proxy Mode is fine. Whether a national_admin may
   materialise a year for an arbitrary squadron is not settled.
2. **What happens to the 2 nights at squadron 718**, which has no planning year
   at all? Carried over from the superseded spec's open question 2, still open.
3. **Does the current+2 cap apply to Wing and National views**, which see many
   squadrons at once?
