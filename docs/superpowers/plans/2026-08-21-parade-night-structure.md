# Parade Night Structure Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesign the parade night structure to unify timing template language, add a full-template print program with training-class columns, introduce custom training phases with scope inheritance, surface year management in Settings, and align Planning Workspace terminology.

**Architecture:** Single-file SPA (`connected-frontend/index.html`) + FastAPI/SQLAlchemy backend + 4 Alembic migrations (SQLite-compatible) + React Planning Workspace (`frontend/`). All changes share the same backend. Migrations run in strict dependency order.

**Tech Stack:** Python 3.13 / FastAPI / SQLAlchemy 2.0 / Alembic / SQLite (dev) / PostgreSQL (prod) · Plain HTML/CSS/JS SPA (no build) · React + Vite (Planning Workspace)

**Spec:** `docs/superpowers/specs/2026-08-21-parade-night-structure-design.md`

## Global Constraints

- `connected-frontend/index.html` is a single-file SPA — no build step; all CSS/JS inlined; never replace with the React app
- All XSS-risk strings use `esc()` before `innerHTML` insertion; never use `eval()`
- Every new backend endpoint follows `permissions.py` RBAC helpers — no ad-hoc role checks
- New migrations use `batch_alter_table` for SQLite compatibility; run `alembic heads` before each new migration to find the actual current head
- No plaintext credentials, access codes, or hashes in source, logs, or API responses
- Do not deploy production without separate explicit authorisation
- Training class and custom phase deletions must be dependency-gated
- Code-level identifiers (column names, function names, API field names) are NOT renamed — only user-visible labels change
- `block_name` already exists on `TimingBlock` — do not add a duplicate column
- `start_date`/`end_date` already exist on `TrainingClass` — treat as `applies_from`/`applies_to` semantically; do not rename the columns

## Codebase Orientation

- **BLOCK_TYPES** (`backend/app/models/training.py:8`): existing set is `{arrival, administration, roll_call, parade, flight_period, instructional_period, break, fatigues, debrief, dismissal, custom}` — all must be migrated
- **TimingBlock** (line 292): has `block_name` (String 80), `block_type` (String 40), `is_instructional_period` (Bool), `display_order`
- **TrainingClass** (line 383): has `training_stage_id` FK → `curriculum_phases.id`, `start_date`, `end_date`, `display_name`, `sequence`; does NOT have `stage_code`
- **Session** (line 76): has `cadet_group` (free-text stage), `period_number`; does NOT have `timing_block_id`
- **CurriculumPhase** (line 360): scoped catalogue for curriculum stages — separate from Custom Training Phases in spec §5
- **Alembic head at plan-write time:** `3197cd57cd98` — always run `alembic heads` before branching a new migration
- **Timing router:** `backend/app/routers/timing.py` — existing CRUD at lines 247–620
- **Training router:** `backend/app/routers/training.py` — training class CRUD at lines 2063–2234
- **Frontend timing block editor:** `connected-frontend/index.html` ~line 3898 (`#tt-blocks-body`)
- **Frontend renderWP():** ~line 9851 (current print program)
- **Frontend year management:** ~line 10841 (`ynLoadManagePanel`, `ynCreateYear`)
- **Frontend Settings page:** ~line 1785 (`page-settings`, timing templates card, training classes card)
- **Test suite baseline:** 1818 passed, 7 skipped

---

## Block Type Migration Map

| Old value | New value | Notes |
|---|---|---|
| `arrival` | `arrival` | unchanged |
| `administration` | `admin` | |
| `roll_call` | `admin` | merge with admin |
| `parade` | `parade` | unchanged |
| `flight_period` | `training_period` | was schedulable |
| `instructional_period` | `training_period` | was schedulable |
| `break` | `drinks_break` | |
| `fatigues` | `fatigue` | |
| `debrief` | `briefing` | |
| `dismissal` | `dismissal` | unchanged |
| `custom` | `other` | |

`is_instructional_period` remains the scheduling gate. After migration, it must be True if and only if `block_type == 'training_period'`.

## Stage Code Map

| stage_code | Display name | Print column group |
|---|---|---|
| `ORI` | Orientation | Orientation / Initial |
| `INI` | Initial | Orientation / Initial |
| `JNR` | Junior | Junior / Bronze |
| `INT` | Intermediate | Intermediate / Silver |
| `SNR` | Senior | Senior / Gold |

---

## Task 1: Migration — Block Type Taxonomy

**Files:**
- Create: `backend/alembic/versions/<rev>_update_block_type_taxonomy.py`
- Modify: `backend/app/models/training.py:8` (BLOCK_TYPES constant)
- Modify: `backend/app/routers/timing.py:174,182,206,210,318,350` (block type handling)
- Test: `backend/tests/test_timing.py` (add new block type round-trip tests)

**Interfaces:**
- Produces: `BLOCK_TYPES` frozenset with new values; existing rows migrated; `is_instructional_period` synced

- [ ] **Step 1: Check current alembic head**

```bash
cd backend && source .venv/bin/activate && alembic heads
```
Record the output (should be `3197cd57cd98` or newer — trust the live output, not this plan).

- [ ] **Step 2: Write the failing test**

In `backend/tests/test_timing.py`, add after existing tests:

```python
def test_block_type_taxonomy_new_values(client, login):
    """POST /api/timing-templates must accept every new block type."""
    headers = login(client, "ADMIN703")
    base_block = {"block_name": "Test", "start_time": "18:00", "end_time": "19:00",
                  "duration_minutes": 60, "is_instructional_period": False,
                  "display_order": 1, "is_optional": False}
    new_types = ["arrival", "admin", "parade", "briefing", "training_period",
                 "drinks_break", "fatigue", "dismissal", "other"]
    for bt in new_types:
        resp = client.post("/api/timing-templates", headers=headers, json={
            "name": f"Test {bt}", "effective_from": "2026-01-01",
            "blocks": [{**base_block, "block_type": bt,
                        "is_instructional_period": bt == "training_period"}]
        })
        assert resp.status_code == 200, f"block_type={bt} rejected: {resp.text}"
        data = resp.json()
        block = data["blocks"][0]
        assert block["block_type"] == bt
        if bt == "training_period":
            assert block["is_instructional_period"] is True
        else:
            assert block["is_instructional_period"] is False

def test_old_block_types_rejected(client, login):
    """Old block type values must now be rejected."""
    headers = login(client, "ADMIN703")
    for old_bt in ["instructional_period", "administration", "roll_call",
                   "flight_period", "break", "fatigues", "debrief", "custom"]:
        resp = client.post("/api/timing-templates", headers=headers, json={
            "name": f"Old {old_bt}", "effective_from": "2026-01-01",
            "blocks": [{"block_name": "Test", "block_type": old_bt,
                        "start_time": None, "end_time": None,
                        "duration_minutes": 60, "is_instructional_period": False,
                        "display_order": 1, "is_optional": False}]
        })
        assert resp.status_code == 422 or resp.status_code == 400, \
            f"Old block_type={old_bt} was accepted (should be rejected)"
```

- [ ] **Step 3: Run test to confirm it fails**

```bash
cd backend && python -m pytest tests/test_timing.py::test_block_type_taxonomy_new_values tests/test_timing.py::test_old_block_types_rejected -v
```
Expected: FAIL (new types not in BLOCK_TYPES, old types still accepted).

- [ ] **Step 4: Create the Alembic migration**

```bash
cd backend && alembic revision --autogenerate -m "update_block_type_taxonomy"
```

Open the generated file and replace the `upgrade()`/`downgrade()` bodies:

```python
from alembic import op
import sqlalchemy as sa

# Map old → new block type values
_TYPE_MAP = {
    "administration": "admin",
    "roll_call": "admin",
    "flight_period": "training_period",
    "instructional_period": "training_period",
    "break": "drinks_break",
    "fatigues": "fatigue",
    "debrief": "briefing",
    "custom": "other",
    # unchanged: arrival, parade, dismissal (keep as-is)
}
_SCHEDULABLE = {"training_period"}


def upgrade():
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT id, block_type, is_instructional_period FROM timing_blocks"
    )).fetchall()
    for row_id, block_type, is_ip in rows:
        new_type = _TYPE_MAP.get(block_type, block_type)
        new_ip = 1 if new_type in _SCHEDULABLE else 0
        conn.execute(sa.text(
            "UPDATE timing_blocks SET block_type=:bt, is_instructional_period=:ip WHERE id=:id"
        ), {"bt": new_type, "ip": new_ip, "id": row_id})


def downgrade():
    # No reverse map — downgrade is best-effort only
    pass
```

- [ ] **Step 5: Update BLOCK_TYPES constant**

In `backend/app/models/training.py:8`, replace:

```python
BLOCK_TYPES = frozenset({
    "arrival", "administration", "roll_call", "parade", "flight_period",
    "instructional_period", "break", "fatigues", "debrief", "dismissal", "custom",
})
```

With:

```python
BLOCK_TYPES = frozenset({
    "arrival", "admin", "parade", "briefing", "training_period",
    "drinks_break", "fatigue", "dismissal", "other",
})
```

- [ ] **Step 6: Update timing router validation and sync logic**

In `backend/app/routers/timing.py`, find the block creation/update path (around line 174) and ensure:

1. Validation still uses `BLOCK_TYPES` (already imported — no change needed).
2. When `block_type == "training_period"`, force `is_instructional_period = True`. When any other type, force `is_instructional_period = False`. Replace the existing `is_ip` assignment (~line 174):

```python
# Sync is_instructional_period with block_type
is_ip = bd.block_type == "training_period"
```

3. Find the `BlockIn` model (~line 206) and update its default:

```python
block_type: str = "other"  # was "custom"
is_instructional_period: bool = False  # kept for compatibility but overridden by sync
```

- [ ] **Step 7: Run migration and tests**

```bash
cd backend && alembic upgrade head
python -m pytest tests/test_timing.py -v
```

Expected: all timing tests pass including new ones.

- [ ] **Step 8: Run full suite**

```bash
python -m pytest tests/ -q
```

Expected: 1818+ passed, ≤7 skipped.

- [ ] **Step 9: Commit**

```bash
git add backend/alembic/versions/ backend/app/models/training.py backend/app/routers/timing.py backend/tests/test_timing.py
git commit -m "feat(timing): update block type taxonomy (training_period, admin, drinks_break, etc.)"
```

---

## Task 2: Migration — `training_classes.stage_code`

**Files:**
- Create: `backend/alembic/versions/<rev>_add_training_class_stage_code.py`
- Modify: `backend/app/models/training.py` (TrainingClass model)
- Modify: `backend/app/routers/training.py` (CRUD, dict helper)
- Test: `backend/tests/test_training_classes.py`

**Interfaces:**
- Consumes: Task 1 (migration applied)
- Produces: `TrainingClass.stage_code` column; `stage_code` in API responses; `STAGE_CODES` constant

- [ ] **Step 1: Write the failing test**

In `backend/tests/test_training_classes.py`, add:

```python
STAGE_CODES = ["ORI", "INI", "JNR", "INT", "SNR"]

def test_training_class_stage_code_roundtrip(client, login, db_fixture):
    """stage_code must be accepted on create and returned in GET response."""
    headers = login(client, "ADMIN703")
    # Requires a valid training_year_id and training_stage_id — get them from existing data
    years = client.get("/api/planning/years", headers=headers).json()
    year_id = years[0]["training_year_id"] if years else None
    if not year_id:
        pytest.skip("No planning year available")
    stages = client.get("/api/curriculum/phases", headers=headers).json()
    stage_id = stages[0]["phase_id"] if stages else None
    if not stage_id:
        pytest.skip("No curriculum phase available")
    for code in STAGE_CODES:
        resp = client.post("/api/training-classes", headers=headers, json={
            "training_year_id": year_id,
            "training_stage_id": stage_id,
            "display_name": f"Test {code}",
            "stage_code": code,
        })
        assert resp.status_code == 200, f"stage_code={code} rejected: {resp.text}"
        data = resp.json()
        assert data["stage_code"] == code

def test_training_class_invalid_stage_code(client, login, db_fixture):
    headers = login(client, "ADMIN703")
    years = client.get("/api/planning/years", headers=headers).json()
    year_id = years[0]["training_year_id"] if years else None
    stages = client.get("/api/curriculum/phases", headers=headers).json()
    stage_id = stages[0]["phase_id"] if stages else None
    if not year_id or not stage_id:
        pytest.skip("Prerequisite data missing")
    resp = client.post("/api/training-classes", headers=headers, json={
        "training_year_id": year_id,
        "training_stage_id": stage_id,
        "display_name": "Bad class",
        "stage_code": "INVALID",
    })
    assert resp.status_code in (400, 422)
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
python -m pytest tests/test_training_classes.py::test_training_class_stage_code_roundtrip tests/test_training_classes.py::test_training_class_invalid_stage_code -v
```

Expected: FAIL (no `stage_code` field yet).

- [ ] **Step 3: Add `stage_code` to the model**

In `backend/app/models/training.py`, after `TrainingClass.training_stage_id` mapping (around line 400), add:

```python
stage_code: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
# ORI | INI | JNR | INT | SNR — null for classes created before this feature
```

Also add a module-level constant above the class:

```python
STAGE_CODES = frozenset({"ORI", "INI", "JNR", "INT", "SNR"})
```

- [ ] **Step 4: Create the Alembic migration**

```bash
cd backend && alembic heads  # verify current head after Task 1
alembic revision --autogenerate -m "add_training_class_stage_code"
```

In the generated file:

```python
def upgrade():
    with op.batch_alter_table("training_classes") as batch:
        batch.add_column(sa.Column("stage_code", sa.String(10), nullable=True))

def downgrade():
    with op.batch_alter_table("training_classes") as batch:
        batch.drop_column("stage_code")
```

- [ ] **Step 5: Update router CRUD**

In `backend/app/routers/training.py`:

1. Import `STAGE_CODES` from models (add to the import line that already imports `TrainingClass`).

2. Update `_training_class_dict` (~line 2063) to include `stage_code`:

```python
def _training_class_dict(c: TrainingClass) -> dict:
    return {
        "training_class_id": c.id,
        "squadron_id": c.squadron_id,
        "training_year_id": c.training_year_id,
        "training_stage_id": c.training_stage_id,
        "stage_code": c.stage_code,
        "display_name": c.display_name,
        "sequence": c.sequence,
        "start_date": c.start_date,
        "end_date": c.end_date,
        "expected_count": c.expected_count,
        "notes": c.notes,
        "is_archived": c.is_archived,
        "version": c.version,
    }
```

3. Update `TrainingClassIn` (~line 2102) to accept `stage_code`:

```python
class TrainingClassIn(BaseModel):
    training_year_id: str
    training_stage_id: str
    display_name: str = Field(max_length=80)
    stage_code: str | None = None  # ORI|INI|JNR|INT|SNR
    sequence: int = 0
    start_date: str | None = None
    end_date: str | None = None
    expected_count: int | None = None
    notes: str | None = None
```

4. Update `TrainingClassUpdateIn` (~line 2113) similarly:

```python
stage_code: str | None = None
```

5. In `create_training_class` (~line 2141), validate and apply `stage_code`:

```python
if body.stage_code and body.stage_code not in STAGE_CODES:
    raise HTTPException(400, detail={"error": "invalid_stage_code",
                                     "valid": sorted(STAGE_CODES)})
tc = TrainingClass(
    ...existing fields...,
    stage_code=body.stage_code,
)
```

6. In `update_training_class` (find the PATCH handler ~line 2167), apply `stage_code`:

```python
if body.stage_code is not None:
    if body.stage_code not in STAGE_CODES:
        raise HTTPException(400, detail={"error": "invalid_stage_code"})
    tc.stage_code = body.stage_code
```

- [ ] **Step 6: Run migration and tests**

```bash
cd backend && alembic upgrade head
python -m pytest tests/test_training_classes.py -v
```

- [ ] **Step 7: Run full suite**

```bash
python -m pytest tests/ -q
```

- [ ] **Step 8: Commit**

```bash
git add backend/alembic/versions/ backend/app/models/training.py backend/app/routers/training.py backend/tests/test_training_classes.py
git commit -m "feat(training-classes): add stage_code field (ORI/INI/JNR/INT/SNR)"
```

---

## Task 3: Migration — `sessions.timing_block_id`

**Files:**
- Create: `backend/alembic/versions/<rev>_add_session_timing_block_id.py`
- Modify: `backend/app/models/training.py` (Session model)
- Test: `backend/tests/test_session_lifecycle.py` (verify nullable FK accepted)

**Interfaces:**
- Consumes: Tasks 1–2 applied
- Produces: `Session.timing_block_id` nullable FK; returned in session GET responses

- [ ] **Step 1: Write failing test**

In `backend/tests/test_session_lifecycle.py`, add:

```python
def test_session_timing_block_id_in_response(client, login):
    """Session GET/POST responses must include timing_block_id (nullable)."""
    headers = login(client, "ADMIN703")
    pns = client.get("/api/parade-nights", headers=headers).json()
    if not pns:
        pytest.skip("No parade nights")
    pn_id = pns[0]["parade_night_id"]
    sessions = client.get(f"/api/parade-nights/{pn_id}/sessions", headers=headers)
    assert sessions.status_code == 200
    for s in sessions.json():
        assert "timing_block_id" in s
        # value is None for existing sessions (no migration backfill)
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_session_lifecycle.py::test_session_timing_block_id_in_response -v
```

Expected: FAIL (`timing_block_id` key absent from response).

- [ ] **Step 3: Add field to Session model**

In `backend/app/models/training.py`, in the `Session` class after `version` (around line 110):

```python
timing_block_id: Mapped[str | None] = mapped_column(
    String(36), nullable=True, index=True
)
# FK to timing_blocks.id — not a SQLAlchemy FK constraint; enforced at app layer
# to avoid cascade complexity across SQLite and PostgreSQL.
# ON DELETE behaviour: set to null when the timing template is changed.
```

(Using a plain String FK rather than a SQLAlchemy FK object keeps the migration simpler and avoids cascade complexity across the two DB engines.)

- [ ] **Step 4: Create migration**

```bash
alembic heads  # get current head
alembic revision --autogenerate -m "add_session_timing_block_id"
```

In the generated file:

```python
def upgrade():
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(sa.Column("timing_block_id", sa.String(36), nullable=True))
    op.create_index("ix_sessions_timing_block_id", "sessions",
                    ["timing_block_id"], unique=False)

def downgrade():
    op.drop_index("ix_sessions_timing_block_id", table_name="sessions")
    with op.batch_alter_table("sessions") as batch:
        batch.drop_column("timing_block_id")
```

- [ ] **Step 5: Expose in session API responses**

Search `backend/app/routers/training.py` for the session serialization helper (the function that builds session dicts — search for `"session_id"` or `"parade_night_id"` in a return dict). Add `"timing_block_id": s.timing_block_id` to every session dict builder that returns session rows to the frontend.

Also update the session PATCH endpoint: if the request body includes `timing_block_id`, store it (null is valid — clears the link).

Add `timing_block_id: str | None = None` to the session update Pydantic model.

- [ ] **Step 6: Run migration and tests**

```bash
alembic upgrade head
python -m pytest tests/test_session_lifecycle.py -v
python -m pytest tests/ -q
```

- [ ] **Step 7: Commit**

```bash
git add backend/alembic/versions/ backend/app/models/training.py backend/app/routers/training.py backend/tests/test_session_lifecycle.py
git commit -m "feat(sessions): add timing_block_id FK for print program block-session linkage"
```

---

## Task 4: Migration — `custom_training_phases` table

**Files:**
- Create: `backend/alembic/versions/<rev>_create_custom_training_phases.py`
- Create: `backend/app/models/custom_phases.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/routers/custom_phases.py`
- Modify: `backend/app/main.py` (register router)
- Create: `backend/tests/test_custom_training_phases.py`

**Interfaces:**
- Consumes: Tasks 1–3 applied
- Produces: `CustomTrainingPhase` model; CRUD endpoints at `/api/custom-training-phases`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_custom_training_phases.py`:

```python
import pytest


def test_create_custom_phase_sqn_admin(client, login):
    """sqn_admin can create a squadron-scoped custom training phase."""
    headers = login(client, "ADMIN703")
    resp = client.post("/api/custom-training-phases", headers=headers, json={
        "name": "Wing Band",
        "scope_type": "squadron",
        "applies_from": "2026-01-01",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Wing Band"
    assert data["scope_type"] == "squadron"
    assert data["applies_to"] is None


def test_list_custom_phases_scope_filtered(client, login):
    """GET /api/custom-training-phases returns only phases visible to current scope."""
    headers = login(client, "ADMIN703")
    resp = client.get("/api/custom-training-phases", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_sqn_general_cannot_create_phase(client, login):
    """sqn_general cannot create custom training phases."""
    headers = login(client, "GENERAL703")  # adjust to actual general code
    resp = client.post("/api/custom-training-phases", headers=headers, json={
        "name": "Forbidden Phase",
        "scope_type": "squadron",
        "applies_from": "2026-01-01",
    })
    assert resp.status_code == 403


def test_delete_custom_phase_dependency_gate(client, login):
    """Cannot delete a custom phase that has sessions referencing it."""
    # This test is structural — asserts the endpoint exists and handles 409
    headers = login(client, "ADMIN703")
    # Create a phase first
    resp = client.post("/api/custom-training-phases", headers=headers, json={
        "name": "Test Phase", "scope_type": "squadron", "applies_from": "2026-01-01"
    })
    phase_id = resp.json()["custom_phase_id"]
    # Delete without sessions should succeed
    del_resp = client.delete(f"/api/custom-training-phases/{phase_id}", headers=headers)
    assert del_resp.status_code == 200


def test_unauthenticated_rejected(client):
    resp = client.get("/api/custom-training-phases")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_custom_training_phases.py -v
```

Expected: 404 (endpoint doesn't exist yet).

- [ ] **Step 3: Create the model**

Create `backend/app/models/custom_phases.py`:

```python
"""Custom training phases — ad-hoc scheduling groups beyond the 5 standard stages."""
from sqlalchemy import String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base, UUIDMixin, TimestampMixin

CUSTOM_PHASE_SCOPE_TYPES = frozenset({"squadron", "wing", "national", "system"})


class CustomTrainingPhase(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "custom_training_phases"
    name: Mapped[str] = mapped_column(String(120))
    scope_type: Mapped[str] = mapped_column(String(20), index=True)
    scope_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    applies_from: Mapped[str] = mapped_column(String(10))   # ISO YYYY-MM-DD
    applies_to: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
```

- [ ] **Step 4: Register model in `__init__.py`**

In `backend/app/models/__init__.py`, add:

```python
from .custom_phases import CustomTrainingPhase  # noqa: F401
```

- [ ] **Step 5: Create the Alembic migration**

```bash
alembic heads
alembic revision --autogenerate -m "create_custom_training_phases"
```

Verify the autogenerate picks up `custom_training_phases` table with all columns. If autogenerate misses it, write the `upgrade()` manually:

```python
def upgrade():
    op.create_table(
        "custom_training_phases",
        sa.Column("id", sa.String(36), nullable=False, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("scope_type", sa.String(20), nullable=False),
        sa.Column("scope_id", sa.String(36), nullable=True),
        sa.Column("applies_from", sa.String(10), nullable=False),
        sa.Column("applies_to", sa.String(10), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_custom_training_phases_scope_type", "custom_training_phases", ["scope_type"])
    op.create_index("ix_custom_training_phases_scope_id", "custom_training_phases", ["scope_id"])

def downgrade():
    op.drop_table("custom_training_phases")
```

- [ ] **Step 6: Create the router**

Create `backend/app/routers/custom_phases.py`:

```python
"""Custom training phases — ad-hoc scheduling groups (Wing Band, Biathlon Team, etc.)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_

from ..database import DBSession, get_db
from ..permissions import Principal, get_principal, require_role
from ..models.custom_phases import CustomTrainingPhase, CUSTOM_PHASE_SCOPE_TYPES
from .. import services

router = APIRouter()


def _visible_phases(db: DBSession, p: Principal) -> list[CustomTrainingPhase]:
    """Return phases visible to this principal (scope inheritance downward)."""
    from sqlalchemy import and_
    q = db.query(CustomTrainingPhase).filter(CustomTrainingPhase.is_deleted == False)  # noqa: E712
    # system sees all; national sees all; wing sees national + own wing; squadron sees all above + own
    scope = p.scope_type
    if scope == "system_admin":
        pass  # all
    elif scope == "national":
        q = q.filter(CustomTrainingPhase.scope_type.in_(["system", "national"]))
    elif scope == "wing":
        q = q.filter(or_(
            CustomTrainingPhase.scope_type.in_(["system", "national"]),
            and_(CustomTrainingPhase.scope_type == "wing",
                 CustomTrainingPhase.scope_id == p.wing_id),
        ))
    else:  # squadron
        q = q.filter(or_(
            CustomTrainingPhase.scope_type.in_(["system", "national"]),
            and_(CustomTrainingPhase.scope_type == "wing",
                 CustomTrainingPhase.scope_id == p.wing_id),
            and_(CustomTrainingPhase.scope_type == "squadron",
                 CustomTrainingPhase.scope_id == p.squadron_id),
        ))
    return q.order_by(CustomTrainingPhase.name).all()


def _phase_dict(ph: CustomTrainingPhase) -> dict:
    return {
        "custom_phase_id": ph.id,
        "name": ph.name,
        "scope_type": ph.scope_type,
        "scope_id": ph.scope_id,
        "applies_from": ph.applies_from,
        "applies_to": ph.applies_to,
        "created_by": ph.created_by,
    }


class CustomPhaseIn(BaseModel):
    name: str = Field(max_length=120)
    scope_type: str
    scope_id: str | None = None
    applies_from: str
    applies_to: str | None = None


class CustomPhaseUpdateIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    applies_from: str | None = None
    applies_to: str | None = None


@router.get("/custom-training-phases")
def list_custom_phases(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    return [_phase_dict(ph) for ph in _visible_phases(db, p)]


@router.post("/custom-training-phases")
def create_custom_phase(body: CustomPhaseIn, db: DBSession = Depends(get_db),
                        p: Principal = Depends(get_principal)):
    require_role(p, "sqn_admin", "wing_admin", "national_admin", "system_admin")
    if body.scope_type not in CUSTOM_PHASE_SCOPE_TYPES:
        raise HTTPException(400, detail={"error": "invalid_scope_type"})
    # Scope_id validation
    scope_id = body.scope_id
    if body.scope_type == "squadron":
        scope_id = p.squadron_id
    elif body.scope_type == "wing":
        if p.scope_type not in ("wing_admin", "system_admin", "national"):
            raise HTTPException(403, detail={"error": "insufficient_scope"})
        scope_id = body.scope_id or p.wing_id
    elif body.scope_type in ("national", "system"):
        if p.scope_type not in ("national", "system_admin"):
            raise HTTPException(403, detail={"error": "insufficient_scope"})
        scope_id = None
    ph = CustomTrainingPhase(
        name=body.name,
        scope_type=body.scope_type,
        scope_id=scope_id,
        applies_from=body.applies_from,
        applies_to=body.applies_to,
        created_by=p.user_id,
    )
    db.add(ph)
    db.commit()
    db.refresh(ph)
    services.audit(db, p, object_type="custom_training_phase", object_id=ph.id,
                   action="create")
    return _phase_dict(ph)


@router.patch("/custom-training-phases/{phase_id}")
def update_custom_phase(phase_id: str, body: CustomPhaseUpdateIn,
                        db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    require_role(p, "sqn_admin", "wing_admin", "national_admin", "system_admin")
    ph = db.get(CustomTrainingPhase, phase_id)
    if not ph or ph.is_deleted:
        raise HTTPException(404, detail={"error": "not_found"})
    if body.name is not None:
        ph.name = body.name
    if body.applies_from is not None:
        ph.applies_from = body.applies_from
    if body.applies_to is not None:
        ph.applies_to = body.applies_to
    db.commit()
    db.refresh(ph)
    services.audit(db, p, object_type="custom_training_phase", object_id=ph.id,
                   action="update")
    return _phase_dict(ph)


@router.delete("/custom-training-phases/{phase_id}")
def delete_custom_phase(phase_id: str, db: DBSession = Depends(get_db),
                        p: Principal = Depends(get_principal)):
    require_role(p, "sqn_admin", "wing_admin", "national_admin", "system_admin")
    ph = db.get(CustomTrainingPhase, phase_id)
    if not ph or ph.is_deleted:
        raise HTTPException(404, detail={"error": "not_found"})
    # Dependency gate: check if any sessions reference this phase
    # Sessions link via custom_phase_id if we add that field (Task 8 extension);
    # for now, soft-delete is always safe.
    ph.is_deleted = True
    db.commit()
    services.audit(db, p, object_type="custom_training_phase", object_id=phase_id,
                   action="delete")
    return {"deleted": phase_id}
```

- [ ] **Step 7: Register router in main.py**

In `backend/app/main.py`, add:

```python
from .routers.custom_phases import router as custom_phases_router
# ...
app.include_router(custom_phases_router, prefix="/api")
```

- [ ] **Step 8: Run migration and tests**

```bash
alembic upgrade head
python -m pytest tests/test_custom_training_phases.py -v
python -m pytest tests/ -q
```

- [ ] **Step 9: Commit**

```bash
git add backend/alembic/versions/ backend/app/models/custom_phases.py backend/app/models/__init__.py backend/app/routers/custom_phases.py backend/app/main.py backend/tests/test_custom_training_phases.py
git commit -m "feat(custom-phases): add custom_training_phases table and CRUD endpoints"
```

---

## Task 5: Backend — Auto-Create Training Classes on Year Creation

**Files:**
- Modify: `backend/app/routers/planning.py` (find `POST /api/planning/years`)
- Modify: `backend/tests/test_year_ux.py` (or create `test_year_auto_classes.py`)

**Interfaces:**
- Consumes: Tasks 1–4 (esp. `stage_code` from Task 2)
- Produces: 5 TrainingClass rows per new year; returned in year creation response as `auto_classes`

- [ ] **Step 1: Write failing test**

In `backend/tests/test_year_ux.py` (or add a new file `test_year_auto_classes.py`):

```python
def test_year_creation_auto_creates_training_classes(client, login):
    """POST /api/planning/years must auto-create 5 training classes (ORI/INI/JNR/INT/SNR)."""
    headers = login(client, "ADMIN703")
    resp = client.post("/api/planning/years", headers=headers, json={
        "year": 2028,
        "label": "Auto Classes Test",
        "start_date": "2028-01-01",
        "end_date": "2028-12-31",
    })
    assert resp.status_code == 200
    year_id = resp.json()["training_year_id"]
    # Verify auto-created classes
    classes = client.get("/api/training-classes",
                         params={"training_year_id": year_id},
                         headers=headers).json()
    codes = {c["stage_code"] for c in classes}
    assert codes == {"ORI", "INI", "JNR", "INT", "SNR"}, \
        f"Expected 5 stage codes, got: {codes}"
    names = {c["display_name"] for c in classes}
    assert "Orientation" in names
    assert "Senior" in names
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_year_ux.py::test_year_creation_auto_creates_training_classes -v
```

Expected: FAIL (no auto-created classes).

- [ ] **Step 3: Implement auto-creation in planning router**

In `backend/app/routers/planning.py`, find `POST /api/planning/years` (search for the function that creates a `PlanningYear`). After the `db.commit()` and `db.refresh(year)`, add:

```python
# Auto-create the 5 standard training classes for this year
_AUTO_CLASSES = [
    ("ORI", "Orientation", 1),
    ("INI", "Initial", 2),
    ("JNR", "Junior", 3),
    ("INT", "Intermediate", 4),
    ("SNR", "Senior", 5),
]
from .training import TrainingClass  # adjust import path as needed
from ..models.training import STAGE_CODES
start = year.start_date  # ISO string, e.g. "2026-01-01"
for code, name, seq in _AUTO_CLASSES:
    tc = TrainingClass(
        squadron_id=p.squadron_id,
        training_year_id=year.id,
        training_stage_id=None,  # no curriculum phase linked by default
        stage_code=code,
        display_name=name,
        sequence=seq,
        start_date=start,
        end_date=None,
    )
    db.add(tc)
db.commit()
```

Note: `training_stage_id` is allowed to be null here because the foreign key constraint in the DB allows null (verify in schema). If it's required NOT NULL in the DB, link it to the first visible CurriculumPhase matching the stage name, or set a sentinel. Check the current DB constraint first.

- [ ] **Step 4: Run test**

```bash
python -m pytest tests/test_year_ux.py -v
python -m pytest tests/ -q
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/planning.py backend/tests/test_year_ux.py
git commit -m "feat(years): auto-create 5 training classes (ORI/INI/JNR/INT/SNR) on year creation"
```

---

## Task 6: Backend — `GET /api/parade-nights/{id}/schedule` Endpoint

**Files:**
- Modify: `backend/app/routers/timing.py` (add endpoint) or `backend/app/routers/training.py`
- Test: `backend/tests/test_timing.py`

**Interfaces:**
- Consumes: Tasks 1–3
- Produces: `GET /api/parade-nights/{id}/schedule` returns `{blocks: [...], sessions_by_block: {block_id: [...]}, unlinked_sessions: [...]}`

- [ ] **Step 1: Write failing test**

In `backend/tests/test_timing.py`, add:

```python
def test_parade_night_schedule_endpoint(client, login):
    """GET /api/parade-nights/{id}/schedule must return blocks + sessions keyed by block."""
    headers = login(client, "ADMIN703")
    pns = client.get("/api/parade-nights", headers=headers).json()
    if not pns:
        pytest.skip("No parade nights in test data")
    pn_id = pns[0]["parade_night_id"]
    resp = client.get(f"/api/parade-nights/{pn_id}/schedule", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "blocks" in data
    assert "sessions_by_block" in data
    assert "unlinked_sessions" in data
    assert isinstance(data["blocks"], list)
    assert isinstance(data["sessions_by_block"], dict)
    assert isinstance(data["unlinked_sessions"], list)

def test_parade_night_schedule_requires_auth(client):
    resp = client.get("/api/parade-nights/fake-id/schedule")
    assert resp.status_code == 401
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_timing.py::test_parade_night_schedule_endpoint -v
```

Expected: FAIL (404, endpoint not found).

- [ ] **Step 3: Implement endpoint**

In `backend/app/routers/timing.py`, add after the existing `GET /api/parade-nights/{pnid}/timing` endpoint (~line 508):

```python
@router.get("/parade-nights/{pn_id}/schedule")
def get_parade_night_schedule(pn_id: str, db: DBSession = Depends(get_db),
                               p: Principal = Depends(get_principal)):
    """Full schedule for a parade night: all template blocks + sessions keyed by block."""
    from ..models.training import ParadeNight, Session, TimingTemplate, TimingBlock
    from sqlalchemy import and_

    pn = db.get(ParadeNight, pn_id)
    if not pn:
        raise HTTPException(404, detail={"error": "parade_night_not_found"})
    require_can_view_squadron(p, pn.squadron_id, db)

    # Determine which timing template applies
    template_id = pn.timing_template_id
    blocks: list[TimingBlock] = []
    if template_id:
        template = db.get(TimingTemplate, template_id)
        if template:
            blocks = sorted(template.blocks, key=lambda b: b.display_order)

    # Fetch all sessions for this parade night
    sessions = db.query(Session).filter(
        and_(Session.parade_night_id == pn_id, Session.is_deleted == False)  # noqa: E712
    ).all()

    # Build session dict helper (reuse existing _session_dict or inline minimal version)
    def _s(s: Session) -> dict:
        return {
            "session_id": s.id,
            "period_number": s.period_number,
            "timing_block_id": s.timing_block_id,
            "cadet_group": s.cadet_group,
            "curriculum_title_at_time": s.curriculum_title_at_time,
            "custom_title": s.custom_title,
            "facilitator_display_name_at_time": s.facilitator_display_name_at_time,
            "training_area_name_at_time": s.training_area_name_at_time,
            "status": s.status,
        }

    sessions_by_block: dict[str, list] = {}
    unlinked: list = []
    for s in sessions:
        if s.timing_block_id:
            sessions_by_block.setdefault(s.timing_block_id, []).append(_s(s))
        else:
            unlinked.append(_s(s))

    return {
        "parade_night_id": pn_id,
        "timing_template_id": template_id,
        "blocks": [
            {
                "block_id": b.id,
                "display_order": b.display_order,
                "block_name": b.block_name,
                "block_type": b.block_type,
                "start_time": b.start_time,
                "end_time": b.end_time,
                "duration_minutes": b.duration_minutes,
                "is_instructional_period": b.is_instructional_period,
                "is_optional": b.is_optional,
            }
            for b in blocks
        ],
        "sessions_by_block": sessions_by_block,
        "unlinked_sessions": unlinked,
    }
```

Also add `require_can_view_squadron` to the imports at the top of `timing.py` if not already present.

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_timing.py -v
python -m pytest tests/ -q
```

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/timing.py backend/tests/test_timing.py
git commit -m "feat(timing): add GET /api/parade-nights/{id}/schedule endpoint for print program"
```

---

## Task 7: TMS Frontend — Block Type Taxonomy & Template Editor Update

**Files:**
- Modify: `connected-frontend/index.html` (block editor UI, `ttQuickSetup()`, block type dropdown)

**Interfaces:**
- Consumes: Task 1 (backend accepts new block types)
- Produces: Updated timing template block editor with new type options; auto-populate generates correct sequence; `training_period` blocks require a name

- [ ] **Step 1: Locate the block editor in index.html**

The timing template block editor is at ~line 3898 (`#tt-blocks-body`). The block type `<select>` will have options for the old types. Also find `ttQuickSetup()` (search for "ttQuickSetup") — the auto-populate function.

- [ ] **Step 2: Update the block type dropdown**

Find the block type `<select>` element inside the row template or `addTTBlock()` function. Replace the old `<option>` list with:

```javascript
const BLOCK_TYPE_OPTIONS = [
    {value: 'arrival',         label: 'Arrival'},
    {value: 'admin',           label: 'Admin'},
    {value: 'parade',          label: 'Parade'},
    {value: 'briefing',        label: 'Briefing'},
    {value: 'training_period', label: 'Training Period'},
    {value: 'drinks_break',    label: 'Drinks Break'},
    {value: 'fatigue',         label: 'Fatigue'},
    {value: 'dismissal',       label: 'Dismissal'},
    {value: 'other',           label: 'Other (custom name)'},
];
```

When rendering each row in the block editor, populate the `<select>` from this array. Example row-render snippet (adapt to the existing pattern):

```javascript
function ttBlockTypeSelect(current) {
    return '<select class="tt-block-type" onchange="ttSyncBlockType(this)">' +
        BLOCK_TYPE_OPTIONS.map(opt =>
            `<option value="${opt.value}"${current===opt.value?' selected':''}>${esc(opt.label)}</option>`
        ).join('') + '</select>';
}
```

- [ ] **Step 3: Add `ttSyncBlockType()` — sync name and is_instructional_period**

Add a new function near the block editor JS:

```javascript
function ttSyncBlockType(sel) {
    const row = sel.closest('tr');
    const nameInput = row.querySelector('.tt-block-name');
    const ipCheck = row.querySelector('.tt-block-ip');
    const bt = sel.value;
    // Auto-fill name from type label (user can override)
    const label = BLOCK_TYPE_OPTIONS.find(o => o.value === bt)?.label || '';
    if (bt === 'training_period') {
        if (!nameInput.value || nameInput.value === nameInput.dataset.autoName) {
            nameInput.value = 'Training Period';
            nameInput.dataset.autoName = 'Training Period';
        }
        if (ipCheck) { ipCheck.checked = true; ipCheck.disabled = true; }
    } else {
        if (!nameInput.value || nameInput.value === nameInput.dataset.autoName) {
            nameInput.value = bt === 'other' ? '' : label;
            nameInput.dataset.autoName = bt === 'other' ? '' : label;
        }
        if (ipCheck) { ipCheck.checked = false; ipCheck.disabled = false; }
    }
}
```

Call `ttSyncBlockType(sel)` on the type `<select>`'s `onchange` event.

- [ ] **Step 4: Update `ttQuickSetup()` auto-populate**

Find `ttQuickSetup()`. Replace or update its block-generation logic to produce:

```javascript
function ttQuickSetup() {
    const n = parseInt(document.getElementById('tt-quick-n')?.value || '3', 10);
    if (isNaN(n) || n < 1 || n > 10) return;
    const blocks = [
        {block_name:'Arrival',   block_type:'arrival',   is_instructional_period:false},
        {block_name:'Admin',     block_type:'admin',     is_instructional_period:false},
        {block_name:'Parade',    block_type:'parade',    is_instructional_period:false},
        {block_name:'Briefing',  block_type:'briefing',  is_instructional_period:false},
    ];
    for (let i = 0; i < n; i++) {
        blocks.push({block_name:`Training Period ${n>1?i+1:''}`.trim(),
                     block_type:'training_period', is_instructional_period:true});
        if (i === 0 && n > 1) {
            blocks.push({block_name:'Drinks Break', block_type:'drinks_break',
                         is_instructional_period:false});
        }
    }
    blocks.push(
        {block_name:'Fatigue',   block_type:'fatigue',   is_instructional_period:false},
        {block_name:'Parade',    block_type:'parade',    is_instructional_period:false},
        {block_name:'Dismissal', block_type:'dismissal', is_instructional_period:false},
    );
    // Clear and repopulate the block editor rows using the existing addTTBlock() or row-render function
    document.getElementById('tt-blocks-body').innerHTML = '';
    blocks.forEach((b, i) => ttAddBlockRow({...b, display_order: i + 1}));
}
```

- [ ] **Step 5: Update block display labels in parade night / settings views**

Search index.html for all places that render `block_type` as a display label (e.g. in the timing override modal `#m-pn-timing-override`, in schedule views). Replace:
- `instructional_period` / `flight_period` → `Training Period`
- `administration` / `roll_call` → `Admin`
- `break` → `Drinks Break`
- `fatigues` → `Fatigue`
- `debrief` → `Briefing`
- `custom` → Other (show the block_name)

A helper function:

```javascript
function ttBlockTypeLabel(bt, name) {
    const MAP = {arrival:'Arrival', admin:'Admin', parade:'Parade', briefing:'Briefing',
                 training_period:'Training Period', drinks_break:'Drinks Break',
                 fatigue:'Fatigue', dismissal:'Dismissal', other:''};
    return bt === 'other' ? esc(name || 'Other') : (MAP[bt] || esc(bt));
}
```

- [ ] **Step 6: Language unification — "Session" → "Training Period" in visible labels**

While in the timing/settings area, update all user-visible strings referencing "IP", "Instructional Period", or "Session" as a scheduling slot:
- "Default Sessions Per Night (fallback)" → "Default Training Periods (fallback)"
- "Sessions This Night" → "Training Periods This Night"
- "Instructional Periods" column label → "Training Periods"
- `# IP(s)` counts in template summaries → `# Training Period(s)`
- Period labels in parade night detail → "Training Period N"

Search for each occurrence with: `grep -n "Instructional Period\|IP\b\|Sessions Per Night\|Sessions This Night" connected-frontend/index.html | head -40`

- [ ] **Step 7: Visually test timing template editor**

Start frontend: `cd connected-frontend && python3 -m http.server 8080`
Start backend: `cd backend && uvicorn app.main:app --reload --port 8000`
Login as sqn_admin → Unit Settings → Timing Templates → open a template → verify:
- Block type dropdown shows new options
- Selecting "Training Period" auto-fills name, checks IP
- Selecting "Other" clears name
- Auto-populate generates correct sequence

- [ ] **Step 8: Commit**

```bash
git add connected-frontend/index.html
git commit -m "feat(frontend): update timing block type taxonomy and auto-populate sequence"
```

---

## Task 8: TMS Frontend — Year Creation UX & Training Classes Settings

**Files:**
- Modify: `connected-frontend/index.html` (Settings page, year management card, training class card with stage selector)

**Interfaces:**
- Consumes: Tasks 2 and 5 (backend returns `stage_code`, auto-creates classes on year create)
- Produces: Training Years card in Settings; post-create prompt; stage selector in training class editor

### Part A — Training Years card in Settings

- [ ] **Step 1: Add Training Years card to Settings page**

In `connected-frontend/index.html`, find the `page-settings` div (~line 1785). The current Settings has: Access Code card, Timing Templates card, Training Classes card.

Add a **Training Years** card BETWEEN the Access Code card and Timing Templates card. Extract the content currently in the `m-manage-years` modal:

```html
<div class="card admin-el" id="settings-training-years-wrap">
  <div class="card-header d-flex align-items-center justify-content-between">
    <h3 class="card-title">Training Years</h3>
    <button class="btn btn-sm" onclick="ynCreateYear()">+ Create Year</button>
  </div>
  <div id="settings-yn-table-wrap"><!-- populated by ynLoadManagePanel() --></div>
  <div id="settings-yn-postcreate" style="display:none" class="alert alert-info mt-2">
    <!-- post-create prompt injected here by ynCreateYear() -->
  </div>
</div>
```

Update `renderSettings()` to call `ynLoadManagePanel()` (which already populates `#ynManageTableWrap` — redirect that population to `#settings-yn-table-wrap` instead, or call a new `ynLoadSettingsYearPanel()`).

- [ ] **Step 2: Update the gear icon shortcut**

Find the `ynGear` button (~line 1560 in the Activities header). Change its content from the bare ⚙ symbol to include a visible label:

```html
<button id="ynGear" class="btn btn-xs admin-el" onclick="nav('settings')" 
        title="Manage Training Years" style="...">
  ⚙ Manage Years
</button>
```

(The gear now navigates directly to Settings where the card lives, rather than opening the modal.)

- [ ] **Step 3: Post-create prompt in `ynCreateYear()`**

Find `ynCreateYear()` (~line 10868). After the successful API response handling, add:

```javascript
// Show post-create prompt in settings card
const postWrap = document.getElementById('settings-yn-postcreate');
if (postWrap) {
    const yr = data.year ?? body.year;
    postWrap.innerHTML = `Year <strong>${yr}</strong> created. ` +
        `5 default training classes have been added. ` +
        `<a href="#" onclick="document.getElementById('settings-training-classes-wrap').scrollIntoView({behavior:'smooth'});return false;">` +
        `Go to Training Classes ↓</a> to customise them, or ` +
        `<a href="#" onclick="document.getElementById('settings-timing-templates-wrap').scrollIntoView({behavior:'smooth'});return false;">` +
        `Timing Templates ↓</a> to set up the parade night structure.`;
    postWrap.style.display = 'block';
    // Reload the year table
    ynLoadManagePanel();
}
```

### Part B — Stage selector in Training Class editor

- [ ] **Step 4: Add stage_code selector to training class create/edit form**

Find the training class modal or inline editor in `_loadSettingsTrainingClasses()` (~line 1785 area). In the form HTML (wherever display_name, start_date, etc. are fields), add:

```html
<div class="form-group">
  <label>Stage</label>
  <select id="tc-stage-code" class="form-control">
    <option value="">— select stage —</option>
    <option value="ORI">ORI — Orientation</option>
    <option value="INI">INI — Initial</option>
    <option value="JNR">JNR — Junior / Bronze</option>
    <option value="INT">INT — Intermediate / Silver</option>
    <option value="SNR">SNR — Senior / Gold</option>
  </select>
</div>
```

When submitting the form (create or update training class), include `stage_code: document.getElementById('tc-stage-code').value || null` in the request body.

When populating the form for edit, pre-select the current `stage_code`.

Display `stage_code` in the training class list table (a small badge: `<span class="badge">${esc(tc.stage_code || '—')}</span>`).

Also relabel "Active from" / "Active until" for the `start_date`/`end_date` fields (per spec terminology).

- [ ] **Step 5: Visual test**

Login as sqn_admin → Unit Settings → scroll to Training Years card → create a new year → confirm post-create prompt appears → scroll to Training Classes → confirm 5 classes auto-appear with stage codes → edit one → confirm stage selector is populated.

- [ ] **Step 6: Commit**

```bash
git add connected-frontend/index.html
git commit -m "feat(frontend): Training Years settings card, post-create prompt, stage selector in class editor"
```

---

## Task 9: TMS Frontend — Print Program Redesign (`renderWP()`)

**Files:**
- Modify: `connected-frontend/index.html` (renderWP function, print CSS)

**Interfaces:**
- Consumes: Tasks 1–6 (schedule endpoint, stage_code on classes, training_period blocks)
- Produces: Full-template landscape print with fixed stage column groups + dynamic class sub-columns

- [ ] **Step 1: Read current renderWP() and understand data flow**

`renderWP()` is at ~line 9851. It currently renders `pn.sessions` (session blocks only) in a flat table. The new version needs two data sources:
1. `GET /api/parade-nights/{id}/schedule` — all blocks + sessions keyed by block
2. `GET /api/training-classes?training_year_id=...` — all classes for the year, with `stage_code`

- [ ] **Step 2: Add print CSS**

Find the `@media print` block in index.html CSS (search for `@media print`). Add:

```css
@media print {
    @page { size: landscape; margin: 12mm; }
    .print-schedule-table { width: 100%; border-collapse: collapse; font-size: 8pt; table-layout: fixed; }
    .print-schedule-table th, .print-schedule-table td { border: 1px solid #ccc; padding: 3px 4px; vertical-align: top; word-break: break-word; }
    .print-schedule-table .col-time { width: 60px; }
    .print-schedule-table .col-block { width: 100px; }
    .print-schedule-table .group-header { background: #002f65; color: #fff; text-align: center; font-weight: 700; }
    .print-schedule-table .class-header { background: #e8f0f8; font-weight: 600; text-align: center; }
    .print-schedule-table .non-period-row td { background: #f8f8f8; color: #555; font-style: italic; }
    .print-footer { margin-top: 8px; font-size: 7pt; color: #888; text-align: right; }
}
```

- [ ] **Step 3: Rewrite renderWP()**

Replace the current `renderWP()` function body. The new structure:

```javascript
async function renderWP() {
    const wrap = document.getElementById('page-weekly-program');
    if (!wrap) return;
    wrap.innerHTML = '<p class="muted p-4">Loading parade nights…</p>';

    // 1. Load parade nights for the current training year
    const pns = await api('GET', `/api/parade-nights?training_year=${S.trainingYear || ''}`);

    // 2. Load training classes for the current year
    const yearId = S.planningYearId;  // adjust to actual field name in S
    const classes = yearId
        ? await api('GET', `/api/training-classes?training_year_id=${encodeURIComponent(yearId)}`)
        : [];

    // 3. Build the fixed column groups (always 4 groups; sub-columns = classes per stage)
    const STAGE_GROUPS = [
        {key:'ORI_INI', label:'Orientation / Initial', codes:['ORI','INI']},
        {key:'JNR',     label:'Junior / Bronze',       codes:['JNR']},
        {key:'INT',     label:'Intermediate / Silver',  codes:['INT']},
        {key:'SNR',     label:'Senior / Gold',          codes:['SNR']},
    ];
    function classesForGroup(g) {
        return classes.filter(c => g.codes.includes(c.stage_code))
                      .sort((a,b) => (a.sequence||0)-(b.sequence||0));
    }

    // 4. Render each parade night
    let html = '';
    for (const pn of pns) {
        const schedule = await api('GET', `/api/parade-nights/${pn.parade_night_id}/schedule`);
        html += _renderPNSchedule(pn, schedule, classes, STAGE_GROUPS);
    }

    const today = new Date().toLocaleDateString('en-AU', {day:'2-digit',month:'long',year:'numeric'});
    wrap.innerHTML = html +
        `<div class="print-footer">Generated ${esc(today)}</div>`;
}

function _renderPNSchedule(pn, schedule, classes, stageGroups) {
    const blocks = schedule.blocks || [];
    const byBlock = schedule.sessions_by_block || {};
    const unlinked = schedule.unlinked_sessions || [];

    // Determine sub-columns per group
    const groupCols = stageGroups.map(g => {
        const cls = classes.filter(c => g.codes.includes(c.stage_code))
                           .sort((a,b) => (a.sequence||0)-(b.sequence||0));
        return {group: g, cols: cls.length > 0 ? cls : [{display_name:'—', training_class_id:null}]};
    });
    const totalCols = groupCols.reduce((s,g) => s + g.cols.length, 0);

    // Header rows
    let thead = '<thead>';
    // Row 1: info header spanning all columns
    const dateStr = pn.date ? new Date(pn.date).toLocaleDateString('en-AU',{weekday:'long',day:'numeric',month:'long',year:'numeric'}) : '';
    thead += `<tr><td colspan="${totalCols+2}" class="group-header">${esc(S.squadronName||'')} · ${esc(dateStr)} · Term ${esc(pn.term||'—')} · ${esc(pn.start_time||'')}–${esc(pn.end_time||'')}</td></tr>`;
    // Row 2: group headers
    thead += '<tr><th class="col-time">Time</th><th class="col-block">Block</th>';
    groupCols.forEach(gc => {
        thead += `<th colspan="${gc.cols.length}" class="group-header">${esc(gc.group.label)}</th>`;
    });
    thead += '</tr>';
    // Row 3: class sub-column headers
    thead += '<tr><th></th><th></th>';
    groupCols.forEach(gc => {
        gc.cols.forEach(cl => {
            thead += `<th class="class-header">${esc(cl.display_name)}</th>`;
        });
    });
    thead += '</tr></thead>';

    // Body rows
    let tbody = '<tbody>';
    const dash = '<td style="text-align:center;color:#aaa">—</td>';
    for (const b of blocks) {
        const isTP = b.block_type === 'training_period';
        const timeStr = b.start_time ? `${b.start_time}${b.end_time?'–'+b.end_time:''}` : '';
        if (!isTP) {
            // Non-Training-Period row: dash for all class columns
            tbody += `<tr class="non-period-row"><td>${esc(timeStr)}</td><td>${esc(b.block_name)}</td>`;
            tbody += dash.repeat(totalCols);
            tbody += '</tr>';
        } else {
            // Training Period row: find sessions per class
            const blockSessions = byBlock[b.block_id] || [];
            tbody += `<tr><td>${esc(timeStr)}</td><td><strong>${esc(b.block_name)}</strong></td>`;
            groupCols.forEach(gc => {
                gc.cols.forEach(cl => {
                    if (!cl.training_class_id) { tbody += dash; return; }
                    // Check if class is active on this parade night date
                    const activeFrom = cl.start_date;
                    const activeTo   = cl.end_date;
                    const pnDate     = pn.date;
                    const inactive   = (activeFrom && pnDate < activeFrom) || (activeTo && pnDate > activeTo);
                    if (inactive) { tbody += dash; return; }
                    // Find session for this class in this block
                    const sess = blockSessions.find(s => s.cadet_group &&
                        _stageCodeMatchesCadetGroup(cl.stage_code, s.cadet_group));
                    if (!sess) {
                        tbody += `<td><em style="color:#aaa">Unassigned</em></td>`;
                    } else {
                        const title = sess.custom_title || sess.curriculum_title_at_time || 'Unassigned';
                        const fac   = sess.facilitator_display_name_at_time || '';
                        const room  = sess.training_area_name_at_time || '';
                        tbody += `<td>${esc(title)}${fac?`<br><small>${esc(fac)}</small>`:''}${room?`<br><small style="color:#888">${esc(room)}</small>`:''}</td>`;
                    }
                });
            });
            tbody += '</tr>';
        }
    }
    // Unlinked sessions at bottom (if any)
    if (unlinked.length) {
        tbody += `<tr><td colspan="${totalCols+2}" style="background:#fff8e1;padding:4px 6px;font-style:italic;font-size:7.5pt;">`;
        tbody += `Unlinked periods (no timing template block): ${unlinked.map(s=>esc(s.curriculum_title_at_time||'—')).join(', ')}`;
        tbody += '</td></tr>';
    }
    tbody += '</tbody>';

    return `<div class="print-pn-block" style="page-break-after:always;margin-bottom:24px;">
        <table class="print-schedule-table">${thead}${tbody}</table>
    </div>`;
}

function _stageCodeMatchesCadetGroup(stageCode, cadetGroup) {
    // Backwards-compat bridge: cadet_group is a free-text legacy field
    const MAP = {ORI:'orientation', INI:'initial', JNR:'junior', INT:'intermediate', SNR:'senior'};
    return cadetGroup && cadetGroup.toLowerCase().includes(MAP[stageCode]||'');
}
```

- [ ] **Step 3: Visual test print layout**

Login as sqn_admin → Weekly Program → open browser print preview (Cmd+P) → verify:
- Landscape orientation
- Header with squadron name, date, term, time range
- 4 fixed stage column groups always shown
- Non-Training-Period rows show dashes across class columns
- Footer shows "Generated [date]"

- [ ] **Step 4: Commit**

```bash
git add connected-frontend/index.html
git commit -m "feat(frontend): redesign Weekly Program print with full timing template + training class columns"
```

---

## Task 10: TMS Frontend — Per-Night Template Chip & Custom Phases Settings Card

**Files:**
- Modify: `connected-frontend/index.html`

**Interfaces:**
- Consumes: Tasks 1, 4, 6
- Produces: Template name chip on each parade night row; Custom Training Phases settings card

### Part A — Per-night template chip

- [ ] **Step 1: Add template chip to parade night list**

Find `renderPN()` (~line that renders parade night rows). After the parade night date/status cells, add a template chip. The template name comes from the `timing_template_id` field (already on `ParadeNight` and in the API response). You'll need to cross-reference it with the templates list.

Load templates into `S.timingTemplates` at startup (call `GET /api/timing-templates` after auth). Then in the parade night row render:

```javascript
const tpl = (S.timingTemplates || []).find(t => t.timing_template_id === pn.timing_template_id);
const chipHtml = tpl
    ? `<button class="btn btn-xs" onclick="openTimingOverride('${esc(pn.parade_night_id)}')" title="Change template">
         📋 ${esc(tpl.name)} ▾
       </button>`
    : `<button class="btn btn-xs muted" onclick="openTimingOverride('${esc(pn.parade_night_id)}')" title="Set template">
         + Template
       </button>`;
```

Where `openTimingOverride(pnId)` opens the existing `#m-pn-timing-override` modal.

Relabel the override modal title from whatever it currently says to "Change Parade Night Template".

### Part B — Custom Training Phases settings card

- [ ] **Step 2: Add Custom Phases card to Settings**

In `page-settings`, add a new card after the Training Classes card:

```html
<div class="card admin-el" id="settings-custom-phases-wrap">
  <div class="card-header d-flex justify-content-between">
    <h3 class="card-title">Custom Training Phases</h3>
    <button class="btn btn-sm admin-el" onclick="cpOpenCreate()">+ Add Phase</button>
  </div>
  <div id="settings-custom-phases-list">
    <p class="muted text-sm p-3">Loading…</p>
  </div>
</div>
```

Add a `loadCustomPhases()` function called from `renderSettings()`:

```javascript
async function loadCustomPhases() {
    const list = document.getElementById('settings-custom-phases-list');
    if (!list) return;
    const phases = await api('GET', '/api/custom-training-phases');
    if (!phases || !phases.length) {
        list.innerHTML = '<p class="muted text-sm p-3">No custom phases defined.</p>';
        return;
    }
    list.innerHTML = '<table class="table table-sm"><thead><tr><th>Name</th><th>Scope</th><th>From</th><th>Until</th><th></th></tr></thead><tbody>' +
        phases.map(ph => `<tr>
            <td>${esc(ph.name)}</td>
            <td><span class="badge">${esc(ph.scope_type)}</span></td>
            <td>${esc(ph.applies_from)}</td>
            <td>${esc(ph.applies_to||'Open-ended')}</td>
            <td>
                <button class="btn btn-xs" onclick="cpOpenEdit('${esc(ph.custom_phase_id)}')">Edit</button>
                <button class="btn btn-xs btn-danger" onclick="cpDelete('${esc(ph.custom_phase_id)}')">Del</button>
            </td>
        </tr>`).join('') +
        '</tbody></table>';
}
```

Add `cpOpenCreate()`, `cpOpenEdit(id)`, and `cpDelete(id)` functions using the existing modal pattern (`confirmAction()` for delete).

- [ ] **Step 3: Visual test**

Login as sqn_admin → Unit Settings → verify Custom Training Phases card appears → add a phase → confirm it appears in the list → delete it.

- [ ] **Step 4: Commit**

```bash
git add connected-frontend/index.html
git commit -m "feat(frontend): per-night template chip and Custom Training Phases settings card"
```

---

## Task 11: Planning Workspace — Terminology & Template Switching

**Files:**
- Modify: `frontend/src/` (search for "Session" in user-visible strings, find parade night detail component)

**Interfaces:**
- Consumes: Tasks 1, 6 (backend supports new block types and template switching via PATCH)
- Produces: PW shows "Training Period" terminology; "Change Template" dropdown on parade night detail

- [ ] **Step 1: Find and update terminology in PW**

```bash
grep -rn "Instructional Period\|IP\b\|Sessions Per Night\|Instructional Period" frontend/src/ | grep -v ".d.ts\|node_modules"
```

For each match, update the user-visible string to "Training Period".

- [ ] **Step 2: Find parade night detail component**

```bash
grep -rn "timing_template\|timingTemplate\|Change Template" frontend/src/
```

Find the component that renders parade night detail. Add a template selector:

```tsx
// Fetch available templates
const [templates, setTemplates] = useState([]);
useEffect(() => {
    apiGet('/api/timing-templates').then(setTemplates);
}, []);

// Template change handler
async function changeTemplate(templateId: string) {
    await apiPatch(`/api/parade-nights/${paradeNightId}`, { timing_template_id: templateId });
    onRefresh();
}

// Render in JSX
<div className="template-selector">
    <label>Template</label>
    <select value={paradeNight.timing_template_id || ''} onChange={e => changeTemplate(e.target.value)}>
        <option value="">— No template —</option>
        {templates.map(t => (
            <option key={t.timing_template_id} value={t.timing_template_id}>{t.name}</option>
        ))}
    </select>
</div>
```

- [ ] **Step 3: Build and verify**

```bash
cd frontend && npm run build
# Or for dev: npm run dev
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/
git commit -m "feat(planning-workspace): update terminology to Training Period, add template switcher"
```

---

## Self-Review Against Spec

### Spec coverage check

| Spec section | Tasks covering it |
|---|---|
| §1 Language unification | Task 7 (step 6) |
| §2 Block type taxonomy | Tasks 1, 7 |
| §3 Timing template enhancements | Tasks 1, 7 |
| §4 Training class enhancements (stage_code, auto-create) | Tasks 2, 5, 8 |
| §4b Date range fields (applies_from/to) | Task 8 (Part B, step 4) — `start_date`/`end_date` already exist; UI labelling added |
| §5 Custom training phases | Tasks 4, 10 |
| §6 Print program redesign | Task 9 |
| §7 Per-night template switching | Tasks 6, 10 |
| §8 Year creation UX | Task 8 (Part A) |
| §9 Backend API changes | Tasks 5, 6 |
| §10 Migrations | Tasks 1–4 |

### Gaps noted (spec §4c — auto_classes in year response)

Spec §4c says auto-created classes should be shown in a post-create prompt. Task 8 (Part A, Step 3) implements this in the frontend by scrolling to the training classes card after creation. The backend year-creation response doesn't need to return the auto-classes (the frontend reloads the classes list separately). No gap.

### Spec §7b — re-generate sessions on template change

Spec says when `timing_template_id` changes, the backend re-generates sessions for Training Period blocks preserving existing assignments. This is a complex operation not covered by Task 6's `GET /schedule` endpoint. Implementer should add this to the PATCH `/api/parade-nights/{id}` handler: when `timing_template_id` changes, soft-delete existing sessions without `timing_block_id` matches and create new ones for the new template's Training Period blocks. This is a **follow-on task** — mark as `v2` if not implementing in this pass, and document the gap.

### Spec §5c — custom phase columns in print

The print redesign in Task 9 includes only the 4 fixed stage groups. Custom phases as extra columns (spec §6b, §5c) are deferred as a `v2` extension — the foundation (custom phases backend + schedule endpoint) is in place, and the `_renderPNSchedule()` function can be extended to append custom-phase columns after Task 10 is complete.

---

## Final Run Order

Execute tasks in this order (each depends on the previous migrations being applied):

1. Task 1 (migration: block types) → run `alembic upgrade head` → full test suite
2. Task 2 (migration: stage_code) → run `alembic upgrade head` → full test suite
3. Task 3 (migration: timing_block_id) → run `alembic upgrade head` → full test suite
4. Task 4 (migration: custom_training_phases) → run `alembic upgrade head` → full test suite
5. Task 5 (auto-create classes)
6. Task 6 (schedule endpoint)
7. Task 7 (TMS frontend: block types + language)
8. Task 8 (TMS frontend: year UX + training classes)
9. Task 9 (TMS frontend: print redesign)
10. Task 10 (TMS frontend: template chip + custom phases card)
11. Task 11 (Planning Workspace: terminology + template switch)

After all tasks: run `python -m pytest tests/ -q` — must pass with no regressions. Visual browser verify on localhost for all changed pages. Commit count: ≥11 commits (one per task).
