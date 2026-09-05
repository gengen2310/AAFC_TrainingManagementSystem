# Parade Night Planning Redesign — Plan A: Backend Foundations

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `SessionAssistantFacilitator` join table, `ParadeNightTimingSnapshot` table, enforce timing template requirement on new parade night creation, add template-impact endpoints, and extend the night-summaries response with instructional period data.

**Architecture:** Two Alembic migrations create the new tables and backfill existing data. The create-parade-night endpoint is tightened to reject requests without a timing template. Three new endpoints (template impact GET, apply template PATCH, assistant facilitator CRUD) complete the backend contract that Plan B (React) and Plan C (connected TMS) depend on.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 mapped-column style, Alembic, pytest, PostgreSQL-compatible migrations using `op.execute` with `sa.text`.

**Spec:** `docs/superpowers/specs/2026-09-05-parade-night-planning-redesign.md`

## Global Constraints

- Never drop `assistant_facilitator_id` or `backup_facilitator_id` columns — keep as deprecated nullable columns.
- Never add a DB-level NOT NULL constraint to `parade_nights.timing_template_id` — enforce at the API layer only.
- All new Alembic revisions chain from head `b1c2d3e4f5a6`.
- Use `op.execute(sa.text(...))` for data backfill — never raw string SQL.
- Run `cd backend && source .venv/bin/activate && python -m pytest tests/ -q` after every task. Do not stack failures.
- Every endpoint follows the existing `require_can_write_squadron` / `require_can_view_squadron` pattern from `permissions.py`.
- `UTCDateTime` is the correct type for timezone-aware columns — import from `..database`.
- New models go in `backend/app/models/training.py` and must be imported in `backend/app/models/__init__.py`.

---

### Task 1: Migration A — SessionAssistantFacilitator

**Files:**
- Create: `backend/alembic/versions/c1d2e3f4a5b6_v64_session_assistant_facilitators.py`
- Modify: `backend/app/models/training.py` (add `SessionAssistantFacilitator` class after `Session`)
- Modify: `backend/app/models/__init__.py` (add import)
- Test: `backend/tests/test_sessions.py` (new or extend)

**Interfaces:**
- Produces: `SessionAssistantFacilitator` ORM class with `session_id`, `user_id`, `created_at`; table name `session_assistant_facilitators`; unique constraint on `(session_id, user_id)`.
- Produces: migration that backfills existing `assistant_facilitator_id` values and leaves the old column intact.

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_sessions.py` (create it if absent, or extend existing):

```python
def test_session_assistant_facilitator_table_exists(client, login):
    """The session_assistant_facilitators table is accessible via the ORM."""
    from app.models.training import SessionAssistantFacilitator
    assert SessionAssistantFacilitator.__tablename__ == "session_assistant_facilitators"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && source .venv/bin/activate
python -m pytest tests/test_sessions.py::test_session_assistant_facilitator_table_exists -v
```
Expected: ImportError or AttributeError (model doesn't exist yet).

- [ ] **Step 3: Add the ORM model to `training.py`**

In `backend/app/models/training.py`, after the `Session` class (after line 126), add:

```python
class SessionAssistantFacilitator(Base, UUIDMixin):
    """Zero-to-many assistant facilitators for a Session.

    Replaces the single assistant_facilitator_id column going forward.
    The old column is retained as a deprecated nullable field — do not drop it.
    """
    __tablename__ = "session_assistant_facilitators"
    __table_args__ = (
        UniqueConstraint("session_id", "user_id", name="uq_saf_session_user"),
    )
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
```

You will need `UniqueConstraint` — it is already imported via the existing `from sqlalchemy import ... UniqueConstraint ...` line in training.py. Verify the import; if missing, add `UniqueConstraint` to the import.

- [ ] **Step 4: Add import to `__init__.py`**

In `backend/app/models/__init__.py`, add:

```python
from .training import SessionAssistantFacilitator  # noqa
```

alongside the other training model imports.

- [ ] **Step 5: Run test to verify it passes**

```bash
python -m pytest tests/test_sessions.py::test_session_assistant_facilitator_table_exists -v
```
Expected: PASS.

- [ ] **Step 6: Create the Alembic migration**

Create `backend/alembic/versions/c1d2e3f4a5b6_v64_session_assistant_facilitators.py`:

```python
"""v64 session_assistant_facilitators join table

Adds zero-to-many assistant facilitator relationship to Session.
Backfills existing assistant_facilitator_id values into the new table.
The old column is retained as deprecated — will be dropped in a later migration
once all consumers have been audited and migrated.

Revision ID: c1d2e3f4a5b6
Revises: b1c2d3e4f5a6
Create Date: 2026-09-05
"""
import sqlalchemy as sa
from alembic import op

revision = 'c1d2e3f4a5b6'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'session_assistant_facilitators',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36),
                  sa.ForeignKey('sessions.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('user_id', sa.String(36), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint('session_id', 'user_id', name='uq_saf_session_user'),
    )
    # Backfill existing assistant_facilitator_id rows
    op.execute(sa.text("""
        INSERT INTO session_assistant_facilitators (id, session_id, user_id, created_at)
        SELECT
            lower(hex(randomblob(4)) || '-' || hex(randomblob(2)) || '-4' ||
                  substr(hex(randomblob(2)),2) || '-' ||
                  substr('89ab', abs(random()) % 4 + 1, 1) ||
                  substr(hex(randomblob(2)),2) || '-' || hex(randomblob(6))),
            id,
            assistant_facilitator_id,
            CURRENT_TIMESTAMP
        FROM sessions
        WHERE assistant_facilitator_id IS NOT NULL
          AND is_deleted = 0
    """))
    # Note: the above UUID generation is SQLite-compatible.
    # On PostgreSQL the backfill uses gen_random_uuid() instead.
    # The migration rehearsal script will catch any syntax issues.


def downgrade():
    op.drop_table('session_assistant_facilitators')
```

**Important — PostgreSQL UUID generation:** The `randomblob` expression above is SQLite-only. The production migration will run on PostgreSQL. Update the backfill to use a conditional approach:

```python
def upgrade():
    op.create_table(
        'session_assistant_facilitators',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36),
                  sa.ForeignKey('sessions.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('user_id', sa.String(36), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint('session_id', 'user_id', name='uq_saf_session_user'),
    )
    # Detect dialect and use appropriate UUID generation
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute(sa.text("""
            INSERT INTO session_assistant_facilitators (id, session_id, user_id, created_at)
            SELECT gen_random_uuid()::text, id, assistant_facilitator_id, NOW()
            FROM sessions
            WHERE assistant_facilitator_id IS NOT NULL
              AND is_deleted = false
        """))
    else:
        # SQLite — used in test DB only; UUIDs generated in Python
        from sqlalchemy import inspect as sa_inspect
        conn = op.get_bind()
        rows = conn.execute(sa.text(
            "SELECT id, assistant_facilitator_id FROM sessions "
            "WHERE assistant_facilitator_id IS NOT NULL AND is_deleted = 0"
        )).fetchall()
        import uuid
        for row in rows:
            conn.execute(sa.text(
                "INSERT OR IGNORE INTO session_assistant_facilitators "
                "(id, session_id, user_id, created_at) VALUES (:id, :sid, :uid, CURRENT_TIMESTAMP)"
            ), {"id": str(uuid.uuid4()), "sid": row[0], "uid": row[1]})
```

- [ ] **Step 7: Run the migration against the test database**

```bash
cd backend && source .venv/bin/activate
alembic upgrade head
```
Expected: Migration runs without error. Head is now `c1d2e3f4a5b6`.

- [ ] **Step 8: Write and run backfill verification test**

```python
def test_assistant_facilitator_backfill(db_session):
    """Every session with assistant_facilitator_id has a matching SAF row."""
    from app.models.training import Session, SessionAssistantFacilitator
    sessions_with_asst = db_session.query(Session).filter(
        Session.assistant_facilitator_id.isnot(None),
        Session.is_deleted.is_(False)
    ).all()
    for s in sessions_with_asst:
        saf = db_session.query(SessionAssistantFacilitator).filter_by(
            session_id=s.id, user_id=s.assistant_facilitator_id
        ).first()
        assert saf is not None, f"Session {s.id} missing SAF row for {s.assistant_facilitator_id}"
```

```bash
python -m pytest tests/test_sessions.py::test_assistant_facilitator_backfill -v
```
Expected: PASS (or no sessions with assistant_facilitator_id in test DB — also PASS).

- [ ] **Step 9: Run full backend suite**

```bash
python -m pytest tests/ -q
```
Expected: all previously passing tests still pass.

- [ ] **Step 10: Commit**

```bash
git add backend/app/models/training.py backend/app/models/__init__.py \
        backend/alembic/versions/c1d2e3f4a5b6_v64_session_assistant_facilitators.py \
        backend/tests/test_sessions.py
git commit -m "feat(db): add SessionAssistantFacilitator join table (v64)

Zero-to-many assistant facilitators. Backfills existing assistant_facilitator_id
rows. Old column retained as deprecated nullable — not dropped in this migration."
```

---

### Task 2: Migration B — ParadeNightTimingSnapshot

**Files:**
- Create: `backend/alembic/versions/d2e3f4a5b6c7_v65_parade_night_timing_snapshots.py`
- Modify: `backend/app/models/training.py` (add `ParadeNightTimingSnapshot` class)
- Modify: `backend/app/models/__init__.py` (add import)
- Test: `backend/tests/test_timing.py` (extend)

**Interfaces:**
- Consumes: Nothing from Task 1.
- Produces: `ParadeNightTimingSnapshot` ORM class; table `parade_night_timing_snapshots`; backfilled for nights that have a `timing_template_id`.
- Produces: helper `_materialise_snapshot(db, parade_night_id, timing_template_id)` in `backend/app/routers/training.py` — called by Task 3's create endpoint and Task 5's apply-template endpoint.

- [ ] **Step 1: Write the failing test**

```python
def test_timing_snapshot_table_exists(client):
    from app.models.training import ParadeNightTimingSnapshot
    assert ParadeNightTimingSnapshot.__tablename__ == "parade_night_timing_snapshots"
```

Run:
```bash
python -m pytest tests/test_timing.py::test_timing_snapshot_table_exists -v
```
Expected: ImportError.

- [ ] **Step 2: Add ORM model to `training.py`**

After the `ParadeNightTimingOverride` class (around line 390), add:

```python
class ParadeNightTimingSnapshot(Base, UUIDMixin):
    """Materialised instructional period data for one Parade Night.

    Written once when a Parade Night is created (or when its template is
    deliberately changed via the PATCH /template endpoint). Changes to the
    master TimingTemplate after this point do not affect existing snapshots.

    period_number is 1-based and counts instructional periods only.
    is_instructional is always True for the period-numbered rows;
    non-instructional blocks (breaks, opening/closing parade) are stored
    with period_number=None and is_instructional=False so the frontend
    can render the timing strip.
    """
    __tablename__ = "parade_night_timing_snapshots"
    __table_args__ = (
        UniqueConstraint("parade_night_id", "period_number", name="uq_pnts_night_period"),
    )
    parade_night_id: Mapped[str] = mapped_column(
        ForeignKey("parade_nights.id", ondelete="CASCADE"), index=True, nullable=False
    )
    period_number: Mapped[int | None] = mapped_column(Integer, nullable=True)  # NULL for non-instructional
    block_label: Mapped[str] = mapped_column(String(120), nullable=False)
    start_time: Mapped[str | None] = mapped_column(String(10), nullable=True)  # HH:MM
    end_time: Mapped[str | None] = mapped_column(String(10), nullable=True)    # HH:MM
    is_instructional: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
```

Note: the `UniqueConstraint` partial index trick used in `PlanningYear` is NOT needed here — the unique constraint on `(parade_night_id, period_number)` should only apply to rows where `period_number IS NOT NULL`. SQLite and PostgreSQL both allow multiple NULLs in a unique index. Verify this works by running the migration.

- [ ] **Step 3: Add import to `__init__.py`**

```python
from .training import ParadeNightTimingSnapshot  # noqa
```

- [ ] **Step 4: Run test to verify it now passes**

```bash
python -m pytest tests/test_timing.py::test_timing_snapshot_table_exists -v
```

- [ ] **Step 5: Add the `_materialise_snapshot` helper to `training.py` router**

In `backend/app/routers/training.py`, find the area near the `create_parade_night` function (around line 400). Add this helper before it:

```python
def _materialise_snapshot(db: DBSession, parade_night_id: str, timing_template_id: str) -> None:
    """Write ParadeNightTimingSnapshot rows for a parade night from its template.

    Deletes any existing snapshots for this night first, so this function is
    safe to call on both creation and template change.
    """
    from ..models.training import ParadeNightTimingSnapshot, TimingTemplate

    # Remove any existing snapshot rows for this night
    db.query(ParadeNightTimingSnapshot).filter_by(
        parade_night_id=parade_night_id
    ).delete(synchronize_session=False)

    tmpl = db.get(TimingTemplate, timing_template_id)
    if tmpl is None:
        return

    blocks = sorted(tmpl.blocks, key=lambda b: b.display_order)
    period_counter = 0
    for display_idx, block in enumerate(blocks):
        if block.is_instructional_period:
            period_counter += 1
            period_number = period_counter
        else:
            period_number = None

        snap = ParadeNightTimingSnapshot(
            parade_night_id=parade_night_id,
            period_number=period_number,
            block_label=block.block_name,
            start_time=block.start_time,
            end_time=block.end_time,
            is_instructional=block.is_instructional_period,
            display_order=display_idx,
        )
        db.add(snap)
```

- [ ] **Step 6: Create the Alembic migration**

Create `backend/alembic/versions/d2e3f4a5b6c7_v65_parade_night_timing_snapshots.py`:

```python
"""v65 parade_night_timing_snapshots

Materialised timing period data for each Parade Night. Written at creation
time so that master template changes do not retroactively alter existing nights.

Backfills existing nights that already have a timing_template_id.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-09-05
"""
import uuid
import sqlalchemy as sa
from alembic import op

revision = 'd2e3f4a5b6c7'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'parade_night_timing_snapshots',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('parade_night_id', sa.String(36),
                  sa.ForeignKey('parade_nights.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('period_number', sa.Integer, nullable=True),
        sa.Column('block_label', sa.String(120), nullable=False),
        sa.Column('start_time', sa.String(10), nullable=True),
        sa.Column('end_time', sa.String(10), nullable=True),
        sa.Column('is_instructional', sa.Boolean, nullable=False, server_default='0'),
        sa.Column('display_order', sa.Integer, nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index(
        'ix_pnts_night_period', 'parade_night_timing_snapshots',
        ['parade_night_id', 'period_number']
    )

    # Backfill: for each parade_night with a timing_template_id, write snapshot rows
    bind = op.get_bind()
    nights = bind.execute(sa.text(
        "SELECT id, timing_template_id FROM parade_nights "
        "WHERE timing_template_id IS NOT NULL AND is_deleted = 0"
    )).fetchall()

    for night_id, tmpl_id in nights:
        blocks = bind.execute(sa.text(
            "SELECT block_name, block_type, start_time, end_time, "
            "       is_instructional_period, display_order "
            "FROM timing_blocks "
            "WHERE timing_template_id = :tid AND is_deleted = 0 "
            "ORDER BY display_order"
        ), {"tid": tmpl_id}).fetchall()

        period_counter = 0
        for display_idx, block in enumerate(blocks):
            block_name, block_type, start_t, end_t, is_instr, disp_ord = block
            if is_instr:
                period_counter += 1
                period_number = period_counter
            else:
                period_number = None

            bind.execute(sa.text(
                "INSERT INTO parade_night_timing_snapshots "
                "(id, parade_night_id, period_number, block_label, start_time, end_time, "
                " is_instructional, display_order, created_at) "
                "VALUES (:id, :night_id, :pnum, :label, :st, :et, :instr, :disp, CURRENT_TIMESTAMP)"
            ), {
                "id": str(uuid.uuid4()),
                "night_id": night_id,
                "pnum": period_number,
                "label": block_name,
                "st": start_t,
                "et": end_t,
                "instr": 1 if is_instr else 0,
                "disp": display_idx,
            })


def downgrade():
    op.drop_index('ix_pnts_night_period', 'parade_night_timing_snapshots')
    op.drop_table('parade_night_timing_snapshots')
```

- [ ] **Step 7: Run migration**

```bash
alembic upgrade head
```
Expected: head is now `d2e3f4a5b6c7`.

- [ ] **Step 8: Write snapshot verification test**

```python
def test_materialise_snapshot_writes_correct_rows(client, db_session, login):
    """_materialise_snapshot writes one row per block with correct period_number."""
    from app.routers.training import _materialise_snapshot
    from app.models.training import (
        TimingTemplate, TimingBlock, ParadeNight, ParadeNightTimingSnapshot
    )
    # Create a template with 3 blocks: non-instr, instr, instr
    tmpl = TimingTemplate(
        squadron_id="test-sqn", name="Test Template",
        effective_from="2026-01-01", active_status=True, version=0
    )
    db_session.add(tmpl)
    db_session.flush()
    blocks = [
        TimingBlock(timing_template_id=tmpl.id, display_order=0,
                    block_name="Opening Parade", block_type="opening",
                    is_instructional_period=False),
        TimingBlock(timing_template_id=tmpl.id, display_order=1,
                    block_name="Period 1", block_type="instruction",
                    start_time="18:30", end_time="19:10",
                    is_instructional_period=True, period_number=1),
        TimingBlock(timing_template_id=tmpl.id, display_order=2,
                    block_name="Period 2", block_type="instruction",
                    start_time="19:20", end_time="20:00",
                    is_instructional_period=True, period_number=2),
    ]
    for b in blocks:
        db_session.add(b)
    db_session.flush()

    pn_id = "test-pn-snap-001"
    _materialise_snapshot(db_session, pn_id, tmpl.id)
    db_session.flush()

    snaps = db_session.query(ParadeNightTimingSnapshot).filter_by(
        parade_night_id=pn_id
    ).order_by(ParadeNightTimingSnapshot.display_order).all()

    assert len(snaps) == 3
    assert snaps[0].period_number is None   # Opening Parade
    assert snaps[0].is_instructional is False
    assert snaps[1].period_number == 1
    assert snaps[1].is_instructional is True
    assert snaps[1].start_time == "18:30"
    assert snaps[2].period_number == 2
    assert snaps[2].is_instructional is True
```

```bash
python -m pytest tests/test_timing.py::test_materialise_snapshot_writes_correct_rows -v
```

- [ ] **Step 9: Run full suite**

```bash
python -m pytest tests/ -q
```

- [ ] **Step 10: Commit**

```bash
git add backend/app/models/training.py backend/app/models/__init__.py \
        backend/alembic/versions/d2e3f4a5b6c7_v65_parade_night_timing_snapshots.py \
        backend/app/routers/training.py \
        backend/tests/test_timing.py
git commit -m "feat(db): add ParadeNightTimingSnapshot table + materialise helper (v65)

Snapshots instructional period data at creation time so master template
changes do not retroactively alter existing parade nights. Backfills all
nights that already have a timing_template_id."
```

---

### Task 3: Enforce timing template on new Parade Night creation

**Files:**
- Modify: `backend/app/routers/training.py` (create endpoint + wire `_materialise_snapshot`)
- Test: `backend/tests/test_timing.py` (extend)

**Interfaces:**
- Consumes: `_materialise_snapshot` from Task 2.
- Produces: `POST /api/training/parade-nights` or the equivalent create endpoint rejects `timing_template_id=None` with HTTP 422. Returns snapshot data in the response. Automatically sets `parade_type="normal"`, derives `session_count` from template.

- [ ] **Step 1: Write failing tests**

Find the existing create-parade-night test (in `test_timing.py` or `test_planning.py`). Add:

```python
def test_create_parade_night_without_template_returns_422(client, login):
    """New parade nights must include timing_template_id."""
    headers = login("sqn_admin_code")
    r = client.post("/api/training/parade-nights", headers=headers, json={
        "date": "2026-10-01",
        "term": "T3",
        "planning_year_id": "some-year-id",
        # no timing_template_id
    })
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"


def test_create_parade_night_with_template_materialises_snapshot(client, login, db_session):
    """Creating a parade night with a template writes snapshot rows."""
    from app.models.training import ParadeNightTimingSnapshot
    headers = login("sqn_admin_code")
    # use a valid template ID from the test DB (set up in conftest or test fixture)
    r = client.post("/api/training/parade-nights", headers=headers, json={
        "date": "2026-10-01",
        "term": "T3",
        "planning_year_id": "<valid_year_id>",
        "timing_template_id": "<valid_template_id>",
    })
    assert r.status_code in (200, 201), r.text
    night_id = r.json()["id"]
    snaps = db_session.query(ParadeNightTimingSnapshot).filter_by(
        parade_night_id=night_id
    ).all()
    assert len(snaps) > 0, "Expected timing snapshot rows after creation"


def test_create_parade_night_auto_sets_parade_type_normal(client, login):
    """Creating a parade night does not require parade_type; it defaults to 'normal'."""
    headers = login("sqn_admin_code")
    r = client.post("/api/training/parade-nights", headers=headers, json={
        "date": "2026-10-02",
        "term": "T3",
        "planning_year_id": "<valid_year_id>",
        "timing_template_id": "<valid_template_id>",
    })
    assert r.status_code in (200, 201)
    assert r.json().get("parade_type") == "normal"
```

```bash
python -m pytest tests/test_timing.py::test_create_parade_night_without_template_returns_422 -v
```
Expected: FAIL (currently returns 200 or 201).

- [ ] **Step 2: Locate the create endpoint**

In `backend/app/routers/training.py`, find `ParadeNightCreateIn` (around line 300) and the `create_parade_night` function (around line 410). The current body model has `session_count: int | None = None`. 

Find the `ParadeNightCreateIn` Pydantic model and add validation:

```python
class ParadeNightCreateIn(BaseModel):
    date: str
    term: str | None = None
    planning_year_id: str
    timing_template_id: str  # Required — no default; HTTP 422 if absent
    notes: str | None = None
    # Legacy fields — accepted for compatibility but not user-facing for standard creation:
    session_count: int | None = None      # Derived from template; ignored if template present
    parade_type: str | None = None        # Auto-set to 'normal' for standard creation
    start_time: str | None = None         # Derived from template
    end_time: str | None = None           # Derived from template
```

If the current model already exists, change `timing_template_id: str | None = None` → `timing_template_id: str` (remove the `None` default and the `| None`). This alone makes the field required and triggers a 422 when absent.

- [ ] **Step 3: Wire `_materialise_snapshot` into the create function**

In `create_parade_night`, after the line that saves the `ParadeNight` to the DB (after `db.add(pn)` / `db.flush()` / `db.commit()`), add:

```python
    _materialise_snapshot(db, pn.id, pn.timing_template_id)
    db.commit()  # commit snapshot rows (if already committed above, use db.flush() here instead)
```

Also ensure `parade_type` is set: if the body sends no `parade_type`, default to `"normal"`. The current line `parade_type=body.parade_type or "normal"` already does this — verify it's present.

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_timing.py::test_create_parade_night_without_template_returns_422 \
                 tests/test_timing.py::test_create_parade_night_with_template_materialises_snapshot \
                 tests/test_timing.py::test_create_parade_night_auto_sets_parade_type_normal -v
```
Expected: all PASS.

- [ ] **Step 5: Run full suite and fix any regressions**

```bash
python -m pytest tests/ -q
```

Any test that previously created a parade night without a template will now fail. For each such test, either:
- Add a valid `timing_template_id` to the creation call (preferred — use a template created in the test), OR
- If the test covers a legacy path, add a note and skip it with `pytest.mark.skip(reason="legacy creation path, no template required pre-v65")`.

Do NOT silently suppress 422 errors without understanding them.

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/training.py backend/tests/test_timing.py
git commit -m "feat(api): require timing_template_id on new parade night creation

Standard parade nights must use a timing template. The template is used to
materialise instructional period snapshots at creation time. parade_type
auto-defaults to 'normal'. session_count is derived from the template's
instructional block count."
```

---

### Task 4: Template impact GET endpoint

**Files:**
- Modify: `backend/app/routers/training.py` (new endpoint)
- Test: `backend/tests/test_timing.py` (extend)

**Interfaces:**
- Produces: `GET /api/training/parade-nights/{night_id}/template-impact?new_template_id={uuid}`
- Response shape:
  ```json
  {
    "retained_periods": [1, 2],
    "removed_periods": [3],
    "added_periods": [4],
    "affected_sessions": [
      {"session_id": "...", "period_number": 3, "has_curriculum": true, "has_facilitator": true}
    ]
  }
  ```

- [ ] **Step 1: Write failing test**

```python
def test_template_impact_returns_diff(client, login, db_session):
    """Template impact endpoint returns retained/removed/added period lists."""
    headers = login("sqn_admin_code")
    # Assumes a parade night with template (3 periods) and a new template (2 periods) exist
    r = client.get(
        f"/api/training/parade-nights/{night_id}/template-impact",
        params={"new_template_id": two_period_template_id},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "retained_periods" in data
    assert "removed_periods" in data
    assert "added_periods" in data
    assert "affected_sessions" in data
```

```bash
python -m pytest tests/test_timing.py::test_template_impact_returns_diff -v
```
Expected: 404 (endpoint not found).

- [ ] **Step 2: Implement the endpoint**

In `backend/app/routers/training.py`, find the pattern for existing parade-night endpoints and add:

```python
@router.get("/parade-nights/{night_id}/template-impact")
def parade_night_template_impact(
    night_id: str,
    new_template_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Return the period diff if the timing template were changed to new_template_id."""
    from ..models.training import ParadeNight, ParadeNightTimingSnapshot, Session, TimingTemplate

    pn = db.get(ParadeNight, night_id)
    if pn is None or pn.is_deleted:
        raise HTTPException(404, "Parade night not found")
    require_can_view_squadron(p, pn.squadron_id)

    new_tmpl = db.get(TimingTemplate, new_template_id)
    if new_tmpl is None or new_tmpl.is_deleted:
        raise HTTPException(404, "New timing template not found")

    # Current instructional period numbers from snapshot
    current_snaps = db.query(ParadeNightTimingSnapshot).filter(
        ParadeNightTimingSnapshot.parade_night_id == night_id,
        ParadeNightTimingSnapshot.is_instructional.is_(True),
    ).all()
    current_periods = {s.period_number for s in current_snaps if s.period_number is not None}

    # New instructional period numbers from new template
    new_instr_blocks = [b for b in new_tmpl.blocks if b.is_instructional_period]
    new_periods = set(range(1, len(new_instr_blocks) + 1))

    retained = sorted(current_periods & new_periods)
    removed = sorted(current_periods - new_periods)
    added = sorted(new_periods - current_periods)

    # Sessions that would be affected (on removed periods)
    affected = []
    if removed:
        sessions = db.query(Session).filter(
            Session.parade_night_id == night_id,
            Session.period_number.in_(removed),
            Session.is_deleted.is_(False),
        ).all()
        affected = [
            {
                "session_id": s.id,
                "period_number": s.period_number,
                "has_curriculum": s.curriculum_item_id is not None,
                "has_facilitator": s.facilitator_id is not None,
            }
            for s in sessions
        ]

    return {
        "retained_periods": retained,
        "removed_periods": removed,
        "added_periods": added,
        "affected_sessions": affected,
    }
```

- [ ] **Step 3: Run tests and full suite**

```bash
python -m pytest tests/test_timing.py::test_template_impact_returns_diff -v
python -m pytest tests/ -q
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/training.py backend/tests/test_timing.py
git commit -m "feat(api): add template-impact GET endpoint for parade nights

Returns period diff (retained/removed/added) and list of Sessions that
would be affected before a template change is confirmed."
```

---

### Task 5: Apply template PATCH endpoint

**Files:**
- Modify: `backend/app/routers/training.py` (new endpoint)
- Test: `backend/tests/test_timing.py`

**Interfaces:**
- Consumes: `_materialise_snapshot` from Task 2.
- Produces: `PATCH /api/training/parade-nights/{night_id}/template`
- Body: `{"timing_template_id": "...", "confirmed": true}`
- Behaviour: Replaces snapshot rows; does NOT delete Sessions. Returns updated night data.

- [ ] **Step 1: Write failing tests**

```python
def test_apply_template_replaces_snapshot(client, login, db_session):
    """Applying a new template replaces the snapshot rows."""
    headers = login("sqn_admin_code")
    r = client.patch(
        f"/api/training/parade-nights/{night_id}/template",
        headers=headers,
        json={"timing_template_id": new_template_id, "confirmed": True},
    )
    assert r.status_code == 200, r.text
    from app.models.training import ParadeNightTimingSnapshot
    snaps = db_session.query(ParadeNightTimingSnapshot).filter_by(
        parade_night_id=night_id
    ).all()
    # snapshot count matches new template's block count
    assert len(snaps) > 0


def test_apply_template_does_not_delete_sessions(client, login, db_session):
    """Applying a new template does not delete existing Sessions."""
    from app.models.training import Session
    headers = login("sqn_admin_code")
    before_count = db_session.query(Session).filter_by(
        parade_night_id=night_id, is_deleted=False
    ).count()
    client.patch(
        f"/api/training/parade-nights/{night_id}/template",
        headers=headers,
        json={"timing_template_id": new_template_id, "confirmed": True},
    )
    after_count = db_session.query(Session).filter_by(
        parade_night_id=night_id, is_deleted=False
    ).count()
    assert after_count == before_count


def test_apply_template_requires_confirmed(client, login):
    """PATCH /template with confirmed=False returns 409 when Sessions exist."""
    headers = login("sqn_admin_code")
    r = client.patch(
        f"/api/training/parade-nights/{night_id}/template",
        headers=headers,
        json={"timing_template_id": new_template_id, "confirmed": False},
    )
    # If sessions exist, must confirm; if no sessions, succeeds regardless
    assert r.status_code in (200, 409)
```

- [ ] **Step 2: Implement the endpoint**

```python
class TemplateChangeIn(BaseModel):
    timing_template_id: str
    confirmed: bool = False


@router.patch("/parade-nights/{night_id}/template")
def apply_parade_night_template(
    night_id: str,
    body: TemplateChangeIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    from ..models.training import ParadeNight, Session, TimingTemplate

    pn = db.get(ParadeNight, night_id)
    if pn is None or pn.is_deleted:
        raise HTTPException(404, "Parade night not found")
    require_can_write_squadron(p, pn.squadron_id)

    new_tmpl = db.get(TimingTemplate, body.timing_template_id)
    if new_tmpl is None or new_tmpl.is_deleted:
        raise HTTPException(404, "Timing template not found")

    # If sessions exist on periods that would be removed, require confirmation
    if not body.confirmed:
        new_period_count = sum(1 for b in new_tmpl.blocks if b.is_instructional_period)
        existing_sessions = db.query(Session).filter(
            Session.parade_night_id == night_id,
            Session.period_number > new_period_count,
            Session.is_deleted.is_(False),
        ).count()
        if existing_sessions > 0:
            raise HTTPException(
                409,
                detail={
                    "error": "confirmation_required",
                    "message": f"{existing_sessions} session(s) exist on periods that would be removed. "
                               "Send confirmed=true to proceed.",
                }
            )

    # Apply template change
    pn.timing_template_id = body.timing_template_id
    instr_blocks = [b for b in new_tmpl.blocks if b.is_instructional_period]
    pn.session_count = len(instr_blocks)
    if instr_blocks:
        all_blocks = sorted(new_tmpl.blocks, key=lambda b: b.display_order)
        pn.start_time = next((b.start_time for b in all_blocks if b.start_time), None)
        pn.end_time = next((b.end_time for b in reversed(all_blocks) if b.end_time), None)
    pn.version += 1

    _materialise_snapshot(db, night_id, body.timing_template_id)
    audit(db, p, object_type="parade_night", object_id=night_id, action="template_change",
          new={"timing_template_id": body.timing_template_id})
    db.commit()

    return {"id": pn.id, "timing_template_id": pn.timing_template_id,
            "session_count": pn.session_count, "version": pn.version}
```

- [ ] **Step 3: Run tests and full suite**

```bash
python -m pytest tests/test_timing.py -v
python -m pytest tests/ -q
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/training.py backend/tests/test_timing.py
git commit -m "feat(api): add apply-template PATCH endpoint for parade nights

Changes the timing template, replaces snapshot rows, updates session_count,
derives start/end from new template. Does not delete existing Sessions.
Requires confirmed=true if Sessions would be orphaned on removed periods."
```

---

### Task 6: Night summaries — add instructional_periods + timing_strip

**Files:**
- Modify: `backend/app/routers/planning.py` (extend `night_summaries` response)
- Test: `backend/tests/test_planning.py`

**Interfaces:**
- Consumes: `parade_night_timing_snapshots` table from Task 2.
- Produces: `GET /api/planning/years/{year_id}/night-summaries` response includes two new fields per night:
  - `instructional_periods: [{period_number, label, start_time, end_time}]` — instructional blocks only
  - `timing_strip: [{label, start_time, end_time, is_instructional, display_order}]` — all blocks in order

- [ ] **Step 1: Write failing test**

```python
def test_night_summaries_includes_instructional_periods(client, login):
    """night-summaries response includes instructional_periods for nights with snapshots."""
    headers = login("sqn_admin_code")
    r = client.get(f"/api/planning/years/{year_id}/night-summaries", headers=headers)
    assert r.status_code == 200
    nights = r.json()
    # Find a night that has a timing template
    nights_with_template = [n for n in nights if n.get("timing_template_id")]
    if nights_with_template:
        n = nights_with_template[0]
        assert "instructional_periods" in n, "instructional_periods missing from night summary"
        assert "timing_strip" in n, "timing_strip missing from night summary"
        # Each instructional period has required fields
        for period in n["instructional_periods"]:
            assert "period_number" in period
            assert "label" in period
```

```bash
python -m pytest tests/test_planning.py::test_night_summaries_includes_instructional_periods -v
```
Expected: KeyError/AssertionError (fields absent).

- [ ] **Step 2: Extend the `night_summaries` endpoint**

In `backend/app/routers/planning.py`, find the `night_summaries` function (line ~5249). Inside it, after loading parade nights, add a snapshot lookup:

```python
# Load timing snapshots for all nights in one query
from ..models.training import ParadeNightTimingSnapshot

night_ids = [pn.id for pn in parade_nights]
snapshots_by_night: dict[str, list] = {}
if night_ids:
    all_snaps = db.query(ParadeNightTimingSnapshot).filter(
        ParadeNightTimingSnapshot.parade_night_id.in_(night_ids)
    ).order_by(
        ParadeNightTimingSnapshot.parade_night_id,
        ParadeNightTimingSnapshot.display_order
    ).all()
    for snap in all_snaps:
        snapshots_by_night.setdefault(snap.parade_night_id, []).append(snap)
```

Then, in the dict/object built for each parade night in the response, add:

```python
snaps = snapshots_by_night.get(pn.id, [])
instructional_periods = [
    {
        "period_number": s.period_number,
        "label": s.block_label,
        "start_time": s.start_time,
        "end_time": s.end_time,
    }
    for s in snaps if s.is_instructional and s.period_number is not None
]
timing_strip = [
    {
        "label": s.block_label,
        "start_time": s.start_time,
        "end_time": s.end_time,
        "is_instructional": s.is_instructional,
        "display_order": s.display_order,
    }
    for s in snaps
]

# Fallback for legacy nights (no snapshot)
if not instructional_periods and pn.session_count:
    instructional_periods = [
        {"period_number": i, "label": f"Period {i}", "start_time": None, "end_time": None}
        for i in range(1, pn.session_count + 1)
    ]

# Add to the night dict:
night_dict["instructional_periods"] = instructional_periods
night_dict["timing_strip"] = timing_strip
```

- [ ] **Step 3: Run tests and full suite**

```bash
python -m pytest tests/test_planning.py::test_night_summaries_includes_instructional_periods -v
python -m pytest tests/ -q
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/planning.py backend/tests/test_planning.py
git commit -m "feat(api): add instructional_periods and timing_strip to night-summaries

instructional_periods lists schedulable columns for the planning grid.
timing_strip lists all blocks (instructional + non-instructional) for the
timeline strip above the grid. Falls back to session_count for legacy nights
without snapshots."
```

---

### Task 7: Session assistant facilitator CRUD + conflict engine

**Files:**
- Modify: `backend/app/routers/training.py` (3 new sub-endpoints)
- Modify: `backend/app/routers/training.py` (conflict detection section)
- Test: `backend/tests/test_sessions.py`

**Interfaces:**
- Consumes: `SessionAssistantFacilitator` from Task 1.
- Produces:
  - `GET /api/training/sessions/{session_id}` — add `assistant_facilitators: [{user_id, display_name}]` to response
  - `POST /api/training/sessions/{session_id}/assistants` — body `{user_id: str}`, adds assistant
  - `DELETE /api/training/sessions/{session_id}/assistants/{user_id}` — removes assistant
  - Conflict engine extended: assistant facilitator double-booking detected same as main facilitator

- [ ] **Step 1: Write failing tests**

```python
def test_add_assistant_facilitator(client, login, db_session):
    """POST /sessions/{id}/assistants adds an assistant facilitator row."""
    from app.models.training import SessionAssistantFacilitator
    headers = login("sqn_admin_code")
    r = client.post(
        f"/api/training/sessions/{session_id}/assistants",
        headers=headers,
        json={"user_id": facilitator_user_id},
    )
    assert r.status_code in (200, 201), r.text
    saf = db_session.query(SessionAssistantFacilitator).filter_by(
        session_id=session_id, user_id=facilitator_user_id
    ).first()
    assert saf is not None


def test_add_duplicate_assistant_is_idempotent(client, login):
    headers = login("sqn_admin_code")
    client.post(f"/api/training/sessions/{session_id}/assistants",
                headers=headers, json={"user_id": facilitator_user_id})
    r = client.post(f"/api/training/sessions/{session_id}/assistants",
                    headers=headers, json={"user_id": facilitator_user_id})
    assert r.status_code in (200, 201)  # idempotent, not 409


def test_delete_assistant_facilitator(client, login, db_session):
    from app.models.training import SessionAssistantFacilitator
    headers = login("sqn_admin_code")
    # Add first
    client.post(f"/api/training/sessions/{session_id}/assistants",
                headers=headers, json={"user_id": facilitator_user_id})
    # Then remove
    r = client.delete(
        f"/api/training/sessions/{session_id}/assistants/{facilitator_user_id}",
        headers=headers,
    )
    assert r.status_code in (200, 204), r.text
    saf = db_session.query(SessionAssistantFacilitator).filter_by(
        session_id=session_id, user_id=facilitator_user_id
    ).first()
    assert saf is None


def test_session_response_includes_assistant_facilitators(client, login):
    headers = login("sqn_admin_code")
    r = client.get(f"/api/training/sessions/{session_id}", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "assistant_facilitators" in data
    assert isinstance(data["assistant_facilitators"], list)


def test_assistant_facilitator_conflict_detected(client, login):
    """An assistant in two simultaneous sessions generates a conflict."""
    headers = login("sqn_admin_code")
    # Add same facilitator as assistant to two different sessions in same parade night / period
    client.post(f"/api/training/sessions/{session_a_id}/assistants",
                headers=headers, json={"user_id": shared_facilitator_id})
    client.post(f"/api/training/sessions/{session_b_id}/assistants",
                headers=headers, json={"user_id": shared_facilitator_id})
    r = client.get(f"/api/planning/parade-nights/{night_id}/conflicts", headers=headers)
    assert r.status_code == 200
    conflicts = r.json()
    facilitator_conflicts = [c for c in conflicts if "double_booked" in c.get("conflict_type", "")]
    assert len(facilitator_conflicts) > 0, "Expected facilitator double-booking conflict"
```

- [ ] **Step 2: Implement the endpoints**

```python
class AddAssistantIn(BaseModel):
    user_id: str


@router.post("/sessions/{session_id}/assistants")
def add_session_assistant(
    session_id: str,
    body: AddAssistantIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    from ..models.training import Session, SessionAssistantFacilitator
    sess = db.get(Session, session_id)
    if sess is None or sess.is_deleted:
        raise HTTPException(404, "Session not found")
    require_can_write_squadron(p, sess.squadron_id)
    # Idempotent: use INSERT OR IGNORE / get_or_create pattern
    existing = db.query(SessionAssistantFacilitator).filter_by(
        session_id=session_id, user_id=body.user_id
    ).first()
    if not existing:
        saf = SessionAssistantFacilitator(session_id=session_id, user_id=body.user_id)
        db.add(saf)
        db.commit()
    return {"session_id": session_id, "user_id": body.user_id}


@router.delete("/sessions/{session_id}/assistants/{user_id}")
def remove_session_assistant(
    session_id: str,
    user_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    from ..models.training import Session, SessionAssistantFacilitator
    sess = db.get(Session, session_id)
    if sess is None or sess.is_deleted:
        raise HTTPException(404, "Session not found")
    require_can_write_squadron(p, sess.squadron_id)
    db.query(SessionAssistantFacilitator).filter_by(
        session_id=session_id, user_id=user_id
    ).delete()
    db.commit()
    return {"removed": True}
```

Extend the existing `GET /sessions/{session_id}` response to include assistant facilitators:

```python
# In the existing get_session or equivalent endpoint, after loading the session:
from ..models.training import SessionAssistantFacilitator, Facilitator
asst_rows = db.query(SessionAssistantFacilitator).filter_by(session_id=sess.id).all()
assistant_facilitators = []
for row in asst_rows:
    f = db.query(Facilitator).filter_by(id=row.user_id).first()
    assistant_facilitators.append({
        "user_id": row.user_id,
        "display_name": f"{f.current_rank} {f.last_name}".strip() if f else row.user_id,
    })
# Add to response dict:
response_dict["assistant_facilitators"] = assistant_facilitators
# Also include legacy assistant_facilitator_id for backwards compatibility:
response_dict["assistant_facilitator_id"] = sess.assistant_facilitator_id
```

- [ ] **Step 3: Extend conflict detection**

Find the `_resource_conflicts` function in `training.py` (around line 710). It currently checks `facilitator_id` for double-booking. Extend it to also query `session_assistant_facilitators`:

```python
# After the existing facilitator_id conflict check, add:
from ..models.training import SessionAssistantFacilitator

# Check if any of our assistant facilitators are already booked (main or assistant) 
# in the same parade night and period
our_asst_rows = db.query(SessionAssistantFacilitator).filter_by(session_id=session_id).all()
our_asst_ids = {row.user_id for row in our_asst_rows}

if our_asst_ids:
    # Check if any of our assistants are main facilitators on other sessions
    other_sessions_with_same_main = db.query(Session).filter(
        Session.parade_night_id == parade_night_id,
        Session.period_number == period_number,
        Session.id != session_id,
        Session.facilitator_id.in_(our_asst_ids),
        Session.is_deleted.is_(False),
    ).all()
    for other in other_sessions_with_same_main:
        conflicts.append({
            "conflict_type": "facilitator_double_booked",
            "severity": "warning",
            "description": f"Assistant facilitator is main facilitator on another session in P{period_number}",
            "session_id": other.id,
        })

    # Check if any of our assistants are assistants on other sessions
    other_asst_rows = db.query(SessionAssistantFacilitator).join(
        Session, Session.id == SessionAssistantFacilitator.session_id
    ).filter(
        Session.parade_night_id == parade_night_id,
        Session.period_number == period_number,
        Session.id != session_id,
        SessionAssistantFacilitator.user_id.in_(our_asst_ids),
        Session.is_deleted.is_(False),
    ).all()
    for row in other_asst_rows:
        conflicts.append({
            "conflict_type": "facilitator_double_booked",
            "severity": "warning",
            "description": f"Assistant facilitator double-booked in P{period_number}",
            "session_id": row.session_id,
        })
```

- [ ] **Step 4: Run tests and full suite**

```bash
python -m pytest tests/test_sessions.py -v
python -m pytest tests/ -q
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/training.py backend/tests/test_sessions.py
git commit -m "feat(api): assistant facilitator CRUD + conflict engine extension

POST/DELETE /sessions/{id}/assistants manage zero-to-many assistant facilitators
via SessionAssistantFacilitator join table. GET /sessions/{id} includes
assistant_facilitators list. Conflict engine extended to detect assistant
double-booking (assistant-vs-main and assistant-vs-assistant)."
```

---

### Task 8: Regression sweep and migration rehearsal

**Files:**
- Run: full test suite
- Run: `backend/scripts/rehearse_data_migrations.py` (or equivalent)
- Modify: any tests broken by Task 3's mandatory template enforcement

- [ ] **Step 1: Run full backend test suite**

```bash
cd backend && source .venv/bin/activate
python -m pytest tests/ -v --tb=short 2>&1 | tee /tmp/plan-a-test-results.txt
```

- [ ] **Step 2: Fix any failures**

For each failure:
- If it's a test that creates a Parade Night without a template: update the test to provide a valid `timing_template_id`, creating a fixture template if needed.
- If it's a model import error: check `__init__.py` imports.
- If it's an Alembic migration failure: read the error carefully and fix the migration; do NOT skip.

- [ ] **Step 3: Run security greps**

```bash
bash -c "
grep -cE 'SYSADMIN2026|ADMIN703|ADMIN7WG|ADMINNATIONAL' connected-frontend/ -r || true
grep -cE 'code_hash|plain_code' connected-frontend/ -r || true
grep -cE 'JWT_SECRET|SECRET_KEY' connected-frontend/ -r || true
grep -cE 'postgresql://|postgres://|sqlite:///' connected-frontend/ -r || true
"
```
All must return 0.

- [ ] **Step 4: Verify Alembic chain**

```bash
alembic heads
```
Expected: single head at `d2e3f4a5b6c7`.

```bash
alembic history | head -5
```

- [ ] **Step 5: Final commit if any fixes were made**

```bash
git add -u
git commit -m "test: fix tests broken by mandatory timing_template_id enforcement

Tests that created parade nights without a template now provide a template
fixture. No test logic was removed — only the missing parameter was added."
```

- [ ] **Step 6: Push**

```bash
git push origin main
```

---

## Plan A complete

Backend API contract delivered:

| Endpoint | Status |
|---|---|
| `SessionAssistantFacilitator` model + migration | Done |
| `ParadeNightTimingSnapshot` model + migration + helper | Done |
| `POST /parade-nights` requires `timing_template_id` | Done |
| `GET /parade-nights/{id}/template-impact` | Done |
| `PATCH /parade-nights/{id}/template` | Done |
| `GET /years/{id}/night-summaries` includes `instructional_periods` + `timing_strip` | Done |
| `POST/DELETE /sessions/{id}/assistants` | Done |
| Conflict engine: assistant double-booking | Done |

**Next:** Plan B (React Planning Workspace) and Plan C (Connected TMS + CEA) can now be implemented in parallel.
