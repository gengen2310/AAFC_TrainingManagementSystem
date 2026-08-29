# Training Year — target model

Date: 2026-08-29
Spec: `docs/superpowers/specs/2026-08-28-training-year-context-model.md`
Supersedes: the draft/active/archived model (reverted from `main` in PR #43)

## The one sentence

**A Training Year is calendar context, not a workflow object.** Nobody creates
it, drafts it, activates it, promotes it or archives it. 2027 exists because
2027 exists.

## What that means concretely

| question | answer |
|---|---|
| What is the current year? | `wing_local_date(db, squadron_id).year` — derived on every read |
| What happens on 1 January? | **No database write.** A derived value changes. |
| Where does a year's state live? | Nowhere. `year_state()` compares the year to today. |
| When does a row get created? | Only when something is written into the year — `ensure_year_context()` |
| What is a year called? | `f"{year} Training Year"` — derived, never user-entered |
| Which years can be selected? | Every past year that has a row, the current year, and two ahead |

The single assertion that distinguishes this model from the one it replaces:

```python
# test_year_context.py
with patch(..., return_value=dt.date(2026, 12, 31)):
    assert current_year(db, s) == 2026
with patch(..., return_value=dt.date(2027, 1, 1)):
    assert current_year(db, s) == 2027
assert db.query(PlanningYear).count() == before, \
    "deriving the current year must not create rows"
```

A stored-lifecycle model cannot pass it. It also means no scheduler is needed —
which matters, because there isn't one: `celery_app.py` has no `beat_schedule`
and Railway has no Redis.

## Logical year vs materialised container

```
read    GET  /api/planning/year-context?squadron_id=…&year=2028
        -> 200, {state: "future", materialised: false, planning_year_id: null,
                 name: "2028 Training Year"}          NO ROW CREATED

write   POST /api/planning/years/copy-setup {target_year: 2028}
        -> ensure_year_context(squadron, 2028)        ROW CREATED HERE
```

`find_year_context()` reads and never writes. `ensure_year_context()` is called
from write paths only, and is idempotent under concurrency: rather than
check-then-write — which has no lock between the check and the insert — it lets
the unique index arbitrate and re-reads on `IntegrityError`.

## Timezone

The current year is the **wing-local** year, so `Wing.timezone` holds an IANA
zone. Squadrons deliberately cannot override it: a wing is the smallest unit
that spans a timezone in practice.

`wing_timezone()` **raises** on a missing zone and never falls back. A wrong
zone is invisible in date arithmetic and corrupts every year boundary, so the
failure must be loud. New wings get an explicit stored zone at creation via
`timezone_for_new_wing()`; existing wings were backfilled once by `v57`.

## Past years

Read-only. Delivered training is history. Correction stays possible through
Delegated Intervention, which already opens a `ProxySession` and writes an audit
trail — so the escape hatch is authorised and recorded rather than absent. Plain
Proxy Mode is deliberately **not** sufficient.

Enforced once, in `_require_year_access(..., write=True)`, which all fifteen
year-scoped write endpoints already pass through, so an endpoint added later
inherits the protection instead of forgetting it.

## What this removes from the interface

Create Training Year · Manage Training Years · Rename · Active chip · Archive ·
Restore · Promote · Rollover · "Planning year required before continuing" ·
`SetupPanel`'s "Create Training Year" step · the hyphenated
`2026–2027 Training Year` name.

Replaced by: a year, two arrows, a menu, and the two actions that are true for
the year you are looking at.

## Deliberately retained

- `rollover_year` stays functional and is marked `deprecated=True`. It copies
  holidays and carries incomplete sessions, which copy-setup does not; degrading
  it to a shim would leave callers getting 200 while silently receiving less.
  Its one production defect — the arrowed `2026 Training Year → 2027` name — is
  fixed.
- `active_status` remains as the archive flag. It is no longer a lifecycle
  marker and no longer decides which year is current.
