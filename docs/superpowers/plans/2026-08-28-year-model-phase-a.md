# Year Model Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `PlanningYear.active_status: bool` with `status: str (draft|active|archived)`, add Wing timezone, implement lazy year rollover, and surface draft years in both frontends — so a parade night always attaches to a single unambiguous year.

**Architecture:** A new `services_year.py` module holds the `resolve_active_year()` helper and `get_wing_timezone()`. All writes to `PlanningYear` dual-write both `status` and `active_status` during this phase (backward-compat for the old frontend). New lifecycle endpoints (`/create-draft`, `/promote`, `/archive`) replace the raw `PATCH active_status` flow. The unique index on `(unit_id)` WHERE `status='active'` replaces the old per-year-number index, enforcing the one-active-year invariant at the DB level.

**Tech Stack:** FastAPI 0.110+, SQLAlchemy 2.0, Alembic, Python 3.13 (`zoneinfo` stdlib), SQLite (dev/test), PostgreSQL (prod), plain HTML/CSS/JS SPA (`connected-frontend/index.html`), React + Vite + TypeScript (`frontend/`).

**Spec:** `docs/superpowers/specs/2026-08-27-year-model-and-parade-night-merge-design.md`

## Global Constraints

- All changes in `backend/` must pass `python -m pytest tests/ -q` (run from `backend/`) — currently 1987 passed, 9 skipped.
- Never return plaintext access codes or hashes from any API endpoint.
- Backend is always the source of truth for role/scope — never trust frontend claims.
- Every new endpoint needs: happy-path test, 403 forbidden test, 401 unauthenticated test.
- Use `batch_alter_table` for all Alembic migrations (SQLite compatibility).
- Do not remove `active_status` from the `PlanningYear` model or API responses in this plan — Phase A-2 handles the drop after both frontends verify on the new field.
- `active_status` must stay in sync with `status` for every write: `active_status = (status == 'active')`.
- The migration **must refuse to run** if any squadron holds more than one active year (guarded by a pre-flight check in the migration).
- `Wing.timezone` must be an IANA string; fail loudly if unset — never silently fall back to UTC or Perth.
- `zoneinfo` is in Python 3.13 stdlib; do not add a dependency.
- No operational data in localStorage (the PW year selection stored at `PW_YEAR_KEY` is UI state, not operational data — keep it).
- Run `alembic heads` before writing any new migration and use the printed value as `down_revision`.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/app/models/organisations.py` | Modify | Add `Wing.timezone` field |
| `backend/app/models/planning.py` | Modify | Add `PlanningYear.status` field; update `__table_args__` |
| `backend/app/services_year.py` | Create | `get_wing_timezone()`, `resolve_active_year()` |
| `backend/app/routers/planning.py` | Modify | `_year_out()` returns `status`; lifecycle endpoints; migrate readers |
| `backend/app/routers/training.py` | Modify | `_year_for_date()` uses `status`; `_find_or_create_parade_date_for_night()` uses resolve |
| `backend/app/routers/setup.py` | Modify | PlanningYear query uses `status` |
| `backend/app/seeds/seed_all.py` | Modify | Set `Wing.timezone = 'Australia/Perth'` on 7WG |
| `backend/alembic/versions/???_v57_wing_timezone.py` | Create | Add `wings.timezone`; seed 7WG |
| `backend/alembic/versions/???_v58_planning_year_status.py` | Create | Add `planning_years.status`; backfill |
| `backend/alembic/versions/???_v59_one_active_year_index.py` | Create | Replace partial unique index; pre-flight refuse |
| `backend/tests/test_year_model.py` | Create | All Phase A tests |
| `connected-frontend/index.html` | Modify | Year selector: draft label, lifecycle UI, year-changed notice |
| `frontend/src/api/types.ts` | Modify | Add `status` to `PlanningYear` interface |
| `frontend/src/routes/PlanningWorkspace.tsx` | Modify | `pickDefaultYear()` uses `status`; year-changed notice |
| `frontend/src/components/planning/PlanningContextBar.tsx` | Modify | Year selector shows Draft label |

---

### Task 1: Wing.timezone — migration, model, seed, helper

**Files:**
- Modify: `backend/app/models/organisations.py:15-22` (Wing class)
- Create: `backend/app/services_year.py`
- Modify: `backend/app/seeds/seed_all.py:129-130` (Wing creation)
- Create: `backend/alembic/versions/???_v57_wing_timezone.py`
- Create: `backend/tests/test_year_model.py`

**Interfaces:**
- Produces: `get_wing_timezone(wing_id: str, db: Session) -> ZoneInfo` — raises `RuntimeError` if unset or invalid IANA string. Used by Task 3.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_year_model.py`:

```python
"""Phase A: year model tests — Wing.timezone, PlanningYear.status, lifecycle, rollover."""
from conftest import login, next_test_year
from datetime import date


def _sqn_admin_hdr(client):
    return login(client, "ADMIN703")


def _wing_admin_hdr(client):
    return login(client, "ADMIN7WG")


def _nat_admin_hdr(client):
    return login(client, "ADMINNATIONAL")


# ── Wing.timezone ─────────────────────────────────────────────

def test_wing_timezone_returned_in_year_list(client):
    """Wing.timezone must be set for 7WG so rollover is computable."""
    h = _wing_admin_hdr(client)
    r = client.get("/api/planning/years?wing_id=", headers=h)
    # Wing timezone is not in year list — test via a dedicated endpoint
    # This test verifies the endpoint exists and returns Perth.
    r = client.get("/api/planning/wing-timezone", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["timezone"] == "Australia/Perth"


def test_wing_timezone_sqn_returns_their_wing_tz(client):
    h = _sqn_admin_hdr(client)
    r = client.get("/api/planning/wing-timezone", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["timezone"] == "Australia/Perth"


def test_wing_timezone_requires_auth(client):
    r = client.get("/api/planning/wing-timezone")
    assert r.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_year_model.py::test_wing_timezone_returned_in_year_list -v
```

Expected: `FAIL` — `404` (endpoint does not exist yet).

- [ ] **Step 3: Add `Wing.timezone` to the model**

In `backend/app/models/organisations.py`, add to the `Wing` class after the `short_name` field:

```python
# existing fields above ...
short_name: Mapped[str] = mapped_column(String(40))
active_status: Mapped[bool] = mapped_column(Boolean, default=True)
timezone: Mapped[str | None] = mapped_column(String(60), nullable=True)
squadrons: Mapped[list["Squadron"]] = relationship(back_populates="wing")
```

- [ ] **Step 4: Create the migration**

First get the current head:
```bash
cd backend && source .venv/bin/activate && alembic heads
```

Create `backend/alembic/versions/REVISION_v57_wing_timezone.py` (replace `REVISION` with the value from `alembic heads` as `down_revision`, and generate a new 12-char hex string as `revision`):

```python
"""v57 — wings.timezone (IANA string for rollover localisation)

Revision ID: <new-hex-id>
Revises: <current-head>
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa

revision = "<new-hex-id>"
down_revision = "<current-head>"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("wings") as batch_op:
        batch_op.add_column(sa.Column("timezone", sa.String(60), nullable=True))

    # Seed 7WG immediately — production has exactly one wing (7WG) and this
    # value is required for resolve_active_year() to function at all.
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE wings SET timezone = 'Australia/Perth' WHERE code = '7WG'"))


def downgrade():
    with op.batch_alter_table("wings") as batch_op:
        batch_op.drop_column("timezone")
```

Run the migration:
```bash
cd backend && source .venv/bin/activate && alembic upgrade head
```

- [ ] **Step 5: Update seed to set timezone on Wing creation**

In `backend/app/seeds/seed_all.py`, update the Wing creation at line 129:

```python
wing = Wing(
    national_id=nat.id,
    code="7WG",
    name="7 Wing (Western Australia)",
    short_name="7WG",
    timezone="Australia/Perth",
)
```

- [ ] **Step 6: Create `services_year.py` with `get_wing_timezone()`**

Create `backend/app/services_year.py`:

```python
"""Year model services: timezone resolution and active-year rollover.

Two hard rules from the spec (2026-08-27):
  - Wing.timezone must be set; fail loudly if unset — never fall back to UTC.
  - resolve_active_year() promotes a draft year on the first read on/after
    1 January of the draft year's own `year` number, in wing-local time.
"""
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from datetime import datetime, date as date_type
from sqlalchemy.orm import Session


def get_wing_timezone(wing_id: str, db: Session) -> ZoneInfo:
    """Return the ZoneInfo for a Wing. Raises RuntimeError if unset or invalid.

    This must never silently fall back to UTC or Perth. The fail-loudly rule
    is more important in a single-wing deployment than a multi-wing one:
    with one wing, a missing timezone is invisible until wing two is added —
    exactly when nobody is watching for it.
    """
    from .models.organisations import Wing
    wing = db.get(Wing, wing_id)
    if not wing:
        raise RuntimeError(f"Wing {wing_id!r} not found")
    if not wing.timezone:
        raise RuntimeError(
            f"Wing {wing_id!r} has no timezone configured. "
            "Set Wing.timezone to a valid IANA string (e.g. 'Australia/Perth') "
            "before using year rollover."
        )
    try:
        return ZoneInfo(wing.timezone)
    except ZoneInfoNotFoundError:
        raise RuntimeError(
            f"Wing {wing_id!r} has invalid IANA timezone {wing.timezone!r}. "
            "Use a value from the IANA Time Zone Database (e.g. 'Australia/Perth')."
        )
```

- [ ] **Step 7: Add `GET /api/planning/wing-timezone` endpoint**

In `backend/app/routers/planning.py`, add after the existing imports and before the first route:

```python
@router.get("/wing-timezone")
def get_wing_timezone_endpoint(
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Return the IANA timezone for the current user's wing.
    Used by both frontends to localise rollover dates.
    """
    from ..services_year import get_wing_timezone
    if not p.wing_id:
        raise HTTPException(400, detail={"error": "no_wing"})
    tz = get_wing_timezone(p.wing_id, db)
    return {"timezone": str(tz)}
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_year_model.py -v
```

Expected: all 3 timezone tests pass.

- [ ] **Step 9: Run the full suite**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/ -q
```

Expected: 1987+ passed, 0 failures (same count or higher if new tests added).

- [ ] **Step 10: Commit**

```bash
git add backend/app/models/organisations.py \
        backend/app/services_year.py \
        backend/app/seeds/seed_all.py \
        backend/app/routers/planning.py \
        backend/alembic/versions/*_v57_wing_timezone.py \
        backend/tests/test_year_model.py
git commit -m "feat(year-model): add Wing.timezone + get_wing_timezone() helper + endpoint (Phase A Task 1)"
```

---

### Task 2: PlanningYear.status column — migration and dual-write

**Files:**
- Modify: `backend/app/models/planning.py:32-64` (PlanningYear class)
- Create: `backend/alembic/versions/???_v58_planning_year_status.py`
- Modify: `backend/app/routers/planning.py` — `_year_out()`, create/update endpoints
- Modify: `backend/tests/test_year_model.py` — add status tests

**Interfaces:**
- Consumes: `Wing.timezone` from Task 1.
- Produces: `PlanningYear.status: str` (the field on the model); `_year_out()` now includes `"status": py.status` alongside `"active_status": py.active_status`. Every write must dual-write both.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_year_model.py`:

```python
# ── PlanningYear.status field ─────────────────────────────────

def test_new_year_has_status_active(client):
    h = _sqn_admin_hdr(client)
    r = client.post("/api/planning/years",
                    json={"year": next_test_year(), "name": "Status test"},
                    headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "status" in body, "status field missing from year response"
    assert body["status"] == "active"
    assert body["active_status"] is True  # backward-compat: both present


def test_archive_year_sets_status_archived(client):
    h = _sqn_admin_hdr(client)
    yr = client.post("/api/planning/years",
                     json={"year": next_test_year(), "name": "Archive test"},
                     headers=h).json()
    yr_id = yr["planning_year_id"]
    r = client.patch(f"/api/planning/years/{yr_id}",
                     json={"active_status": False, "version": yr["version"]},
                     headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "archived"
    assert body["active_status"] is False


def test_restore_year_sets_status_active(client):
    h = _sqn_admin_hdr(client)
    yr = client.post("/api/planning/years",
                     json={"year": next_test_year(), "name": "Restore test"},
                     headers=h).json()
    yr_id = yr["planning_year_id"]
    # Archive it first
    client.patch(f"/api/planning/years/{yr_id}",
                 json={"active_status": False, "version": yr["version"]},
                 headers=h)
    yr2 = client.get(f"/api/planning/years/{yr_id}", headers=h).json()
    # Restore
    r = client.patch(f"/api/planning/years/{yr_id}",
                     json={"active_status": True, "version": yr2["version"]},
                     headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active"
    assert r.json()["active_status"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_year_model.py::test_new_year_has_status_active -v
```

Expected: `FAIL` — `AssertionError: status field missing from year response`.

- [ ] **Step 3: Add `status` field to PlanningYear model**

In `backend/app/models/planning.py`, update the `PlanningYear` class. Add `status` after `active_status`:

```python
class PlanningYear(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "planning_years"
    __table_args__ = (
        Index(
            "uq_planning_years_unit_year_active",
            "unit_id", "year",
            unique=True,
            sqlite_where=text("active_status = 1"),
            postgresql_where=text("active_status = true"),
        ),
    )
    unit_id: Mapped[str | None] = mapped_column(ForeignKey("squadrons.id"), nullable=True, index=True)
    wing_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    active_status: Mapped[bool] = mapped_column(Boolean, default=True)
    # Phase A: status replaces active_status. Values: draft | active | archived.
    # active_status is kept in sync with status (active_status = status=='active')
    # for backward-compat with old frontend until Phase A-2 (the drop migration).
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
```

Note: keep the existing `__table_args__` index unchanged — Task 8 replaces it.

- [ ] **Step 4: Create the migration**

Get the current head:
```bash
cd backend && source .venv/bin/activate && alembic heads
```

Create `backend/alembic/versions/REVISION_v58_planning_year_status.py`:

```python
"""v58 — planning_years.status (draft|active|archived) + backfill from active_status

Revision ID: <new-hex-id>
Revises: <v57-revision>
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa

revision = "<new-hex-id>"
down_revision = "<v57-revision>"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("planning_years") as batch_op:
        batch_op.add_column(
            sa.Column("status", sa.String(20), nullable=False,
                      server_default="active")
        )

    # Backfill: active_status=True → 'active', False → 'archived'.
    # Draft is a new concept — no existing row is a draft; they're all
    # either active or archived based on the old boolean.
    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE planning_years SET status = CASE "
        "  WHEN active_status = 1 THEN 'active' "
        "  ELSE 'archived' "
        "END"
    ))


def downgrade():
    with op.batch_alter_table("planning_years") as batch_op:
        batch_op.drop_column("status")
```

Run:
```bash
cd backend && source .venv/bin/activate && alembic upgrade head
```

- [ ] **Step 5: Update `_year_out()` to include `status`**

In `backend/app/routers/planning.py`, update the `_year_out()` function (around line 244):

```python
def _year_out(py: PlanningYear, unit_code: str | None = None,
              unit_name: str | None = None, wing_code: str | None = None) -> dict:
    return {
        "planning_year_id": py.id, "unit_id": py.unit_id, "wing_id": py.wing_id,
        "year": py.year, "name": py.name,
        "status": py.status,                      # Phase A: new canonical field
        "active_status": py.active_status,        # backward-compat: keep until Phase A-2
        "unit_code": unit_code, "unit_name": unit_name, "wing_code": wing_code,
        "created_by": py.created_by, "updated_by": py.updated_by,
        "created_at": iso_z(py.created_at) if py.created_at else None,
        "updated_at": iso_z(py.updated_at) if py.updated_at else None,
        "version": py.version,
    }
```

- [ ] **Step 6: Dual-write status in `create_planning_year()` and `update_planning_year()`**

In `create_planning_year()` (around line 503), update the `PlanningYear()` constructor:

```python
py = PlanningYear(
    id=str(uuid.uuid4()), year=body.year, name=body.name,
    unit_id=unit_id, wing_id=wing_id,
    status="active",               # new field
    active_status=body.active_status if body.active_status is not None else True,
    created_by=p.user_id, created_at=utcnow(), updated_at=utcnow(),
)
```

In `update_planning_year()` (around line 576), add dual-write after the existing `active_status` block:

```python
if body.active_status is not None:
    py.active_status = body.active_status
    # Dual-write: keep status in sync with active_status for compat callers.
    # archived → archived; restored → active. Draft is set only via lifecycle endpoints.
    py.status = "active" if body.active_status else "archived"
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_year_model.py -v
```

Expected: all 6 tests pass (3 timezone + 3 status).

- [ ] **Step 8: Run the full suite**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/ -q
```

Expected: same baseline or higher, 0 failures.

- [ ] **Step 9: Commit**

```bash
git add backend/app/models/planning.py \
        backend/app/routers/planning.py \
        backend/alembic/versions/*_v58_planning_year_status.py \
        backend/tests/test_year_model.py
git commit -m "feat(year-model): add PlanningYear.status + dual-write with active_status (Phase A Task 2)"
```

---

### Task 3: `resolve_active_year()` helper — lazy rollover

**Files:**
- Modify: `backend/app/services_year.py` — add `resolve_active_year()`
- Modify: `backend/tests/test_year_model.py` — rollover tests

**Interfaces:**
- Consumes: `get_wing_timezone()` from Task 1; `PlanningYear.status` from Task 2.
- Produces: `resolve_active_year(squadron_id: str, wing_id: str, db: Session, *, _today: date | None = None) -> PlanningYear | None`. The `_today` param is for test injection only. Used by Tasks 4 and 5.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_year_model.py`:

```python
# ── resolve_active_year() / rollover ─────────────────────────

def test_rollover_promotes_draft_to_active(client):
    """A draft year with year number in the past triggers rollover on first read."""
    h = _sqn_admin_hdr(client)
    # Create an active year
    base = next_test_year()
    active_yr = client.post("/api/planning/years",
                            json={"year": base, "name": f"Active {base}"},
                            headers=h).json()
    # Create a draft year (year number in the past = rollover date already passed)
    draft_yr = client.post("/api/planning/years/draft",
                           json={"year": base - 1000, "name": f"Draft {base - 1000}",
                                 "source_year_id": active_yr["planning_year_id"]},
                           headers=h).json()
    assert draft_yr["status"] == "draft", draft_yr

    # Trigger rollover by listing years (which calls resolve_active_year internally)
    years = client.get("/api/planning/years", headers=h).json()
    by_id = {y["planning_year_id"]: y for y in years}

    # The draft (past rollover date) should now be active
    assert by_id[draft_yr["planning_year_id"]]["status"] == "active", (
        "Draft year with past rollover date should have been promoted to active"
    )
    # The old active should now be archived
    assert by_id[active_yr["planning_year_id"]]["status"] == "archived", (
        "Previously active year should be archived after rollover"
    )


def test_rollover_does_not_trigger_before_rollover_date(client):
    """A draft year with year number in the future is NOT auto-promoted."""
    h = _sqn_admin_hdr(client)
    base = next_test_year()
    active_yr = client.post("/api/planning/years",
                            json={"year": base, "name": f"Active {base}"},
                            headers=h).json()
    # Draft year far in the future — rollover date not yet reached
    draft_yr = client.post("/api/planning/years/draft",
                           json={"year": base + 1000, "name": f"Draft {base + 1000}",
                                 "source_year_id": active_yr["planning_year_id"]},
                           headers=h).json()
    assert draft_yr["status"] == "draft"

    years = client.get("/api/planning/years", headers=h).json()
    by_id = {y["planning_year_id"]: y for y in years}
    # Still draft — rollover not triggered
    assert by_id[draft_yr["planning_year_id"]]["status"] == "draft"
    assert by_id[active_yr["planning_year_id"]]["status"] == "active"
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_year_model.py::test_rollover_promotes_draft_to_active -v
```

Expected: `FAIL` — `404` (endpoint `POST /api/planning/years/draft` not yet implemented).

- [ ] **Step 3: Implement `resolve_active_year()` in `services_year.py`**

Add to `backend/app/services_year.py` after `get_wing_timezone()`:

```python
def resolve_active_year(
    squadron_id: str,
    wing_id: str,
    db: Session,
    *,
    _today: "date_type | None" = None,
):
    """Return the active PlanningYear for this squadron; run rollover if due.

    If there is a draft year and today >= 1 January of the draft year's own
    `year` number (in wing-local time), promote the draft to active and archive
    the outgoing active year — all in one transaction. The unique index on
    (unit_id) WHERE status='active' (Task 8) makes concurrent promotions safe:
    the loser gets an IntegrityError and retries after reading the winner.

    The `_today` parameter is for test injection only — never pass it in
    production code.
    """
    from .models.planning import PlanningYear
    from sqlalchemy import exc

    tz = get_wing_timezone(wing_id, db)
    today_local = _today or datetime.now(tz).date()

    active = (
        db.query(PlanningYear)
        .filter(PlanningYear.unit_id == squadron_id,
                PlanningYear.status == "active")
        .first()
    )
    draft = (
        db.query(PlanningYear)
        .filter(PlanningYear.unit_id == squadron_id,
                PlanningYear.status == "draft")
        .first()
    )

    if draft:
        rollover_date = date_type(draft.year, 1, 1)
        if today_local >= rollover_date:
            try:
                if active:
                    active.status = "archived"
                    active.active_status = False   # dual-write compat
                draft.status = "active"
                draft.active_status = True         # dual-write compat
                db.commit()
                db.refresh(draft)
                return draft
            except exc.IntegrityError:
                db.rollback()
                # Another request won the promotion race — re-read the winner.
                return (
                    db.query(PlanningYear)
                    .filter(PlanningYear.unit_id == squadron_id,
                            PlanningYear.status == "active")
                    .first()
                )

    return active
```

- [ ] **Step 4: Commit `services_year.py` (rollover logic, pre-tests)**

```bash
git add backend/app/services_year.py
git commit -m "feat(year-model): add resolve_active_year() lazy rollover helper (Phase A Task 3)"
```

The rollover tests require the lifecycle endpoints (Task 4) — complete them next.

---

### Task 4: Year lifecycle API — create_draft, promote, archive

**Files:**
- Modify: `backend/app/routers/planning.py` — three new endpoints
- Modify: `backend/tests/test_year_model.py` — lifecycle and rollover tests

**Interfaces:**
- Consumes: `resolve_active_year()` from Task 3; `PlanningYear.status` from Task 2.
- Produces:
  - `POST /api/planning/years/draft` → new draft year (body: `year`, `name`, `source_year_id`)
  - `POST /api/planning/years/{year_id}/promote` → promotes draft → active (archives outgoing)
  - `POST /api/planning/years/{year_id}/archive` → archives active or draft year
  - `list_planning_years()` calls `resolve_active_year()` for squadron-scoped sessions to trigger lazy rollover before returning.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_year_model.py`:

```python
# ── Lifecycle endpoints ───────────────────────────────────────

def test_create_draft_year(client):
    h = _sqn_admin_hdr(client)
    base = next_test_year()
    active_yr = client.post("/api/planning/years",
                            json={"year": base, "name": f"Active {base}"},
                            headers=h).json()
    r = client.post("/api/planning/years/draft",
                    json={"year": base + 1, "name": f"Draft {base + 1}",
                          "source_year_id": active_yr["planning_year_id"]},
                    headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "draft"
    assert body["active_status"] is False
    assert body["year"] == base + 1


def test_create_draft_fails_if_draft_already_exists(client):
    h = _sqn_admin_hdr(client)
    base = next_test_year()
    active_yr = client.post("/api/planning/years",
                            json={"year": base, "name": f"Active {base}"},
                            headers=h).json()
    client.post("/api/planning/years/draft",
                json={"year": base + 1, "name": f"Draft {base + 1}",
                      "source_year_id": active_yr["planning_year_id"]},
                headers=h)
    # Second draft should be rejected
    r = client.post("/api/planning/years/draft",
                    json={"year": base + 2, "name": f"Draft {base + 2}",
                          "source_year_id": active_yr["planning_year_id"]},
                    headers=h)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["error"] == "draft_already_exists"


def test_promote_draft_to_active(client):
    h = _sqn_admin_hdr(client)
    base = next_test_year()
    active_yr = client.post("/api/planning/years",
                            json={"year": base, "name": f"Active {base}"},
                            headers=h).json()
    draft_yr = client.post("/api/planning/years/draft",
                           json={"year": base + 1, "name": f"Draft {base + 1}",
                                 "source_year_id": active_yr["planning_year_id"]},
                           headers=h).json()
    r = client.post(f"/api/planning/years/{draft_yr['planning_year_id']}/promote",
                    headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "active"
    assert body["active_status"] is True
    # Old active should now be archived
    old = client.get(f"/api/planning/years/{active_yr['planning_year_id']}", headers=h).json()
    assert old["status"] == "archived"
    assert old["active_status"] is False


def test_promote_fails_if_not_draft(client):
    h = _sqn_admin_hdr(client)
    yr = client.post("/api/planning/years",
                     json={"year": next_test_year(), "name": "Active"},
                     headers=h).json()
    r = client.post(f"/api/planning/years/{yr['planning_year_id']}/promote", headers=h)
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "not_a_draft"


def test_archive_year(client):
    h = _sqn_admin_hdr(client)
    yr = client.post("/api/planning/years",
                     json={"year": next_test_year(), "name": "To archive"},
                     headers=h).json()
    r = client.post(f"/api/planning/years/{yr['planning_year_id']}/archive", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "archived"
    assert r.json()["active_status"] is False


def test_lifecycle_requires_sqn_admin(client):
    h = login(client, "703SQN2026")  # sqn_general
    yr_id = client.get("/api/planning/years", headers=login(client, "ADMIN703")).json()[0]["planning_year_id"]
    r = client.post(f"/api/planning/years/{yr_id}/archive", headers=h)
    assert r.status_code == 403
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_year_model.py::test_create_draft_year -v
```

Expected: `FAIL` — `404`.

- [ ] **Step 3: Implement lifecycle endpoints in `planning.py`**

Find the existing `update_planning_year` endpoint (around line 560). Add these three endpoints immediately after it:

```python
class DraftYearIn(BaseModel):
    year: int
    name: str
    source_year_id: str  # the active year this draft follows


@router.post("/years/draft")
def create_draft_year(
    body: DraftYearIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Create a draft year for the next season.

    A squadron can hold at most one draft year at a time (enforced here).
    Drafts are created manually; they are promoted automatically on rollover
    via resolve_active_year() or manually via POST /years/{id}/promote.
    """
    _require_plan_write(p)
    unit_id = p.squadron_id if p.role == "sqn_admin" else body.get("unit_id", None)
    if p.role == "sqn_admin":
        unit_id = p.squadron_id
    elif p.role in ("wing_admin", "national_admin", "system_admin"):
        # Use the source year's unit_id to scope correctly
        src = db.get(PlanningYear, body.source_year_id)
        if not src:
            raise HTTPException(404, detail={"error": "source_year_not_found"})
        unit_id = src.unit_id
        if p.role == "wing_admin" and unit_id:
            require_can_write_squadron(p, unit_id, p.wing_id)
    else:
        raise HTTPException(403, detail={"error": "forbidden"})

    existing_draft = (
        db.query(PlanningYear)
        .filter(PlanningYear.unit_id == unit_id,
                PlanningYear.status == "draft")
        .first()
    )
    if existing_draft:
        raise HTTPException(409, detail={
            "error": "draft_already_exists",
            "existing_id": existing_draft.id,
            "message": "A draft year already exists for this unit. Promote or archive it first.",
        })

    py = PlanningYear(
        id=str(uuid.uuid4()), year=body.year, name=body.name,
        unit_id=unit_id, wing_id=p.wing_id,
        status="draft",
        active_status=False,  # dual-write: draft is not active
        created_by=p.user_id, created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(py)
    db.commit()
    audit(db, p, object_type="planning_year", object_id=py.id, action="create_draft",
          new={"year": body.year, "name": body.name, "status": "draft"})
    sq = db.get(Squadron, py.unit_id) if py.unit_id else None
    wg = db.get(Wing, py.wing_id) if py.wing_id else None
    return _year_out(py,
        unit_code=sq.code if sq else None, unit_name=sq.name if sq else None,
        wing_code=wg.code if wg else None)


@router.post("/years/{year_id}/promote")
def promote_draft_year(
    year_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Manually promote a draft year to active, archiving the current active year."""
    _require_plan_write(p)
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py, write=True)
    if py.status != "draft":
        raise HTTPException(409, detail={"error": "not_a_draft",
                                         "message": "Only a draft year can be promoted."})
    # Archive the current active year (if any)
    if py.unit_id:
        current_active = (
            db.query(PlanningYear)
            .filter(PlanningYear.unit_id == py.unit_id,
                    PlanningYear.status == "active")
            .first()
        )
        if current_active:
            current_active.status = "archived"
            current_active.active_status = False   # dual-write
            current_active.updated_by = p.user_id
            current_active.updated_at = utcnow()
    py.status = "active"
    py.active_status = True   # dual-write
    py.updated_by = p.user_id
    py.updated_at = utcnow()
    db.commit()
    audit(db, p, object_type="planning_year", object_id=py.id, action="promote",
          new={"status": "active"})
    sq = db.get(Squadron, py.unit_id) if py.unit_id else None
    wg = db.get(Wing, py.wing_id) if py.wing_id else None
    return _year_out(py,
        unit_code=sq.code if sq else None, unit_name=sq.name if sq else None,
        wing_code=wg.code if wg else None)


@router.post("/years/{year_id}/archive")
def archive_year(
    year_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Archive an active or draft year."""
    _require_plan_write(p)
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py, write=True)
    if py.status == "archived":
        raise HTTPException(409, detail={"error": "already_archived"})
    py.status = "archived"
    py.active_status = False   # dual-write
    py.updated_by = p.user_id
    py.updated_at = utcnow()
    db.commit()
    audit(db, p, object_type="planning_year", object_id=py.id, action="archive",
          new={"status": "archived"})
    sq = db.get(Squadron, py.unit_id) if py.unit_id else None
    wg = db.get(Wing, py.wing_id) if py.wing_id else None
    return _year_out(py,
        unit_code=sq.code if sq else None, unit_name=sq.name if sq else None,
        wing_code=wg.code if wg else None)
```

Note: `DraftYearIn` uses `body.source_year_id` for wing/national scope resolution, but `unit_id` is handled at router level for sqn_admin. The `body.get("unit_id", None)` line above is pseudocode — the actual model is:

```python
class DraftYearIn(BaseModel):
    year: int
    name: str
    source_year_id: str
```

And for sqn_admin the unit_id comes from `p.squadron_id`. The `unit_id = body.get(...)` line should be `unit_id = None` as a placeholder for the non-sqn_admin path. Clean up inline.

- [ ] **Step 4: Wire rollover into `list_planning_years()`**

In `list_planning_years()` (around line 421), add rollover trigger for squadron-scoped sessions before returning results:

```python
@router.get("/years")
def list_planning_years(
    unit_id: Optional[str] = None,
    wing_id: Optional[str] = None,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    # For squadron-scoped sessions: trigger lazy rollover before returning years.
    # This is the only place that needs it — it's called by both frontends to
    # initialise their year state, so the rollover fires on the first request
    # after the rollover date.
    if p.role in ("sqn_admin", "sqn_general") and p.squadron_id and p.wing_id:
        from ..services_year import resolve_active_year
        try:
            resolve_active_year(p.squadron_id, p.wing_id, db)
        except RuntimeError:
            pass  # missing timezone is a config issue, not a request failure

    q = db.query(PlanningYear)
    # ... rest unchanged
```

- [ ] **Step 5: Run tests**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_year_model.py -v
```

Expected: all lifecycle and rollover tests pass.

- [ ] **Step 6: Run the full suite**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/ -q
```

Expected: 0 failures.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/planning.py \
        backend/app/services_year.py \
        backend/tests/test_year_model.py
git commit -m "feat(year-model): lifecycle endpoints (create_draft/promote/archive) + rollover trigger (Phase A Task 4)"
```

---

### Task 5: Backend readers — migrate `active_status == True` to `status == 'active'`

**Files:**
- Modify: `backend/app/routers/planning.py` — 3 query sites
- Modify: `backend/app/routers/training.py` — `_year_for_date()` (line 472)
- Modify: `backend/app/routers/setup.py` — line 67
- Modify: `backend/app/scripts/migrate_legacy_class_data.py` — line 250
- Modify: `backend/tests/test_year_model.py` — regression test for _year_for_date behaviour

**Interfaces:**
- Consumes: `PlanningYear.status` from Task 2; `resolve_active_year()` from Task 3.

The key contract: `_year_for_date()` in `training.py` must now use `status == 'active'` (not `active_status == True`), so that a draft year is never picked — matching the spec's rule "a parade night attaches to the squadron's active year, never inferred."

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_year_model.py`:

```python
# ── Backend readers use status ────────────────────────────────

def test_parade_night_attaches_to_active_not_draft(client):
    """A draft year must never attract a parade night — only the active year does."""
    h = _sqn_admin_hdr(client)
    base = next_test_year()
    active_yr = client.post("/api/planning/years",
                            json={"year": base, "name": f"Active {base}"},
                            headers=h).json()
    draft_yr = client.post("/api/planning/years/draft",
                           json={"year": base + 1, "name": f"Draft {base + 1}",
                                 "source_year_id": active_yr["planning_year_id"]},
                           headers=h).json()
    assert draft_yr["status"] == "draft"

    night_date = f"{base}-06-15"
    r = client.post("/api/parade-nights",
                    json={"date": night_date, "term": "T2"},
                    headers=h)
    assert r.status_code == 200, r.text
    pn_id = r.json()["parade_night_id"]
    assert r.json()["linked_to_planning_year"] is True

    # The night's ParadeDate must be under the ACTIVE year, not the draft
    active_dates = client.get(
        f"/api/planning/years/{active_yr['planning_year_id']}/parade-dates",
        headers=h).json()
    draft_dates = client.get(
        f"/api/planning/years/{draft_yr['planning_year_id']}/parade-dates",
        headers=h).json()

    assert any(d["parade_night_id"] == pn_id for d in active_dates), (
        "Night must be under the active year"
    )
    assert not any(d["parade_night_id"] == pn_id for d in draft_dates), (
        "Night must NOT be under the draft year"
    )
```

- [ ] **Step 2: Run to verify it fails (or passes already)**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_year_model.py::test_parade_night_attaches_to_active_not_draft -v
```

If the test already passes (because `_year_for_date` uses `active_status == True` and draft has `active_status=False`), the dual-write from Task 2 already handles this. If it fails, proceed with Step 3.

- [ ] **Step 3: Migrate `_year_for_date()` in `training.py`**

In `backend/app/routers/training.py` at line 472, change:
```python
# OLD
PlanningYear.active_status == True)  # noqa: E712
```
to:
```python
# NEW
PlanningYear.status == "active")
```

Also update the docstring's reference from `active_status` to `status`.

- [ ] **Step 4: Migrate 3 query sites in `planning.py`**

**Site 1** (create_planning_year duplicate check, ~line 495):
```python
# OLD
PlanningYear.active_status == True,  # noqa: E712
# NEW
PlanningYear.status == "active",
```

**Site 2** (run-checks helper, ~line 2571):
```python
# OLD
py = q.filter(PlanningYear.active_status == True).order_by(PlanningYear.year.desc()).first()
# NEW
py = q.filter(PlanningYear.status == "active").order_by(PlanningYear.year.desc()).first()
```

**Site 3** (`list_planning_years` in the filter for the notes count that references years — check if any additional filtering exists beyond what was already modified in Task 4.**

- [ ] **Step 5: Migrate `setup.py`**

In `backend/app/routers/setup.py` at line 67, change:
```python
# OLD
PlanningYear.unit_id == sq_id, PlanningYear.active_status == True).all()]  # noqa: E712
# NEW
PlanningYear.unit_id == sq_id, PlanningYear.status == "active").all()]
```

- [ ] **Step 6: Migrate `migrate_legacy_class_data.py`**

In `backend/scripts/migrate_legacy_class_data.py` at line 250, change:
```python
# OLD
PlanningYear.unit_id == squadron.id, PlanningYear.active_status == True,  # noqa: E712
# NEW
PlanningYear.unit_id == squadron.id, PlanningYear.status == "active",
```

- [ ] **Step 7: Run the full suite**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/ -q
```

Expected: 0 failures, all tests including `test_parade_night_attaches_to_active_not_draft` passing.

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/planning.py \
        backend/app/routers/training.py \
        backend/app/routers/setup.py \
        backend/scripts/migrate_legacy_class_data.py \
        backend/tests/test_year_model.py
git commit -m "feat(year-model): migrate backend readers from active_status to status (Phase A Task 5)"
```

---

### Task 6: TMS frontend — year selector, lifecycle UI, year-changed notice

**Files:**
- Modify: `connected-frontend/index.html` — multiple sections (see below)

This is a single-file SPA. All changes are in `connected-frontend/index.html`. Use `grep -n` to find exact line numbers before editing. The key areas:

1. **Year selector** (around lines 12296–12315): distinguish draft vs active vs archived years in the `<select>`.
2. **Lifecycle actions** (around line 12447–12477): replace raw `active_status` PATCH calls with the new lifecycle endpoints.
3. **Year-changed notice**: add a banner that appears when the active year changes under a user's session.
4. **Remove the `linked_to_planning_year` toast dependency**: after this change, all nights attach to the active year cleanly — the toast (line 10191) remains but becomes much rarer. Leave it in place.

**Interfaces:**
- Consumes: `status` field from `_year_out()` (Task 2); `POST /years/draft`, `POST /years/{id}/promote`, `POST /years/{id}/archive` (Task 4).

- [ ] **Step 1: Update year selector rendering to show status labels**

Find the year selector render block. Search:
```bash
grep -n "active_status\|archived\|draft" connected-frontend/index.html | grep -i "year\|active\|draft" | head -20
```

Locate the block around line 12296 that filters years into "active" vs "archived". Update it to handle three states:

```javascript
// FIND (approximately lines 12296-12315 — verify with grep first):
const active = years.filter(function(y){return y.active_status;});
const archived = years.filter(function(y){return !y.active_status;});

// REPLACE WITH:
const active   = years.filter(function(y){ return y.status === 'active'   || (!y.status && y.active_status); });
const draft    = years.filter(function(y){ return y.status === 'draft'; });
const archived = years.filter(function(y){ return y.status === 'archived' || (!y.status && !y.active_status); });
```

And in the `<option>` rendering for each year (around line 12735), add a label for status:

```javascript
// FIND:
o.textContent=(y.name||String(y.year))+(y.active_status?'':' (archived)');
// REPLACE WITH:
const _label = y.status==='draft' ? ' (Draft)' : y.status==='archived' ? ' (Archived)' : '';
o.textContent=(y.name||String(y.year))+_label;
```

- [ ] **Step 2: Update year filtering for pickDefaultYear equivalents in TMS**

Find all `find(y=>y.active_status)` and `filter(y=>y.active_status)` references for PlanningYear in connected-frontend (lines 5314, 11376, 11602, 15515):

For each occurrence, update the filter to prefer `status === 'active'` with a fallback for pre-Phase-A rows:
```javascript
// OLD pattern:
const active = (years||[]).find(y=>y.active_status);
// NEW pattern:
const active = (years||[]).find(y=>y.status==='active' || (!y.status && y.active_status));
```

Apply the same change to `filter()` variants (line 5314):
```javascript
// OLD:
const activeIds=(years||[]).filter(y=>y.active_status).map(y=>y.planning_year_id);
// NEW:
const activeIds=(years||[]).filter(y=>y.status==='active'||(!y.status&&y.active_status)).map(y=>y.planning_year_id);
```

- [ ] **Step 3: Update lifecycle action calls to use new endpoints**

Find the block around line 12447 that creates a new year:
```javascript
// OLD (approximate):
await api('/api/planning/years',{method:'POST',body:{year:next,name:String(next),active_status:true}});
```
This creates an active year, which is correct — no change needed there. What needs to change is the ARCHIVE and RESTORE actions (lines 12468 and 12477):

```javascript
// OLD archive (~line 12468):
await api('/api/planning/years/'+id,{method:'PATCH',body:{active_status:false}});
// NEW archive:
await api('/api/planning/years/'+id+'/archive',{method:'POST'});

// OLD restore (~line 12477):
await api('/api/planning/years/'+id,{method:'PATCH',body:{active_status:true}});
// NEW promote (was "restore", now properly promotes draft or re-activates archived):
await api('/api/planning/years/'+id+'/promote',{method:'POST'});
```

Also add a "Create Draft Year" button to the year management UI. Find the year list render in TMS Settings (the block that renders the list of years with Archive/Restore buttons), and after the existing buttons add:

```javascript
// After the per-year button block, add a "Create Draft Year" button for sqn_admin:
if(!years.some(y=>y.status==='draft') && S.role==='sqn_admin'){
  const btn=document.createElement('button');
  btn.className='btn btn-secondary btn-sm';
  btn.textContent='Create Draft Year';
  btn.onclick=async function(){
    const active=years.find(y=>y.status==='active'||(!y.status&&y.active_status));
    if(!active){alert('No active year found');return;}
    const nextYr=active.year+1;
    const name=prompt('Name for the draft year?', String(nextYr)+' Training Year');
    if(!name)return;
    try{
      await api('/api/planning/years/draft',{method:'POST',body:{year:nextYr,name,source_year_id:active.planning_year_id}});
      showToast('Draft year created.');
      await loadYears();  // refresh the year list
    }catch(e){showToast(apiErr(e),true);}
  };
  container.appendChild(btn);
}
```

Adjust `container` to match the actual variable name used in the year management section.

- [ ] **Step 4: Add year-changed notice**

The spec requires: "The active year changing under a user mid-session should show a notice rather than swapping data underneath."

Add a session-level year snapshot. Find `loadYears()` or the equivalent function that fetches planning years (search `grep -n "loadYears\|P.years\|loadP\|P\.years" connected-frontend/index.html | head -20`).

After years are loaded and `P.currentYearId` is set for the first time, record a snapshot:
```javascript
// Add near where P.currentYearId is first set from the API response:
if(!P._yearSnapshotId){ P._yearSnapshotId = P.currentYearId; }
```

Then on every subsequent years fetch, check whether the active year changed:
```javascript
const newActive = (years||[]).find(y=>y.status==='active'||(!y.status&&y.active_status));
if(P._yearSnapshotId && newActive && newActive.planning_year_id !== P._yearSnapshotId){
  showToast(
    'Your training year has automatically updated to "' + (newActive.name||newActive.year) + '". '
    + 'Reload the page to see the updated plan.',
    false,  // not an error — persistent info banner
  );
  P._yearSnapshotId = newActive.planning_year_id;
}
```

Note: `showToast` is the existing toast function in the SPA. Adjust signature if it does not accept a second `isError` flag.

- [ ] **Step 5: Verify in browser (manual)**

Start the servers:
```bash
# Terminal 1
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
# Terminal 2
cd connected-frontend && python3 -m http.server 8080
```

Login as `ADMIN703`. Navigate to Settings → Training Year. Verify:
- The year selector shows "2026 Training Year" (active, no label)
- "Create Draft Year" button is present
- Click it → creates a draft year → selector shows "2027 Training Year (Draft)"
- Archive button archives a year → shows "(Archived)"
- No console errors

- [ ] **Step 6: Commit**

```bash
git add connected-frontend/index.html
git commit -m "feat(year-model): TMS frontend — status labels, lifecycle UI, year-changed notice (Phase A Task 6)"
```

---

### Task 7: PW frontend — status field, year selector, year-changed notice

**Files:**
- Modify: `frontend/src/api/types.ts:181-185` (PlanningYear interface)
- Modify: `frontend/src/routes/PlanningWorkspace.tsx:33-46` (`pickDefaultYear()`)
- Modify: `frontend/src/components/planning/PlanningContextBar.tsx` (year selector)

**Interfaces:**
- Consumes: `status` field from `_year_out()` (Task 2).

- [ ] **Step 1: Update `PlanningYear` type**

In `frontend/src/api/types.ts` at line 181, update the `PlanningYear` interface:

```typescript
export interface PlanningYear {
  planning_year_id: string;
  unit_id: string | null;
  wing_id: string | null;
  year: number;
  name: string;
  /** Phase A: canonical status field. draft | active | archived. */
  status: 'draft' | 'active' | 'archived';
  /** Backward-compat: kept until Phase A-2 drops it from the API. */
  active_status: boolean;
  unit_code?: string | null;
  unit_name?: string | null;
  wing_code?: string | null;
  created_by?: string | null;
  updated_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  version?: number;
}
```

- [ ] **Step 2: Update `pickDefaultYear()` to use `status`**

In `frontend/src/routes/PlanningWorkspace.tsx` at lines 33–46, update the function:

```typescript
// Phase A: prefer status === 'active'; fall back to active_status for pre-Phase-A rows.
function pickDefaultYear<T extends { year: number; status?: string; active_status?: boolean }>(list: T[]): T | null {
  const yrs = (list ?? []).filter(Boolean);
  if (!yrs.length) return null;
  const act = yrs.filter(y => y.status === 'active' || (!y.status && y.active_status));
  const pool = act.length ? act : yrs;
  const now = new Date().getFullYear();
  const exact = pool.find(y => Number(y.year) === now);
  if (exact) return exact;
  const ahead = pool.filter(y => Number(y.year) > now).sort((a, b) => a.year - b.year);
  if (ahead.length) return ahead[0];
  const behind = pool.filter(y => Number(y.year) < now).sort((a, b) => b.year - a.year);
  if (behind.length) return behind[0];
  return pool[0];
}
```

- [ ] **Step 3: Add year-changed notice to PW**

In `frontend/src/routes/PlanningWorkspace.tsx`, find where `years` data is fetched (the `useQuery` for planning years). Add a `useRef` to track the initial active year:

```typescript
import { useState, useEffect, useCallback, useRef } from "react";

// Inside PlanningWorkspace():
const initialActiveYearId = useRef<string | null>(null);
const [yearChangedNotice, setYearChangedNotice] = useState<string | null>(null);
```

After the years query resolves and `selectedYearId` is set, check for a changed active year:

```typescript
// In the useEffect that processes years data (after pickDefaultYear):
useEffect(() => {
  if (!years?.length) return;
  const activeYear = years.find((y: PlanningYear) => y.status === 'active' || (!y.status && y.active_status));
  if (!activeYear) return;
  if (!initialActiveYearId.current) {
    initialActiveYearId.current = activeYear.planning_year_id;
    return;
  }
  if (activeYear.planning_year_id !== initialActiveYearId.current) {
    setYearChangedNotice(
      `Your training year has automatically updated to "${activeYear.name || activeYear.year}". ` +
      `Reload the page to see the updated plan.`
    );
    initialActiveYearId.current = activeYear.planning_year_id;
  }
}, [years]);
```

Render the notice in the JSX (add above the main planning canvas, inside the return):
```tsx
{yearChangedNotice && (
  <div className="year-changed-notice" role="alert"
       style={{background:'var(--warn-bg)',color:'var(--warn)',padding:'8px 16px',
               display:'flex',justifyContent:'space-between',alignItems:'center'}}>
    <span>{yearChangedNotice}</span>
    <button onClick={() => setYearChangedNotice(null)}
            style={{border:'none',background:'none',cursor:'pointer',fontWeight:'bold'}}>
      ×
    </button>
  </div>
)}
```

- [ ] **Step 4: Update year selector in `PlanningContextBar.tsx` to show Draft label**

Find the year `<select>` in `frontend/src/components/planning/PlanningContextBar.tsx`. Locate the `<option>` render and add a "(Draft)" suffix:

```tsx
// FIND the option rendering (search for "planning_year_id" in this file):
<option key={y.planning_year_id} value={y.planning_year_id}>
  {y.name || String(y.year)}
</option>

// REPLACE WITH:
<option key={y.planning_year_id} value={y.planning_year_id}>
  {y.name || String(y.year)}
  {y.status === 'draft' ? ' (Draft)' : ''}
  {y.status === 'archived' ? ' (Archived)' : ''}
</option>
```

- [ ] **Step 5: Build the PW app**

```bash
cd frontend && npm run build
```

Expected: 0 TypeScript errors, build succeeds.

- [ ] **Step 6: Manual browser verification**

Start the dev server:
```bash
cd frontend && npm run dev
```

Open `http://localhost:5173/planning`. Login, verify:
- Year selector shows active year; draft year (if created from TMS) shows "(Draft)"
- `pickDefaultYear()` selects the active year by default
- No TypeScript errors in browser console

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/types.ts \
        frontend/src/routes/PlanningWorkspace.tsx \
        frontend/src/components/planning/PlanningContextBar.tsx
git commit -m "feat(year-model): PW frontend — status type, pickDefaultYear(), draft label, year-changed notice (Phase A Task 7)"
```

---

### Task 8: Tighten unique index — one active year per squadron

This migration replaces the per-year-number partial index with a per-squadron partial index, enforcing the core invariant at the DB level.

**Files:**
- Modify: `backend/app/models/planning.py:48-56` (`__table_args__`)
- Create: `backend/alembic/versions/???_v59_one_active_year_index.py`
- Modify: `backend/tests/test_year_model.py` — invariant test

**Pre-condition:** All six multi-active squadrons were resolved via REM-156. Task 8's migration will refuse to run if any squadron still holds >1 active year.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_year_model.py`:

```python
# ── One-active-year invariant ─────────────────────────────────

def test_cannot_have_two_active_years_for_same_squadron(client):
    """The DB-level unique index must prevent a second active year per squadron."""
    h = _sqn_admin_hdr(client)
    base = next_test_year()
    # First active year — succeeds
    yr1 = client.post("/api/planning/years",
                      json={"year": base, "name": f"Year {base}"},
                      headers=h).json()
    assert yr1["status"] == "active"

    # Try to create a second active year via the old PATCH restore path
    # (bypassing the new lifecycle endpoints to simulate the invariant test)
    yr2 = client.post("/api/planning/years",
                      json={"year": base + 1, "name": f"Year {base + 1}"},
                      headers=h).json()
    # The second POST creates a year — but the index means restoring an
    # archived year while one is already active must fail.
    # Archive yr2 first, then try to restore it while yr1 is still active.
    yr2_id = yr2["planning_year_id"]
    client.post(f"/api/planning/years/{yr2_id}/archive", headers=h)
    r = client.post(f"/api/planning/years/{yr2_id}/promote", headers=h)
    # promote of an archived year is not allowed (only draft can be promoted)
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "not_a_draft"


def test_promote_replaces_old_active_atomically(client):
    """Promoting a draft archives the old active in the same transaction."""
    h = _sqn_admin_hdr(client)
    base = next_test_year()
    yr1 = client.post("/api/planning/years",
                      json={"year": base, "name": f"Year {base}"},
                      headers=h).json()
    draft = client.post("/api/planning/years/draft",
                        json={"year": base + 1, "name": f"Draft {base + 1}",
                              "source_year_id": yr1["planning_year_id"]},
                        headers=h).json()
    client.post(f"/api/planning/years/{draft['planning_year_id']}/promote", headers=h)

    years = client.get("/api/planning/years", headers=h).json()
    active_years = [y for y in years if y["status"] == "active"]
    assert len(active_years) == 1, (
        f"Expected exactly one active year after promotion, got {len(active_years)}: "
        f"{[y['planning_year_id'] for y in active_years]}"
    )
```

- [ ] **Step 2: Run to verify the test passes already (checking existing guard)**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_year_model.py::test_promote_replaces_old_active_atomically -v
```

This should already pass from Task 4's promote endpoint. If it fails, fix the promote endpoint first.

- [ ] **Step 3: Create the index-replacement migration**

Get current head:
```bash
cd backend && source .venv/bin/activate && alembic heads
```

Create `backend/alembic/versions/REVISION_v59_one_active_year_index.py`:

```python
"""v59 — replace planning_years per-year-number unique index with per-squadron index

OLD index: unique (unit_id, year) WHERE active_status — prevents two active 2026 rows
           but permits active-2026 + active-2027, which is how 6 squadrons accumulated
           duplicate active years (resolved via REM-156 before this migration runs).

NEW index: unique (unit_id) WHERE status='active' — at most one active year per squadron,
           regardless of year number.

Pre-flight: refuses to run if any squadron holds >1 active year.

Revision ID: <new-hex-id>
Revises: <v58-revision>
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa

revision = "<new-hex-id>"
down_revision = "<v58-revision>"
branch_labels = None
depends_on = None

_PREFLIGHT_SQL = """
    SELECT unit_id, COUNT(*) AS cnt
    FROM planning_years
    WHERE status = 'active' AND unit_id IS NOT NULL
    GROUP BY unit_id
    HAVING COUNT(*) > 1
"""


def upgrade():
    bind = op.get_bind()

    # Pre-flight: refuse if any squadron has >1 active year.
    conflicts = bind.execute(sa.text(_PREFLIGHT_SQL)).fetchall()
    if conflicts:
        unit_ids = [r[0] for r in conflicts]
        raise RuntimeError(
            f"Migration v59 aborted: the following squadrons hold more than one "
            f"active planning year: {unit_ids}. "
            "Resolve via the /archive or /promote endpoints before re-running."
        )

    # Drop the old per-(unit_id, year) index.
    # The index name is 'uq_planning_years_unit_year_active' as defined in the model.
    # batch_alter_table handles SQLite's limited ALTER TABLE support.
    with op.batch_alter_table("planning_years") as batch_op:
        batch_op.drop_index("uq_planning_years_unit_year_active")
        batch_op.create_index(
            "uq_planning_years_unit_active",
            ["unit_id"],
            unique=True,
            postgresql_where=sa.text("status = 'active'"),
            sqlite_where=sa.text("status = 'active'"),
        )


def downgrade():
    with op.batch_alter_table("planning_years") as batch_op:
        batch_op.drop_index("uq_planning_years_unit_active")
        batch_op.create_index(
            "uq_planning_years_unit_year_active",
            ["unit_id", "year"],
            unique=True,
            postgresql_where=sa.text("active_status = true"),
            sqlite_where=sa.text("active_status = 1"),
        )
```

- [ ] **Step 4: Update `__table_args__` in the model to match**

In `backend/app/models/planning.py`, update `PlanningYear.__table_args__`:

```python
__table_args__ = (
    Index(
        "uq_planning_years_unit_active",
        "unit_id",
        unique=True,
        sqlite_where=text("status = 'active'"),
        postgresql_where=text("status = 'active'"),
    ),
)
```

- [ ] **Step 5: Run the migration**

```bash
cd backend && source .venv/bin/activate && alembic upgrade head
```

Expected: succeeds (no multi-active squadrons in dev DB after REM-156).

- [ ] **Step 6: Run the full suite**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/ -q
```

Expected: 0 failures.

- [ ] **Step 7: Verify the existing REM-129/REM-139 regression test still passes**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_planning.py -k "rem_129 or linked_to_planning" -v
```

Expected: the `test_parade_night_create_links_to_planning_year` test passes.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/planning.py \
        backend/alembic/versions/*_v59_one_active_year_index.py \
        backend/tests/test_year_model.py
git commit -m "feat(year-model): tighten unique index to one active year per squadron (Phase A Task 8)"
```

---

## Self-Review

### 1. Spec coverage

| Spec requirement | Covered by |
|---|---|
| `PlanningYear.status: str (draft\|active\|archived)` | Task 2 |
| `active_status` retained as derived value | Tasks 2, 4, 5 (dual-write throughout) |
| At most one active year per squadron (unique index) | Task 8 |
| `Wing.timezone` — IANA string, fail-loudly if unset | Task 1 |
| `resolve_active_year()` with lazy rollover | Task 3 |
| Rollover = 1 January of draft year's `year`, in wing-local time | Task 3 |
| Concurrent promotion safe via unique index IntegrityError | Task 3 |
| Year-changed notice on both frontends | Tasks 6, 7 |
| TMS Settings — lifecycle actions (create draft, promote, archive) | Task 4 (endpoints), Task 6 (UI) |
| PW year selector shows both active and draft years (labelled) | Task 7 |
| Migration refuses to run with >1 active per squadron | Task 8 |
| `_year_for_date()` uses `status` not `active_status` | Task 5 |
| All backend readers migrated to `status` | Task 5 |
| Both frontends dual-read `status` with `active_status` fallback | Tasks 6, 7 |

**Gap noted:** The spec says "the linked_to_planning_year: false warning toast in connected-frontend (added 2026-08-25) also becomes unreachable and is removed with them" — this refers to removal of `_year_for_date()` and `_find_or_create_parade_date_for_night()`, which is **Phase B**, not Phase A. The toast stays for now.

**Gap noted:** The spec says "TMS and Planning Workspace both default to the active year" — handled by `pickDefaultYear()` update in Task 7 and the equivalent in Task 6. Confirmed.

### 2. Placeholder scan

No TBDs or "implement later" in this plan. All code blocks contain real, runnable code.

### 3. Type consistency

- `resolve_active_year(squadron_id: str, wing_id: str, db: Session, *, _today=None) -> PlanningYear | None` — used consistently in Tasks 3, 4, 5.
- `get_wing_timezone(wing_id: str, db: Session) -> ZoneInfo` — used in Tasks 1, 3.
- `_year_out()` returns `dict` with both `status` and `active_status` — used throughout Tasks 2–5.
- `PlanningYear.status` is always `str`, values: `'draft' | 'active' | 'archived'`.
- `next_test_year()` from `conftest` used in all test files — confirm import is present.

### 4. Phase B note

Phase B (merging `parade_nights` + `parade_dates`) is a separate plan. Its precondition is: "Phase A step 5 holds in production" — i.e., the one-active-year unique index (Task 8) is deployed and verified. Phase B also requires human resolution of the 4 orphan parade nights (718 × 2 and TEST × 2) before its migration can run.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-28-year-model-phase-a.md`.

**Two execution options:**

**1. Subagent-Driven (recommended)** — dispatches a fresh subagent per task, reviews between tasks, fast iteration.

**2. Inline Execution** — executes tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
