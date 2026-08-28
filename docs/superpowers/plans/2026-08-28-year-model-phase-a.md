# Training Year Model — Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give a squadron exactly one active training year plus an optional draft, and promote the draft automatically on 1 January in squadron-local time.

**Architecture:** `PlanningYear.active_status` (boolean) becomes `status` (`draft|active|archived`), with the boolean retained and dual-written through one release so the two independently deployed frontends keep working. Rollover creates the next year as a **draft** instead of a second active year. Promotion is **lazy** — evaluated when a squadron's active year is resolved — because this system has no scheduler: `workers/celery_app.py` declares no `beat_schedule` and the Railway project has no Redis service, so `dispatcher.py` always runs synchronously in-process.

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, PostgreSQL (prod/staging) and SQLite (tests), Python 3.13 (`zoneinfo` is stdlib — no new dependency).

**Spec:** `docs/superpowers/specs/2026-08-27-year-model-and-parade-night-merge-design.md`

## Global Constraints

- **Phase B is NOT in this plan.** The spec sequences it after Phase A holds in production. It gets its own plan.
- **Current Alembic head is `e2f3a4b5c6d7`.** Task 1's migration uses it as `down_revision`; each later migration chains to the previous task's. Re-run `alembic heads` before writing each one rather than trusting this line. `<rev>` in the migration templates below is not a placeholder to invent: generate the file with `alembic revision -m "..."` and use the id it creates.
- **`Australia/Perth` on 7WG. Squadrons cannot override.** 7WG is production's only wing and holds all 18 squadrons.
- **An unset timezone must raise, never default.** With one wing a missing value is invisible — every lookup finds Perth. It first bites when wing two is created.
- **Never drop `active_status` in this plan.** Task 8 is deliberately deferred until both frontends have shipped and been verified.
- **Archive, never delete.** `active_status=false` is this system's archive state (see `.claude/rules/capability-preservation.md`).
- **Tests use the real SQLite DB from `backend/tests/conftest.py`.** Use `login(client, code)` for auth and `next_test_year()` for year numbers — the DB seeds once per session and is never reset, so hardcoded years collide.
- Run tests with `cd backend && source .venv/bin/activate && python -m pytest tests/ -q`.

## File Structure

| File | Responsibility |
|---|---|
| `backend/app/models/organisations.py` | add `Wing.timezone` |
| `backend/app/models/planning.py` | add `PlanningYear.status`; retain `active_status`; index change (Task 6) |
| `backend/app/services_year.py` | **new** — the only place that resolves a squadron's active year, performs lazy promotion, and reads timezone |
| `backend/app/routers/planning.py` | year create/patch/rollover write through the helper; API returns `status` |
| `backend/alembic/versions/` | one migration per schema task |
| `backend/tests/test_year_model.py` | **new** — status, invariant, rollover-creates-draft |
| `backend/tests/test_year_rollover.py` | **new** — lazy promotion, timezone, idempotence, concurrency |

---

### Task 1: `Wing.timezone`, and a resolver that refuses to guess

**Files:**
- Modify: `backend/app/models/organisations.py` (the `Wing` class)
- Create: `backend/app/services_year.py`
- Create: `backend/alembic/versions/<rev>_add_wing_timezone.py`
- Test: `backend/tests/test_year_model.py`

**Interfaces:**
- Produces: `squadron_timezone(db, squadron_id) -> ZoneInfo` and `squadron_today(db, squadron_id) -> datetime.date`, both in `app/services_year.py`. Later tasks call these; nothing else reads `Wing.timezone` directly.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_year_model.py
import pytest
from zoneinfo import ZoneInfo
from app.database import SessionLocal
from app.models import Wing, Squadron
from app.services_year import squadron_timezone, MissingTimezone


def test_squadron_timezone_comes_from_its_wing():
    db = SessionLocal()
    try:
        sqn = db.query(Squadron).filter(Squadron.code == "703").first()
        assert squadron_timezone(db, sqn.id) == ZoneInfo("Australia/Perth")
    finally:
        db.close()


def test_missing_timezone_raises_rather_than_defaulting():
    """A silent UTC or Perth default is the bug: with one wing it is invisible
    until a second wing is created, which is exactly when nobody is looking."""
    db = SessionLocal()
    try:
        sqn = db.query(Squadron).filter(Squadron.code == "703").first()
        wing = db.get(Wing, sqn.wing_id)
        original = wing.timezone
        wing.timezone = None
        db.flush()
        with pytest.raises(MissingTimezone):
            squadron_timezone(db, sqn.id)
        wing.timezone = original
        db.commit()
    finally:
        db.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_year_model.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services_year'`

- [ ] **Step 3: Add the column**

```python
# backend/app/models/organisations.py — inside class Wing, after short_name
    # IANA zone, e.g. "Australia/Perth". Squadrons deliberately cannot override:
    # a wing is the smallest unit that spans a timezone in practice.
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
```

- [ ] **Step 4: Write the resolver**

```python
# backend/app/services_year.py
"""Everything that decides which training year a squadron is in.

Deliberately the only module that reads Wing.timezone or performs the
draft -> active promotion, so there is one place to reason about both.
"""
from __future__ import annotations

import datetime as _dt
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session as DBSession

from .models import Squadron, Wing


class MissingTimezone(RuntimeError):
    """Raised when a wing has no IANA timezone set."""


def squadron_timezone(db: DBSession, squadron_id: str) -> ZoneInfo:
    sqn = db.get(Squadron, squadron_id)
    if sqn is None:
        raise MissingTimezone(f"unknown squadron {squadron_id}")
    wing = db.get(Wing, sqn.wing_id) if sqn.wing_id else None
    if wing is None or not wing.timezone:
        raise MissingTimezone(
            f"wing for squadron {sqn.code} has no timezone set; refusing to "
            f"assume UTC or Australia/Perth"
        )
    return ZoneInfo(wing.timezone)


def squadron_today(db: DBSession, squadron_id: str) -> _dt.date:
    """Today's date as the squadron experiences it, not as the server does."""
    return _dt.datetime.now(squadron_timezone(db, squadron_id)).date()
```

- [ ] **Step 5: Write the migration**

```python
# backend/alembic/versions/<rev>_add_wing_timezone.py
"""add Wing.timezone

Revision ID: <rev>
Revises: e2f3a4b5c6d7
"""
import sqlalchemy as sa
from alembic import op

revision = "<rev>"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("wings") as b:
        b.add_column(sa.Column("timezone", sa.String(64), nullable=True))
    # 7WG is the only wing in production and holds all 18 squadrons.
    # Backfilled by code, not left to a default, so a NEW wing still arrives
    # with NULL and trips MissingTimezone rather than silently inheriting Perth.
    op.execute("UPDATE wings SET timezone = 'Australia/Perth' WHERE code = '7WG'")


def downgrade() -> None:
    with op.batch_alter_table("wings") as b:
        b.drop_column("timezone")
```

- [ ] **Step 6: Seed the value so tests and fresh databases have it**

```python
# backend/app/seeds/seed_all.py — where the Wing is constructed, add timezone
        wing = Wing(national_id=nat.id, code="7WG",
                    name="7 Wing - Western Australia", short_name="7WG",
                    timezone="Australia/Perth")
```

- [ ] **Step 7: Run migration and tests**

Run:
```bash
cd backend && source .venv/bin/activate
alembic upgrade head
rm -f aafc_tms.db && python -m pytest tests/test_year_model.py -q
```
Expected: PASS, 2 passed

- [ ] **Step 8: Run the full suite for regressions**

Run: `python -m pytest tests/ -q`
Expected: no new failures against the recorded baseline

- [ ] **Step 9: Commit**

```bash
git add backend/app/models/organisations.py backend/app/services_year.py \
        backend/alembic/versions backend/app/seeds/seed_all.py \
        backend/tests/test_year_model.py
git commit -m "feat(year): add Wing.timezone and a resolver that refuses to guess"
```

---

### Task 2: `PlanningYear.status`, dual-written with `active_status`

**Files:**
- Modify: `backend/app/models/planning.py`
- Modify: `backend/app/services_year.py`
- Create: `backend/alembic/versions/<rev>_add_planning_year_status.py`
- Test: `backend/tests/test_year_model.py`

**Interfaces:**
- Consumes: nothing from Task 1 except the module.
- Produces: `YEAR_STATUS = ("draft", "active", "archived")` and `set_year_status(py, status) -> None` in `app/services_year.py`. Every write to a planning year's state goes through it; nothing assigns `active_status` directly after this task.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_year_model.py — append
from app.services_year import set_year_status
from app.models import PlanningYear


def test_set_year_status_keeps_the_boolean_in_step():
    """active_status stays real and dual-written for one release: 24 references
    in connected-frontend and 22 in the React app are deployed separately from
    the backend, so an old frontend must keep working against a new backend."""
    py = PlanningYear(unit_id=None, wing_id=None, year=2999, name="dual-write")
    set_year_status(py, "active")
    assert (py.status, py.active_status) == ("active", True)
    set_year_status(py, "draft")
    assert (py.status, py.active_status) == ("draft", False)
    set_year_status(py, "archived")
    assert (py.status, py.active_status) == ("archived", False)


def test_set_year_status_rejects_anything_else():
    py = PlanningYear(unit_id=None, wing_id=None, year=2999, name="bad")
    with pytest.raises(ValueError):
        set_year_status(py, "current")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_year_model.py -q -k status`
Expected: FAIL — `ImportError: cannot import name 'set_year_status'`

- [ ] **Step 3: Add the column**

```python
# backend/app/models/planning.py — inside class PlanningYear, beside active_status
    # draft | active | archived. active_status is retained and dual-written for
    # one release; see services_year.set_year_status. Do not read one without
    # the other until Task 8 drops the boolean.
    status: Mapped[str] = mapped_column(String(20), nullable=False,
                                        default="active", server_default="active",
                                        index=True)
```

- [ ] **Step 4: Write the helper**

```python
# backend/app/services_year.py — append
from .models import PlanningYear

YEAR_STATUS = ("draft", "active", "archived")


def set_year_status(py: PlanningYear, status: str) -> None:
    """The single place a planning year's state changes.

    Writes both columns. A draft is NOT active_status=True: only 'active' is,
    which is what keeps the one-active-year index meaningful during the
    compatibility window.
    """
    if status not in YEAR_STATUS:
        raise ValueError(f"status must be one of {YEAR_STATUS}, got {status!r}")
    py.status = status
    py.active_status = (status == "active")
```

- [ ] **Step 5: Write the migration**

```python
# backend/alembic/versions/<rev>_add_planning_year_status.py
"""add PlanningYear.status, backfilled from active_status

Revision ID: <rev>
Revises: <Task 1's rev>
"""
import sqlalchemy as sa
from alembic import op

revision = "<rev>"
down_revision = "<Task 1's rev>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("planning_years") as b:
        b.add_column(sa.Column("status", sa.String(20), nullable=False,
                               server_default="active"))
    # Every existing row is active or archived; nothing is a draft yet.
    op.execute("UPDATE planning_years SET status = 'active' WHERE active_status")
    op.execute("UPDATE planning_years SET status = 'archived' WHERE NOT active_status")
    op.create_index("ix_planning_years_status", "planning_years", ["status"])


def downgrade() -> None:
    op.drop_index("ix_planning_years_status", table_name="planning_years")
    with op.batch_alter_table("planning_years") as b:
        b.drop_column("status")
```

- [ ] **Step 6: Route the existing write sites through the helper**

There are four. Replace each direct assignment:

```python
# backend/app/routers/planning.py:457 area — POST /years
    py = PlanningYear(unit_id=unit_id, wing_id=wing_id, ...)
    set_year_status(py, "active" if body.active_status else "archived")

# backend/app/routers/planning.py:560 area — PATCH /years/{id}
    if body.active_status is not None:
        set_year_status(py, "active" if body.active_status else "archived")

# backend/app/routers/planning.py:3658 — rollover (changed again in Task 3)
    set_year_status(new_py, "active")

# backend/app/seeds/seed_all.py:451 area
    set_year_status(py, "active")
```

- [ ] **Step 7: Run tests**

Run:
```bash
cd backend && alembic upgrade head && rm -f aafc_tms.db
python -m pytest tests/test_year_model.py tests/test_planning.py -q
```
Expected: PASS

> **Why no task implements "a draft is never a candidate unless deliberately
> targeted".** The spec requires it and nothing here codes it, which is correct
> rather than an omission: `set_year_status` writes `active_status = (status ==
> "active")`, so a draft has `active_status = False`, and `_year_for_date` in
> `training.py` already filters on `active_status`. Drafts are therefore excluded
> from parade-night year resolution for free during the whole compatibility
> window. When Task 8 drops the boolean, that filter must already have moved to
> `status == "active"` in Task 7 — which is why Task 8 is gated behind it.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/planning.py backend/app/services_year.py \
        backend/app/routers/planning.py backend/app/seeds/seed_all.py \
        backend/alembic/versions backend/tests/test_year_model.py
git commit -m "feat(year): add PlanningYear.status, dual-written with active_status"
```

---

### Task 3: Rollover creates a draft, not a second active year

**Files:**
- Modify: `backend/app/routers/planning.py:3631-3660` (`rollover_year`)
- Test: `backend/tests/test_year_model.py`

**Interfaces:**
- Consumes: `set_year_status` from Task 2.
- Produces: no new symbols. `POST /api/planning/years/{id}/rollover` now returns a year whose `status` is `"draft"`.

**Why this task exists:** `rollover_year` currently sets `active_status=True` on the new year, which puts the squadron into two-active-years the moment it is called, and names it `f"{py.name} → {target_year}"`. That is the mechanism that produced the six multi-active squadrons cleaned up in REM-156. Without this change the cleanup regenerates.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_year_model.py — append
from tests.conftest import login, next_test_year


def test_rollover_creates_a_draft_not_a_second_active_year(client):
    hdr = login(client, "ADMIN703")
    yr = next_test_year()
    src = client.post("/api/planning/years",
                      json={"year": yr, "name": f"{yr} Training Year"},
                      headers=hdr).json()["planning_year_id"]

    out = client.post(f"/api/planning/years/{src}/rollover",
                      json={"target_year": yr + 1}, headers=hdr)
    assert out.status_code == 200, out.text
    new_id = out.json()["planning_year_id"]

    rolled = client.get(f"/api/planning/years/{new_id}", headers=hdr).json()
    assert rolled["status"] == "draft"
    assert rolled["active_status"] is False

    # and the source year is untouched
    source = client.get(f"/api/planning/years/{src}", headers=hdr).json()
    assert source["status"] == "active"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m pytest tests/test_year_model.py -q -k rollover`
Expected: FAIL — `assert 'active' == 'draft'`

- [ ] **Step 3: Change rollover**

```python
# backend/app/routers/planning.py — in rollover_year, replacing active_status=True
    new_py = PlanningYear(
        id=str(uuid.uuid4()),
        unit_id=py.unit_id, wing_id=py.wing_id,
        year=target_year, name=new_name,
        created_by=p.user_id, created_at=utcnow(), updated_at=utcnow(),
    )
    # A rolled-over year is next year's PLAN, not a second current year. It
    # becomes active on 1 January, squadron-local, via services_year.
    set_year_status(new_py, "draft")
```

- [ ] **Step 4: Expose `status` on the year payloads**

Find `_year_out` in `backend/app/routers/planning.py` and add the field beside `active_status` — both are returned during the compatibility window:

```python
        "active_status": py.active_status,
        "status": py.status,
```

- [ ] **Step 5: Run tests**

Run: `cd backend && python -m pytest tests/test_year_model.py tests/test_planning.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/planning.py backend/tests/test_year_model.py
git commit -m "feat(year): rollover creates a draft rather than a second active year"
```

---

### Task 4: Lazy promotion on 1 January, squadron-local

**Files:**
- Modify: `backend/app/services_year.py`
- Create: `backend/tests/test_year_rollover.py`

**Interfaces:**
- Consumes: `squadron_today`, `set_year_status`.
- Produces: `rollover_date(py) -> datetime.date` and `resolve_active_year(db, squadron_id) -> PlanningYear | None`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_year_rollover.py
"""Lazy promotion. There is no scheduler: celery_app.py declares no
beat_schedule and Railway has no Redis, so dispatcher.py always runs
synchronously. Promotion therefore happens when the active year is resolved.
"""
import datetime as dt
from unittest.mock import patch

from app.database import SessionLocal
from app.models import PlanningYear, Squadron
from app.services_year import resolve_active_year, rollover_date, set_year_status


def _sqn(db):
    return db.query(Squadron).filter(Squadron.code == "703").first()


def test_rollover_date_is_1_january_of_the_drafts_own_year():
    py = PlanningYear(unit_id=None, wing_id=None, year=2031, name="d")
    assert rollover_date(py) == dt.date(2031, 1, 1)


def test_draft_is_not_promoted_before_its_rollover_date():
    db = SessionLocal()
    try:
        s = _sqn(db)
        draft = PlanningYear(unit_id=s.id, wing_id=s.wing_id, year=2041, name="2041")
        set_year_status(draft, "draft")
        db.add(draft); db.commit()
        with patch("app.services_year.squadron_today",
                   return_value=dt.date(2040, 12, 31)):
            resolve_active_year(db, s.id)
        db.refresh(draft)
        assert draft.status == "draft"
    finally:
        db.close()


def test_draft_is_promoted_on_the_day_and_the_old_year_is_archived():
    db = SessionLocal()
    try:
        s = _sqn(db)
        old = db.query(PlanningYear).filter(
            PlanningYear.unit_id == s.id, PlanningYear.status == "active").first()
        draft = PlanningYear(unit_id=s.id, wing_id=s.wing_id, year=2042, name="2042")
        set_year_status(draft, "draft")
        db.add(draft); db.commit()

        with patch("app.services_year.squadron_today",
                   return_value=dt.date(2042, 1, 1)):
            got = resolve_active_year(db, s.id)

        db.refresh(draft)
        assert got.id == draft.id
        assert draft.status == "active"
        if old is not None:
            db.refresh(old)
            assert old.status == "archived"
    finally:
        db.close()


def test_promotion_is_idempotent():
    """Called on every read, so it must be safe to call repeatedly."""
    db = SessionLocal()
    try:
        s = _sqn(db)
        with patch("app.services_year.squadron_today",
                   return_value=dt.date(2043, 6, 1)):
            a = resolve_active_year(db, s.id)
            b = resolve_active_year(db, s.id)
        assert a is not None and a.id == b.id
        actives = db.query(PlanningYear).filter(
            PlanningYear.unit_id == s.id, PlanningYear.status == "active").count()
        assert actives == 1
    finally:
        db.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest tests/test_year_rollover.py -q`
Expected: FAIL — `ImportError: cannot import name 'resolve_active_year'`

- [ ] **Step 3: Implement**

```python
# backend/app/services_year.py — append
import datetime as _dt


def rollover_date(py: PlanningYear) -> _dt.date:
    """1 January of the draft's own year value.

    Chosen over "the day after the outgoing year's last parade date" because it
    is predictable and does not change when someone edits a parade date. Note
    the spec records that a year's `year` number does not always describe the
    dates it contains; see the "year numbers lie" section.
    """
    return _dt.date(py.year, 1, 1)


def resolve_active_year(db: DBSession, squadron_id: str) -> PlanningYear | None:
    """The squadron's active year, promoting its draft first if the date says so.

    Mutates on a read, deliberately: there is no scheduler. Two concurrent
    callers can both see an unpromoted draft, so this commits inside one
    transaction and lets the one-active-year index (Task 6) fail the loser,
    which then re-reads. Do NOT convert this to check-then-write.
    """
    draft = (db.query(PlanningYear)
               .filter(PlanningYear.unit_id == squadron_id,
                       PlanningYear.status == "draft")
               .order_by(PlanningYear.year)
               .first())
    if draft is not None and squadron_today(db, squadron_id) >= rollover_date(draft):
        outgoing = (db.query(PlanningYear)
                      .filter(PlanningYear.unit_id == squadron_id,
                              PlanningYear.status == "active")
                      .all())
        for py in outgoing:
            set_year_status(py, "archived")
        set_year_status(draft, "active")
        db.commit()

    return (db.query(PlanningYear)
              .filter(PlanningYear.unit_id == squadron_id,
                      PlanningYear.status == "active")
              .first())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest tests/test_year_rollover.py -q`
Expected: PASS, 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services_year.py backend/tests/test_year_rollover.py
git commit -m "feat(year): lazy draft promotion on 1 January, squadron-local"
```

---

### Task 5: Tighten the invariant to one active year per squadron

**Files:**
- Modify: `backend/app/models/planning.py` (`__table_args__`)
- Create: `backend/alembic/versions/<rev>_one_active_year_per_squadron.py`
- Test: `backend/tests/test_year_model.py`

**Interfaces:**
- Consumes: `status` from Task 2.
- Produces: index `uq_planning_years_one_active_per_unit`.

**Precondition — already met.** REM-156 resolved production: 703, 721, 704 and 708 were consolidated, and 702 and TEST were reviewed and need no change because their second year becomes the draft. Verify before deploying rather than trusting this line.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_year_model.py — append
from sqlalchemy.exc import IntegrityError


def test_a_squadron_cannot_hold_two_active_years():
    db = SessionLocal()
    try:
        s = db.query(Squadron).filter(Squadron.code == "703").first()
        extra = PlanningYear(unit_id=s.id, wing_id=s.wing_id, year=2051, name="second")
        set_year_status(extra, "active")
        db.add(extra)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()


def test_a_draft_alongside_an_active_year_is_allowed():
    db = SessionLocal()
    try:
        s = db.query(Squadron).filter(Squadron.code == "703").first()
        draft = PlanningYear(unit_id=s.id, wing_id=s.wing_id, year=2052, name="draft")
        set_year_status(draft, "draft")
        db.add(draft)
        db.commit()          # must NOT raise
        db.delete(draft); db.commit()
    finally:
        db.close()
```

- [ ] **Step 2: Run tests to verify the first fails**

Run: `cd backend && python -m pytest tests/test_year_model.py -q -k active_years`
Expected: FAIL — no IntegrityError raised, because today's index is on `(unit_id, year)`

- [ ] **Step 3: Replace the index**

```python
# backend/app/models/planning.py — replace the existing Index in __table_args__
    __table_args__ = (
        # One ACTIVE year per squadron. Supersedes uq_planning_years_unit_year_active,
        # which was unique on (unit_id, year) and so permitted an active 2026 AND an
        # active 2027 — exactly how six squadrons reached multi-active state (REM-156).
        # unit_id IS NULL for wing/national years and NULLs are distinct in both
        # SQLite and PostgreSQL, so those rows stay unconstrained. Correct: they are
        # not squadron-scoped.
        Index(
            "uq_planning_years_one_active_per_unit",
            "unit_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
    )
```

- [ ] **Step 4: Write the migration**

```python
# backend/alembic/versions/<rev>_one_active_year_per_squadron.py
"""one active planning year per squadron

Revision ID: <rev>
Revises: <Task 2's rev>
"""
from alembic import op
import sqlalchemy as sa

revision = "<rev>"
down_revision = "<Task 2's rev>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Fail loudly rather than silently dropping data if any squadron is still
    # multi-active. REM-156 resolved production on 2026-08-28, but this must not
    # depend on that having stayed true.
    conn = op.get_bind()
    bad = conn.execute(sa.text(
        "SELECT count(*) FROM (SELECT unit_id FROM planning_years "
        "WHERE unit_id IS NOT NULL AND status = 'active' "
        "GROUP BY unit_id HAVING count(*) > 1) x")).scalar()
    if bad:
        raise RuntimeError(
            f"{bad} squadron(s) still hold more than one ACTIVE planning year. "
            f"Resolve them before applying this migration (see REM-156)."
        )
    op.drop_index("uq_planning_years_unit_year_active", table_name="planning_years")
    op.create_index("uq_planning_years_one_active_per_unit", "planning_years",
                    ["unit_id"], unique=True,
                    sqlite_where=sa.text("status = 'active'"),
                    postgresql_where=sa.text("status = 'active'"))


def downgrade() -> None:
    op.drop_index("uq_planning_years_one_active_per_unit", table_name="planning_years")
    op.create_index("uq_planning_years_unit_year_active", "planning_years",
                    ["unit_id", "year"], unique=True,
                    sqlite_where=sa.text("active_status = 1"),
                    postgresql_where=sa.text("active_status = true"))
```

- [ ] **Step 5: Run tests**

Run:
```bash
cd backend && alembic upgrade head && rm -f aafc_tms.db
python -m pytest tests/test_year_model.py tests/test_year_rollover.py -q
```
Expected: PASS

- [ ] **Step 6: Rehearse the migration against a production-shaped database**

Never against production. Restore a dump into a disposable PostgreSQL and run `alembic upgrade head`, confirming the guard passes rather than raising.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/planning.py backend/alembic/versions \
        backend/tests/test_year_model.py
git commit -m "feat(year): enforce one active planning year per squadron"
```

---

### Task 6: Route year resolution through the helper, and tell the user when it changes

**Files:**
- Modify: `backend/app/routers/planning.py` (`GET /years` and anywhere a squadron's current year is chosen)
- Modify: `connected-frontend/index.html` (year selector)
- Modify: `frontend/src/` (Planning Workspace year display)
- Test: `frontend/e2e-connected/year-rollover-notice.spec.ts`

**Interfaces:**
- Consumes: `resolve_active_year` from Task 4.
- Produces: `GET /api/planning/years` returns `status` on each year; the frontends compare the active year id against the one they loaded with.

**Why the notice is required, not optional.** The spec records that automatic promotion changing the year under a user mid-session is the same class of surprise as the defect this work removes. Both frontends already display the year; they must notice it changed and say so rather than swapping the data silently.

- [ ] **Step 1: Write the failing e2e test**

```typescript
// frontend/e2e-connected/year-rollover-notice.spec.ts
import { test, expect, Page } from "@playwright/test";
import { resetBackendRateLimits } from "../e2e-rate-limit-reset";

const LOCAL_API_BASE = process.env.CONNECTED_LOCAL_API_BASE;
declare const S: any;
declare function _onActiveYearChanged(newId: string): void;

test.beforeAll(async () => {
  await resetBackendRateLimits(
    process.env.E2E_BACKEND_BASE_URL || LOCAL_API_BASE || "http://localhost:8000");
});

test("YEAR-ROLL-01: a changed active year is announced, not swapped silently", async ({ page }) => {
  if (LOCAL_API_BASE) {
    await page.addInitScript((b) => { (window as any).AAFC_API_BASE = b; }, LOCAL_API_BASE);
  }
  await page.goto("/");
  await page.locator("#auth-type").selectOption("squadron");
  await page.locator("#auth-wing-select").selectOption("7WG");
  await page.locator("#auth-sqn-select").selectOption("703");
  await page.locator("#auth-role").selectOption("sqn_admin");
  await page.locator("#auth-continue-btn").click();
  await page.locator("#auth-code").fill("ADMIN703");
  await page.locator("#auth-btn").click();
  await expect(page.locator("#app")).toBeVisible({ timeout: 15000 });

  await page.evaluate(() => _onActiveYearChanged("some-other-year-id"));
  await expect(page.locator("#year-changed-notice")).toBeVisible();
  await expect(page.locator("#year-changed-notice")).toContainText("training year");
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd frontend && npx playwright test --config=playwright.connected.config.ts year-rollover-notice`
Expected: FAIL — `_onActiveYearChanged is not a function`

- [ ] **Step 3: Add the notice to connected-frontend**

```html
<!-- connected-frontend/index.html — inside the topbar, before the page container -->
<div id="year-changed-notice" class="alert a-warn no-print" style="display:none">
  The training year has rolled over since this page was opened. Reload to see the
  current year. <button class="btn btn-xs" onclick="location.reload()">Reload</button>
</div>
```

```javascript
// connected-frontend/index.html — beside the year selector logic
// Promotion is lazy and happens on the server during a read, so the active year
// can change while a page is open. Announce it; never swap the data underneath.
function _onActiveYearChanged(newId){
  if(!newId || newId===S.activeYearId) return;
  const el=document.getElementById('year-changed-notice');
  if(el) el.style.display='';
}
```

- [ ] **Step 4: Call it wherever years are loaded**

```javascript
  const years = await api('/api/planning/years');
  const active = (years||[]).find(y=>y.status==='active');
  if(active) _onActiveYearChanged(active.planning_year_id);
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd frontend && npx playwright test --config=playwright.connected.config.ts year-rollover-notice`
Expected: PASS

- [ ] **Step 6: Mirror the notice in Planning Workspace**

```tsx
// frontend/src/components/YearRolloverNotice.tsx
import { useEffect, useState } from "react";

/** The server promotes a draft lazily during a read, so the active year can
 *  change while this tab is open. Announce it; never swap the data underneath. */
export function YearRolloverNotice({ activeYearId }: { activeYearId: string | null }) {
  const [loadedWith, setLoadedWith] = useState<string | null>(null);
  useEffect(() => { if (loadedWith === null && activeYearId) setLoadedWith(activeYearId); },
            [activeYearId, loadedWith]);
  if (!activeYearId || loadedWith === null || activeYearId === loadedWith) return null;
  return (
    <div className="alert a-warn" role="status">
      The training year has rolled over since this page was opened.{" "}
      <button onClick={() => window.location.reload()}>Reload</button>
    </div>
  );
}
```

Render it in the planning shell, passing the id of the year whose `status` is
`"active"` from the years query.

- [ ] **Step 7: Commit**

```bash
git add connected-frontend/index.html frontend/src \
        frontend/e2e-connected/year-rollover-notice.spec.ts
git commit -m "feat(year): announce an active-year rollover instead of swapping silently"
```

---

### Task 7: Migrate backend readers from `active_status` to `status`

**Files:**
- Modify: `backend/app/routers/planning.py`, `backend/app/routers/training.py`, and the other backend modules that filter on `PlanningYear.active_status`
- Test: existing suite

**Interfaces:** no new symbols.

**Scale — read this before starting.** `active_status` has **296** references across the repo: 156 in `backend/app`, 63 in tests, 31 in migrations, 24 in connected-frontend, 22 in the React app. Most belong to `Squadron`, `Wing` or `User` and **must not be touched** — only `PlanningYear` filters change here. Migrations are historical and are never edited.

- [ ] **Step 1: Enumerate the real work**

Run:
```bash
cd backend && grep -rn "PlanningYear.active_status" app/ | tee /tmp/year_readers.txt | wc -l
```
Every line in that file is in scope; nothing else is.

- [ ] **Step 2: Replace each filter**

```python
# before
    .filter(PlanningYear.active_status)
# after
    .filter(PlanningYear.status == "active")
```

For a query that means "not archived", which now includes drafts, be explicit:

```python
    .filter(PlanningYear.status.in_(("active", "draft")))
```

- [ ] **Step 3: Run the full suite after each file**

Run: `cd backend && python -m pytest tests/ -q`
Expected: no new failures. Commit per file so a regression bisects to one change.

- [ ] **Step 4: Confirm nothing reads the boolean for planning years**

Run: `cd backend && grep -rn "PlanningYear.active_status" app/ | grep -v "set_year_status" | wc -l`
Expected: `0`

- [ ] **Step 5: Commit**

```bash
git commit -m "refactor(year): read PlanningYear.status instead of active_status"
```

---

### Task 8: Drop `active_status` — DEFERRED, do not run with the rest

**Files:**
- Modify: `backend/app/models/planning.py`, `backend/app/services_year.py`
- Create: `backend/alembic/versions/<rev>_drop_planning_year_active_status.py`

**Do not start this task until all of the following are true.** Both frontends have shipped with `status`, been verified in a browser, and run in production for a release; and `grep -rn "active_status" connected-frontend/ frontend/src/` returns nothing referencing a planning year. Dropping the column while an older frontend is still deployed breaks that frontend, and the two are deployed independently.

- [ ] **Step 1: Re-verify the preconditions above and record the evidence**
- [ ] **Step 2: Remove `active_status` from the model and the dual-write in `set_year_status`**
- [ ] **Step 3: Write the migration dropping the column, with a `downgrade` that re-adds and backfills it from `status`**
- [ ] **Step 4: Rehearse forward and backward against a disposable PostgreSQL restored from a production dump**
- [ ] **Step 5: Run the full suite**
- [ ] **Step 6: Commit**

---

## Deployment sequence

1. Tasks 1–4 → deploy → verify staging. Nothing reads `status` in anger yet; drafts exist but no squadron has one.
2. Task 7 → deploy → verify. Backend now reads `status`.
3. Task 5 (the index) → **verify no squadron is multi-active first** → deploy.
4. Task 6 → deploy both frontends → verify the notice in a browser.
5. Task 8 only after a release has passed.

Production is behind on migrations; catching it up is a prerequisite for any of this and is not part of this plan.
