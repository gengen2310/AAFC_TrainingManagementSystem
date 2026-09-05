# Parade Night Planning Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hard-coded 3-period, 4-group planning grid with a timing-template-driven, phase-grouped matrix while adding unlimited assistant facilitators, a template-change confirmation flow, shared-session dimming, and CEA import access for squadron admins.

**Architecture:** The backend adds a `session_assistant_facilitators` join table (replacing `backup_facilitator_id`), exposes per-night `instructional_periods` in `night_summaries`, and adds a template-impact preview endpoint. The React Planning Workspace replaces `BLOCK_PERIODS = [1,2,3]` with dynamic template-derived columns and groups `TrainingClass` rows by phase. The connected frontend gains a CEA import button for wing_admin+ and sqn_admin.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Alembic (backend); React 18 + TypeScript + TanStack Query (Planning Workspace frontend); plain HTML/CSS/JS (connected frontend `index.html`).

**Spec:** This plan implements the user's 22-requirement parade-night planning redesign brief plus product decisions recorded 2026-09-05: template swap → preview+confirm; backup facilitator → merge into assistants; CEA → extend to sqn_admin; shared sessions → same card, dimmed.

## Global Constraints

- All tests must pass: `cd backend && python -m pytest tests/ -q`
- Current alembic head: `b1c2d3e4f5a6` — always run `alembic heads` before creating a migration
- Never hard-code a `down_revision` value in this file — always check live
- Use `batch_alter_table` for every SQLite-compatible column change
- No operational data in localStorage; no access-code hashes in any response
- Security invariant: `BLOCK_PERIODS` removal must not regress `sessionCount` tracking
- TypeScript: `npm run typecheck` must pass before committing React changes
- Each task ends with a `git commit`

---

## File Map

**New files:**
- `backend/alembic/versions/v_assistant_facilitators.py` — migration: create `session_assistant_facilitators`, drop `backup_facilitator_id` + `assistant_facilitator_id` from `sessions`
- `backend/tests/test_assistant_facilitator.py` — tests for the new join table, conflict engine
- `frontend/src/components/planning/TemplateImpactModal.tsx` — confirmation dialog for template swap after sessions exist

**Modified files:**
- `backend/app/models/training.py` — add `SessionAssistantFacilitator` model; remove two columns from `Session`
- `backend/app/routers/training.py` — `_sess_dict` output; `_resource_conflicts`; template-impact endpoint; PATCH parade night; create PN
- `backend/app/routers/planning.py` — `night_summaries` adds `instructional_periods` per night; CEA import gains `sqn_admin`
- `frontend/src/api/types.ts` — `NightSummary` + `NightSessionSummary` gain `instructional_periods`; add `AssistantFacilitatorEntry`
- `frontend/src/api/index.ts` — `templateImpact()` call; `createSession` body gains `assistant_facilitator_ids`
- `frontend/src/components/planning/ParadeNightBlock.tsx` — replace `BLOCK_PERIODS` with `instructionalPeriods` prop; phase-group rows; shared-session dimming
- `frontend/src/routes/PlanningWorkspace.tsx` — pass `instructionalPeriods` from night summary to `ParadeNightBlock`
- `frontend/src/routes/ParadeNightDetail.tsx` — template impact preview before PATCH; assistant facilitator multi-select
- `connected-frontend/index.html` — CEA import button in TMS Activities; create PN form simplification

---

### Task 1: SessionAssistantFacilitator model + migration

**Files:**
- Create: `backend/alembic/versions/v_assistant_facilitators.py`
- Modify: `backend/app/models/training.py` (add model class; remove 2 columns from Session)

**Interfaces:**
- Produces: `SessionAssistantFacilitator` model with `session_id`, `facilitator_id`, `display_order`, `rank_at_time`, `display_name_at_time`; `Session` loses `assistant_facilitator_id` and `backup_facilitator_id` columns

- [ ] **Step 1: Add SessionAssistantFacilitator to models/training.py**

After the `SessionStatusHistory` class (around line 140 in `backend/app/models/training.py`), add:

```python
class SessionAssistantFacilitator(Base, UUIDMixin):
    """Unlimited assistant facilitators for a Session (replaces single assistant_facilitator_id
    and backup_facilitator_id columns — both migrated into this table in v_assistant_facilitators)."""
    __tablename__ = "session_assistant_facilitators"
    __table_args__ = (
        UniqueConstraint("session_id", "facilitator_id", name="uq_saf_session_facilitator"),
    )
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    facilitator_id: Mapped[str] = mapped_column(String(36), index=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    rank_at_time: Mapped[str | None] = mapped_column(String(40), nullable=True)
    display_name_at_time: Mapped[str | None] = mapped_column(String(120), nullable=True)
```

Also remove the two lines from `Session`:
```python
# REMOVE:  assistant_facilitator_id: Mapped[str | None] = mapped_column(String(36))
# REMOVE:  backup_facilitator_id: Mapped[str | None] = mapped_column(String(36))
```

- [ ] **Step 2: Import UniqueConstraint at top of models/training.py if not already present**

Check: `from sqlalchemy import ... UniqueConstraint ...` — it's already imported via `__table_args__` on SessionAudience.

- [ ] **Step 3: Add import in models/__init__.py**

In `backend/app/models/__init__.py`, import `SessionAssistantFacilitator` alongside the other training models:
```python
from .training import (
    ...,
    SessionAssistantFacilitator,
)
```

- [ ] **Step 4: Write the Alembic migration**

```bash
cd backend && source .venv/bin/activate && alembic heads
# Note the head revision — use it as down_revision below
```

Create `backend/alembic/versions/v_assistant_facilitators.py`:

```python
"""Add session_assistant_facilitators; drop backup/assistant_facilitator_id from sessions.

Revision ID: <generate with alembic revision --autogenerate -m "..." then copy>
Revises: <current head from alembic heads>
Create Date: 2026-09-05
"""
from __future__ import annotations
import uuid
import sqlalchemy as sa
from alembic import op

revision = "v_asst_fac_001"  # replace with real generated id
down_revision = None  # replace with output of `alembic heads`
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session_assistant_facilitators",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36),
                  sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("facilitator_id", sa.String(36), nullable=False),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rank_at_time", sa.String(40), nullable=True),
        sa.Column("display_name_at_time", sa.String(120), nullable=True),
        sa.UniqueConstraint("session_id", "facilitator_id", name="uq_saf_session_facilitator"),
    )
    op.create_index("ix_saf_session_id", "session_assistant_facilitators", ["session_id"])
    op.create_index("ix_saf_facilitator_id", "session_assistant_facilitators", ["facilitator_id"])

    # Migrate assistant_facilitator_id rows into the join table
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, assistant_facilitator_id FROM sessions WHERE assistant_facilitator_id IS NOT NULL")
    ).fetchall()
    for session_id, fac_id in rows:
        conn.execute(
            sa.text(
                "INSERT INTO session_assistant_facilitators "
                "(id, session_id, facilitator_id, display_order) VALUES (:id, :sid, :fid, 0)"
            ),
            {"id": str(uuid.uuid4()), "sid": session_id, "fid": fac_id},
        )

    # Drop the old columns (batch_alter_table for SQLite compatibility)
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_column("assistant_facilitator_id")
        batch_op.drop_column("backup_facilitator_id")


def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(sa.Column("assistant_facilitator_id", sa.String(36), nullable=True))
        batch_op.add_column(sa.Column("backup_facilitator_id", sa.String(36), nullable=True))

    # Restore first assistant for each session back to assistant_facilitator_id
    conn = op.get_bind()
    rows = conn.execute(
        sa.text(
            "SELECT session_id, facilitator_id FROM session_assistant_facilitators "
            "WHERE display_order = 0 ORDER BY session_id"
        )
    ).fetchall()
    for session_id, fac_id in rows:
        conn.execute(
            sa.text("UPDATE sessions SET assistant_facilitator_id = :fid WHERE id = :sid"),
            {"fid": fac_id, "sid": session_id},
        )

    op.drop_table("session_assistant_facilitators")
```

**Important:** After writing the file, generate the real revision ID:
```bash
cd backend && source .venv/bin/activate
alembic revision --rev-id v_asst_fac_001 -m "add session_assistant_facilitators drop backup_assistant_cols"
# Then copy the actual down_revision from `alembic heads` and paste it in
```

Actually — use `alembic revision` to generate a stub, then fill in the upgrade/downgrade from above. Set `down_revision` to the value printed by `alembic heads`.

- [ ] **Step 5: Run the migration**

```bash
cd backend && source .venv/bin/activate && alembic upgrade head
```

Expected: migration applies cleanly. `alembic heads` shows one head.

- [ ] **Step 6: Write failing tests**

Create `backend/tests/test_assistant_facilitator.py`:

```python
"""Tests for SessionAssistantFacilitator join table and conflict engine."""
import pytest
from tests.conftest import client, login

def test_assistant_facilitator_table_exists(client):
    """Migration created the table and the old columns are gone."""
    from sqlalchemy import inspect, text
    from app.database import engine
    insp = inspect(engine)
    tables = insp.get_table_names()
    assert "session_assistant_facilitators" in tables
    session_cols = [c["name"] for c in insp.get_columns("sessions")]
    assert "assistant_facilitator_id" not in session_cols
    assert "backup_facilitator_id" not in session_cols

def test_create_session_accepts_assistant_facilitator_ids(client):
    """POST /api/sessions accepts assistant_facilitator_ids list."""
    admin_headers = login(client, "ADMIN_CODE")
    # Create a parade night first — use the test fixtures
    pn = client.post("/api/parade-nights", json={"date": "2026-10-07", "term": "T1"},
                     headers=admin_headers)
    assert pn.status_code == 200
    pn_id = pn.json()["parade_night_id"]
    r = client.post("/api/sessions", json={
        "parade_night_id": pn_id,
        "period_number": 1,
        "assistant_facilitator_ids": [],
    }, headers=admin_headers)
    assert r.status_code == 200

def test_assistant_facilitator_conflict_detected(client):
    """Two sessions in the same period with the same assistant raise 409."""
    admin_headers = login(client, "ADMIN_CODE")
    pn = client.post("/api/parade-nights", json={"date": "2026-10-14", "term": "T1"},
                     headers=admin_headers)
    pn_id = pn.json()["parade_night_id"]
    fac_id = "00000000-0000-0000-0000-000000000001"  # use seed facilitator id
    # First session — succeeds
    r1 = client.post("/api/sessions", json={
        "parade_night_id": pn_id, "period_number": 1,
        "assistant_facilitator_ids": [fac_id],
    }, headers=admin_headers)
    assert r1.status_code == 200
    # Second session — same period, same assistant → conflict
    r2 = client.post("/api/sessions", json={
        "parade_night_id": pn_id, "period_number": 1,
        "assistant_facilitator_ids": [fac_id],
    }, headers=admin_headers)
    assert r2.status_code == 409
    assert r2.json()["detail"]["error"] == "resource_conflict"
```

- [ ] **Step 7: Run tests — expect failures (endpoints don't exist yet)**

```bash
cd backend && python -m pytest tests/test_assistant_facilitator.py -v
```

Expected: `test_assistant_facilitator_table_exists` passes; the other two fail with 422 (unknown field `assistant_facilitator_ids`).

- [ ] **Step 8: Update routers/training.py — SessionIn / EditIn models and _sess_dict**

In `SessionIn` (the create body Pydantic model), add:
```python
assistant_facilitator_ids: list[str] = Field(default_factory=list)
```
Remove the old `assistant_facilitator_id: str | None` field if present.

In `EditIn`, add same field:
```python
assistant_facilitator_ids: list[str] | None = None  # None = don't change; [] = clear all
```

In `_sess_dict`, replace the `assistant_facilitator_id` key with:
```python
from app.models.training import SessionAssistantFacilitator as SAF
...
def _sess_dict(s: Session, db: DBSession | None = None) -> dict:
    asst_ids: list[str] = []
    if db is not None:
        asst_ids = [
            row.facilitator_id
            for row in db.query(SAF)
                .filter(SAF.session_id == s.id)
                .order_by(SAF.display_order)
                .all()
        ]
    return {
        ...,
        "assistant_facilitator_ids": asst_ids,
        # backward-compat alias — first assistant or None
        "assistant_facilitator_id": asst_ids[0] if asst_ids else None,
    }
```

In `create_session` handler, after `db.add(s); db.flush()`, add:
```python
for i, fac_id in enumerate(body.assistant_facilitator_ids):
    db.add(SAF(session_id=s.id, facilitator_id=fac_id, display_order=i))
```

In `edit_session` handler, when `body.assistant_facilitator_ids is not None`, replace:
```python
db.query(SAF).filter(SAF.session_id == s.id).delete()
for i, fac_id in enumerate(body.assistant_facilitator_ids):
    db.add(SAF(session_id=s.id, facilitator_id=fac_id, display_order=i))
```

- [ ] **Step 9: Update _resource_conflicts to check assistant facilitators**

In `_resource_conflicts`, after the `sib.facilitator_id` check, add:
```python
# Check assistant facilitator double-booking
sib_asst_ids = {
    row.facilitator_id
    for row in db.query(SAF).filter(SAF.session_id == sib.id).all()
}
for asst_id in getattr(body, "assistant_facilitator_ids", []) or []:
    if asst_id and asst_id == sib.facilitator_id:
        conflicts.append({"type": "facilitator_clash", "session_id": sib.id,
                          "resource_id": asst_id, "resource_name": sib.facilitator_display_name_at_time,
                          "detail": "assistant_vs_main"})
    if asst_id and asst_id in sib_asst_ids:
        conflicts.append({"type": "facilitator_clash", "session_id": sib.id,
                          "resource_id": asst_id, "resource_name": None,
                          "detail": "assistant_double_booked"})
```

- [ ] **Step 10: Run tests — expect all pass**

```bash
cd backend && python -m pytest tests/test_assistant_facilitator.py tests/test_planning.py -q
```

- [ ] **Step 11: Full suite**

```bash
cd backend && python -m pytest tests/ -q
```

- [ ] **Step 12: Commit**

```bash
git add backend/alembic/versions/v_assistant_facilitators.py \
        backend/app/models/training.py \
        backend/app/routers/training.py \
        backend/tests/test_assistant_facilitator.py
git commit -m "feat: replace backup/assistant_facilitator_id cols with SessionAssistantFacilitator join table"
```

---

### Task 2: CEA import — add sqn_admin permission (backend)

**Files:**
- Modify: `backend/app/routers/planning.py` line 5633

**Interfaces:**
- Consumes: `require_role` helper from `permissions.py`
- Produces: `/years/{year_id}/cea/import` now accepts `sqn_admin` callers

- [ ] **Step 1: Write failing test**

In `backend/tests/test_planning.py`, add:

```python
def test_sqn_admin_can_import_cea(client):
    """sqn_admin can POST to /api/planning/years/{year_id}/cea/import."""
    headers = login(client, "SQN_ADMIN_CODE")
    # Use an existing year_id from fixtures
    years = client.get("/api/planning/years", headers=headers).json()
    if not years:
        pytest.skip("no planning year in test db")
    year_id = years[0]["year_id"]
    csv_content = b"SeqNr,Name,Start date,Start time,End date,End time,Unit,Location,Activity Notes\n"
    r = client.post(
        f"/api/planning/years/{year_id}/cea/import",
        files={"file": ("test.csv", csv_content, "text/csv")},
        data={"keep_existing": ""},
        headers=headers,
    )
    assert r.status_code == 200
```

- [ ] **Step 2: Run — expect 403**

```bash
cd backend && python -m pytest tests/test_planning.py::test_sqn_admin_can_import_cea -v
```

Expected: 403 Forbidden.

- [ ] **Step 3: Edit planning.py line 5633**

Change:
```python
require_role(p, "wing_admin", "national_admin", "system_admin")
```
to:
```python
require_role(p, "sqn_admin", "wing_admin", "national_admin", "system_admin")
```

Also update `_require_year_access(p, year, write=True)` — sqn_admin must be granted write access to their own year. Check that `_require_year_access` handles sqn_admin correctly (it checks `p.squadron_id == year.squadron_id`). If it rejects sqn_admin, add the role to its allowed list. Search: `def _require_year_access` in `planning.py`.

- [ ] **Step 4: Run test — expect pass**

```bash
cd backend && python -m pytest tests/test_planning.py::test_sqn_admin_can_import_cea -v
```

- [ ] **Step 5: Full suite**

```bash
cd backend && python -m pytest tests/ -q
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/planning.py backend/tests/test_planning.py
git commit -m "feat: extend CEA import to sqn_admin role"
```

---

### Task 3: Template impact preview — backend endpoint

**Files:**
- Modify: `backend/app/routers/training.py` — add `GET /parade-nights/{pnid}/template-impact`

**Interfaces:**
- Produces: `GET /api/parade-nights/{id}/template-impact?new_template_id=X` → `{current_template_id, new_template_id, added_periods: [{period_number, block_name}], removed_periods: [{period_number, block_name}], orphaned_sessions: [{session_id, title, period_number}]}`

- [ ] **Step 1: Write failing test**

In `backend/tests/test_planning.py`, add:

```python
def test_template_impact_no_change(client):
    """Impact endpoint returns empty lists when template has the same periods."""
    headers = login(client, "ADMIN_CODE")
    pn_r = client.post("/api/parade-nights", json={"date": "2026-11-04", "term": "T2"},
                       headers=headers)
    pn_id = pn_r.json()["parade_night_id"]
    # Get current template
    pn = client.get(f"/api/parade-nights/{pn_id}", headers=headers).json()
    tmpl_id = pn.get("timing_template_id")
    if not tmpl_id:
        pytest.skip("no timing template on test night")
    r = client.get(f"/api/parade-nights/{pn_id}/template-impact?new_template_id={tmpl_id}",
                   headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["added_periods"] == []
    assert body["removed_periods"] == []
    assert body["orphaned_sessions"] == []
```

- [ ] **Step 2: Run — expect 404 (endpoint doesn't exist)**

```bash
cd backend && python -m pytest tests/test_planning.py::test_template_impact_no_change -v
```

- [ ] **Step 3: Add endpoint in routers/training.py**

After `update_parade_night` and before the notices section, add:

```python
@router.get("/parade-nights/{pnid}/template-impact")
def template_impact(
    pnid: str,
    new_template_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Compute period additions/removals/orphans if this parade night switches timing templates.

    Used by the frontend to show a preview before the user confirms the change.
    Returns empty lists when the change has no effect on scheduled sessions.
    """
    pn = db.get(ParadeNight, pnid)
    if not pn or pn.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    require_can_view_squadron(p, pn.squadron_id, pn.wing_id)

    new_tmpl = db.get(TimingTemplate, new_template_id)
    if not new_tmpl or new_tmpl.is_archived:
        raise HTTPException(404, detail={"error": "timing_template_not_found"})

    # Current instructional periods
    current_periods: dict[int, str] = {}  # period_number → block_name
    if pn.timing_template_id:
        cur_tmpl = db.get(TimingTemplate, pn.timing_template_id)
        if cur_tmpl:
            for b in cur_tmpl.blocks:
                if b.is_instructional_period and b.period_number is not None:
                    current_periods[b.period_number] = b.block_name

    # New instructional periods
    new_periods: dict[int, str] = {}
    for b in new_tmpl.blocks:
        if b.is_instructional_period and b.period_number is not None:
            new_periods[b.period_number] = b.block_name

    added = [
        {"period_number": p, "block_name": new_periods[p]}
        for p in sorted(set(new_periods) - set(current_periods))
    ]
    removed = [
        {"period_number": p, "block_name": current_periods[p]}
        for p in sorted(set(current_periods) - set(new_periods))
    ]

    # Sessions whose period_number falls outside new_periods
    removed_period_numbers = {item["period_number"] for item in removed}
    orphaned = []
    if removed_period_numbers:
        sessions = db.query(Session).filter(
            Session.parade_night_id == pnid,
            Session.is_archived == False,  # noqa: E712
            Session.period_number.in_(list(removed_period_numbers)),
        ).all()
        orphaned = [
            {
                "session_id": s.id,
                "title": s.custom_title or s.curriculum_title_at_time or s.session_title,
                "period_number": s.period_number,
            }
            for s in sessions
        ]

    return {
        "current_template_id": pn.timing_template_id,
        "new_template_id": new_template_id,
        "added_periods": added,
        "removed_periods": removed,
        "orphaned_sessions": orphaned,
    }
```

- [ ] **Step 4: Run test — expect pass**

```bash
cd backend && python -m pytest tests/test_planning.py::test_template_impact_no_change -v
```

- [ ] **Step 5: Full suite**

```bash
cd backend && python -m pytest tests/ -q
```

- [ ] **Step 6: Commit**

```bash
git add backend/app/routers/training.py backend/tests/test_planning.py
git commit -m "feat: add GET /parade-nights/{id}/template-impact endpoint"
```

---

### Task 4: Dynamic periods — backend exposes instructional_periods in night_summaries

**Files:**
- Modify: `backend/app/routers/planning.py` — `night_summaries` adds `instructional_periods` per night

**Interfaces:**
- Produces: each night in `night_summaries` gains `"instructional_periods": [{"period_number": int, "block_name": str, "timing_block_id": str}]` (empty list when no template)

- [ ] **Step 1: Write failing test**

```python
def test_night_summaries_include_instructional_periods(client):
    """night_summaries response includes instructional_periods per night."""
    headers = login(client, "ADMIN_CODE")
    years = client.get("/api/planning/years", headers=headers).json()
    if not years:
        pytest.skip("no year")
    year_id = years[0]["year_id"]
    r = client.get(f"/api/planning/night-summaries?year_id={year_id}", headers=headers)
    assert r.status_code == 200
    nights = r.json()
    if nights:
        assert "instructional_periods" in nights[0]
```

- [ ] **Step 2: Run — expect KeyError on field check**

```bash
cd backend && python -m pytest tests/test_planning.py::test_night_summaries_include_instructional_periods -v
```

- [ ] **Step 3: Find and edit night_summaries in planning.py**

The function is at line ~5250. After it builds the `all_dates` query, batch-load timing templates and their instructional blocks:

```python
# Batch-load timing template instructional blocks for all nights
tmpl_ids = list({pn.timing_template_id for pn in all_dates if pn.timing_template_id})
ip_by_tmpl: dict[str, list[dict]] = {}
if tmpl_ids:
    from ..models.training import TimingBlock as TBlock
    blocks = db.query(TBlock).filter(
        TBlock.timing_template_id.in_(tmpl_ids),
        TBlock.is_instructional_period == True,  # noqa: E712
    ).order_by(TBlock.display_order).all()
    for b in blocks:
        if b.period_number is not None:
            ip_by_tmpl.setdefault(b.timing_template_id, []).append({
                "period_number": b.period_number,
                "block_name": b.block_name,
                "timing_block_id": b.id,
            })
```

Then in the per-night output dict, add:
```python
"instructional_periods": ip_by_tmpl.get(pn.timing_template_id, []),
```

- [ ] **Step 4: Run test — expect pass**

```bash
cd backend && python -m pytest tests/test_planning.py::test_night_summaries_include_instructional_periods -v
```

- [ ] **Step 5: Full suite and commit**

```bash
cd backend && python -m pytest tests/ -q
git add backend/app/routers/planning.py backend/tests/test_planning.py
git commit -m "feat: night_summaries includes instructional_periods per parade night"
```

---

### Task 5: Dynamic periods — React replaces BLOCK_PERIODS

**Files:**
- Modify: `frontend/src/api/types.ts` — add `instructional_periods` to night summary type
- Modify: `frontend/src/components/planning/ParadeNightBlock.tsx` — replace `BLOCK_PERIODS` with prop
- Modify: `frontend/src/routes/PlanningWorkspace.tsx` — pass `instructionalPeriods` from night data

**Interfaces:**
- Consumes: `instructional_periods: {period_number: number; block_name: string; timing_block_id: string}[]` from backend
- Produces: `ParadeNightBlock` accepts `instructionalPeriods` prop; falls back to `[{period_number:1},{period_number:2},{period_number:3}]` when absent (backward compat for CalendarView / other call sites)

`★ Insight ─────────────────────────────────────`
`BLOCK_PERIODS` is used in 4 distinct places in `ParadeNightBlock.tsx`: compact mode row cells, compact mode P-labels, standard table headers, and standard table cells. All four must be replaced in one task to avoid a partial state where the UI renders a different number of columns than it receives sessions for.
`─────────────────────────────────────────────────`

- [ ] **Step 1: Update frontend/src/api/types.ts**

On `NightSummary` (or wherever night data is typed — search for `instructional_period_count` or `parade_night_id` in types.ts):

```typescript
export interface InstructionalPeriod {
  period_number: number;
  block_name: string;
  timing_block_id: string;
}
```

Add `instructional_periods: InstructionalPeriod[]` to the night summary interface.
Also add `instructional_periods?: InstructionalPeriod[]` to `NightSessionSummary` (optional for call sites that don't fetch it yet).

- [ ] **Step 2: Update ParadeNightBlock.tsx**

Replace the export:
```typescript
// OLD: export const BLOCK_PERIODS = [1, 2, 3] as const;
// NEW:
const DEFAULT_PERIODS: InstructionalPeriod[] = [
  { period_number: 1, block_name: "Period 1", timing_block_id: "" },
  { period_number: 2, block_name: "Period 2", timing_block_id: "" },
  { period_number: 3, block_name: "Period 3", timing_block_id: "" },
];
export const BLOCK_PERIODS = [1, 2, 3] as const;  // keep for external callers temporarily
```

Add `instructionalPeriods?: InstructionalPeriod[]` to the component's Props interface.

Inside the component function, resolve the effective periods:
```typescript
const periods: InstructionalPeriod[] = (instructionalPeriods && instructionalPeriods.length > 0)
  ? instructionalPeriods
  : DEFAULT_PERIODS;
```

Replace every usage of `BLOCK_PERIODS` inside the component body with `periods`:

**Compact mode** (line ~513):
```typescript
// OLD: const cells = BLOCK_PERIODS.map(p => row.getCellFn(p));
const cells = periods.map(ip => row.getCellFn(ip.period_number));
```
```typescript
// OLD: <span className="pw-block-cg-p">P{BLOCK_PERIODS[i]}</span>
<span className="pw-block-cg-p">P{ip.period_number}</span>
```

**Standard table header** (line ~545):
```typescript
// OLD: {BLOCK_PERIODS.map(p => <th key={p}>P{p}</th>)}
{periods.map(ip => <th key={ip.period_number}>P{ip.period_number}</th>)}
```

**Standard table cells** (line ~552):
```typescript
// OLD: {BLOCK_PERIODS.map(period => {
{periods.map(ip => {
  const period = ip.period_number;
```

- [ ] **Step 3: Update PlanningWorkspace.tsx — pass instructionalPeriods**

The PW passes `trainingClasses` to `ParadeNightBlock` at lines 424, 445, 468, 533. For each, also pass:

```tsx
instructionalPeriods={nightSummary?.instructional_periods ?? []}
```

where `nightSummary` is the matching night summary from `cc?.nights` (or wherever the command-centre data is accessed in the render path for each block). You'll need to look up the night summary by `dateId` / `parade_night_id` from the `cc` data.

Find the pattern in PlanningWorkspace.tsx where `ParadeNightBlock` is rendered and add the prop there.

- [ ] **Step 4: TypeScript check**

```bash
cd frontend && npm run typecheck
```

Fix any type errors before proceeding.

- [ ] **Step 5: Build check**

```bash
cd frontend && npm run build
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/types.ts \
        frontend/src/components/planning/ParadeNightBlock.tsx \
        frontend/src/routes/PlanningWorkspace.tsx
git commit -m "feat: replace BLOCK_PERIODS hardcode with dynamic template-derived instructional periods"
```

---

### Task 6: Phase grouping in Planning Workspace grid rows

**Files:**
- Modify: `frontend/src/components/planning/ParadeNightBlock.tsx` — group `trainingClasses` by `stage_code` with phase section headers

**Interfaces:**
- Consumes: `TrainingClassSummary` with `training_stage_id`, `stage_code` (or equivalent from PW data)
- Produces: `gridRows` array interleaved with phase header rows; `getCellFn` unchanged

The stage ordering (ORI → INI → JNR → INT → SNR) maps to existing `stage_code` values. Groups with no stage_code get an "Other" bucket last.

- [ ] **Step 1: Define stage order constant at top of ParadeNightBlock.tsx**

```typescript
const STAGE_ORDER: Record<string, number> = {
  ORI: 0, INI: 1, JNR: 2, INT: 3, SNR: 4,
};
const STAGE_LABELS: Record<string, string> = {
  ORI: "Orientation", INI: "Initial", JNR: "Junior", INT: "Intermediate", SNR: "Senior",
};
```

- [ ] **Step 2: Replace the `gridRows` construction block (lines 399–415)**

The `trainingClasses.length > 0` branch sorts by `class_number` only. Replace it with phase-grouped rows:

```typescript
const gridRows: GridRow[] = trainingClasses.length > 0
  ? (() => {
      // Group by stage_code; classes without a stage_code go into "Other"
      const groups = new Map<string, TrainingClassSummary[]>();
      for (const tc of trainingClasses) {
        const key = tc.stage_code ?? "__other__";
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key)!.push(tc);
      }
      // Sort groups by STAGE_ORDER; sort classes within each group by class_number
      const sortedKeys = [...groups.keys()].sort((a, b) => {
        const oa = STAGE_ORDER[a] ?? 99;
        const ob = STAGE_ORDER[b] ?? 99;
        return oa - ob;
      });
      const rows: GridRow[] = [];
      for (const key of sortedKeys) {
        const classes = groups.get(key)!.sort((a, b) => a.class_number - b.class_number);
        // Phase header row — getCellFn always null, emptyCellClickFn is no-op
        rows.push({
          key: `__phase_${key}`,
          shortLabel: STAGE_LABELS[key] ?? "Other",
          fullLabel: STAGE_LABELS[key] ?? "Other",
          isPhaseHeader: true,
          getCellFn: () => null,
          emptyCellClickFn: () => {},
          dropKeySuffix: () => "",
        });
        for (const tc of classes) {
          rows.push({
            key: tc.training_class_id,
            shortLabel: tc.display_name,
            fullLabel: tc.display_name,
            getCellFn: (p: number) => getCellByClassId(sessions, tc.training_class_id, p),
            emptyCellClickFn: (p: number) => {
              if (onEmptyCellClick) onEmptyCellClick("", p, tc.training_class_id);
              else onHeaderClick();
            },
            dropKeySuffix: (p: number) => `${p}-${tc.training_class_id}`,
          });
        }
      }
      return rows;
    })()
  : BLOCK_GROUPS.map(g => ({
      key: g.key,
      shortLabel: g.label,
      fullLabel: g.fullLabel,
      getCellFn: (p: number) => getCell(sessions, g.cadetGroups, p),
      emptyCellClickFn: (p: number) => {
        if (onEmptyCellClick) onEmptyCellClick(g.cadetGroups[0], p); else onHeaderClick();
      },
      dropKeySuffix: (p: number) => `${p}-${g.cadetGroups[0]}`,
    }));
```

- [ ] **Step 3: Update GridRow type to include optional isPhaseHeader**

```typescript
type GridRow = {
  key: string;
  shortLabel: string;
  fullLabel: string;
  isPhaseHeader?: boolean;
  getCellFn: (period: number) => DisplaySession | null;
  emptyCellClickFn: (period: number) => void;
  dropKeySuffix: (period: number) => string;
};
```

- [ ] **Step 4: Update render loops to handle phase header rows**

In the compact mode `gridRows.map`:
```tsx
if (row.isPhaseHeader) {
  return (
    <div key={row.key} className="pw-phase-header">
      {row.shortLabel}
    </div>
  );
}
```

In the standard table `gridRows.map`:
```tsx
if (row.isPhaseHeader) {
  return (
    <tr key={row.key} className="pw-phase-header-row">
      <th colSpan={periods.length + 1} className="pw-phase-header-cell">
        {row.fullLabel}
      </th>
    </tr>
  );
}
```

- [ ] **Step 5: Add CSS for phase header rows**

In `frontend/src/styles/planning.css` (or wherever PW styles live — check `@import` chain):

```css
.pw-phase-header { font-size: var(--fs-xs); font-weight: 600; color: var(--muted-text);
  text-transform: uppercase; letter-spacing: 0.04em; padding: 4px 8px 2px; }
.pw-phase-header-row th { background: var(--surface-2); font-size: var(--fs-xs);
  font-weight: 600; color: var(--muted-text); text-transform: uppercase; padding: 4px 8px; }
```

- [ ] **Step 6: TypeScript check and build**

```bash
cd frontend && npm run typecheck && npm run build
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/planning/ParadeNightBlock.tsx \
        frontend/src/styles/  # whichever CSS file was changed
git commit -m "feat: group TrainingClass grid rows by phase with section headers"
```

---

### Task 7: Shared session dimming in grid cells

**Files:**
- Modify: `frontend/src/components/planning/ParadeNightBlock.tsx` — detect shared cells and apply dimmed style

**Interfaces:**
- Consumes: `DisplaySession.training_classes` length > 1 → shared
- Produces: shared cells get `pw-night-cell--shared` CSS class; a "shared" badge appears

- [ ] **Step 1: Add isShared detection in standard table cell render**

In the standard table's `BLOCK_PERIODS.map` (now `periods.map`) cell render, when `cell !== null`, detect shared:

```tsx
const isShared = (cell.training_classes?.length ?? 0) > 1;
```

Apply to the `<td>`:
```tsx
<td
  className={`pw-night-cell${isShared ? " pw-night-cell--shared" : ""}...`}
  ...
>
  {isShared && <span className="pw-shared-badge">shared</span>}
  {/* existing cell content */}
</td>
```

- [ ] **Step 2: Add CSS**

```css
.pw-night-cell--shared { opacity: 0.72; }
.pw-night-cell--shared:hover { opacity: 1; }
.pw-shared-badge {
  display: inline-block; font-size: var(--fs-3xs, 9px); font-weight: 600;
  background: var(--aafc-blue, #51b0e3); color: #fff;
  border-radius: 2px; padding: 0 3px; margin-left: 4px; vertical-align: middle;
}
```

- [ ] **Step 3: Build check**

```bash
cd frontend && npm run typecheck && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/planning/ParadeNightBlock.tsx frontend/src/styles/
git commit -m "feat: dim shared-audience session cells with 'shared' badge"
```

---

### Task 8: Template change confirmation flow (React)

**Files:**
- Create: `frontend/src/components/planning/TemplateImpactModal.tsx`
- Modify: `frontend/src/routes/ParadeNightDetail.tsx` — call impact endpoint, show modal before applying

**Interfaces:**
- Consumes: `GET /api/parade-nights/{id}/template-impact?new_template_id=X` (Task 3)
- Produces: user sees added/removed periods and orphaned sessions before confirming; PATCH is sent only after explicit confirm

- [ ] **Step 1: Create TemplateImpactModal.tsx**

```tsx
import type { FC } from "react";

interface ImpactPeriod { period_number: number; block_name: string; }
interface ImpactSession { session_id: string; title: string | null; period_number: number; }

interface Props {
  added: ImpactPeriod[];
  removed: ImpactPeriod[];
  orphaned: ImpactSession[];
  onConfirm: () => void;
  onCancel: () => void;
}

export const TemplateImpactModal: FC<Props> = ({ added, removed, orphaned, onConfirm, onCancel }) => (
  <div className="modal-overlay" role="dialog" aria-modal="true" aria-label="Template change impact">
    <div className="modal-card" style={{ maxWidth: 480 }}>
      <h3 style={{ marginTop: 0 }}>Change timing template?</h3>
      {added.length > 0 && (
        <div>
          <strong>Periods added:</strong>
          <ul>{added.map(p => <li key={p.period_number}>Period {p.period_number} — {p.block_name}</li>)}</ul>
        </div>
      )}
      {removed.length > 0 && (
        <div>
          <strong>Periods removed:</strong>
          <ul>{removed.map(p => <li key={p.period_number}>Period {p.period_number} — {p.block_name}</li>)}</ul>
        </div>
      )}
      {orphaned.length > 0 && (
        <div style={{ color: "var(--aafc-red, #e51937)", marginTop: 8 }}>
          <strong>⚠ {orphaned.length} session{orphaned.length > 1 ? "s" : ""} will be orphaned</strong>
          <ul>
            {orphaned.map(s => (
              <li key={s.session_id}>
                Period {s.period_number} — {s.title ?? "(untitled)"}
              </li>
            ))}
          </ul>
          <p style={{ fontSize: "0.875rem" }}>
            These sessions will remain but will no longer appear on the timetable grid. Resolve them manually after switching.
          </p>
        </div>
      )}
      {added.length === 0 && removed.length === 0 && orphaned.length === 0 && (
        <p>No impact on scheduled sessions.</p>
      )}
      <div style={{ display: "flex", gap: 8, marginTop: 16, justifyContent: "flex-end" }}>
        <button className="btn out" onClick={onCancel}>Cancel</button>
        <button className="btn primary" onClick={onConfirm}>
          {orphaned.length > 0 ? "Change anyway" : "Confirm"}
        </button>
      </div>
    </div>
  </div>
);
```

- [ ] **Step 2: Wire into ParadeNightDetail.tsx template switcher**

Find the template apply handler in `ParadeNightDetail.tsx`. Before calling `PATCH /parade-nights/{id}` with the new `timing_template_id`:

```tsx
const [impactData, setImpactData] = useState<null | {
  added: ImpactPeriod[]; removed: ImpactPeriod[]; orphaned: ImpactSession[];
  pendingTemplateId: string;
}>(null);

async function handleTemplateApply(newTemplateId: string) {
  // 1. Fetch impact first
  const impact = await trainingApi.templateImpact(paradeNightId, newTemplateId);
  // 2. If no sessions affected AND no periods changed, apply immediately
  if (impact.added_periods.length === 0 && impact.removed_periods.length === 0) {
    await applyTemplateChange(newTemplateId);
    return;
  }
  // 3. Otherwise show the modal
  setImpactData({
    added: impact.added_periods,
    removed: impact.removed_periods,
    orphaned: impact.orphaned_sessions,
    pendingTemplateId: newTemplateId,
  });
}

async function applyTemplateChange(templateId: string) {
  await trainingApi.patchParadeNight(paradeNightId, { timing_template_id: templateId, version: currentVersion });
  setImpactData(null);
  // refresh
}
```

Render `TemplateImpactModal` conditionally when `impactData !== null`.

- [ ] **Step 3: Add templateImpact to frontend/src/api/index.ts**

```typescript
templateImpact: (parade_night_id: string, new_template_id: string) =>
  api.get<{
    current_template_id: string | null;
    new_template_id: string;
    added_periods: { period_number: number; block_name: string }[];
    removed_periods: { period_number: number; block_name: string }[];
    orphaned_sessions: { session_id: string; title: string | null; period_number: number }[];
  }>(`/api/parade-nights/${parade_night_id}/template-impact?new_template_id=${new_template_id}`),
```

- [ ] **Step 4: TypeScript check and build**

```bash
cd frontend && npm run typecheck && npm run build
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/planning/TemplateImpactModal.tsx \
        frontend/src/routes/ParadeNightDetail.tsx \
        frontend/src/api/index.ts
git commit -m "feat: template-change impact preview + confirmation modal in ParadeNightDetail"
```

---

### Task 9: CEA import button in connected frontend (TMS Activities)

**Files:**
- Modify: `connected-frontend/index.html` — add CEA import button for wing_admin+/sqn_admin

**Interfaces:**
- Consumes: canonical `POST /api/planning/years/{year_id}/cea/import` (Task 2 extended to sqn_admin)
- Produces: button visible only to roles with access; calls `api()` with FormData (multipart/form-data)

- [ ] **Step 1: Find TMS Activities section in index.html**

```bash
grep -n "page-activities\|page-cea\|cea.import\|TMS.*Activities\|m-cea-import\|importCea\|loadActivities" connected-frontend/index.html | head -20
```

Identify: the page container, the load function, and the render function for the Activities page.

- [ ] **Step 2: Add import button HTML (inside TMS Activities page container)**

```html
<!-- CEA Import button — visible to wing_admin+, sqn_admin -->
<div id="cea-import-section" style="display:none">
  <button class="btn primary" onclick="showCeaImportModal()" id="btn-cea-import">
    Import CEA CSV
  </button>
</div>
<!-- Modal -->
<div id="m-cea-import" class="modal-overlay" style="display:none" role="dialog" aria-modal="true">
  <div class="modal-card" style="max-width:420px">
    <h3>Import CEA Activities</h3>
    <label>Planning year:
      <select id="cea-import-year"></select>
    </label><br><br>
    <label>CEA CSV file:
      <input type="file" id="cea-import-file" accept=".csv">
    </label>
    <div id="cea-import-err" style="color:var(--red);margin-top:8px;display:none"></div>
    <div style="display:flex;gap:8px;margin-top:16px;justify-content:flex-end">
      <button class="btn out" onclick="closeCeaImportModal()">Cancel</button>
      <button class="btn primary" onclick="submitCeaImport()">Import</button>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Add JS for the modal**

```javascript
function showCeaImportModal() {
  // Populate year selector from S.years (or fetch if not cached)
  const sel = el('cea-import-year');
  sel.innerHTML = '';
  (S.years || []).forEach(y => {
    const opt = document.createElement('option');
    opt.value = y.year_id;
    opt.textContent = y.year_label || y.year;
    sel.appendChild(opt);
  });
  show('m-cea-import');
}
function closeCeaImportModal() { hide('m-cea-import'); }

async function submitCeaImport() {
  const yearId = el('cea-import-year').value;
  const file = el('cea-import-file').files[0];
  if (!file) { showErr('cea-import-err', 'Select a CSV file.'); return; }
  const fd = new FormData();
  fd.append('file', file);
  fd.append('keep_existing', '');
  try {
    const r = await api(`/api/planning/years/${yearId}/cea/import`, {method:'POST', body:fd});
    closeCeaImportModal();
    showToast(`Imported ${r.imported_count ?? 0} activities.`);
    if (typeof loadActivities === 'function') loadActivities();
  } catch(e) { showErr('cea-import-err', apiErr(e)); }
}
```

- [ ] **Step 4: Show/hide import section based on role**

In the Activities page load function (or `loadActivities`), add:
```javascript
const canImport = ['sqn_admin','wing_admin','national_admin','system_admin'].includes(S.role);
toggle('cea-import-section', canImport);
```

- [ ] **Step 5: Manual test in browser**

Start backend + frontend:
```bash
cd backend && uvicorn app.main:app --reload --port 8000 &
cd connected-frontend && python3 -m http.server 8080
```

Open `http://localhost:8080`, log in as sqn_admin, navigate to Activities. Verify:
- Import button is visible
- Modal opens
- Selecting a CSV and submitting calls the endpoint

Log in as sqn_general — verify import button is absent.

- [ ] **Step 6: Commit**

```bash
git add connected-frontend/index.html
git commit -m "feat: CEA import button in TMS Activities for wing_admin+/sqn_admin"
```

---

### Task 10: Create Parade Night — simplify form (connected frontend)

**Files:**
- Modify: `connected-frontend/index.html` — simplify create PN form to Term, Date, Timing Template, Notes only

**Interfaces:**
- Consumes: `POST /api/parade-nights` with `{date, term, timing_template_id?, notes?}`
- Produces: simplified modal; after creation, navigate to the new parade night's detail page

- [ ] **Step 1: Find existing create parade night form**

```bash
grep -n "createParadeNight\|create.*parade\|POST.*parade-nights\|m-create-pn\|m-pn-create" connected-frontend/index.html | head -15
```

From the context gathered earlier, line 10140 calls:
```javascript
await api('/api/parade-nights',{method:'POST',body:JSON.stringify({date,term,parade_type:notes||'normal'})});
```

This call incorrectly uses `notes` as `parade_type`. The simplification replaces this with a proper form.

- [ ] **Step 2: Update create PN modal HTML**

Replace the existing create PN modal body with:
```html
<div class="form-row">
  <label>Date <input type="date" id="cpn-date" required></label>
  <label>Term <input type="text" id="cpn-term" placeholder="T1" maxlength="10"></label>
</div>
<div class="form-row">
  <label>Timing Template
    <select id="cpn-template">
      <option value="">(use squadron default)</option>
    </select>
  </label>
</div>
<div class="form-row">
  <label>Notes <textarea id="cpn-notes" rows="2" placeholder="Optional"></textarea></label>
</div>
```

- [ ] **Step 3: Populate timing template dropdown**

When the modal opens, fetch available templates and populate the select:
```javascript
async function openCreatePNModal() {
  const templates = await api('/api/timing-templates');
  const sel = el('cpn-template');
  sel.innerHTML = '<option value="">(use squadron default)</option>';
  (templates || []).filter(t => t.active_status && !t.is_archived).forEach(t => {
    const opt = document.createElement('option');
    opt.value = t.timing_template_id;
    opt.textContent = t.name;
    sel.appendChild(opt);
  });
  show('m-create-pn');
}
```

- [ ] **Step 4: Update submit handler**

```javascript
async function submitCreatePN() {
  const date = el('cpn-date').value;
  const term = el('cpn-term').value.trim() || null;
  const timing_template_id = el('cpn-template').value || null;
  const notes = el('cpn-notes').value.trim() || null;
  if (!date) { showErr('cpn-err', 'Date is required.'); return; }
  try {
    const r = await api('/api/parade-nights', {
      method: 'POST',
      body: JSON.stringify({ date, term, timing_template_id, notes }),
    });
    hide('m-create-pn');
    showToast('Parade night created.');
    // Navigate to the new night's detail
    if (r.parade_night_id) navToScheduledPN(date);
    else await reloadAndRender();
  } catch(e) { showErr('cpn-err', apiErr(e)); }
}
```

- [ ] **Step 5: Also update ParadeNightUpdateIn backend to accept notes on PATCH**

Check `backend/app/routers/training.py` `ParadeNightUpdateIn` — `notes` is already present (`notes: str | None = None`). No change needed.

- [ ] **Step 6: Manual browser test**

Open `http://localhost:8080`, create a new parade night. Verify:
- Only Term, Date, Timing Template, Notes fields appear
- Parade type is NOT in the create form (only in detail)
- Creation succeeds and navigates to the new night

- [ ] **Step 7: Commit**

```bash
git add connected-frontend/index.html
git commit -m "feat: simplify create parade night form to Term/Date/Template/Notes"
```

---

### Task 12: Immutable timing snapshot — schema + migration + backend wiring

**Files:**
- Create: `backend/alembic/versions/v_timing_snapshot.py` — new table + backfill
- Modify: `backend/app/models/training.py` — add `ParadeNightTimingSnapshot`
- Modify: `backend/app/routers/training.py` — write snapshot on create/template-change; read snapshot in `builder`, `_validate_timing_block`; `template_impact` compares against snapshot
- Modify: `backend/app/routers/planning.py` — `night_summaries` reads snapshot for `instructional_periods`

**Interfaces:**
- Produces: every parade night that has a `timing_template_id` at the time of this migration gets a backfilled snapshot; new nights get a snapshot on creation; template changes replace the snapshot atomically with the PATCH commit

**Design note:** `Session.timing_block_id` continues to point to the original `timing_blocks.id` from the live template. The snapshot stores `source_block_id` for reconciliation. The builder and night_summaries use the snapshot's `is_instructional_period` / `period_number` to derive the grid structure — they no longer follow `pn.timing_template_id` through the live template. The `_validate_timing_block` check validates that `session.timing_block_id` appears in the snapshot's `source_block_id` list (not the live template), so a session referencing a block that was in the template when the snapshot was taken remains valid even if the block is later removed from the template.

- [ ] **Step 1: Add ParadeNightTimingSnapshot model to models/training.py**

After `ParadeNightTimingOverride` (around line 372):

```python
class ParadeNightTimingSnapshot(Base, UUIDMixin, TimestampMixin):
    """Immutable copy of a TimingTemplate's blocks at the moment a parade night adopts it.

    Once written, these rows are never updated — even if the source template is edited.
    Protects historical nights from silent period-structure rewrites (Requirement 3).

    source_block_id: the original timing_blocks.id this row was copied from.
    Session.timing_block_id continues to reference timing_blocks.id; the snapshot
    uses source_block_id to reconcile which sessions fall in which period for this night.
    """
    __tablename__ = "parade_night_timing_snapshots"
    parade_night_id: Mapped[str] = mapped_column(ForeignKey("parade_nights.id"), index=True)
    source_template_id: Mapped[str] = mapped_column(String(36))
    source_block_id: Mapped[str] = mapped_column(String(36))
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    block_name: Mapped[str] = mapped_column(String(80))
    block_type: Mapped[str] = mapped_column(String(40), default="custom")
    start_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    end_time: Mapped[str | None] = mapped_column(String(10), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_instructional_period: Mapped[bool] = mapped_column(Boolean, default=False)
    period_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

- [ ] **Step 2: Add import to models/__init__.py**

```python
from .training import (..., ParadeNightTimingSnapshot)
```

- [ ] **Step 3: Write migration v_timing_snapshot.py**

```python
"""Create parade_night_timing_snapshots and backfill from existing timing_template_id references.

Revision ID: v_timing_snap_001
Revises: <result of `alembic heads` after Task 1 migration>
Create Date: 2026-09-05
"""
from __future__ import annotations
import uuid
import sqlalchemy as sa
from alembic import op

revision = "v_timing_snap_001"
down_revision = "v_asst_fac_001"  # chain after Task 1; replace with real head
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parade_night_timing_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("parade_night_id", sa.String(36),
                  sa.ForeignKey("parade_nights.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_template_id", sa.String(36), nullable=False),
        sa.Column("source_block_id", sa.String(36), nullable=False),
        sa.Column("display_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("block_name", sa.String(80), nullable=False),
        sa.Column("block_type", sa.String(40), nullable=False, server_default="custom"),
        sa.Column("start_time", sa.String(10), nullable=True),
        sa.Column("end_time", sa.String(10), nullable=True),
        sa.Column("duration_minutes", sa.Integer, nullable=True),
        sa.Column("is_instructional_period", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("period_number", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_pnts_parade_night_id", "parade_night_timing_snapshots", ["parade_night_id"])

    # Backfill: for every existing parade night with a timing_template_id,
    # copy the current template blocks into the snapshot table.
    conn = op.get_bind()
    nights = conn.execute(
        sa.text("SELECT id, timing_template_id FROM parade_nights WHERE timing_template_id IS NOT NULL")
    ).fetchall()
    for pn_id, tmpl_id in nights:
        blocks = conn.execute(
            sa.text(
                "SELECT id, display_order, block_name, block_type, start_time, end_time, "
                "duration_minutes, is_instructional_period, period_number "
                "FROM timing_blocks WHERE timing_template_id = :tid ORDER BY display_order"
            ),
            {"tid": tmpl_id},
        ).fetchall()
        for b in blocks:
            conn.execute(
                sa.text(
                    "INSERT INTO parade_night_timing_snapshots "
                    "(id, parade_night_id, source_template_id, source_block_id, display_order, "
                    "block_name, block_type, start_time, end_time, duration_minutes, "
                    "is_instructional_period, period_number) "
                    "VALUES (:id, :pn_id, :tmpl_id, :block_id, :ord, :name, :btype, "
                    ":st, :et, :dur, :is_ip, :pn)"
                ),
                {
                    "id": str(uuid.uuid4()), "pn_id": pn_id, "tmpl_id": tmpl_id,
                    "block_id": b[0], "ord": b[1], "name": b[2], "btype": b[3],
                    "st": b[4], "et": b[5], "dur": b[6], "is_ip": b[7], "pn": b[8],
                },
            )


def downgrade() -> None:
    op.drop_table("parade_night_timing_snapshots")
```

- [ ] **Step 4: Run migration**

```bash
cd backend && source .venv/bin/activate && alembic upgrade head
```

- [ ] **Step 5: Write snapshot helper function in routers/training.py**

Add before `create_parade_night`:

```python
def _write_timing_snapshot(db: DBSession, pn_id: str, tmpl: TimingTemplate) -> None:
    """Copy a timing template's blocks into an immutable snapshot for one parade night.
    Deletes any existing snapshot for this night first (idempotent for re-apply on template change).
    """
    from app.models.training import ParadeNightTimingSnapshot as PNTS
    db.query(PNTS).filter(PNTS.parade_night_id == pn_id).delete()
    for b in tmpl.blocks:
        db.add(PNTS(
            id=str(uuid.uuid4()),
            parade_night_id=pn_id,
            source_template_id=tmpl.id,
            source_block_id=b.id,
            display_order=b.display_order,
            block_name=b.block_name,
            block_type=b.block_type,
            start_time=b.start_time,
            end_time=b.end_time,
            duration_minutes=b.duration_minutes,
            is_instructional_period=b.is_instructional_period,
            period_number=b.period_number,
        ))
```

- [ ] **Step 6: Call _write_timing_snapshot on create_parade_night**

In the `create_parade_night` handler, after `db.add(pn); db.flush()` (after the `pn` object gets its ID), and when `effective_tmpl` is set:

```python
if effective_tmpl:
    _write_timing_snapshot(db, pn.id, effective_tmpl)
```

This must happen before `db.commit()`.

- [ ] **Step 7: Call _write_timing_snapshot on update_parade_night (template change)**

In `update_parade_night`, inside the `"timing_template_id" in body.model_fields_set` branch, after setting `pn.timing_template_id = body.timing_template_id`:

```python
if body.timing_template_id:
    _write_timing_snapshot(db, pn.id, tmpl)  # tmpl already fetched above
else:
    # Template cleared — remove snapshot
    from app.models.training import ParadeNightTimingSnapshot as PNTS
    db.query(PNTS).filter(PNTS.parade_night_id == pn.id).delete()
```

- [ ] **Step 8: Update builder endpoint to read from snapshot**

In `parade_night_builder`, replace:
```python
if pn.timing_template_id:
    tmpl = db.get(TimingTemplate, pn.timing_template_id)
if not tmpl:
    tmpl = _effective_template(db, pn.squadron_id, pn.date)
if tmpl:
    blocks = db.query(TimingBlock).filter(TimingBlock.timing_template_id == tmpl.id) ...
```
With:
```python
from app.models.training import ParadeNightTimingSnapshot as PNTS
snap_blocks = db.query(PNTS).filter(
    PNTS.parade_night_id == pnid,
).order_by(PNTS.display_order).all()

if snap_blocks:
    timing_blocks = [
        {
            "display_order": b.display_order, "block_name": b.block_name,
            "block_type": b.block_type, "start_time": b.start_time,
            "end_time": b.end_time, "duration_minutes": b.duration_minutes,
            "is_instructional_period": b.is_instructional_period,
            "period_number": b.period_number,
            "timing_block_id": b.source_block_id,  # original block id for session linkage
        }
        for b in snap_blocks
    ]
    ip_count = sum(1 for b in snap_blocks if b.is_instructional_period)
    if ip_count > 0:
        session_count = ip_count
    timing_template_id = snap_blocks[0].source_template_id
else:
    # No snapshot — fall back to effective template (new nights without a template)
    tmpl = _effective_template(db, pn.squadron_id, pn.date)
    if tmpl:
        # ... existing block-loading code ...
```

- [ ] **Step 9: Update _validate_timing_block to check snapshot first**

In `_validate_timing_block`, after checking `blk is None`:

```python
from app.models.training import ParadeNightTimingSnapshot as PNTS
if pn is not None:
    snap_ids = {
        row.source_block_id
        for row in db.query(PNTS).filter(PNTS.parade_night_id == pn.id).all()
    }
    if snap_ids:
        # This night has a snapshot — validate against snapshot, not live template
        if block_id not in snap_ids:
            raise HTTPException(400, detail={
                "error": "unknown_timing_block",
                "message": "That program period is not part of this night's timing template.",
            })
        return  # valid — skip live-template check below
```

- [ ] **Step 10: Update night_summaries to read from snapshot**

In `planning.py`'s `night_summaries`, replace the batch-load of `timing_blocks` by `tmpl_id` (from Task 4) with snapshot-based loading:

```python
# Batch-load snapshot instructional periods for all nights
from ..models.training import ParadeNightTimingSnapshot as PNTS
night_ids_with_tmpl = [pn.id for pn in all_dates if pn.timing_template_id]
ip_by_night: dict[str, list[dict]] = {}
if night_ids_with_tmpl:
    snaps = db.query(PNTS).filter(
        PNTS.parade_night_id.in_(night_ids_with_tmpl),
        PNTS.is_instructional_period == True,  # noqa: E712
    ).order_by(PNTS.display_order).all()
    for s in snaps:
        if s.period_number is not None:
            ip_by_night.setdefault(s.parade_night_id, []).append({
                "period_number": s.period_number,
                "block_name": s.block_name,
                "timing_block_id": s.source_block_id,
            })
```

Then in per-night output:
```python
"instructional_periods": ip_by_night.get(pn.id, []),
```

- [ ] **Step 11: Update template_impact to compare against snapshot**

In `template_impact` (Task 3), replace the `current_periods` derivation:

```python
# Current periods come from the snapshot (if exists), not the live template
from app.models.training import ParadeNightTimingSnapshot as PNTS
snap_blocks = db.query(PNTS).filter(
    PNTS.parade_night_id == pnid,
    PNTS.is_instructional_period == True,  # noqa: E712
).all()
if snap_blocks:
    current_periods = {b.period_number: b.block_name for b in snap_blocks if b.period_number is not None}
elif pn.timing_template_id:
    cur_tmpl = db.get(TimingTemplate, pn.timing_template_id)
    if cur_tmpl:
        for b in cur_tmpl.blocks:
            if b.is_instructional_period and b.period_number is not None:
                current_periods[b.period_number] = b.block_name
```

- [ ] **Step 12: Write tests**

Add to `backend/tests/test_assistant_facilitator.py` (or a new `test_timing_snapshot.py`):

```python
def test_timing_snapshot_created_on_parade_night_create(client):
    """Creating a parade night with a timing template writes a snapshot."""
    headers = login(client, "ADMIN_CODE")
    # Get a template with blocks
    templates = client.get("/api/timing-templates", headers=headers).json()
    if not templates:
        pytest.skip("no timing templates")
    tmpl_id = templates[0]["timing_template_id"]
    r = client.post("/api/parade-nights", json={
        "date": "2026-11-11", "term": "T2", "timing_template_id": tmpl_id,
    }, headers=headers)
    assert r.status_code == 200
    pn_id = r.json()["parade_night_id"]
    # Verify snapshot exists
    from app.database import get_db
    from app.models.training import ParadeNightTimingSnapshot as PNTS
    db = next(get_db())
    snaps = db.query(PNTS).filter(PNTS.parade_night_id == pn_id).all()
    assert len(snaps) > 0

def test_template_impact_uses_snapshot_not_live_template(client):
    """template-impact compares against the snapshot, not the current live template."""
    # This test verifies that even if the live template was edited after creation,
    # the impact endpoint shows a diff against what the night actually has.
    headers = login(client, "ADMIN_CODE")
    # Create night with template
    templates = client.get("/api/timing-templates", headers=headers).json()
    if not templates:
        pytest.skip("no timing templates")
    tmpl_id = templates[0]["timing_template_id"]
    pn = client.post("/api/parade-nights", json={
        "date": "2026-11-18", "term": "T2", "timing_template_id": tmpl_id,
    }, headers=headers)
    pn_id = pn.json()["parade_night_id"]
    # Impact against same template should be empty
    r = client.get(f"/api/parade-nights/{pn_id}/template-impact?new_template_id={tmpl_id}",
                   headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["added_periods"] == []
    assert body["removed_periods"] == []
```

- [ ] **Step 13: Full suite**

```bash
cd backend && python -m pytest tests/ -q
```

- [ ] **Step 14: Commit**

```bash
git add backend/alembic/versions/v_timing_snapshot.py \
        backend/app/models/training.py \
        backend/app/routers/training.py \
        backend/app/routers/planning.py \
        backend/tests/
git commit -m "feat: immutable timing snapshot per parade night (Req 3 — historical nights immune to template edits)"
```

---

### Task 11: Regression sweep + full test suite

**Files:** No new files. Verification only.

- [ ] **Step 1: Full backend test suite**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/ -q --tb=short
```

Expected: all tests pass (2258+). If any fail, fix before continuing.

- [ ] **Step 2: Security greps**

```bash
cd /path/to/repo
grep -Rc -E "your unit only|Controlled access for training" connected-frontend backend
grep -Rc -E "View current code|Show access code|Reveal code|Display existing code" connected-frontend backend
grep -Rc -E "ADMIN703|ADMIN7WG|ADMINNATIONAL|SYSADMIN2026|plain_code|code_hash|access_code|localStorage" connected-frontend
grep -Rc -E "JWT_SECRET|SECRET_KEY|DATABASE_URL" connected-frontend
```

All must return 0 matches (or known-false-positives already documented in security.md).

- [ ] **Step 3: TypeScript check**

```bash
cd frontend && npm run typecheck
```

- [ ] **Step 4: Deploy script gates**

```bash
bash scripts/deploy-production.sh --dry-run
```

Or run the gate checks manually. Verify Gate 8 (localStorage) and Gate 5 (security greps) still pass.

- [ ] **Step 5: Manual browser smoke test — Planning Workspace**

Start backend + planning workspace:
```bash
cd backend && uvicorn app.main:app --reload --port 8000 &
cd frontend && npm run dev
```

Verify:
1. Planning Workspace loads — grid shows phase-grouped rows (ORI, INI, JNR, INT, SNR headers)
2. Period columns derive from timing template — not hard-coded to 3
3. Shared-audience sessions show dimmed with "shared" badge
4. Template switcher shows impact preview before confirming

- [ ] **Step 6: Final commit**

```bash
git add .
git commit -m "feat: parade night planning redesign — assistant facilitators, dynamic periods, phase grouping, CEA, template impact"
```

---

## Self-Review

### Spec coverage check

| Requirement | Task |
|---|---|
| 1. Retire default 1/2/3 periods — template is source of truth | Task 4 (backend) + Task 5 (React) |
| 2. Remove BLOCK_PERIODS hard-code from Planning Workspace | Task 5 |
| 3. Template snapshot safety | Task 12 — `parade_night_timing_snapshots` table, backfill migration, snapshot written on create/template-change |
| 4. Template change after planning — impact preview + confirm | Task 3 + Task 8 |
| 5. Simplify Create Parade Night UI | Task 10 |
| 6. After creation → navigate to training plan | Task 10 (navToScheduledPN) |
| 7. Redesign planning as phase-grouped rows × period columns | Task 5 + Task 6 |
| 8. Show every Training Class in every Phase | Task 6 |
| 9. Session/SessionAudience remain authoritative | No new table — preserved |
| 10. Shared/combined sessions representable without duplicates | Task 7 (dimming) |
| 11. Main + unlimited assistant facilitators | Task 1 |
| 12. Rooms = existing TrainingArea records | No change needed — already mapped |
| 13. TMS and Planning Workspace convergence | night_summaries extension (Task 4) |
| 14. CEA import exposure from TMS Activities | Task 2 + Task 9 |
| 15. Responsive design + accessibility | Not explicitly tasked — separate CSS task |


**Gap — Req 15 (responsive/a11y):** Not scoped as a discrete task. Phase-header rows include `colSpan` which is accessible. Dynamic period columns preserve the existing `role="button"` / `tabIndex` / `onKeyDown` patterns. A dedicated accessibility review pass would be appropriate after all UI tasks are complete.

### Placeholder scan

None found — all code blocks are complete implementations.

### Type consistency

- `InstructionalPeriod` defined in Task 5 (types.ts) and consumed in same task (ParadeNightBlock)
- `SessionAssistantFacilitator` defined in Task 1 (model) consumed in Task 1 (router)
- `templateImpact` API call defined in Task 8 (api/index.ts) — used in same task
- `ImpactPeriod` / `ImpactSession` defined in Task 8 (TemplateImpactModal) — internal only
