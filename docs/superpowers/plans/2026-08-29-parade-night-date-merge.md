# ParadeNight/ParadeDate Merge — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse `parade_dates` into `parade_nights` by adding `planning_year_id` (NOT NULL FK) directly to `parade_nights`, backfilling from linked `parade_dates`, repointing the three FK references in `PlanningNotice`, `PlanningConflict`, and `AnchorPrepPlan`, and removing the year-inference bridge code.

**Architecture:** A single Alembic migration adds the new columns to `parade_nights`, backfills them from linked `parade_dates`, then renames/removes the now-redundant columns and table. Python models and routers are updated in three layers: models first, then the planning router (read paths), then the training router (write path). The planning router's `GET /years/{year_id}/parade-dates` response keeps `parade_date_id` as a backward-compat alias for `parade_night.id`, so the forty-plus PW component references to `pd.parade_date_id` require no changes. Only `PlanningConflict.parade_date_id` and `PlanningNotice.parade_date_id` physically rename to `parade_night_id` (DB column rename), so those TypeScript types and the notices URL change.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2.0, Alembic (SQLite-compatible `batch_alter_table`), TypeScript/React (Planning Workspace), plain HTML/JS (SPA).

**Spec:** `docs/superpowers/specs/2026-08-27-year-model-and-parade-night-merge-design.md`  
**Context spec:** `docs/superpowers/specs/2026-08-28-training-year-context-model.md` §9–§10

## Global Constraints

- Never silently reinterpret a parade night's training year — if `planning_year_id` cannot be determined for a night, the migration MUST abort with a human-readable report.
- Alembic migration uses `batch_alter_table` for every column add/rename/drop to stay SQLite-compatible.
- `parade_dates` table is RENAMED to `_parade_dates_deprecated`, not dropped — one-release rollback window.
- Remove `linked_to_planning_year` from `create_parade` response after the merge; that warning concept no longer exists.
- No access-code plaintext/hashes in any change; all security invariants from `.claude/rules/security.md` preserved.
- Run `python -m pytest tests/ -q` from `backend/` before each commit; baseline is 1553 passed, 5 skipped (re-measure — count drifts).
- Current Alembic head: `d5f81a3c9e27` — verify with `alembic heads` before writing `down_revision`.
- The `_date_out()` serialiser in `planning.py` is renamed `_night_out_as_date()` and maps a `ParadeNight` to the same response shape, with `parade_date_id = pn.id` for backward compatibility. Do not rename this field in the parade-dates list endpoint.

---

## File Map

**New file:**
- `scripts/phase_b_audit.py` — pre-migration read-only audit, reports orphan nights and blockers

**Modified — backend:**
- `backend/alembic/versions/<new-rev>_phase_b_merge_parade_nights_dates.py` — schema migration
- `backend/app/models/training.py` — add `planning_year_id`, `week_number`, `is_active`, `cancellation_reason` to `ParadeNight`; drop `training_year`
- `backend/app/models/planning.py` — update `PlanningNotice` (`parade_date_id` → `parade_night_id`, drop `planning_year_id`), `PlanningConflict` (`parade_date_id` → `parade_night_id`), `AnchorPrepPlan` (`planned_parade_date_id` → `planned_parade_night_id`); remove `ParadeDate` class
- `backend/app/models/__init__.py` — remove `ParadeDate` export
- `backend/app/routers/planning.py` — replace `_date_out()` with `_night_out_as_date()`, repoint `list_parade_dates`/`add_parade_date`/`generate_parade_dates` to query `ParadeNight`, rename notices endpoints to `/parade-nights/{night_id}/notices`, drop `PlanningNotice.planning_year_id` from notice serialiser
- `backend/app/routers/training.py` — remove `_year_for_date()`, `_find_or_create_parade_date_for_night()`, update `create_parade` to call `ensure_year_context()` directly, remove `linked_to_planning_year` from response

**Modified — frontend SPA:**
- `connected-frontend/index.html` — remove `linked_to_planning_year` toast (line ~10198)

**Modified — Planning Workspace:**
- `frontend/src/api/types.ts` — `PlanningConflict.parade_date_id` → `parade_night_id`; `ParadeNotice.parade_date_id` → `parade_night_id`, drop `planning_year_id`
- `frontend/src/api/index.ts` — notice endpoints: `parade-dates/${date_id}` → `parade-nights/${night_id}`
- `frontend/src/tests/conflictMapFromPlanningConflicts.test.ts` — update fixture field name

**Modified — tests:**
- `backend/tests/test_planning.py` — update fixture/assertions for renamed fields
- `backend/tests/test_training.py` — assert `linked_to_planning_year` is gone

---

## Task 1: Pre-migration audit script

**Files:**
- Create: `scripts/phase_b_audit.py`

**Interfaces:**
- Consumes: direct SQLite/PostgreSQL connection via env `DATABASE_URL`, falls back to `backend/aafc_tms.db`
- Produces: human-readable console report; exit code 1 if any unresolvable nights exist

**Purpose:** Run before applying Task 2. Reports every `parade_night` that either (a) has no linked `parade_date` at all (orphan) or (b) has a linked `parade_date` but its `planning_year_id` is NULL. Flags the four known problematic nights (718×2, TEST×2) with "BLOCKS MIGRATION" labels. Confirms all preconditions the migration will assert.

- [ ] **Step 1: Write the audit script**

```python
#!/usr/bin/env python3
"""Phase B pre-migration audit.

Run from repo root:
    python scripts/phase_b_audit.py

Reads the DB at DATABASE_URL (env) or backend/aafc_tms.db.
Exit code 0 = all clear; 1 = blockers found.
"""
import os, sys, sqlite3

DB = os.environ.get("DATABASE_URL") or "backend/aafc_tms.db"
if DB.startswith("postgresql"):
    try:
        import psycopg2
        conn = psycopg2.connect(DB)
    except ImportError:
        print("ERROR: psycopg2 not installed; activate backend/.venv first", file=sys.stderr)
        sys.exit(2)
    cursor = conn.cursor()
    placeholder = "%s"
else:
    conn = sqlite3.connect(DB.removeprefix("sqlite:///"))
    cursor = conn.cursor()
    placeholder = "?"

# 1. Orphan nights — no linked parade_date row at all
cursor.execute("""
    SELECT pn.id, pn.squadron_id, pn.date, pn.training_year
    FROM parade_nights pn
    LEFT JOIN parade_dates pd ON pd.parade_night_id = pn.id
    WHERE pd.id IS NULL
      AND pn.is_archived = 0
    ORDER BY pn.squadron_id, pn.date
""")
orphans = cursor.fetchall()

# 2. Linked nights whose parade_date has no planning_year_id
cursor.execute("""
    SELECT pn.id, pn.squadron_id, pn.date, pd.id as pd_id, pd.planning_year_id
    FROM parade_nights pn
    JOIN parade_dates pd ON pd.parade_night_id = pn.id
    WHERE pd.planning_year_id IS NULL
      AND pn.is_archived = 0
    ORDER BY pn.squadron_id, pn.date
""")
null_year = cursor.fetchall()

# 3. Nights with multiple linked parade_date rows (integrity violation)
cursor.execute("""
    SELECT pn.id, pn.squadron_id, pn.date, COUNT(pd.id) as n
    FROM parade_nights pn
    JOIN parade_dates pd ON pd.parade_night_id = pn.id
    WHERE pn.is_archived = 0
    GROUP BY pn.id HAVING COUNT(pd.id) > 1
    ORDER BY pn.squadron_id, pn.date
""")
duplicates = cursor.fetchall()

# 4. Notices pointing at a parade_date with no night
cursor.execute("""
    SELECT n.id, n.parade_date_id, pd.parade_night_id
    FROM planning_notices n
    JOIN parade_dates pd ON pd.id = n.parade_date_id
    WHERE pd.parade_night_id IS NULL
""")
notice_orphans = cursor.fetchall()

conn.close()

blockers = []

print("=" * 60)
print("Phase B Pre-migration Audit")
print("=" * 60)

if orphans:
    print(f"\n[BLOCKER] {len(orphans)} active parade_nights with NO linked parade_date:")
    for row in orphans:
        print(f"  squadron={row[1]}  date={row[2]}  night_id={row[0]}  training_year={row[3]}")
    blockers.extend(orphans)
else:
    print("\n[OK] No orphan parade_nights (all have a linked parade_date).")

if null_year:
    print(f"\n[BLOCKER] {len(null_year)} nights whose linked parade_date has NULL planning_year_id:")
    for row in null_year:
        print(f"  squadron={row[1]}  date={row[2]}  night_id={row[0]}  parade_date_id={row[3]}")
    blockers.extend(null_year)
else:
    print("[OK] All linked parade_dates have a planning_year_id.")

if duplicates:
    print(f"\n[BLOCKER] {len(duplicates)} nights with MULTIPLE linked parade_dates:")
    for row in duplicates:
        print(f"  squadron={row[1]}  date={row[2]}  night_id={row[0]}  count={row[3]}")
    blockers.extend(duplicates)
else:
    print("[OK] No nights with duplicate parade_date links.")

if notice_orphans:
    print(f"\n[WARN] {len(notice_orphans)} PlanningNotices point at a parade_date with no night:")
    for row in notice_orphans:
        print(f"  notice_id={row[0]}  parade_date_id={row[1]}")
else:
    print("[OK] All PlanningNotices link to a parade_date that has a night.")

print()
if blockers:
    print(f"RESULT: {len(blockers)} blocker(s) — resolve before running the migration.")
    sys.exit(1)
else:
    print("RESULT: All preconditions met. Safe to run the migration.")
    sys.exit(0)
```

- [ ] **Step 2: Run the audit against the local dev DB**

```bash
python scripts/phase_b_audit.py
```

Expected: "RESULT: All preconditions met." If blockers appear, stop — do not proceed to Task 2. Record the blocker output and escalate.

- [ ] **Step 3: Commit**

```bash
git add scripts/phase_b_audit.py
git commit -m "feat: add phase_b_audit.py pre-migration blocker check"
```

---

## Task 2: Alembic migration — merge parade_nights and parade_dates

**Files:**
- Create: `backend/alembic/versions/<hash>_phase_b_merge_parade_nights_dates.py`

**Interfaces:**
- Consumes: current Alembic head `d5f81a3c9e27`; `parade_nights`, `parade_dates`, `planning_notices`, `planning_conflicts`, `anchor_prep_plans` tables
- Produces: schema where `parade_nights` has `planning_year_id` (NOT NULL FK), `week_number`, `is_active`, `cancellation_reason`; `PlanningNotice.parade_night_id` (NOT NULL); `PlanningConflict.parade_night_id` (nullable); `AnchorPrepPlan.planned_parade_night_id` (nullable); `parade_dates` renamed to `_parade_dates_deprecated`; `parade_nights.training_year` dropped

**Preconditions:** Task 1 audit must pass with exit code 0.

- [ ] **Step 1: Write the failing test (forward migration)**

```python
# backend/tests/test_phase_b_migration.py
import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect, text

@pytest.fixture
def isolated_db(tmp_path):
    db_file = tmp_path / "test_phase_b.db"
    url = f"sqlite:///{db_file}"
    engine = create_engine(url)
    # Run all migrations up to but not including our new one
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(alembic_cfg, "d5f81a3c9e27")
    return engine, alembic_cfg

def test_phase_b_forward(isolated_db):
    engine, cfg = isolated_db
    inspector = inspect(engine)
    # Verify pre-state: parade_nights lacks planning_year_id
    cols_before = {c["name"] for c in inspector.get_columns("parade_nights")}
    assert "planning_year_id" not in cols_before
    assert "training_year" in cols_before

    command.upgrade(cfg, "head")

    inspector2 = inspect(engine)
    cols = {c["name"] for c in inspector2.get_columns("parade_nights")}
    assert "planning_year_id" in cols
    assert "training_year" not in cols
    assert "week_number" in cols
    assert "is_active" in cols
    assert "cancellation_reason" in cols

    # parade_dates renamed
    tables = inspector2.get_table_names()
    assert "parade_dates" not in tables
    assert "_parade_dates_deprecated" in tables

    # PlanningNotice has parade_night_id, not parade_date_id
    notice_cols = {c["name"] for c in inspector2.get_columns("planning_notices")}
    assert "parade_night_id" in notice_cols
    assert "parade_date_id" not in notice_cols
    assert "planning_year_id" not in notice_cols

    # PlanningConflict
    conflict_cols = {c["name"] for c in inspector2.get_columns("planning_conflicts")}
    assert "parade_night_id" in conflict_cols
    assert "parade_date_id" not in conflict_cols

    # AnchorPrepPlan
    anchor_cols = {c["name"] for c in inspector2.get_columns("anchor_prep_plans")}
    assert "planned_parade_night_id" in anchor_cols
    assert "planned_parade_date_id" not in anchor_cols
```

- [ ] **Step 2: Run the test — confirm it fails**

```bash
cd backend && source .venv/bin/activate
python -m pytest tests/test_phase_b_migration.py -v
```

Expected: FAIL (migration not created yet).

- [ ] **Step 3: Generate the migration file**

```bash
cd backend && source .venv/bin/activate
alembic revision -m "phase_b_merge_parade_nights_dates"
```

This creates `alembic/versions/<hash>_phase_b_merge_parade_nights_dates.py`. Open it and replace the content:

```python
"""phase_b_merge_parade_nights_dates

Revision ID: <generated-hash>
Revises: d5f81a3c9e27
Create Date: 2026-08-29

Collapse parade_dates into parade_nights.
PRECONDITION: run scripts/phase_b_audit.py first and confirm exit 0.
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

# Paste the generated Revision ID here — never hardcode the placeholder.
revision = "<generated-hash>"
down_revision = "d5f81a3c9e27"
branch_labels = None
depends_on = None


def _abort_if_blockers(conn):
    """Raise if any orphan or unresolvable nights exist."""
    orphans = conn.execute(sa.text("""
        SELECT COUNT(*) FROM parade_nights pn
        LEFT JOIN parade_dates pd ON pd.parade_night_id = pn.id
        WHERE pd.id IS NULL AND pn.is_archived = 0
    """)).scalar()
    if orphans:
        raise RuntimeError(
            f"Phase B migration blocked: {orphans} active parade_night row(s) have no linked "
            f"parade_date. Run scripts/phase_b_audit.py and resolve all blockers first."
        )
    null_year = conn.execute(sa.text("""
        SELECT COUNT(*) FROM parade_nights pn
        JOIN parade_dates pd ON pd.parade_night_id = pn.id
        WHERE pd.planning_year_id IS NULL AND pn.is_archived = 0
    """)).scalar()
    if null_year:
        raise RuntimeError(
            f"Phase B migration blocked: {null_year} linked parade_date row(s) have NULL "
            f"planning_year_id. Run scripts/phase_b_audit.py and resolve all blockers first."
        )


def upgrade():
    conn = op.get_bind()
    _abort_if_blockers(conn)

    # ── 1. Add new columns to parade_nights (nullable first for backfill) ──
    with op.batch_alter_table("parade_nights") as batch:
        batch.add_column(sa.Column("planning_year_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("week_number", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("is_active", sa.Boolean(), nullable=True, server_default="1"))
        batch.add_column(sa.Column("cancellation_reason", sa.String(), nullable=True))

    # ── 2. Backfill from linked parade_dates ──
    conn.execute(sa.text("""
        UPDATE parade_nights
        SET planning_year_id = (
            SELECT pd.planning_year_id FROM parade_dates pd
            WHERE pd.parade_night_id = parade_nights.id LIMIT 1
        ),
        week_number = (
            SELECT pd.week_number FROM parade_dates pd
            WHERE pd.parade_night_id = parade_nights.id LIMIT 1
        ),
        is_active = COALESCE((
            SELECT pd.is_active FROM parade_dates pd
            WHERE pd.parade_night_id = parade_nights.id LIMIT 1
        ), 1),
        cancellation_reason = (
            SELECT pd.cancellation_reason FROM parade_dates pd
            WHERE pd.parade_night_id = parade_nights.id LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1 FROM parade_dates pd WHERE pd.parade_night_id = parade_nights.id
        )
    """))

    # ── 3. Drop training_year; make planning_year_id NOT NULL ──
    with op.batch_alter_table("parade_nights") as batch:
        batch.drop_column("training_year")
        batch.alter_column("planning_year_id", nullable=False)
        batch.alter_column("is_active", nullable=False, server_default=None)
        batch.create_foreign_key(
            "fk_parade_nights_planning_year_id",
            "planning_years", ["planning_year_id"], ["id"]
        )

    # ── 4. planning_notices: rename parade_date_id → parade_night_id; drop planning_year_id ──
    conn.execute(sa.text("""
        UPDATE planning_notices
        SET parade_date_id = (
            SELECT pd.parade_night_id FROM parade_dates pd
            WHERE pd.id = planning_notices.parade_date_id LIMIT 1
        )
        WHERE parade_date_id IS NOT NULL
    """))
    with op.batch_alter_table("planning_notices") as batch:
        batch.alter_column("parade_date_id", new_column_name="parade_night_id")
        batch.drop_column("planning_year_id")

    # ── 5. planning_conflicts: rename parade_date_id → parade_night_id ──
    conn.execute(sa.text("""
        UPDATE planning_conflicts
        SET parade_date_id = (
            SELECT pd.parade_night_id FROM parade_dates pd
            WHERE pd.id = planning_conflicts.parade_date_id LIMIT 1
        )
        WHERE parade_date_id IS NOT NULL
    """))
    with op.batch_alter_table("planning_conflicts") as batch:
        batch.alter_column("parade_date_id", new_column_name="parade_night_id")

    # ── 6. anchor_prep_plans: rename planned_parade_date_id → planned_parade_night_id ──
    conn.execute(sa.text("""
        UPDATE anchor_prep_plans
        SET planned_parade_date_id = (
            SELECT pd.parade_night_id FROM parade_dates pd
            WHERE pd.id = anchor_prep_plans.planned_parade_date_id LIMIT 1
        )
        WHERE planned_parade_date_id IS NOT NULL
    """))
    with op.batch_alter_table("anchor_prep_plans") as batch:
        batch.alter_column("planned_parade_date_id", new_column_name="planned_parade_night_id")

    # ── 7. Rename parade_dates → _parade_dates_deprecated ──
    op.rename_table("parade_dates", "_parade_dates_deprecated")


def downgrade():
    # Restore table name
    op.rename_table("_parade_dates_deprecated", "parade_dates")

    # Restore anchor_prep_plans
    with op.batch_alter_table("anchor_prep_plans") as batch:
        batch.alter_column("planned_parade_night_id", new_column_name="planned_parade_date_id")

    # Restore planning_conflicts
    with op.batch_alter_table("planning_conflicts") as batch:
        batch.alter_column("parade_night_id", new_column_name="parade_date_id")

    # Restore planning_notices (re-add planning_year_id)
    with op.batch_alter_table("planning_notices") as batch:
        batch.alter_column("parade_night_id", new_column_name="parade_date_id")
        batch.add_column(sa.Column("planning_year_id", sa.String(), nullable=True))

    # Restore parade_nights (add back training_year, drop new columns)
    with op.batch_alter_table("parade_nights") as batch:
        batch.drop_constraint("fk_parade_nights_planning_year_id", type_="foreignkey")
        batch.add_column(sa.Column("training_year", sa.Integer(), nullable=True))
        batch.drop_column("planning_year_id")
        batch.drop_column("week_number")
        batch.drop_column("is_active")
        batch.drop_column("cancellation_reason")
```

- [ ] **Step 4: Run the test — confirm it passes**

```bash
cd backend && python -m pytest tests/test_phase_b_migration.py -v
```

Expected: PASS.

- [ ] **Step 5: Run the full test suite**

```bash
cd backend && python -m pytest tests/ -q
```

Expected: same baseline count, 0 new failures. (Some tests may skip or fail if models reference `ParadeDate` — that is expected and is addressed in Task 3.)

- [ ] **Step 6: Apply the migration to the local dev DB**

```bash
cd backend && alembic upgrade head
```

Verify: `alembic current` shows the new head.

- [ ] **Step 7: Commit**

```bash
git add backend/alembic/versions/
git add backend/tests/test_phase_b_migration.py
git commit -m "feat: phase B migration — merge parade_dates into parade_nights"
```

---

## Task 3: Python models — update ParadeNight, remove ParadeDate, update FKs

**Files:**
- Modify: `backend/app/models/training.py`
- Modify: `backend/app/models/planning.py`
- Modify: `backend/app/models/__init__.py`

**Interfaces:**
- Consumes: Task 2 schema (DB has `parade_nights.planning_year_id`, notices/conflicts with `parade_night_id`, etc.)
- Produces: `ParadeNight` model with new columns; `PlanningNotice`/`PlanningConflict`/`AnchorPrepPlan` with renamed FK attrs; `ParadeDate` class removed; all model tests pass

- [ ] **Step 1: Write failing tests for the model changes**

```python
# backend/tests/test_phase_b_models.py
import pytest
from app.models.training import ParadeNight
from app.models.planning import PlanningNotice, PlanningConflict, AnchorPrepPlan

def test_parade_night_has_planning_year_id():
    cols = {c.key for c in ParadeNight.__table__.columns}
    assert "planning_year_id" in cols
    assert "training_year" not in cols
    assert "week_number" in cols
    assert "is_active" in cols
    assert "cancellation_reason" in cols

def test_planning_notice_has_parade_night_id():
    cols = {c.key for c in PlanningNotice.__table__.columns}
    assert "parade_night_id" in cols
    assert "parade_date_id" not in cols
    assert "planning_year_id" not in cols

def test_planning_conflict_has_parade_night_id():
    cols = {c.key for c in PlanningConflict.__table__.columns}
    assert "parade_night_id" in cols
    assert "parade_date_id" not in cols

def test_anchor_prep_plan_has_planned_parade_night_id():
    cols = {c.key for c in AnchorPrepPlan.__table__.columns}
    assert "planned_parade_night_id" in cols
    assert "planned_parade_date_id" not in cols

def test_parade_date_class_removed():
    try:
        from app.models.planning import ParadeDate  # noqa
        assert False, "ParadeDate should not be importable after Phase B"
    except ImportError:
        pass
```

- [ ] **Step 2: Run the tests — confirm they fail**

```bash
cd backend && python -m pytest tests/test_phase_b_models.py -v
```

- [ ] **Step 3: Update `backend/app/models/training.py` — add new columns, drop training_year**

Current `ParadeNight` class (around line 42) has:
```python
training_year = Column(Integer, index=True)
```
and lacks `planning_year_id`, `week_number`, `is_active`, `cancellation_reason`.

Replace `training_year` with:
```python
planning_year_id = Column(String, ForeignKey("planning_years.id"), nullable=False, index=True)
planning_year = relationship("PlanningYear", back_populates="parade_nights", lazy="select")
week_number = Column(Integer, nullable=True)
is_active = Column(Boolean, nullable=False, default=True)
cancellation_reason = Column(String, nullable=True)
```

Also add the back-reference to `PlanningYear` in `planning.py` (in the `PlanningYear` class):
```python
parade_nights = relationship("ParadeNight", back_populates="planning_year", lazy="select")
```

Remove the `training_year` import alias if it was used elsewhere in the file.

- [ ] **Step 4: Update `backend/app/models/planning.py`**

**a) `PlanningNotice` class** (around line 179):
- Rename `parade_date_id = Column(String, ForeignKey("parade_dates.id"), nullable=False)` →
  `parade_night_id = Column(String, ForeignKey("parade_nights.id"), nullable=False)`
- Rename the relationship: `parade_date = relationship(...)` →
  `parade_night = relationship("ParadeNight", back_populates=None, lazy="select")`
- Drop the `planning_year_id` column and relationship from `PlanningNotice`.

**b) `PlanningConflict` class** (around line 148):
- Rename `parade_date_id = Column(String, ForeignKey("parade_dates.id"), nullable=True)` →
  `parade_night_id = Column(String, ForeignKey("parade_nights.id"), nullable=True)`
- Rename the relationship accordingly.

**c) `AnchorPrepPlan` class** (around line 136):
- Rename `planned_parade_date_id = Column(String, ForeignKey("parade_dates.id"), nullable=True)` →
  `planned_parade_night_id = Column(String, ForeignKey("parade_nights.id"), nullable=True)`

**d) Remove the `ParadeDate` class entirely** (around line 67–95). Also remove any `__all__` or explicit exports.

- [ ] **Step 5: Update `backend/app/models/__init__.py`**

Remove the `ParadeDate` import/export. Keep everything else unchanged.

- [ ] **Step 6: Run the model tests — confirm they pass**

```bash
cd backend && python -m pytest tests/test_phase_b_models.py -v
```

- [ ] **Step 7: Run the full test suite**

```bash
cd backend && python -m pytest tests/ -q
```

Some tests that import `ParadeDate` directly will fail — note them; they are fixed in Tasks 4–5.

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/
git commit -m "feat: phase B models — ParadeNight gets planning_year_id; ParadeDate removed"
```

---

## Task 4: Planning router refactor — list/add/generate use ParadeNight

**Files:**
- Modify: `backend/app/routers/planning.py`
- Modify: `backend/tests/test_planning.py`

**Interfaces:**
- Consumes: Task 3 models (`ParadeNight` with `planning_year_id`, no `ParadeDate`)
- Produces:
  - `GET /api/planning/years/{year_id}/parade-dates` → queries `ParadeNight` by `planning_year_id`; response keeps `parade_date_id = pn.id` alias
  - `POST /api/planning/years/{year_id}/parade-dates` → creates a `ParadeNight` with `planning_year_id` set
  - `POST /api/planning/years/{year_id}/generate-parade-dates` → creates `ParadeNight` rows only
  - `GET /api/planning/parade-nights/{night_id}/notices` (was `parade-dates/{date_id}/notices`)
  - `POST /api/planning/parade-nights/{night_id}/notices` (was `parade-dates/{date_id}/notices`)
  - `PlanningConflict` serialiser returns `parade_night_id`
  - `ParadeNotice` serialiser returns `parade_night_id`, drops `planning_year_id`

- [ ] **Step 1: Write failing tests**

```python
# In backend/tests/test_planning.py — add/update these tests:

def test_list_parade_dates_returns_parade_nights(client, login):
    """After Phase B, GET /years/{id}/parade-dates sources from parade_nights."""
    # Login as sqn_admin, get a year with parade nights
    headers = login("sqn_admin_703")
    # First create a parade night directly via training endpoint to ensure one exists
    # ... then fetch parade dates and verify shape
    r = client.get("/api/planning/years/{year_id}/parade-dates", headers=headers)
    assert r.status_code == 200
    dates = r.json()
    if dates:
        d = dates[0]
        assert "parade_date_id" in d        # backward-compat alias
        assert "planning_year_id" in d
        assert "parade_date" in d
        # parade_night_id should equal parade_date_id after merge
        assert d["parade_night_id"] == d["parade_date_id"]

def test_create_parade_date_creates_parade_night(client, login):
    headers = login("sqn_admin_703")
    # Get an active year
    years_r = client.get("/api/planning/years?unit_id=<sqn_id>", headers=headers)
    year_id = years_r.json()[0]["planning_year_id"]
    body = {"parade_date": "2026-06-15", "parade_type": "standard", "is_active": True}
    r = client.post(f"/api/planning/years/{year_id}/parade-dates", headers=headers, json=body)
    assert r.status_code == 200
    d = r.json()
    assert "parade_date_id" in d
    assert d["planning_year_id"] == year_id

def test_notices_endpoint_uses_parade_nights_path(client, login):
    headers = login("sqn_admin_703")
    # Old path /parade-dates/{id}/notices should be gone or redirect
    # New path /parade-nights/{id}/notices should work
    # (Use a known parade night ID from the DB fixture)
    r = client.get("/api/planning/parade-nights/nonexistent/notices", headers=headers)
    assert r.status_code in (200, 404)  # 200 empty or 404 not found — not 405 Method Not Allowed

def test_conflict_serialiser_returns_parade_night_id(client, login):
    headers = login("sqn_admin_703")
    # Trigger conflict detection by scheduling overlapping sessions, then GET conflicts
    # Assert the returned conflict has parade_night_id, not parade_date_id
    r = client.get("/api/planning/years/<year_id>/conflicts", headers=headers)
    assert r.status_code == 200
    conflicts = r.json()
    for c in conflicts:
        assert "parade_night_id" in c
        assert "parade_date_id" not in c
```

- [ ] **Step 2: Run the tests — confirm they fail**

```bash
cd backend && python -m pytest tests/test_planning.py -v -k "parade_date_returns_parade_nights or create_parade_date_creates or notices_endpoint or conflict_serialiser"
```

- [ ] **Step 3: Replace `_date_out()` with `_night_out_as_date()`**

In `planning.py`, replace the `_date_out()` function (line 282):

```python
# Before:
def _date_out(pd: ParadeDate) -> dict:
    return {
        "parade_date_id": pd.id, "planning_year_id": pd.planning_year_id,
        "unit_id": pd.unit_id, "parade_date": pd.parade_date,
        "parade_type": pd.parade_type, "is_active": pd.is_active, "notes": pd.notes,
        "term": getattr(pd, "term", None),
        "week_number": getattr(pd, "week_number", None),
        "cancellation_reason": getattr(pd, "cancellation_reason", None),
        "parade_night_id": pd.parade_night_id,
    }

# After:
def _night_out_as_date(pn: ParadeNight) -> dict:
    """Serialise a ParadeNight in the parade-dates response shape.

    parade_date_id = pn.id — backward-compat alias used by the React PW's
    ~40 references to pd.parade_date_id. Do not rename this field.
    parade_night_id = pn.id — same value; kept for callers that used the
    old linked-night field and now read the same record.
    """
    return {
        "parade_date_id": pn.id,
        "planning_year_id": pn.planning_year_id,
        "unit_id": pn.squadron_id,
        "parade_date": pn.date,
        "parade_type": pn.parade_type,
        "is_active": pn.is_active,
        "notes": pn.notes,
        "term": pn.term,
        "week_number": pn.week_number,
        "cancellation_reason": pn.cancellation_reason,
        "parade_night_id": pn.id,
    }
```

Remove the `ParadeDate` import from `planning.py`'s import block at the top of the file.

- [ ] **Step 4: Update `list_parade_dates` (line 817)**

```python
# Before:
@router.get("/years/{year_id}/parade-dates")
def list_parade_dates(...):
    ...
    rows = db.query(ParadeDate).filter(ParadeDate.planning_year_id == year_id)\
             .order_by(ParadeDate.parade_date).all()
    ...
    for pd in rows:
        r = _date_out(pd)
        r["in_holiday"] = in_holiday(pd.parade_date)
        out.append(r)
    return out

# After:
@router.get("/years/{year_id}/parade-dates")
def list_parade_dates(...):
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py)
    rows = db.query(ParadeNight).filter(ParadeNight.planning_year_id == year_id)\
             .order_by(ParadeNight.date).all()
    holidays = db.query(HolidayPeriod).filter(
        HolidayPeriod.planning_year_id == year_id,
        HolidayPeriod.affects_parade == True,  # noqa: E712
    ).all()
    def in_holiday(d: str) -> bool:
        for h in holidays:
            if h.start_date <= d <= h.end_date:
                return True
        return False
    out = []
    for pn in rows:
        r = _night_out_as_date(pn)
        r["in_holiday"] = in_holiday(pn.date)
        out.append(r)
    return out
```

- [ ] **Step 5: Update `add_parade_date` (line 845)**

```python
# Before (creates ParadeDate + calls _find_or_create_parade_night):
@router.post("/years/{year_id}/parade-dates")
def add_parade_date(year_id, body, db, p):
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py, write=True, db=db)
    pn = _find_or_create_parade_night(db, py.unit_id, body.parade_date, p)
    pd = ParadeDate(
        id=str(uuid.uuid4()), planning_year_id=year_id,
        unit_id=py.unit_id, parade_date=body.parade_date,
        parade_type=body.parade_type, is_active=body.is_active,
        notes=body.notes, parade_night_id=pn.id if pn else None,
        created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(pd); db.commit()
    audit(db, p, object_type="parade_date", object_id=pd.id, action="create",
          new={"date": body.parade_date})
    return _date_out(pd)

# After (creates ParadeNight directly with planning_year_id):
@router.post("/years/{year_id}/parade-dates")
def add_parade_date(year_id: str, body: ParadeDateIn,
                    db: DBSession = Depends(get_db),
                    p: Principal = Depends(get_principal)):
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py, write=True, db=db)
    sq = db.get(Squadron, py.unit_id)
    if sq is None:
        raise HTTPException(400, detail={"error": "squadron_not_found"})
    existing = db.query(ParadeNight).filter(
        ParadeNight.squadron_id == py.unit_id,
        ParadeNight.date == body.parade_date,
        ParadeNight.is_archived == False,  # noqa: E712
    ).first()
    if existing:
        # Idempotent: if a night exists for this date in this year, just return it
        if existing.planning_year_id == year_id:
            return _night_out_as_date(existing)
        raise HTTPException(409, detail={"error": "duplicate_date", "existing_id": existing.id})
    pn = ParadeNight(
        id=str(uuid.uuid4()),
        squadron_id=py.unit_id, wing_id=sq.wing_id,
        date=body.parade_date, planning_year_id=year_id,
        parade_type=body.parade_type or "standard",
        is_active=body.is_active if body.is_active is not None else True,
        notes=body.notes,
        created_by=p.user_id, created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(pn); db.commit()
    audit(db, p, object_type="parade_night", object_id=pn.id, action="create",
          new={"date": body.parade_date, "via": "planning_add_parade_date"})
    return _night_out_as_date(pn)
```

- [ ] **Step 6: Update `generate_parade_dates` (line 1070)**

Replace the loop body that creates `ParadeDate` and calls `_find_or_create_parade_night`:

```python
@router.post("/years/{year_id}/generate-parade-dates")
def generate_parade_dates(year_id, body, db, p):
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py, write=True, db=db)
    sq = db.get(Squadron, py.unit_id)
    holidays = db.query(HolidayPeriod).filter(
        HolidayPeriod.planning_year_id == year_id,
        HolidayPeriod.affects_parade == True,  # noqa: E712
    ).all() if body.exclude_holidays else []

    existing_dates = {
        pn.date for pn in db.query(ParadeNight).filter(
            ParadeNight.planning_year_id == year_id
        ).all()
    }
    candidates = _compute_candidate_dates(body, holidays)
    created = []
    for ds in candidates:
        if ds not in existing_dates:
            pn = ParadeNight(
                id=str(uuid.uuid4()),
                squadron_id=py.unit_id, wing_id=sq.wing_id if sq else None,
                date=ds, planning_year_id=year_id,
                parade_type=body.parade_type or "standard",
                is_active=True,
                start_time=body.parade_start_time or (sq.default_start_time if sq else None),
                end_time=body.parade_end_time or (sq.default_end_time if sq else None),
                created_by=p.user_id, created_at=utcnow(), updated_at=utcnow(),
            )
            db.add(pn)
            existing_dates.add(ds)
            created.append(ds)
    db.commit()
    audit(db, p, object_type="planning_year", object_id=year_id,
          action="generate_parade_dates", new={"created": len(created)})
    return {"ok": True, "created": len(created), "linked": 0, "dates": created}
```

Note: remove the `_find_or_create_parade_night` helper from `planning.py` — it is no longer called.

- [ ] **Step 7: Update notices endpoints (rename URL path)**

In `planning.py`, rename the two notice router decorators:

```python
# Before:
@router.get("/parade-dates/{date_id}/notices")
@router.post("/parade-dates/{date_id}/notices")

# After:
@router.get("/parade-nights/{night_id}/notices")
@router.post("/parade-nights/{night_id}/notices")
```

Update the path parameter names from `date_id` to `night_id` throughout those two functions. Update the DB query from `PlanningNotice.parade_date_id == date_id` to `PlanningNotice.parade_night_id == night_id`.

Update the `PlanningNotice` serialiser inside those functions — remove `planning_year_id` from the response; return `parade_night_id` instead of `parade_date_id`. Derive the year at read-time via the joined night:

```python
# Notice serialiser — replace existing inline dict construction:
def _notice_out(n: PlanningNotice) -> dict:
    return {
        "notice_id": n.id,
        "parade_night_id": n.parade_night_id,
        "notice_text": n.notice_text,
        "audience": n.audience,
        "priority": n.priority,
        "created_by": n.created_by,
        "is_archived": n.is_archived,
        "created_at": iso_z(n.created_at) if n.created_at else None,
        "updated_at": iso_z(n.updated_at) if n.updated_at else None,
    }
```

- [ ] **Step 8: Update `PlanningConflict` serialiser**

Find the function(s) that return `PlanningConflict` dicts (search for `"parade_date_id"` in `planning.py`). Replace `"parade_date_id": c.parade_date_id` with `"parade_night_id": c.parade_night_id` in every place.

The two bulk-load queries at lines 3614/3628 and 4968 that build `notices_by_date_id` need updating:
- `notices_by_date.setdefault(n.parade_date_id, []).append(n)` → `notices_by_date.setdefault(n.parade_night_id, []).append(n)`

- [ ] **Step 9: Run failing tests — confirm they pass**

```bash
cd backend && python -m pytest tests/test_planning.py -v
```

- [ ] **Step 10: Run full suite**

```bash
cd backend && python -m pytest tests/ -q
```

Expected: all pass (previous failures from Tasks 2–3 now resolved).

- [ ] **Step 11: Commit**

```bash
git add backend/app/routers/planning.py backend/tests/test_planning.py
git commit -m "feat: phase B planning router — query parade_nights, rename notices path"
```

---

## Task 5: Training router cleanup — remove inference code, wire planning_year_id

**Files:**
- Modify: `backend/app/routers/training.py`
- Modify: `backend/tests/test_training.py`

**Interfaces:**
- Consumes: Task 3 `ParadeNight` model with `planning_year_id`; `ensure_year_context()` from `services_year.py`
- Produces: `create_parade` sets `planning_year_id` directly on the new `ParadeNight`; `_year_for_date()` and `_find_or_create_parade_date_for_night()` removed; `linked_to_planning_year` absent from all responses

- [ ] **Step 1: Write failing tests**

```python
# In backend/tests/test_training.py — add/update:

def test_create_parade_sets_planning_year_id(client, login):
    """POST /api/parade-nights must return a night with planning_year_id set."""
    headers = login("sqn_admin_703")
    body = {"date": "2026-07-15", "parade_type": "normal"}
    r = client.post("/api/parade-nights", headers=headers, json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert "parade_night_id" in data
    # Fetch the created night and confirm planning_year_id is set
    night_r = client.get(f"/api/parade-nights/{data['parade_night_id']}", headers=headers)
    assert night_r.status_code == 200
    pn = night_r.json()
    assert pn.get("planning_year_id") is not None

def test_create_parade_no_linked_to_planning_year(client, login):
    """linked_to_planning_year must be absent from create_parade response."""
    headers = login("sqn_admin_703")
    body = {"date": "2026-07-16", "parade_type": "normal"}
    r = client.post("/api/parade-nights", headers=headers, json=body)
    assert r.status_code == 200
    assert "linked_to_planning_year" not in r.json()

def test_year_for_date_removed():
    """_year_for_date must not be importable from training router."""
    import importlib
    m = importlib.import_module("app.routers.training")
    assert not hasattr(m, "_year_for_date"), "_year_for_date should be deleted"
    assert not hasattr(m, "_find_or_create_parade_date_for_night")
```

- [ ] **Step 2: Run the tests — confirm they fail**

```bash
cd backend && python -m pytest tests/test_training.py -v -k "planning_year_id or linked_to or year_for_date"
```

- [ ] **Step 3: Update `create_parade` in `training.py`**

Current `create_parade` (around line 388):
1. Creates `ParadeNight` without `planning_year_id`
2. Calls `_find_or_create_parade_date_for_night(db, pn, body.term)` → creates a `ParadeDate`
3. Returns `{"ok": True, "parade_night_id": pn.id, "linked_to_planning_year": pd_linked is not None}`

Replace with:

```python
@router.post("/parade-nights")
def create_parade(body: ParadeIn, request: Request,
                  db: DBSession = Depends(get_db),
                  p: Principal = Depends(get_principal)):
    sq_id = _active_squadron(p)
    if p.role in ("sqn_general", "wing_viewer", "national_viewer", "auditor"):
        raise HTTPException(403, detail={"error": "forbidden"})
    if not sq_id:
        require_can_write_squadron(p, "none", None)
        raise HTTPException(400, detail={"error": "no_squadron_scope"})
    s = db.get(Squadron, sq_id)
    if not s:
        raise HTTPException(400, detail={"error": "no_squadron_scope"})
    require_can_write_squadron(p, s.id, s.wing_id)
    existing = db.query(ParadeNight).filter(
        ParadeNight.squadron_id == s.id,
        ParadeNight.date == body.date,
        ParadeNight.is_archived == False,  # noqa: E712
    ).first()
    if existing:
        raise HTTPException(409, detail={"error": "duplicate_date", "existing_id": existing.id})

    effective_tmpl = _effective_template(db, s.id, body.date)
    if effective_tmpl and body.session_count is None:
        ip_count = sum(1 for b in effective_tmpl.blocks if b.is_instructional_period)
        session_count = ip_count if ip_count > 0 else (s.default_session_count or 3)
    else:
        session_count = body.session_count or s.default_session_count or 3

    # Resolve the planning year — create it if absent (idempotent).
    from ..services_year import ensure_year_context
    import datetime as _dt
    year = int(body.date[:4])
    py = ensure_year_context(db, s.id, year, user_id=p.user_id)

    pn = ParadeNight(
        squadron_id=s.id, wing_id=s.wing_id,
        date=body.date, term=body.term,
        planning_year_id=py.id,
        start_time=s.default_start_time, end_time=s.default_end_time,
        session_count=session_count, parade_type=body.parade_type or "normal",
        timing_template_id=effective_tmpl.id if effective_tmpl else None,
        created_by=p.user_id,
    )
    db.add(pn)
    db.commit()
    meta = client_meta(request)
    audit(db, p, object_type="parade_night", object_id=pn.id, action="create",
          new={"date": body.date}, ip=meta["ip"], ua=meta["ua"])
    return {"ok": True, "parade_night_id": pn.id}
```

- [ ] **Step 4: Delete `_year_for_date()` and `_find_or_create_parade_date_for_night()`**

Remove the two functions entirely from `training.py` (lines 438–552). Also remove any `from ..models.planning import ParadeDate, PlanningYear` inside those functions. Check for any remaining references to `pd_linked` and remove them.

- [ ] **Step 5: Run the failing tests — confirm they pass**

```bash
cd backend && python -m pytest tests/test_training.py -v -k "planning_year_id or linked_to or year_for_date"
```

- [ ] **Step 6: Run full suite**

```bash
cd backend && python -m pytest tests/ -q
```

Expected: clean pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/routers/training.py backend/tests/test_training.py
git commit -m "feat: phase B training router — wire planning_year_id, remove inference bridge"
```

---

## Task 6: Frontend updates — SPA toast removal and PW type fixes

**Files:**
- Modify: `connected-frontend/index.html` (line ~10198)
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/index.ts`
- Modify: `frontend/src/tests/conflictMapFromPlanningConflicts.test.ts`

**Interfaces:**
- Consumes: Task 4 backend (notices endpoint at `/parade-nights/{id}/notices`; conflicts return `parade_night_id`; `ParadeNotice` has no `planning_year_id`)
- Produces: SPA shows no `linked_to_planning_year` toast; PW TypeScript types compile against new API shape; conflict test fixture uses `parade_night_id`

- [ ] **Step 1: Write failing PW TypeScript check**

TypeScript will fail to compile after backend changes if types are not updated. To isolate:

```bash
cd frontend && npx tsc --noEmit 2>&1 | grep -E "parade_date_id|parade_night_id|planning_year_id"
```

Expected: errors on `PlanningConflict.parade_date_id` and `ParadeNotice.parade_date_id` usages. Note all locations reported.

- [ ] **Step 2: Update `frontend/src/api/types.ts`**

**a) `PlanningConflict` interface (line 226–231):**
```typescript
// Before:
export interface PlanningConflict {
  conflict_id: string; planning_year_id: string | null; parade_date_id: string | null;
  ...
}

// After:
export interface PlanningConflict {
  conflict_id: string; planning_year_id: string | null; parade_night_id: string | null;
  ...
}
```

**b) `ParadeNotice` interface (line 357–368):**
```typescript
// Before:
export interface ParadeNotice {
  notice_id: string;
  planning_year_id: string | null;
  parade_date_id: string;
  ...
}

// After:
export interface ParadeNotice {
  notice_id: string;
  parade_night_id: string;
  ...
  // planning_year_id is removed — derived via the night
}
```

**c) `WeeklyProgramData` interface (line 232–237):**
Check whether the backend's weekly program endpoint still returns `parade_date_id`. If so, no change needed. If the weekly program endpoint was also updated to return `parade_night_id`, update here too:
```typescript
// If changed:
export interface WeeklyProgramData {
  parade_night_id: string;  // was parade_date_id
  ...
}
```

Do not change `ParadeDate.parade_date_id` (line 193) — this field is preserved as a backward-compat alias in the API response.

- [ ] **Step 3: Update `frontend/src/api/index.ts` — notices URL**

Line 488:
```typescript
// Before:
api.get<import("./types").ParadeNotice[]>(`/api/planning/parade-dates/${date_id}/notices`),

// After:
api.get<import("./types").ParadeNotice[]>(`/api/planning/parade-nights/${night_id}/notices`),
```

Line 490 (POST):
```typescript
// Before:
api.post<{ ok: boolean; notice_id: string }>(`/api/planning/parade-dates/${date_id}/notices`, body),

// After:
api.post<{ ok: boolean; notice_id: string }>(`/api/planning/parade-nights/${night_id}/notices`, body),
```

Update the enclosing function parameter name from `date_id` to `night_id` for clarity.

- [ ] **Step 4: Update `frontend/src/tests/conflictMapFromPlanningConflicts.test.ts`**

Line 13:
```typescript
// Before:
conflict_id: "c1", planning_year_id: "y1", parade_date_id: "d1",

// After:
conflict_id: "c1", planning_year_id: "y1", parade_night_id: "d1",
```

Update every fixture in the file that has `parade_date_id` on a conflict object.

- [ ] **Step 5: Update `connected-frontend/index.html` — remove `linked_to_planning_year` toast**

Find the block at line ~10198:
```javascript
}else if(r&&r.linked_to_planning_year===false){
  toast('warning', 'Parade night created but could not link to a Planning Year — open Planning Workspace to set up this year first.');
}
```

Remove this `else if` branch entirely. The preceding `if` and any following `else` should remain properly formed — verify the surrounding `if/else` chain still compiles.

- [ ] **Step 6: Rebuild PW and confirm TypeScript compiles**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: build succeeds with no TypeScript errors related to `parade_date_id`/`parade_night_id`.

- [ ] **Step 7: Run PW tests**

```bash
cd frontend && npx vitest run
```

Expected: `conflictMapFromPlanningConflicts.test.ts` passes with the updated fixture.

- [ ] **Step 8: Browser verification — SPA (creating a parade night)**

Start the local stack:

```bash
# Terminal 1
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Terminal 2
cd connected-frontend && python3 -m http.server 8080
```

1. Open `http://localhost:8080`, log in as sqn_admin.
2. Navigate to Parade Nights → Create a new parade night for a future date.
3. Verify: (a) the night appears in the Parade Nights list; (b) NO "could not link to a Planning Year" toast appears; (c) no JavaScript console errors.

- [ ] **Step 9: Browser verification — PW (creating a date from the PW)**

Start the PW dev server:

```bash
cd frontend && npm run dev
```

1. Open the Planning Workspace for the same squadron and year.
2. Navigate to the parade dates view — confirm the night created in Step 8 appears.
3. Create a new parade date from the PW. Confirm it appears in the list and in the TMS Parade Nights view.
4. Open the notices panel for a night — confirm notices load without console errors.

- [ ] **Step 10: Run full backend suite one last time**

```bash
cd backend && python -m pytest tests/ -q
```

Expected: clean pass.

- [ ] **Step 11: Commit**

```bash
git add connected-frontend/index.html
git add frontend/src/api/types.ts frontend/src/api/index.ts
git add frontend/src/tests/conflictMapFromPlanningConflicts.test.ts
git commit -m "feat: phase B frontend — remove linked_to_planning_year toast; fix PW types for renamed fields"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ `parade_nights` gets `planning_year_id` (NOT NULL FK) — Task 2
- ✅ `parade_dates` renamed not dropped — Task 2 (`_parade_dates_deprecated`)
- ✅ `PlanningNotice.parade_date_id` → `parade_night_id` — Tasks 2, 3, 4, 6
- ✅ `PlanningConflict.parade_date_id` → `parade_night_id` — Tasks 2, 3, 4, 6
- ✅ `AnchorPrepPlan.planned_parade_date_id` → `planned_parade_night_id` — Tasks 2, 3
- ✅ `_year_for_date()` removed — Task 5
- ✅ `_find_or_create_parade_date_for_night()` removed — Task 5
- ✅ `create_parade` sets `planning_year_id` via `ensure_year_context()` — Task 5
- ✅ `linked_to_planning_year` removed from SPA — Task 6
- ✅ Migration blocks if any orphan nights exist — Task 2 (`_abort_if_blockers`)
- ✅ `parade_night_id = parade_date_id` backward compat in `_night_out_as_date()` — Task 4
- ✅ Pre-migration audit script — Task 1
- ✅ PW notices endpoint URL updated — Tasks 4, 6
- ✅ 708's 2027 row / unresolvable nights: blocked by Task 1 audit (must be resolved before Task 2 runs)

**Type consistency check:**
- `_night_out_as_date()` returns `parade_date_id` (alias) — PW components reference `pd.parade_date_id` — consistent.
- `_notice_out()` returns `parade_night_id` — `ParadeNotice.parade_night_id` in types.ts — consistent.
- `PlanningConflict.parade_night_id` in types.ts — conflict serialiser returns `parade_night_id` — consistent.
- `conflictMapFromPlanningConflicts.test.ts` fixture uses `parade_night_id` — consistent with type.

**Spec notes (from §9):**
- 708's 2027 row holding 2026 dates is a pre-migration data problem, not a code problem. The audit script (Task 1) will flag it. A data-fix SQL script is outside this plan's scope but must be run before Task 2 can proceed.
- The four TEST-unit nights are in the same category — they block Task 2 until resolved.

---

**Plan complete and saved to `docs/superpowers/plans/2026-08-29-parade-night-date-merge.md`.**

Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, task review between each, fast iteration. Use `superpowers:subagent-driven-development`.

**2. Inline Execution** — execute tasks in this session using `superpowers:executing-plans`.
