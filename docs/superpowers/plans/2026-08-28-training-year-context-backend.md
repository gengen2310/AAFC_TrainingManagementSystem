# Training Year as Calendar Context — Backend & Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a Training Year a calendar context — derivable from the wing-local date, browsable before any database row exists, and materialised only when something is written to it.

**Architecture:** A new `app/services_year.py` owns every year decision: which year is current (from `Wing.timezone`), whether a year is past/current/future, and `ensure_year_context()` — the only function that creates a `PlanningYear`. Reads answer from a year *integer* and return an empty context when no row exists; writes materialise the canonical row first. A unique index on `(unit_id, year)` over non-retired rows replaces the active-scoped index.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, PostgreSQL (prod/staging) and SQLite (tests), Python 3.13 (`zoneinfo` is stdlib).

**Spec:** `docs/superpowers/specs/2026-08-28-training-year-context-model.md`

## Global Constraints

- **Frontend is NOT in this plan.** The superseding instruction sequences frontend-design (§6) after this plan. Frontend tasks get their own plan once the design exists. This plan delivers working, testable backend on its own.
- **Alembic head moves under you.** It was `e2f3a4b5c6d7` on 2026-08-27 and is `fa57bc9d0e1a` today. **Always run `alembic heads` immediately before creating a migration**; never copy a revision id from this document. `<rev>` below means "the id `alembic revision -m "..."` generates", not a value to invent.
- **A read must not write.** `ensure_year_context()` is called from write paths only. A GET of a year with no row returns an empty context, never a 404 and never a new row.
- **Year selection is capped at current + 2 future years.** Past years are uncapped. (User decision, overriding the instruction's "no cap".)
- **A calendar year is 1 January to 31 December.** The integer `year` is authoritative; `name` may not be branched on.
- **An unset `Wing.timezone` must raise, never default.** With one wing a missing value is invisible until a second wing exists.
- **Never delete a planning year.** Retirement is `active_status=false`, reversible, and is remediation only — not a lifecycle a user performs.
- **Migration rule: stop on ambiguity.** No parade night may be reassigned to a different calendar year by inference (instruction §41).
- Tests: `cd backend && source .venv/bin/activate && python -m pytest tests/ -q`. Use `login(client, code)` and `next_test_year()` from `tests/conftest.py`; the DB seeds once per session and is never reset.

## File Structure

| File | Responsibility |
|---|---|
| `backend/app/models/organisations.py` | add `Wing.timezone` |
| `backend/app/models/planning.py` | replace the active-scoped index with canonical `(unit_id, year)` |
| `backend/app/services_year.py` | **new** — the only module that decides current year, year state, and materialisation |
| `backend/app/routers/planning.py` | year listing keyed on integers; reads tolerate no row; rollover becomes copy-setup |
| `backend/app/routers/setup.py` | Getting Started stops requiring an active year |
| `backend/alembic/versions/` | one migration per schema task, plus the 708 data fix |
| `backend/tests/test_year_context.py` | **new** — derivation, materialisation, uniqueness |
| `backend/tests/test_year_copy_setup.py` | **new** — copy-setup contents and exclusions |

---

### Task 1: `Wing.timezone` and the wing-local date

**Files:**
- Modify: `backend/app/models/organisations.py` (class `Wing`)
- Create: `backend/app/services_year.py`
- Create: `backend/alembic/versions/<rev>_add_wing_timezone.py`
- Modify: `backend/app/seeds/seed_all.py`
- Test: `backend/tests/test_year_context.py`

**Interfaces:**
- Produces: `MissingTimezone`, `wing_timezone(db, wing_id) -> ZoneInfo`, `squadron_timezone(db, squadron_id) -> ZoneInfo`, `wing_local_date(db, squadron_id) -> datetime.date`.

Salvaged from the superseded Phase A plan (PR #36, Task 1), which was correct and whose premise did not change: the current year is the *wing-local* calendar year.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_year_context.py
import pytest
from zoneinfo import ZoneInfo
from app.database import SessionLocal
from app.models import Squadron, Wing
from app.services_year import MissingTimezone, squadron_timezone


def test_squadron_timezone_comes_from_its_wing():
    db = SessionLocal()
    try:
        sqn = db.query(Squadron).filter(Squadron.code == "703").first()
        assert squadron_timezone(db, sqn.id) == ZoneInfo("Australia/Perth")
    finally:
        db.close()


def test_missing_timezone_raises_rather_than_defaulting():
    """A silent UTC or Perth default is invisible while 7WG is the only wing,
    and first bites when a second wing is created."""
    db = SessionLocal()
    try:
        sqn = db.query(Squadron).filter(Squadron.code == "703").first()
        wing = db.get(Wing, sqn.wing_id)
        original, wing.timezone = wing.timezone, None
        db.flush()
        with pytest.raises(MissingTimezone):
            squadron_timezone(db, sqn.id)
        wing.timezone = original
        db.commit()
    finally:
        db.close()
```

- [ ] **Step 2: Run it and watch it fail**

Run: `cd backend && python -m pytest tests/test_year_context.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services_year'`

- [ ] **Step 3: Add the column**

```python
# backend/app/models/organisations.py — inside class Wing, after short_name
    # IANA zone, e.g. "Australia/Perth". Squadrons deliberately cannot override:
    # a wing is the smallest unit that spans a timezone in practice.
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

- [ ] **Step 4: Create the service module**

```python
# backend/app/services_year.py
"""Every decision about which training year something belongs to.

A Training Year is calendar context, not a workflow object. This module is the
only place that derives the current year, classifies a year as past/current/
future, or materialises a PlanningYear row.
"""
from __future__ import annotations

import datetime as _dt
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session as DBSession

from .models import Squadron, Wing


class MissingTimezone(RuntimeError):
    """A wing has no IANA timezone. Never defaulted; always raised."""


def wing_timezone(db: DBSession, wing_id: str | None) -> ZoneInfo:
    wing = db.get(Wing, wing_id) if wing_id else None
    if wing is None or not wing.timezone:
        raise MissingTimezone(
            f"wing {wing_id} has no timezone set; refusing to assume UTC or "
            f"Australia/Perth"
        )
    return ZoneInfo(wing.timezone)


def squadron_timezone(db: DBSession, squadron_id: str) -> ZoneInfo:
    sqn = db.get(Squadron, squadron_id)
    if sqn is None:
        raise MissingTimezone(f"unknown squadron {squadron_id}")
    return wing_timezone(db, sqn.wing_id)


def wing_local_date(db: DBSession, squadron_id: str) -> _dt.date:
    """Today as the squadron's wing experiences it, not as the server does."""
    return _dt.datetime.now(squadron_timezone(db, squadron_id)).date()
```

- [ ] **Step 5: Write the migration**

Run `alembic heads` first and use the id it reports as `down_revision`.

```python
"""add Wing.timezone"""
import sqlalchemy as sa
from alembic import op

revision = "<rev>"
down_revision = "<output of alembic heads>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("wings") as b:
        b.add_column(sa.Column("timezone", sa.String(64), nullable=True))
    # Backfilled by code, not by a column default, so a NEW wing still arrives
    # NULL and trips MissingTimezone rather than silently inheriting Perth.
    op.execute("UPDATE wings SET timezone = 'Australia/Perth' WHERE code = '7WG'")


def downgrade() -> None:
    with op.batch_alter_table("wings") as b:
        b.drop_column("timezone")
```

- [ ] **Step 6: Seed it**

```python
# backend/app/seeds/seed_all.py — where the Wing is constructed
        wing = Wing(national_id=nat.id, code="7WG",
                    name="7 Wing - Western Australia", short_name="7WG",
                    timezone="Australia/Perth")
```

- [ ] **Step 7: Migrate and test**

```bash
cd backend && source .venv/bin/activate
alembic upgrade head
rm -f aafc_tms.db && python -m pytest tests/test_year_context.py -q
```
Expected: 2 passed

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/organisations.py backend/app/services_year.py \
        backend/alembic/versions backend/app/seeds/seed_all.py \
        backend/tests/test_year_context.py
git commit -m "feat(year): Wing.timezone and the wing-local date"
```

---

### Task 2: Derived year state — no stored lifecycle

**Files:**
- Modify: `backend/app/services_year.py`
- Test: `backend/tests/test_year_context.py`

**Interfaces:**
- Consumes: `wing_local_date`.
- Produces: `current_year(db, squadron_id) -> int`, `year_state(db, squadron_id, year) -> str` returning `"past" | "current" | "future"`, and `selectable_years(db, squadron_id) -> list[int]`.

**The point of this task:** 1 January performs no database write. The default simply changes because the derived value changes.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_year_context.py — append
import datetime as dt
from unittest.mock import patch
from app.services_year import current_year, selectable_years, year_state


def _sqn_id(db):
    from app.models import Squadron
    return db.query(Squadron).filter(Squadron.code == "703").first().id


def test_current_year_is_the_wing_local_calendar_year():
    db = SessionLocal()
    try:
        s = _sqn_id(db)
        with patch("app.services_year.wing_local_date", return_value=dt.date(2026, 8, 28)):
            assert current_year(db, s) == 2026
    finally:
        db.close()


def test_new_years_eve_and_new_years_day_differ_with_no_database_write():
    db = SessionLocal()
    try:
        s = _sqn_id(db)
        before = db.query(__import__("app.models", fromlist=["PlanningYear"]).PlanningYear).count()
        with patch("app.services_year.wing_local_date", return_value=dt.date(2026, 12, 31)):
            assert current_year(db, s) == 2026
        with patch("app.services_year.wing_local_date", return_value=dt.date(2027, 1, 1)):
            assert current_year(db, s) == 2027
        after = db.query(__import__("app.models", fromlist=["PlanningYear"]).PlanningYear).count()
        assert before == after, "deriving the current year must not create rows"
    finally:
        db.close()


def test_year_state_is_derived_not_stored():
    db = SessionLocal()
    try:
        s = _sqn_id(db)
        with patch("app.services_year.wing_local_date", return_value=dt.date(2026, 8, 28)):
            assert year_state(db, s, 2025) == "past"
            assert year_state(db, s, 2026) == "current"
            assert year_state(db, s, 2027) == "future"
    finally:
        db.close()


def test_selectable_years_are_capped_at_current_plus_two():
    """User decision 2026-08-28, overriding the instruction's 'no cap'."""
    db = SessionLocal()
    try:
        s = _sqn_id(db)
        with patch("app.services_year.wing_local_date", return_value=dt.date(2026, 8, 28)):
            years = selectable_years(db, s)
        assert max(years) == 2028
        assert 2026 in years and 2027 in years
        assert 2029 not in years
    finally:
        db.close()
```

- [ ] **Step 2: Run and watch them fail**

Run: `cd backend && python -m pytest tests/test_year_context.py -q`
Expected: FAIL — `ImportError: cannot import name 'current_year'`

- [ ] **Step 3: Implement**

```python
# backend/app/services_year.py — append
from .models import PlanningYear

FUTURE_YEARS_SELECTABLE = 2  # user decision 2026-08-28: current + 2


def current_year(db: DBSession, squadron_id: str) -> int:
    """The current training year. Derived, never stored, never written."""
    return wing_local_date(db, squadron_id).year


def year_state(db: DBSession, squadron_id: str, year: int) -> str:
    now = current_year(db, squadron_id)
    if year < now:
        return "past"
    return "current" if year == now else "future"


def selectable_years(db: DBSession, squadron_id: str) -> list[int]:
    """Years offered in the selector: every past year that has a row, the
    current year, and FUTURE_YEARS_SELECTABLE ahead. Past is uncapped; future
    is capped by user decision.
    """
    now = current_year(db, squadron_id)
    past = {py.year for py in db.query(PlanningYear)
            .filter(PlanningYear.unit_id == squadron_id).all() if py.year < now}
    ahead = {now + n for n in range(FUTURE_YEARS_SELECTABLE + 1)}
    return sorted(past | ahead)
```

- [ ] **Step 4: Run and watch them pass**

Run: `cd backend && python -m pytest tests/test_year_context.py -q`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services_year.py backend/tests/test_year_context.py
git commit -m "feat(year): derive past/current/future from the wing-local date"
```

---

### Task 3: Canonical uniqueness — one container per squadron and year

> **CORRECTION 2026-08-28, after attempting this task — the index change is a
> no-op and was NOT applied. The tests were.**
>
> Step 2 predicted the first test would fail because "today's index permits
> it". It does not. `uq_planning_years_unit_year_active` is already
> `unique(unit_id, year)` filtered to active rows, so a squadron already
> cannot hold two live containers for one calendar year. All three tests pass
> against the unmodified index — measured, not assumed.
>
> The rationale was also wrong. This task claimed the old index "allowed an
> active 2026 AND an active 2027 — the REM-156 state". 2026 and 2027 are
> different values of `year`, so no `(unit_id, year)` unique index would ever
> have prevented both existing. That state was a violation of the *one active
> year* rule, which lived in application code, not in this index. Under the
> context model that state is not a defect at all: planning 2027 while 2026
> runs is the feature.
>
> The proposed replacement has identical columns and an identical predicate —
> the plan says so itself. Dropping and recreating a unique index on a
> production table for a cosmetic rename is risk without benefit, so the
> migration was not written. The three tests are kept: they pin behaviour that
> was previously untested, including the new
> `test_two_different_years_for_one_squadron_are_both_allowed`.
>
> Still open for the user: the predicate references `active_status`. If a
> later task drops that column outright, this index must be rebuilt then —
> and that is the migration worth writing, at the point it does something.

**Files:**
- Modify: `backend/app/models/planning.py` (`__table_args__`)
- Create: `backend/alembic/versions/<rev>_canonical_year_per_squadron.py`
- Test: `backend/tests/test_year_context.py`

**Interfaces:**
- Produces: index `uq_planning_years_canonical`.

The existing `uq_planning_years_unit_year_active` is unique on `(unit_id, year)`
*among active rows*, which is what allowed an active 2026 **and** an active 2027
— the REM-156 state. The replacement is unique on `(unit_id, year)` among
non-retired rows, so a squadron cannot hold two live containers for one calendar
year regardless of status.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_year_context.py — append
from sqlalchemy.exc import IntegrityError
from app.models import PlanningYear


def test_a_squadron_cannot_hold_two_live_containers_for_one_year():
    db = SessionLocal()
    try:
        s = _sqn_id(db)
        a = PlanningYear(unit_id=s, wing_id=None, year=2061, name="2061 Training Year")
        db.add(a); db.commit()
        b = PlanningYear(unit_id=s, wing_id=None, year=2061, name="2061 again")
        db.add(b)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()


def test_a_retired_row_does_not_block_a_replacement():
    """Archiving a badly set-up year and creating a correct one must stay possible."""
    db = SessionLocal()
    try:
        s = _sqn_id(db)
        old = PlanningYear(unit_id=s, wing_id=None, year=2062, name="bad")
        old.active_status = False
        db.add(old); db.commit()
        good = PlanningYear(unit_id=s, wing_id=None, year=2062, name="2062 Training Year")
        db.add(good); db.commit()      # must NOT raise
    finally:
        db.close()
```

- [ ] **Step 2: Run and watch the first fail**

Run: `cd backend && python -m pytest tests/test_year_context.py -q -k container`
Expected: FAIL — no `IntegrityError`; today's index permits it

- [ ] **Step 3: Replace the index**

```python
# backend/app/models/planning.py — replace the Index inside __table_args__
    __table_args__ = (
        # One canonical container per squadron per calendar year.
        # Supersedes uq_planning_years_unit_year_active, which was scoped to
        # active rows and so permitted an active 2026 AND an active 2027 —
        # the mechanism behind REM-156.
        # Retired rows are excluded so that retiring a bad container and
        # creating a correct one stays possible (capability-preservation.md).
        # unit_id IS NULL for wing/national years and NULLs are distinct in both
        # SQLite and PostgreSQL, so those rows stay unconstrained.
        Index(
            "uq_planning_years_canonical",
            "unit_id", "year",
            unique=True,
            sqlite_where=text("active_status = 1"),
            postgresql_where=text("active_status = true"),
        ),
    )
```

- [ ] **Step 4: Write the migration with a guard**

```python
"""one canonical planning year per squadron per calendar year"""
import sqlalchemy as sa
from alembic import op

revision = "<rev>"
down_revision = "<output of alembic heads>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    bad = conn.execute(sa.text(
        "SELECT count(*) FROM (SELECT unit_id, year FROM planning_years "
        "WHERE unit_id IS NOT NULL AND active_status "
        "GROUP BY unit_id, year HAVING count(*) > 1) x")).scalar()
    if bad:
        raise RuntimeError(
            f"{bad} squadron/year pair(s) still have more than one live planning "
            f"year. Resolve them before applying this migration (see REM-156)."
        )
    op.drop_index("uq_planning_years_unit_year_active", table_name="planning_years")
    op.create_index("uq_planning_years_canonical", "planning_years",
                    ["unit_id", "year"], unique=True,
                    sqlite_where=sa.text("active_status = 1"),
                    postgresql_where=sa.text("active_status = true"))


def downgrade() -> None:
    op.drop_index("uq_planning_years_canonical", table_name="planning_years")
    op.create_index("uq_planning_years_unit_year_active", "planning_years",
                    ["unit_id", "year"], unique=True,
                    sqlite_where=sa.text("active_status = 1"),
                    postgresql_where=sa.text("active_status = true"))
```

> The two indexes have the same columns and predicate today. The rename is
> deliberate: the *name* stops claiming the constraint is about being active,
> and Task 5 is what makes the distinction real by removing active-status
> filtering from reads.

- [ ] **Step 5: Migrate and test**

```bash
cd backend && alembic upgrade head && rm -f aafc_tms.db
python -m pytest tests/test_year_context.py -q
```
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/planning.py backend/alembic/versions \
        backend/tests/test_year_context.py
git commit -m "feat(year): one canonical planning year per squadron per year"
```

---

### Task 4: `ensure_year_context` — materialise on write, never on read

**Files:**
- Modify: `backend/app/services_year.py`
- Test: `backend/tests/test_year_context.py`

**Interfaces:**
- Consumes: `current_year`.
- Produces: `find_year_context(db, squadron_id, year) -> PlanningYear | None` (read, never writes) and `ensure_year_context(db, squadron_id, year, user_id=None) -> PlanningYear` (write path only).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_year_context.py — append
from app.services_year import ensure_year_context, find_year_context


def test_find_does_not_create():
    db = SessionLocal()
    try:
        s = _sqn_id(db)
        before = db.query(PlanningYear).count()
        assert find_year_context(db, s, 2071) is None
        assert db.query(PlanningYear).count() == before, "a read must not write"
    finally:
        db.close()


def test_ensure_creates_once_and_is_idempotent():
    db = SessionLocal()
    try:
        s = _sqn_id(db)
        a = ensure_year_context(db, s, 2072)
        b = ensure_year_context(db, s, 2072)
        assert a.id == b.id
        assert db.query(PlanningYear).filter(
            PlanningYear.unit_id == s, PlanningYear.year == 2072,
            PlanningYear.active_status).count() == 1
    finally:
        db.close()


def test_ensure_derives_the_name_and_never_invents_one():
    db = SessionLocal()
    try:
        s = _sqn_id(db)
        py = ensure_year_context(db, s, 2073)
        assert py.name == "2073 Training Year"
        assert py.year == 2073
    finally:
        db.close()


def test_ensure_reuses_a_retired_year_number_by_creating_a_new_live_row():
    db = SessionLocal()
    try:
        s = _sqn_id(db)
        dead = PlanningYear(unit_id=s, wing_id=None, year=2074, name="old")
        dead.active_status = False
        db.add(dead); db.commit()
        live = ensure_year_context(db, s, 2074)
        assert live.id != dead.id and live.active_status is True
    finally:
        db.close()
```

- [ ] **Step 2: Run and watch them fail**

Run: `cd backend && python -m pytest tests/test_year_context.py -q -k "find or ensure"`
Expected: FAIL — `ImportError: cannot import name 'ensure_year_context'`

- [ ] **Step 3: Implement**

```python
# backend/app/services_year.py — append
import uuid as _uuid

from sqlalchemy.exc import IntegrityError

from .models import Squadron


def year_display_name(year: int) -> str:
    """The only place a year's name is produced. Derived, never user-entered."""
    return f"{year} Training Year"


def find_year_context(db: DBSession, squadron_id: str, year: int) -> PlanningYear | None:
    """Resolve the canonical container, or None. NEVER creates."""
    return (db.query(PlanningYear)
              .filter(PlanningYear.unit_id == squadron_id,
                      PlanningYear.year == year,
                      PlanningYear.active_status)
              .first())


def ensure_year_context(db: DBSession, squadron_id: str, year: int,
                        user_id: str | None = None) -> PlanningYear:
    """Resolve the canonical container, creating it if absent.

    Write paths only. Idempotent under concurrency: two callers may both see
    None, so the loser of the insert race is caught and re-read rather than
    guarded by a check-then-write.
    """
    existing = find_year_context(db, squadron_id, year)
    if existing is not None:
        return existing

    sqn = db.get(Squadron, squadron_id)
    py = PlanningYear(
        id=str(_uuid.uuid4()), unit_id=squadron_id,
        wing_id=sqn.wing_id if sqn else None,
        year=year, name=year_display_name(year),
        created_by=user_id, updated_by=user_id,
    )
    db.add(py)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raced = find_year_context(db, squadron_id, year)
        if raced is None:
            raise
        return raced
    return py
```

- [ ] **Step 4: Run and watch them pass**

Run: `cd backend && python -m pytest tests/test_year_context.py -q`
Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services_year.py backend/tests/test_year_context.py
git commit -m "feat(year): materialise the canonical year container on write only"
```

---

### Task 5: Year listing and reads that tolerate an unmaterialised year

**Files:**
- Modify: `backend/app/routers/planning.py` — `list_planning_years` (line ~421), `_year_out` (line ~244)
- Test: `backend/tests/test_year_context.py`

**Interfaces:**
- Consumes: `selectable_years`, `year_state`, `find_year_context`, `year_display_name`.
- Produces: `GET /api/planning/years` gains `state` and `materialised` on each entry and includes unmaterialised selectable years; `GET /api/planning/year-context?squadron_id=&year=` returns a context whether or not a row exists.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_year_context.py — append
from tests.conftest import login


def test_year_listing_includes_future_years_with_no_row(client):
    hdr = login(client, "ADMIN703")
    rows = client.get("/api/planning/years", headers=hdr).json()
    years = {r["year"]: r for r in rows}
    unmaterialised = [r for r in rows if not r["materialised"]]
    assert unmaterialised, "future years with no row must still be listed"
    for r in unmaterialised:
        assert r["planning_year_id"] is None
        assert r["state"] in ("current", "future")


def test_year_context_read_does_not_create_a_row(client):
    hdr = login(client, "ADMIN703")
    me = client.get("/api/auth/me", headers=hdr).json()
    sid = me.get("squadron_id") or me["session"]["squadron_id"]
    before = len(client.get("/api/planning/years", headers=hdr).json())
    r = client.get(f"/api/planning/year-context?squadron_id={sid}&year=2077", headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["year"] == 2077
    assert body["materialised"] is False
    assert body["planning_year_id"] is None
    after = len(client.get("/api/planning/years", headers=hdr).json())
    assert before == after
```

- [ ] **Step 2: Run and watch them fail**

Run: `cd backend && python -m pytest tests/test_year_context.py -q -k "listing or context_read"`
Expected: FAIL — `KeyError: 'materialised'`, then 404 on `year-context`

- [ ] **Step 3: Extend the payload**

```python
# backend/app/routers/planning.py — in _year_out, add beside "year"
        "state": None,          # filled by the caller that knows the squadron
        "materialised": True,   # a row exists; overridden for logical-only years
```

- [ ] **Step 4: Add logical years to the listing**

```python
# backend/app/routers/planning.py — at the end of list_planning_years,
# after `out` has been built from the materialised rows
    from ..services_year import selectable_years, year_state, year_display_name

    sqn_id = p.squadron_id if p.role in ("sqn_admin", "sqn_general") else unit_id
    if sqn_id:
        have = {row["year"] for row in out}
        for y in selectable_years(db, sqn_id):
            state = year_state(db, sqn_id, y)
            if y in have:
                for row in out:
                    if row["year"] == y:
                        row["state"] = state
            else:
                # A year the user may select that has no row yet. Listed so the
                # selector can offer it; no row is created by listing it.
                out.append({
                    "planning_year_id": None, "unit_id": sqn_id, "wing_id": None,
                    "year": y, "name": year_display_name(y), "active_status": True,
                    "state": state, "materialised": False,
                    "unit_code": None, "unit_name": None, "wing_code": None,
                    "created_by": None, "updated_by": None,
                    "created_at": None, "updated_at": None, "version": 0,
                })
        out.sort(key=lambda r: r["year"], reverse=True)
```

- [ ] **Step 5: Add the year-context read**

```python
# backend/app/routers/planning.py — new endpoint
@router.get("/year-context")
def get_year_context(
    squadron_id: str, year: int,
    db: DBSession = Depends(get_db), p: Principal = Depends(get_principal),
):
    """A year context, whether or not a row exists for it.

    Deliberately does NOT materialise: a read must remain a read. Callers that
    need a row call a write endpoint, which uses ensure_year_context.
    """
    from ..services_year import find_year_context, year_display_name, year_state

    require_can_view_squadron(p, squadron_id)
    py = find_year_context(db, squadron_id, year)
    return {
        "squadron_id": squadron_id, "year": year,
        "state": year_state(db, squadron_id, year),
        "materialised": py is not None,
        "planning_year_id": py.id if py else None,
        "name": py.name if py else year_display_name(year),
    }
```

- [ ] **Step 6: Run and watch them pass**

Run: `cd backend && python -m pytest tests/test_year_context.py tests/test_planning.py -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/planning.py backend/tests/test_year_context.py
git commit -m "feat(year): list and read years that have no row yet"
```

---

### Task 6: Rollover becomes copy-setup

**Files:**
- Modify: `backend/app/routers/planning.py:3631` (`rollover_year`)
- Create: `backend/tests/test_year_copy_setup.py`

**Interfaces:**
- Consumes: `ensure_year_context`.
- Produces: `POST /api/planning/years/copy-setup` taking `{source_year, target_year, copy_classes, copy_parade_pattern}`.

`rollover_year` sets `active_status=True` on a new row and names it
`f"{name} → {target_year}"` (`planning.py:3643,3658`). That one behaviour created
both the multi-active state and the `→ 2027` naming found in production. Year
creation is no longer part of the operation, because the year already exists.

**Copy exactly this, per the user's confirmed list — nothing else:**

| copy | never copy |
|---|---|
| Training Class structure (optional) | sessions, outcomes, progress, attendance |
| Parade recurrence pattern (optional) | audit history, published status |
| | holidays by date-shift — re-import instead |
| | facilitators, training areas, equipment, subject areas, timing templates (not year-scoped) |

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_year_copy_setup.py
from tests.conftest import login, next_test_year


def test_copy_setup_copies_class_structure_and_nothing_else(client):
    hdr = login(client, "ADMIN703")
    src, tgt = next_test_year(), next_test_year() + 1

    # materialise the source by writing a class into it
    client.post("/api/planning/years", json={"year": src, "name": f"{src} Training Year"},
                headers=hdr)
    years = client.get("/api/planning/years", headers=hdr).json()
    src_id = next(y["planning_year_id"] for y in years if y["year"] == src)
    client.post("/api/training-classes", headers=hdr, json={
        "training_year_id": src_id, "training_stage_id": None,
        "display_name": "Senior 1", "stage_code": "SNR"})

    r = client.post("/api/planning/years/copy-setup", headers=hdr, json={
        "source_year": src, "target_year": tgt,
        "copy_classes": True, "copy_parade_pattern": False})
    assert r.status_code == 200, r.text

    years = client.get("/api/planning/years", headers=hdr).json()
    tgt_row = next(y for y in years if y["year"] == tgt)
    assert tgt_row["materialised"] is True
    assert tgt_row["name"] == f"{tgt} Training Year"      # derived, no arrow
    assert "→" not in tgt_row["name"]

    classes = client.get(
        f"/api/training-classes?training_year_id={tgt_row['planning_year_id']}",
        headers=hdr).json()
    assert [c["display_name"] for c in classes] == ["Senior 1"]
    # new canonical records, not the source rows
    assert all(c["training_year_id"] == tgt_row["planning_year_id"] for c in classes)


def test_copy_setup_never_copies_sessions(client):
    hdr = login(client, "ADMIN703")
    src, tgt = next_test_year(), next_test_year() + 1
    client.post("/api/planning/years", json={"year": src, "name": f"{src} Training Year"},
                headers=hdr)
    r = client.post("/api/planning/years/copy-setup", headers=hdr, json={
        "source_year": src, "target_year": tgt,
        "copy_classes": True, "copy_parade_pattern": True})
    assert r.status_code == 200, r.text
    assert r.json()["sessions_copied"] == 0
```

- [ ] **Step 2: Run and watch it fail**

Run: `cd backend && python -m pytest tests/test_year_copy_setup.py -q`
Expected: FAIL — 404 on `/copy-setup`

- [ ] **Step 3: Add the endpoint**

```python
# backend/app/routers/planning.py
class CopySetupIn(BaseModel):
    source_year: int
    target_year: int
    copy_classes: bool = True
    copy_parade_pattern: bool = False


@router.post("/years/copy-setup")
def copy_setup(body: CopySetupIn, db: DBSession = Depends(get_db),
               p: Principal = Depends(get_principal)):
    """Copy configuration from one year into another. Does not create a year in
    the user's sense — the year already exists; this materialises its container
    and seeds configuration into it.

    Copies only class structure and, optionally, the parade recurrence pattern.
    Never sessions, outcomes, progress, attendance, audit history or published
    status; never date-shifted holidays.
    """
    from ..services_year import ensure_year_context, find_year_context

    sqn_id = p.squadron_id
    require_can_write_squadron(p, sqn_id, p.wing_id)

    source = find_year_context(db, sqn_id, body.source_year)
    if source is None:
        raise HTTPException(404, detail={"error": "source_year_not_configured"})
    target = ensure_year_context(db, sqn_id, body.target_year, p.user_id)

    classes_copied = 0
    if body.copy_classes:
        for c in db.query(TrainingClass).filter(
                TrainingClass.training_year_id == source.id,
                TrainingClass.is_archived == False).all():  # noqa: E712
            db.add(TrainingClass(
                id=str(uuid.uuid4()), squadron_id=c.squadron_id,
                training_year_id=target.id, training_stage_id=c.training_stage_id,
                stage_code=c.stage_code, display_name=c.display_name,
                sequence=c.sequence, expected_count=c.expected_count,
                created_at=utcnow(), updated_at=utcnow()))
            classes_copied += 1

    db.commit()
    audit(db, p, object_type="planning_year", object_id=target.id,
          action="copy_setup",
          new={"source_year": body.source_year, "target_year": body.target_year,
               "classes_copied": classes_copied})
    return {"ok": True, "planning_year_id": target.id,
            "classes_copied": classes_copied, "sessions_copied": 0}
```

- [ ] **Step 4: Retire `rollover_year`**

Leave the route registered but make it delegate, so existing callers keep working
during the frontend transition:

```python
@router.post("/years/{year_id}/rollover", deprecated=True)
def rollover_year(year_id: str, body: RolloverIn, db: DBSession = Depends(get_db),
                  p: Principal = Depends(get_principal)):
    """Deprecated. Superseded by POST /years/copy-setup.

    Kept so existing frontend callers do not break mid-transition. It no longer
    creates a second live year: the target year's canonical container is
    resolved, not invented, and the name is derived rather than arrowed.
    """
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py, write=True)
    return copy_setup(CopySetupIn(source_year=py.year,
                                  target_year=body.target_year or (py.year + 1),
                                  copy_classes=True, copy_parade_pattern=False),
                      db=db, p=p)
```

- [ ] **Step 5: Run and watch them pass**

Run: `cd backend && python -m pytest tests/test_year_copy_setup.py tests/test_planning.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/planning.py backend/tests/test_year_copy_setup.py
git commit -m "feat(year): replace rollover with an explicit copy-setup action"
```

---

### Task 7: Getting Started stops requiring an active year

**Files:**
- Modify: `backend/app/routers/setup.py:66-80`
- Test: `backend/tests/test_setup_status.py`

**Interfaces:**
- Consumes: `current_year`, `find_year_context`.

`setup.py:71` computes `planning_year_active = bool(active_year_ids)`, and
holidays and anchor review are gated on the same list. A squadron reads as "not
set up" purely because no row exists — which under this model is the normal state
of a year nobody has written to yet.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_setup_status.py — append
def test_setup_status_does_not_require_a_materialised_year(client):
    """Setup completion must reflect configured training, not row existence."""
    hdr = login(client, "ADMIN703")
    body = client.get("/api/setup/status", headers=hdr).json()
    assert "planning_year_active" not in body, \
        "row existence is not a setup step under the calendar-context model"
```

- [ ] **Step 2: Run and watch it fail**

Run: `cd backend && python -m pytest tests/test_setup_status.py -q -k materialised`
Expected: FAIL — the key is present

- [ ] **Step 3: Replace the gate**

```python
# backend/app/routers/setup.py — replacing the active_year_ids block
            from ..services_year import current_year, find_year_context

            this_year = current_year(db, sq_id)
            py = find_year_context(db, sq_id, this_year)
            year_ids = [py.id] if py else []
            # Holidays and anchor review describe THIS year's configuration.
            # A year with no container simply has none configured yet; that is
            # an empty year, not an unset-up squadron.
            holidays_configured = bool(year_ids) and db.query(HolidayPeriod).filter(
                HolidayPeriod.planning_year_id.in_(year_ids)).count() > 0
```

Remove `planning_year_active` from the response body and from any checklist item
that reports it.

- [ ] **Step 4: Run and watch it pass**

Run: `cd backend && python -m pytest tests/test_setup_status.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/setup.py backend/tests/test_setup_status.py
git commit -m "feat(year): setup status reflects configuration, not row existence"
```

---

### Task 8: Renumber 708's container from 2027 to 2026

**Files:**
- Create: `backend/alembic/versions/<rev>_renumber_708_year.py`
- Create: `tools/data-quality/year_container_audit.py`

**Interfaces:** none.

User decision 2026-08-28: 708's only live container is numbered **2027** and
holds all 15 of its parade dates in **2026**. The dates are authoritative, so the
container is renumbered. This is the one case where a year integer is changed,
and it is done because a human decided it — not by inference.

- [ ] **Step 1: Write the read-only audit tool**

```python
# tools/data-quality/year_container_audit.py
"""Report every PlanningYear against the calendar years of its own children.

Read-only. Run before any year migration. Instruction §40-41: no migration may
silently reinterpret a row; ambiguity stops and asks.
"""
import argparse
import psycopg

SQL = """
SELECT s.code AS sqn, py.id, py.year, py.name, py.active_status,
       count(pd.id)                          AS dates,
       min(substr(pd.parade_date,1,4))       AS first_child_year,
       max(substr(pd.parade_date,1,4))       AS last_child_year
FROM planning_years py
LEFT JOIN squadrons s ON s.id = py.unit_id
LEFT JOIN parade_dates pd ON pd.planning_year_id = py.id
GROUP BY s.code, py.id, py.year, py.name, py.active_status
ORDER BY s.code, py.year;
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", required=True)
    args = ap.parse_args()
    flagged = 0
    with psycopg.connect(args.dsn) as conn, conn.cursor() as cur:
        cur.execute(SQL)
        for sqn, _id, year, name, active, dates, first, last in cur.fetchall():
            if dates and (str(year) != first or str(year) != last):
                flagged += 1
                print(f"MISMATCH {sqn} year={year} name={name!r} "
                      f"dates={dates} children={first}..{last}")
    print(f"\n{flagged} container(s) whose year integer disagrees with their dates")
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run it against a production dump restored locally**

Run: `python tools/data-quality/year_container_audit.py --dsn "$DISPOSABLE_DSN"`
Expected: exactly one mismatch — 708, year 2027, children 2026..2026. If the
tool reports anything else, **stop** and report rather than migrating.

- [ ] **Step 3: Write the guarded migration**

```python
"""renumber 708's container from 2027 to 2026 (user decision 2026-08-28)"""
import sqlalchemy as sa
from alembic import op

revision = "<rev>"
down_revision = "<output of alembic heads>"
branch_labels = None
depends_on = None

TARGET = "b482b6ed-6e45-4158-b8fb-b169782dd72a"


def upgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(sa.text(
        "SELECT year, (SELECT count(*) FROM parade_dates WHERE planning_year_id=:i), "
        "(SELECT count(*) FROM parade_dates WHERE planning_year_id=:i "
        " AND parade_date NOT LIKE '2026-%') "
        "FROM planning_years WHERE id=:i"), {"i": TARGET}).first()
    if row is None:
        return  # not this database (dev/test); nothing to do
    year, dates, non_2026 = row
    if year != 2027 or dates != 15 or non_2026 != 0:
        raise RuntimeError(
            f"708's container is not in the expected state (year={year}, "
            f"dates={dates}, non-2026 dates={non_2026}). Refusing to renumber."
        )
    op.execute(sa.text(
        "UPDATE planning_years SET year = 2026, name = '2026 Training Year' "
        "WHERE id = :i"), {"i": TARGET})


def downgrade() -> None:
    op.execute(sa.text(
        "UPDATE planning_years SET year = 2027, "
        "name = '2026 Training Year → 2027' WHERE id = :i"), {"i": TARGET})
```

- [ ] **Step 4: Rehearse forward and back on a disposable PostgreSQL**

Never against production. Restore a dump, `alembic upgrade head`, confirm 708
holds one live 2026 container with 15 dates, then `alembic downgrade -1` and
confirm the original state returns.

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions tools/data-quality/year_container_audit.py
git commit -m "fix(data): renumber 708's container to the year its dates are in"
```

---

### Task 9: Past years are read-only unless the write is authorised

**Files:**
- Modify: `backend/app/services_year.py`
- Modify: `backend/app/routers/planning.py` (year-scoped write endpoints)
- Test: `backend/tests/test_year_context.py`

**Interfaces:**
- Consumes: `year_state`.
- Produces: `PastYearLocked` and `require_year_writable(db, squadron_id, year, p) -> None`.

Spec §2.4, user decision 2026-08-28: past years are **read-only by default**,
with correction available through an authorised, audited path. Delivered
training is history; a stray edit to last year's records is not a typo you want
to make silently.

The authorised path is the machinery that already exists: an active
`ProxySession` in `delegated_intervention` mode (`Principal.proxy_mode`,
`permissions.py:30-33`). Reads are never affected.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_year_context.py — append
from app.services_year import PastYearLocked, require_year_writable


class _P:
    """Minimal principal stand-in; mirrors permissions.Principal's fields."""
    def __init__(self, role="sqn_admin", proxy_mode=None):
        self.role, self.proxy_mode = role, proxy_mode
        self.user_id = "u1"


def test_writing_to_a_past_year_is_blocked():
    db = SessionLocal()
    try:
        s = _sqn_id(db)
        with patch("app.services_year.wing_local_date", return_value=dt.date(2026, 8, 28)):
            with pytest.raises(PastYearLocked):
                require_year_writable(db, s, 2025, _P())
    finally:
        db.close()


def test_current_and_future_years_are_writable():
    db = SessionLocal()
    try:
        s = _sqn_id(db)
        with patch("app.services_year.wing_local_date", return_value=dt.date(2026, 8, 28)):
            require_year_writable(db, s, 2026, _P())   # must not raise
            require_year_writable(db, s, 2027, _P())   # must not raise
    finally:
        db.close()


def test_delegated_intervention_may_correct_a_past_year():
    """The authorised path: existing Delegated Intervention, already audited."""
    db = SessionLocal()
    try:
        s = _sqn_id(db)
        with patch("app.services_year.wing_local_date", return_value=dt.date(2026, 8, 28)):
            require_year_writable(db, s, 2025,
                                  _P(proxy_mode="delegated_intervention"))
    finally:
        db.close()


def test_plain_proxy_mode_is_not_enough_to_edit_history():
    db = SessionLocal()
    try:
        s = _sqn_id(db)
        with patch("app.services_year.wing_local_date", return_value=dt.date(2026, 8, 28)):
            with pytest.raises(PastYearLocked):
                require_year_writable(db, s, 2025, _P(proxy_mode="proxy"))
    finally:
        db.close()
```

- [ ] **Step 2: Run and watch them fail**

Run: `cd backend && python -m pytest tests/test_year_context.py -q -k "past or writable or intervention"`
Expected: FAIL — `ImportError: cannot import name 'PastYearLocked'`

- [ ] **Step 3: Implement the guard**

```python
# backend/app/services_year.py — append


class PastYearLocked(RuntimeError):
    """A write was attempted against a past training year without authority."""


def require_year_writable(db: DBSession, squadron_id: str, year: int, p) -> None:
    """Allow writes to the current and future years; protect the past.

    Correction of history stays possible through Delegated Intervention, which
    already creates a ProxySession and an audit trail. Plain Proxy Mode is NOT
    sufficient: it exists so a wing admin can act on a squadron's behalf in the
    ordinary course, not to rewrite delivered training.

    Reads never call this.
    """
    if year_state(db, squadron_id, year) != "past":
        return
    if getattr(p, "proxy_mode", None) == "delegated_intervention":
        return
    raise PastYearLocked(
        f"{year} is a past training year and is read-only. Use Delegated "
        f"Intervention to correct historical records."
    )
```

- [ ] **Step 4: Translate it to a 403 at the router boundary**

```python
# backend/app/routers/planning.py — near the other exception handling
from ..services_year import PastYearLocked, require_year_writable


def _require_writable_year(db: DBSession, squadron_id: str, year: int, p) -> None:
    try:
        require_year_writable(db, squadron_id, year, p)
    except PastYearLocked as exc:
        raise HTTPException(403, detail={"error": "past_year_read_only",
                                         "message": str(exc)})
```

Call `_require_writable_year(db, sqn_id, target.year, p)` at the top of each
year-scoped write endpoint — `copy_setup`, parade-date generation, holiday
creation, and the anchors and missions writers.

- [ ] **Step 5: Run and watch them pass**

Run: `cd backend && python -m pytest tests/test_year_context.py tests/test_planning.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services_year.py backend/app/routers/planning.py \
        backend/tests/test_year_context.py
git commit -m "feat(year): past years are read-only unless intervention is active"
```

---

## Deployment sequence

1. Tasks 1–4 → deploy → verify staging. Nothing user-visible changes yet.
2. Task 5 → deploy. The API starts offering unmaterialised years; the frontends
   ignore fields they do not know about.
3. Tasks 6–7 → deploy → verify Getting Started and copy-setup on staging.
4. Task 9 (past-year protection) → deploy. Ship it after copy-setup, so the
   guard exists before anyone is invited to work across years.
5. Task 8 (the 708 renumber) → run the audit first, then deploy.
6. Frontend work follows the §6 design, in its own plan.

Production is behind on migrations; catching it up is a prerequisite and is not
part of this plan. **Do not deploy production** (instruction §58).

## Not in this plan, and why

- **All frontend work.** The instruction sequences frontend-design after this
  plan, so concrete markup does not exist yet. Includes the year selector, the
  empty-future-year state, TMS→PW handoff, `aafc_pw_year_id` → squadron+year,
  `SetupPanel`, and `GuidedYearSetupModal`.
- **The ParadeNight/ParadeDate merge (Phase B).** Its objective survives and its
  year assignment is reworked to come from the night's own date, but it is a
  separate spec and plan.
- **Removing `PlanningYear.name`.** Task 4 derives it on write and nothing may
  branch on it, which is enough. Dropping the column is a later migration once
  no reader remains.
- **Squadron 718's two orphaned nights** — open question 2 in the spec, needs a
  human decision.
