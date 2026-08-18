# Service Desk (Sub-project E) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a lightweight internal service desk — public and in-app ticket submission, role-scoped ticket list, and system_admin actioning — to the AAFC TMS.

**Architecture:** New `service_tickets` table + 4 FastAPI endpoints in a new router + modal form and Service Desk page added to the single-file SPA (`connected-frontend/index.html`). No changes to existing tables or endpoints.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + Alembic (SQLite-compatible), Pydantic v2 + `email-validator`, plain HTML/CSS/JS in the existing SPA.

**Spec:** `docs/superpowers/specs/2026-08-19-service-desk-design.md`

## Global Constraints

- Repo root: `/Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v17_1_source`
- Backend test DB: SQLite in-memory (conftest.py). All tests use `login(client, code)` from `tests/conftest.py`. Never mock the DB.
- Seed access codes (from `backend/app/seeds/seed_all.py`):
  - `SYSADMIN2026` → system_admin
  - `ADMINNATIONAL` → national_admin
  - `ADMIN7WG` → wing_admin (wing containing 703, 704, etc.)
  - `ADMIN703` → sqn_admin for 703 SQN (code `703SQN`)
  - `ADMIN704` → sqn_admin for 704 SQN (code `704SQN`)
  - `703SQN2026` → sqn_general for 703 SQN
  - `AUDITOR2026` → auditor
- No soft-delete on tickets. No email notifications. No ticket reference numbers.
- Design tokens from `connected-frontend/index.html` (AAFC VIG palette): `--blue #51b0e3`, `--dark #002f65`, `--royal #004b8d`, `--steel #455560`, `--bg #f4f8fc`, `--surface #ffffff`, `--border #d1dce8`. Font: Montserrat.
- Type scale (B-DS): 12px UI chrome, 10px labels/badges, 9px status chips. No fractional px.
- XSS: always use `esc()` for user-supplied content in innerHTML.
- Security rules: never embed access codes in frontend JS; use `--border-light #e4edf5` not hardcoded.
- B-DS token names: `--sp-xs` (4px), `--sp-sm` (8px), `--sp-md` (16px), `--sp-lg` (24px), `--sp-xl` (32px); `--radius` (6px).
- Audit log required on every successful PATCH.
- Only `system_admin` may call PATCH.

---

## File Map

**Create:**
- `backend/app/models/service_ticket.py` — `ServiceTicket` SQLAlchemy model
- `backend/alembic/versions/<generated-id>_v44_add_service_tickets.py` — Alembic migration
- `backend/app/routers/service_desk.py` — 4 endpoints
- `backend/tests/test_service_desk.py` — full backend test suite

**Modify:**
- `backend/app/models/__init__.py` — add `ServiceTicket` import and re-export
- `backend/app/main.py` — register `service_desk` router
- `backend/requirements.txt` — add `email-validator>=2.0`
- `connected-frontend/index.html` — modal HTML + pre-login link + page-service-desk HTML + nav entry + JS

---

### Task 1: ServiceTicket Model and Migration

**Files:**
- Create: `backend/app/models/service_ticket.py`
- Create: `backend/alembic/versions/<generated-id>_v44_add_service_tickets.py`
- Modify: `backend/app/models/__init__.py`

**Interfaces:**
- Produces: `ServiceTicket` class importable from `app.models`; table `service_tickets` in all environments

- [ ] **Step 1: Write the failing test (migration smoke test)**

Create `backend/tests/test_service_desk.py` with just an import test to verify the model loads:

```python
"""Service desk — backend tests."""
import pytest


def test_service_ticket_model_importable():
    from app.models.service_ticket import ServiceTicket
    assert ServiceTicket.__tablename__ == "service_tickets"
```

- [ ] **Step 2: Run it to confirm it fails**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_service_desk.py::test_service_ticket_model_importable -v
```

Expected: `FAILED` — `ModuleNotFoundError: No module named 'app.models.service_ticket'`

- [ ] **Step 3: Create the ServiceTicket model**

Create `backend/app/models/service_ticket.py`:

```python
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, UUIDMixin, TimestampMixin


class ServiceTicket(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "service_tickets"

    rank: Mapped[str] = mapped_column(String(40), nullable=False)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    # nullable in DB so archived squadrons can SET NULL; validated non-null at app layer
    squadron_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("squadrons.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    squadron: Mapped["Squadron"] = relationship("Squadron", lazy="joined", foreign_keys=[squadron_id])
```

- [ ] **Step 4: Update models/__init__.py**

Open `backend/app/models/__init__.py` and add `ServiceTicket` to the imports and `__all__`. Find the section that imports other models and add:

```python
from .service_ticket import ServiceTicket
```

And add `"ServiceTicket"` to the `__all__` list alongside the other model names.

- [ ] **Step 5: Run the import test to verify it passes**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_service_desk.py::test_service_ticket_model_importable -v
```

Expected: `PASSED`

- [ ] **Step 6: Check the current Alembic head**

```bash
cd backend && source .venv/bin/activate && alembic heads
```

Note the revision ID printed — this becomes `down_revision` in the next step.

- [ ] **Step 7: Generate a revision ID for the new migration**

```bash
python -c "import secrets; print(secrets.token_hex(6))"
```

Note this value — use it as the `revision` field and in the filename.

- [ ] **Step 8: Create the Alembic migration**

Create `backend/alembic/versions/<generated-id>_v44_add_service_tickets.py` (replace `<generated-id>` with the 12-char hex value from Step 7, and `<current-head>` with the value from Step 6):

```python
"""v44 Add service_tickets table (Service Desk Sub-project E).

Revision ID: <generated-id>
Revises: <current-head>
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa

revision = '<generated-id>'
down_revision = '<current-head>'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table.__module__ and True:
        pass  # batch_alter_table guard — actual table is new, use create_table
    op.create_table(
        "service_tickets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rank", sa.String(40), nullable=False),
        sa.Column("first_name", sa.String(80), nullable=False),
        sa.Column("last_name", sa.String(80), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("squadron_id", sa.String(36),
                  sa.ForeignKey("squadrons.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("admin_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False,
                  server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime, nullable=True),
    )
    with op.batch_alter_table("service_tickets") as batch_op:
        batch_op.create_index("ix_service_tickets_status", ["status"])
        batch_op.create_index("ix_service_tickets_squadron_id", ["squadron_id"])
        batch_op.create_index("ix_service_tickets_created_at", ["created_at"])


def downgrade():
    op.drop_table("service_tickets")
```

**Important:** Replace the `with op.batch_alter_table.__module__ and True: pass` guard with actual `op.create_table(...)`. The guard above is just a placeholder comment style — write the `op.create_table` call directly.

Actually — write the file exactly as follows (corrected):

```python
"""v44 Add service_tickets table (Service Desk Sub-project E).

Revision ID: <generated-id>
Revises: <current-head>
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa

revision = '<generated-id>'
down_revision = '<current-head>'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "service_tickets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rank", sa.String(40), nullable=False),
        sa.Column("first_name", sa.String(80), nullable=False),
        sa.Column("last_name", sa.String(80), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("squadron_id", sa.String(36),
                  sa.ForeignKey("squadrons.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("admin_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False,
                  server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime, nullable=True),
    )
    with op.batch_alter_table("service_tickets") as batch_op:
        batch_op.create_index("ix_service_tickets_status", ["status"])
        batch_op.create_index("ix_service_tickets_squadron_id", ["squadron_id"])
        batch_op.create_index("ix_service_tickets_created_at", ["created_at"])


def downgrade():
    op.drop_table("service_tickets")
```

- [ ] **Step 9: Verify migration runs cleanly**

```bash
cd backend && source .venv/bin/activate && alembic upgrade head
```

Expected: no errors; new migration applied.

- [ ] **Step 10: Run the full test suite to confirm no regressions**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/ -q --tb=short
```

Expected: all pre-existing tests pass (1753+ passing from before this work began, excluding the new service desk test file).

- [ ] **Step 11: Commit**

```bash
git add backend/app/models/service_ticket.py \
        backend/app/models/__init__.py \
        backend/alembic/versions/<generated-id>_v44_add_service_tickets.py \
        backend/tests/test_service_desk.py
git commit -m "feat(service-desk): add ServiceTicket model and v44 migration"
```

---

### Task 2: Service Desk Router, Registration, and Tests

Builds the 4 API endpoints, registers the router, and writes the full backend test suite. Depends on Task 1 (ServiceTicket model must exist).

**Files:**
- Create: `backend/app/routers/service_desk.py`
- Modify: `backend/app/main.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/tests/test_service_desk.py`

**Interfaces:**
- Consumes: `ServiceTicket` from `app.models`; `Squadron` from `app.models`; `get_db`, `utcnow` from `app.database`; `get_principal`, `client_meta` from `app.dependencies`; `Principal`, `require_role` from `app.permissions`; `audit` from `app.services`
- Produces:
  - `GET /api/public/squadrons` → `[{squadron_id, name}]` (no auth)
  - `POST /api/service-desk/tickets` → `{ok, ticket_id}` (no auth, rate-limited)
  - `GET /api/service-desk/tickets` → list of ticket objects (auth required, role-scoped)
  - `PATCH /api/service-desk/tickets/{ticket_id}` → `{ok}` (system_admin only)

- [ ] **Step 1: Add email-validator to requirements.txt**

Open `backend/requirements.txt` and add `email-validator>=2.0` after the pydantic line:

```
pydantic>=2.6
pydantic-settings>=2.1
email-validator>=2.0
```

Install it:

```bash
cd backend && source .venv/bin/activate && pip install email-validator>=2.0
```

- [ ] **Step 2: Write all failing backend tests**

Replace the content of `backend/tests/test_service_desk.py` with the full test suite below. All tests except the import test will fail until the router is implemented.

```python
"""Service desk — backend tests (Sub-project E)."""
import pytest
from app.database import SessionLocal
from app.models import Squadron


# ── helpers ──────────────────────────────────────────────────────────────────

def login(client, code):
    r = client.post("/api/auth/login", json={"code": code})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _sqn_id(code: str) -> str:
    db = SessionLocal()
    try:
        sqn = db.query(Squadron).filter(Squadron.code == code).first()
        assert sqn, f"Squadron with code {code!r} not found in seed data"
        return sqn.id
    finally:
        db.close()


def _make_ticket(client, sqn_id: str, **overrides) -> dict:
    body = {
        "rank": "Fg Off",
        "first_name": "Test",
        "last_name": "User",
        "email": "test@example.com",
        "squadron_id": sqn_id,
        "description": "This is a test issue description.",
        **overrides,
    }
    r = client.post("/api/service-desk/tickets", json=body)
    assert r.status_code == 201, r.text
    return r.json()


# ── Task 1 smoke test ─────────────────────────────────────────────────────────

def test_service_ticket_model_importable():
    from app.models.service_ticket import ServiceTicket
    assert ServiceTicket.__tablename__ == "service_tickets"


# ── Public squadrons list ─────────────────────────────────────────────────────

def test_public_squadrons_returns_active_only(client):
    r = client.get("/api/public/squadrons")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) > 0
    # Each item has squadron_id and name only
    for item in data:
        assert "squadron_id" in item
        assert "name" in item
        assert len(item) == 2
    # Alphabetically ordered
    names = [item["name"] for item in data]
    assert names == sorted(names)


def test_public_squadrons_no_auth_required(client):
    r = client.get("/api/public/squadrons")
    assert r.status_code == 200  # succeeds with no auth header


# ── Create ticket ─────────────────────────────────────────────────────────────

def test_create_ticket_unauthenticated(client):
    sqn_id = _sqn_id("703SQN")
    r = client.post("/api/service-desk/tickets", json={
        "rank": "Fg Off",
        "first_name": "Jane",
        "last_name": "Smith",
        "email": "jane.smith@example.com",
        "squadron_id": sqn_id,
        "description": "The cadet roster is not loading.",
    })
    assert r.status_code == 201
    data = r.json()
    assert data["ok"] is True
    assert "ticket_id" in data


def test_create_ticket_validates_required_fields(client):
    sqn_id = _sqn_id("703SQN")
    # Missing rank
    r = client.post("/api/service-desk/tickets", json={
        "first_name": "Jane", "last_name": "Smith",
        "email": "jane@example.com", "squadron_id": sqn_id,
        "description": "Some description here.",
    })
    assert r.status_code == 422

    # Missing description
    r = client.post("/api/service-desk/tickets", json={
        "rank": "Fg Off", "first_name": "Jane", "last_name": "Smith",
        "email": "jane@example.com", "squadron_id": sqn_id,
    })
    assert r.status_code == 422


def test_create_ticket_validates_email_format(client):
    sqn_id = _sqn_id("703SQN")
    r = client.post("/api/service-desk/tickets", json={
        "rank": "Fg Off", "first_name": "Jane", "last_name": "Smith",
        "email": "not-an-email",
        "squadron_id": sqn_id,
        "description": "Valid description here.",
    })
    assert r.status_code == 422


def test_create_ticket_validates_description_length(client):
    sqn_id = _sqn_id("703SQN")
    r = client.post("/api/service-desk/tickets", json={
        "rank": "Fg Off", "first_name": "Jane", "last_name": "Smith",
        "email": "jane@example.com",
        "squadron_id": sqn_id,
        "description": "Too short",  # 9 chars — under 10 minimum
    })
    assert r.status_code == 422


def test_create_ticket_archived_squadron_rejected(client):
    # Create and archive a squadron, then submit a ticket for it
    h = login(client, "SYSADMIN2026")
    # Create a temporary wing + squadron for this test
    r = client.get("/api/squadrons", headers=h)
    assert r.status_code == 200
    # Use an existing squadron and archive it — but we don't want to corrupt seed data.
    # Instead, submit with a made-up UUID (not in DB) which should also 404.
    import uuid
    fake_id = str(uuid.uuid4())
    r = client.post("/api/service-desk/tickets", json={
        "rank": "Fg Off", "first_name": "Jane", "last_name": "Smith",
        "email": "jane@example.com",
        "squadron_id": fake_id,
        "description": "Valid description here.",
    })
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "squadron_not_found"


# ── List tickets — role scoping ───────────────────────────────────────────────

def test_sqn_admin_sees_own_squadron_tickets_only(client):
    sqn703 = _sqn_id("703SQN")
    sqn704 = _sqn_id("704SQN")
    # Create tickets for both squadrons
    _make_ticket(client, sqn703, description="703 issue — visible to 703 admin.")
    _make_ticket(client, sqn704, description="704 issue — invisible to 703 admin.")

    h = login(client, "ADMIN703")
    r = client.get("/api/service-desk/tickets", headers=h)
    assert r.status_code == 200
    tickets = r.json()
    # Every ticket must belong to 703 SQN
    for t in tickets:
        assert t["squadron_id"] == sqn703


def test_wing_admin_sees_wing_scope_tickets(client):
    sqn703 = _sqn_id("703SQN")
    _make_ticket(client, sqn703, description="Wing-scope ticket visible to wing admin.")

    h = login(client, "ADMIN7WG")
    r = client.get("/api/service-desk/tickets", headers=h)
    assert r.status_code == 200
    tickets = r.json()
    # Must contain at least the ticket we just created
    ticket_ids = {t["ticket_id"] for t in tickets}
    assert len(ticket_ids) > 0


def test_national_admin_sees_all_tickets(client):
    sqn703 = _sqn_id("703SQN")
    _make_ticket(client, sqn703, description="National scope ticket — visible to all.")

    h = login(client, "ADMINNATIONAL")
    r = client.get("/api/service-desk/tickets", headers=h)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_system_admin_sees_all_tickets(client):
    sqn703 = _sqn_id("703SQN")
    _make_ticket(client, sqn703, description="Sysadmin scope ticket — visible to all.")

    h = login(client, "SYSADMIN2026")
    r = client.get("/api/service-desk/tickets", headers=h)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_auditor_cannot_list_tickets(client):
    h = login(client, "AUDITOR2026")
    r = client.get("/api/service-desk/tickets", headers=h)
    assert r.status_code == 403


def test_sqn_general_cannot_list_tickets(client):
    h = login(client, "703SQN2026")
    r = client.get("/api/service-desk/tickets", headers=h)
    assert r.status_code == 403


def test_unauthenticated_cannot_list_tickets(client):
    r = client.get("/api/service-desk/tickets")
    assert r.status_code == 401


# ── Status filter ─────────────────────────────────────────────────────────────

def test_status_filter_param(client):
    sqn703 = _sqn_id("703SQN")
    h_sys = login(client, "SYSADMIN2026")

    # Create one ticket and immediately resolve it
    created = _make_ticket(client, sqn703, description="Filter test ticket — will be resolved.")
    ticket_id = created["ticket_id"]
    r = client.patch(f"/api/service-desk/tickets/{ticket_id}",
                     json={"status": "resolved"}, headers=h_sys)
    assert r.status_code == 200

    # Filter to open — resolved ticket should not appear
    r = client.get("/api/service-desk/tickets?status=open", headers=h_sys)
    assert r.status_code == 200
    open_ids = {t["ticket_id"] for t in r.json()}
    assert ticket_id not in open_ids

    # Filter to resolved — resolved ticket should appear
    r = client.get("/api/service-desk/tickets?status=resolved", headers=h_sys)
    assert r.status_code == 200
    resolved_ids = {t["ticket_id"] for t in r.json()}
    assert ticket_id in resolved_ids


# ── Patch (system_admin actioning) ────────────────────────────────────────────

def test_system_admin_can_update_status(client):
    sqn703 = _sqn_id("703SQN")
    h_sys = login(client, "SYSADMIN2026")

    created = _make_ticket(client, sqn703, description="Status update test ticket.")
    ticket_id = created["ticket_id"]

    # Move to in_progress
    r = client.patch(f"/api/service-desk/tickets/{ticket_id}",
                     json={"status": "in_progress"}, headers=h_sys)
    assert r.status_code == 200
    assert r.json()["ok"] is True

    # Verify status changed
    r = client.get("/api/service-desk/tickets", headers=h_sys)
    ticket = next(t for t in r.json() if t["ticket_id"] == ticket_id)
    assert ticket["status"] == "in_progress"

    # Resolve — resolved_at should be stamped
    r = client.patch(f"/api/service-desk/tickets/{ticket_id}",
                     json={"status": "resolved"}, headers=h_sys)
    assert r.status_code == 200
    r = client.get("/api/service-desk/tickets", headers=h_sys)
    ticket = next(t for t in r.json() if t["ticket_id"] == ticket_id)
    assert ticket["status"] == "resolved"
    assert ticket["resolved_at"] is not None

    # Re-open — resolved_at should be cleared
    r = client.patch(f"/api/service-desk/tickets/{ticket_id}",
                     json={"status": "open"}, headers=h_sys)
    assert r.status_code == 200
    r = client.get("/api/service-desk/tickets", headers=h_sys)
    ticket = next(t for t in r.json() if t["ticket_id"] == ticket_id)
    assert ticket["resolved_at"] is None


def test_system_admin_can_add_notes(client):
    sqn703 = _sqn_id("703SQN")
    h_sys = login(client, "SYSADMIN2026")

    created = _make_ticket(client, sqn703, description="Notes update test ticket here.")
    ticket_id = created["ticket_id"]

    r = client.patch(f"/api/service-desk/tickets/{ticket_id}",
                     json={"admin_notes": "Investigating with Railway logs."}, headers=h_sys)
    assert r.status_code == 200

    r = client.get("/api/service-desk/tickets", headers=h_sys)
    ticket = next(t for t in r.json() if t["ticket_id"] == ticket_id)
    assert ticket["admin_notes"] == "Investigating with Railway logs."


def test_non_system_admin_cannot_patch(client):
    sqn703 = _sqn_id("703SQN")
    created = _make_ticket(client, sqn703, description="Patch forbidden test ticket here.")
    ticket_id = created["ticket_id"]

    for code in ("ADMIN7WG", "ADMINNATIONAL", "ADMIN703"):
        h = login(client, code)
        r = client.patch(f"/api/service-desk/tickets/{ticket_id}",
                         json={"status": "in_progress"}, headers=h)
        assert r.status_code == 403, f"Expected 403 for {code}, got {r.status_code}"


def test_audit_log_entry_created_on_patch(client):
    from app.database import SessionLocal
    from app.models import AuditLog

    sqn703 = _sqn_id("703SQN")
    h_sys = login(client, "SYSADMIN2026")
    created = _make_ticket(client, sqn703, description="Audit log test ticket for checking.")
    ticket_id = created["ticket_id"]

    r = client.patch(f"/api/service-desk/tickets/{ticket_id}",
                     json={"status": "in_progress", "admin_notes": "Audit test note."},
                     headers=h_sys)
    assert r.status_code == 200

    db = SessionLocal()
    try:
        entry = (
            db.query(AuditLog)
            .filter(AuditLog.object_type == "service_ticket",
                    AuditLog.object_id == ticket_id,
                    AuditLog.action == "updated")
            .first()
        )
        assert entry is not None, "AuditLog entry not found after PATCH"
    finally:
        db.close()
```

- [ ] **Step 3: Run tests to confirm all new tests fail (model import passes, rest fail)**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_service_desk.py -v
```

Expected: `test_service_ticket_model_importable` passes; all others fail with `404` or connection errors (router not registered yet).

- [ ] **Step 4: Implement the service_desk router**

Create `backend/app/routers/service_desk.py`:

```python
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session as DBSession

from ..database import get_db, utcnow
from ..models import Squadron, ServiceTicket, AuditLog
from ..dependencies import get_principal
from ..permissions import Principal, require_role
from ..services import audit

router = APIRouter(prefix="/api", tags=["service_desk"])

_VALID_STATUSES = frozenset({"open", "in_progress", "resolved"})


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class TicketCreateIn(BaseModel):
    rank: str
    first_name: str
    last_name: str
    email: EmailStr
    squadron_id: str
    description: str

    @field_validator("rank", "first_name", "last_name", "squadron_id", mode="before")
    @classmethod
    def strip_and_require(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("field is required and must not be blank")
        return v

    @field_validator("description", mode="before")
    @classmethod
    def description_min_length(cls, v):
        v = (v or "").strip()
        if len(v) < 10:
            raise ValueError("description must be at least 10 characters")
        return v


class TicketUpdateIn(BaseModel):
    status: str | None = None
    admin_notes: str | None = None

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v):
        if v is not None and v not in _VALID_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(_VALID_STATUSES))}")
        return v


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ticket_out(t: ServiceTicket) -> dict:
    return {
        "ticket_id": t.id,
        "rank": t.rank,
        "first_name": t.first_name,
        "last_name": t.last_name,
        "email": t.email,
        "squadron_id": t.squadron_id,
        "squadron_name": t.squadron.name if t.squadron else None,
        "description": t.description,
        "status": t.status,
        "admin_notes": t.admin_notes,
        "created_at": t.created_at.isoformat() + "Z" if t.created_at else None,
        "resolved_at": t.resolved_at.isoformat() + "Z" if t.resolved_at else None,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/public/squadrons")
def public_squadrons(db: DBSession = Depends(get_db)):
    """Active squadrons list for pre-login ticket form — no auth required."""
    sqns = (
        db.query(Squadron)
        .filter(Squadron.is_archived == False)  # noqa: E712
        .order_by(Squadron.name)
        .all()
    )
    return [{"squadron_id": s.id, "name": s.name} for s in sqns]


@router.post("/service-desk/tickets", status_code=201)
def create_ticket(body: TicketCreateIn, db: DBSession = Depends(get_db)):
    """Submit a new service ticket — public, no auth required."""
    sqn = db.query(Squadron).filter(
        Squadron.id == body.squadron_id,
        Squadron.is_archived == False  # noqa: E712
    ).first()
    if not sqn:
        raise HTTPException(404, detail={"error": "squadron_not_found",
                                          "message": "Squadron not found or archived."})

    ticket = ServiceTicket(
        rank=body.rank,
        first_name=body.first_name,
        last_name=body.last_name,
        email=body.email,
        squadron_id=body.squadron_id,
        description=body.description,
        status="open",
    )
    db.add(ticket)
    db.commit()
    return {"ok": True, "ticket_id": ticket.id}


@router.get("/service-desk/tickets")
def list_tickets(
    status: str | None = Query(default=None),
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """List tickets, scoped by caller's role."""
    if p.role in ("auditor", "sqn_general"):
        raise HTTPException(403, detail={"error": "forbidden"})

    q = db.query(ServiceTicket)

    if p.role == "wing_admin":
        q = (
            q.join(Squadron, ServiceTicket.squadron_id == Squadron.id)
            .filter(Squadron.wing_id == p.wing_id)
        )
    elif p.role == "sqn_admin":
        q = q.filter(ServiceTicket.squadron_id == p.squadron_id)
    # national_admin and system_admin see all — no additional filter

    if status is not None:
        if status not in _VALID_STATUSES:
            raise HTTPException(400, detail={"error": "invalid_status"})
        q = q.filter(ServiceTicket.status == status)

    tickets = q.order_by(ServiceTicket.created_at.desc()).all()
    return [_ticket_out(t) for t in tickets]


@router.patch("/service-desk/tickets/{ticket_id}")
def update_ticket(
    ticket_id: str,
    body: TicketUpdateIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Update status and/or admin notes — system_admin only."""
    require_role(p, "system_admin")

    ticket = db.get(ServiceTicket, ticket_id)
    if not ticket:
        raise HTTPException(404, detail={"error": "not_found"})

    old_snapshot = {"status": ticket.status, "admin_notes": ticket.admin_notes}
    changed: dict = {}

    if body.status is not None:
        changed["status"] = body.status
        ticket.status = body.status
        if body.status == "resolved" and ticket.resolved_at is None:
            ticket.resolved_at = utcnow()
        elif body.status != "resolved":
            ticket.resolved_at = None

    if body.admin_notes is not None:
        changed["admin_notes_updated"] = True
        ticket.admin_notes = body.admin_notes

    db.commit()

    audit(
        db, p,
        object_type="service_ticket",
        object_id=ticket_id,
        action="updated",
        old=old_snapshot,
        new={**old_snapshot, **changed},
    )
    return {"ok": True}
```

- [ ] **Step 5: Register the router in main.py**

Open `backend/app/main.py`. Find the block where other routers are imported (around line 14) and add:

```python
from .routers import auth, organisations, ..., search, service_desk
```

Then find where `app.include_router(r)` calls are made (around line 362-365) and add:

```python
app.include_router(service_desk.router)
```

- [ ] **Step 6: Run the full service desk test suite**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/test_service_desk.py -v
```

Expected: all tests pass.

- [ ] **Step 7: Run the full backend suite to confirm no regressions**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/ -q --tb=short
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add backend/app/routers/service_desk.py \
        backend/app/main.py \
        backend/requirements.txt \
        backend/tests/test_service_desk.py
git commit -m "feat(service-desk): add 4 endpoints (public squadrons, create, list, patch) + tests"
```

---

### Task 3: Frontend Submission Modal and Pre-login Link

Adds the shared ticket submission modal HTML + JS to `connected-frontend/index.html`, and adds the "Report an Issue" link below the login card. Works from both pre-login and in-app contexts. Depends on Task 2 (endpoints must exist).

**Files:**
- Modify: `connected-frontend/index.html`

**Interfaces:**
- Consumes: `GET /api/public/squadrons` (no auth), `POST /api/service-desk/tickets` (no auth)
- Produces: `sdOpenModal(preselectedSquadronId?)`, `sdCloseModal()`, `sdSubmit(event)` functions; `#sd-modal` element; `window._sdSquadrons` cache; `.login-report-link` below login card

All insertions are in `connected-frontend/index.html`. The file is ~16,000 lines. Use these grep patterns to locate insertion points:

```bash
# Find the login card container to insert the pre-login link after it:
grep -n "login-card\|login-box\|id=\"login\"" connected-frontend/index.html | head -20

# Find where other modals are defined (for modal HTML insertion):
grep -n "modal-overlay\|class=\"modal\"" connected-frontend/index.html | head -10

# Find the JS section end (for JS function insertion):
grep -n "^</script>" connected-frontend/index.html | tail -5

# Find the closing </body> tag (alternate modal HTML insertion):
grep -n "</body>" connected-frontend/index.html
```

- [ ] **Step 1: Locate insertion points in index.html**

Run the greps above to find the exact line numbers for:
1. Where the login card ends (to insert `.login-report-link` after it)
2. Where to insert the modal HTML (near other modal definitions, or before `</body>`)
3. Where to insert the JS functions (before the closing `</script>`)

- [ ] **Step 2: Insert the modal CSS**

Find the `<style>` block that contains `.modal-overlay` or existing modal styles. Add the following CSS near it:

```css
/* ── Service Desk modal ── */
.login-report-link {
  display: block;
  text-align: center;
  margin-top: var(--sp-md);
  font-size: 11px;
  font-weight: 600;
  color: rgba(255,255,255,.45);
  cursor: pointer;
  background: none;
  border: none;
  text-decoration: none;
  font-family: inherit;
}
.login-report-link:hover { color: rgba(255,255,255,.72); }
#sd-modal .ff-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .04em;
  color: var(--steel);
  display: block;
  margin-bottom: 4px;
}
#sd-modal .ff-input,
#sd-modal .ff-select {
  width: 100%;
  box-sizing: border-box;
  font-size: 12px;
  font-family: inherit;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text);
}
#sd-modal textarea.ff-input { resize: vertical; }
#sd-modal .form-group { margin-bottom: var(--sp-sm); }
#sd-modal .form-err {
  font-size: 11px;
  color: var(--red);
  margin-top: var(--sp-xs);
}
```

- [ ] **Step 3: Insert the "Report an Issue" link in the login card**

Find the HTML for the login screen card (search for `id="login"` or `login-card` or the login button). After the closing tag of the login card `<div>`, insert:

```html
<button class="login-report-link" onclick="sdOpenModal()" id="login-report-btn">
  Report an Issue
</button>
```

- [ ] **Step 4: Insert the modal HTML**

Before `</body>` (or near other modal definitions), add:

```html
<!-- ── Service Desk submission modal ── -->
<div id="sd-modal" class="modal-overlay" style="display:none;z-index:1100">
  <div class="modal card" style="width:480px;max-width:96vw;margin:auto">
    <div class="modal-hdr">
      <span class="modal-title">Report an Issue</span>
      <button class="modal-close" onclick="sdCloseModal()">✕</button>
    </div>
    <form id="sd-form" onsubmit="sdSubmit(event)" style="padding:var(--sp-md)">
      <div class="form-group">
        <label class="ff-label" for="sd-rank">Rank</label>
        <input id="sd-rank" type="text" class="ff-input" placeholder="e.g. Fg Off" required>
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:var(--sp-sm)">
        <div class="form-group">
          <label class="ff-label" for="sd-first">First Name</label>
          <input id="sd-first" type="text" class="ff-input" required>
        </div>
        <div class="form-group">
          <label class="ff-label" for="sd-last">Last Name</label>
          <input id="sd-last" type="text" class="ff-input" required>
        </div>
      </div>
      <div class="form-group">
        <label class="ff-label" for="sd-email">Email</label>
        <input id="sd-email" type="email" class="ff-input" required>
      </div>
      <div class="form-group">
        <label class="ff-label" for="sd-sqn">Unit</label>
        <select id="sd-sqn" class="ff-select ff-input" required></select>
      </div>
      <div class="form-group">
        <label class="ff-label" for="sd-desc">Description of Issue</label>
        <textarea id="sd-desc" class="ff-input" rows="4"
          placeholder="Describe the issue (minimum 10 characters)…" required></textarea>
      </div>
      <div id="sd-err" style="display:none" class="form-err"></div>
      <div class="modal-footer" style="display:flex;gap:var(--sp-sm);justify-content:flex-end;padding-top:var(--sp-sm)">
        <button type="button" class="btn btn-secondary" onclick="sdCloseModal()">Cancel</button>
        <button type="submit" class="btn btn-primary" id="sd-submit-btn">Submit</button>
      </div>
    </form>
  </div>
</div>
```

- [ ] **Step 5: Insert the modal JS functions**

Before the closing `</script>` tag, add:

```javascript
// ── Service Desk modal ──────────────────────────────────────────────────────
window._sdSquadrons = null; // cached squadron list

async function sdLoadSquadrons() {
  if (window._sdSquadrons) return window._sdSquadrons;
  try {
    const r = await fetch(API_BASE + '/api/public/squadrons');
    if (!r.ok) throw new Error('Failed to load squadrons');
    window._sdSquadrons = await r.json();
  } catch (e) {
    window._sdSquadrons = [];
  }
  return window._sdSquadrons;
}

async function sdOpenModal(preselectedSquadronId) {
  const modal = document.getElementById('sd-modal');
  const form = document.getElementById('sd-form');
  const errEl = document.getElementById('sd-err');
  form.reset();
  errEl.style.display = 'none';
  document.getElementById('sd-submit-btn').disabled = false;

  const sqns = await sdLoadSquadrons();
  const sel = document.getElementById('sd-sqn');
  sel.innerHTML = '<option value="">— Select unit —</option>' +
    sqns.map(s => `<option value="${esc(s.squadron_id)}">${esc(s.name)}</option>`).join('');

  if (preselectedSquadronId) {
    sel.value = preselectedSquadronId;
    sel.disabled = true;
  } else {
    sel.disabled = false;
  }

  modal.style.display = 'flex';
  document.getElementById('sd-rank').focus();

  // Close on Escape
  modal._escHandler = (e) => { if (e.key === 'Escape') sdCloseModal(); };
  document.addEventListener('keydown', modal._escHandler);
}

function sdCloseModal() {
  const modal = document.getElementById('sd-modal');
  modal.style.display = 'none';
  if (modal._escHandler) {
    document.removeEventListener('keydown', modal._escHandler);
    modal._escHandler = null;
  }
}

async function sdSubmit(event) {
  event.preventDefault();
  const errEl = document.getElementById('sd-err');
  const submitBtn = document.getElementById('sd-submit-btn');
  errEl.style.display = 'none';
  submitBtn.disabled = true;

  const body = {
    rank: document.getElementById('sd-rank').value.trim(),
    first_name: document.getElementById('sd-first').value.trim(),
    last_name: document.getElementById('sd-last').value.trim(),
    email: document.getElementById('sd-email').value.trim(),
    squadron_id: document.getElementById('sd-sqn').value,
    description: document.getElementById('sd-desc').value.trim(),
  };

  try {
    const r = await fetch(API_BASE + '/api/service-desk/tickets', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });

    if (r.status === 201) {
      sdCloseModal();
      showToast('Ticket submitted — a system administrator will follow up.');
      return;
    }

    if (r.status === 429) {
      errEl.textContent = 'Too many requests — please wait before submitting again.';
      errEl.style.display = 'block';
    } else {
      const data = await r.json().catch(() => ({}));
      const msg = (data.detail && typeof data.detail === 'object' && data.detail.message)
        ? data.detail.message
        : 'Submission failed — please check the form and try again.';
      errEl.textContent = msg;
      errEl.style.display = 'block';
    }
  } catch (e) {
    errEl.textContent = 'Network error — please try again.';
    errEl.style.display = 'block';
  }
  submitBtn.disabled = false;
}
```

**Note:** `showToast()` is the existing toast helper in the SPA. Verify the exact function name by grepping: `grep -n "function showToast\|function toast" connected-frontend/index.html | head -5`. If it has a different name, use the correct one.

- [ ] **Step 6: Manual verification**

Start the backend and frontend servers:

```bash
# Terminal 1
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Terminal 2
cd connected-frontend && python3 -m http.server 8080
```

Open `http://localhost:8080` in a browser:
1. Verify "Report an Issue" link appears below the login card.
2. Click it — modal opens with squadron dropdown populated.
3. Fill in the form with a valid email and description ≥10 chars, submit — toast appears.
4. Submit with invalid email — browser HTML5 validation or 422 shows error inline.
5. Close modal with ✕ button and Escape key.

- [ ] **Step 7: Commit**

```bash
git add connected-frontend/index.html
git commit -m "feat(service-desk): add submission modal + pre-login 'Report an Issue' link"
```

---

### Task 4: Frontend Service Desk Page

Adds the `page-service-desk` page to the SPA: nav entry, ticket list table, slide-in detail panel, filter bar, and role-aware Save Changes form. Depends on Task 3 (modal functions must exist).

**Files:**
- Modify: `connected-frontend/index.html`

**Interfaces:**
- Consumes: `sdOpenModal(preselectedSquadronId?)` from Task 3; `GET /api/service-desk/tickets` (auth); `PATCH /api/service-desk/tickets/{id}` (system_admin only)
- Produces: `loadServiceDesk()`, `sdSave(ticketId)` functions; `page-service-desk` HTML; `NAV_BY_SCOPE` entry for `service-desk` in scopes `squadron`, `wing`, `national`, `system_admin`

- [ ] **Step 1: Add CSS for the Service Desk page**

Find the `<style>` block and add after the existing service desk modal CSS from Task 3:

```css
/* ── Service Desk page ── */
#page-service-desk .sd-filter-bar {
  display: flex;
  gap: var(--sp-xs);
  margin-bottom: var(--sp-md);
}
#page-service-desk .sd-filter-bar button {
  font-size: 12px;
  padding: 4px 12px;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  font-family: inherit;
}
#page-service-desk .sd-filter-bar button.active {
  background: var(--blue);
  color: #fff;
  border-color: var(--blue);
}
#page-service-desk .sd-layout {
  display: flex;
  gap: 0;
  min-height: 400px;
  overflow: hidden;
}
#page-service-desk .sd-list {
  flex: 1;
  overflow-x: auto;
  transition: flex .18s;
}
#page-service-desk .sd-detail {
  width: 360px;
  flex-shrink: 0;
  border-left: 1px solid var(--border);
  background: var(--surface);
  transform: translateX(100%);
  transition: transform .18s;
  overflow-y: auto;
  padding: var(--sp-md);
  box-sizing: border-box;
}
#page-service-desk .sd-detail.open {
  transform: translateX(0);
}
#page-service-desk .sd-detail-section {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .05em;
  color: var(--steel);
  margin: var(--sp-sm) 0 var(--sp-xs);
}
#page-service-desk .sd-detail hr {
  border: none;
  border-top: 1px solid var(--border);
  margin: var(--sp-xs) 0 var(--sp-sm);
}
#page-service-desk .sd-row-active td { background: var(--accent-light); }
.badge-open   { background: #e0f0fa; color: #004b8d; }
.badge-in_progress { background: #fff3cd; color: #7a4800; }
.badge-resolved { background: #d4f0e3; color: #145f38; }
```

- [ ] **Step 2: Add the page-service-desk HTML**

Locate where other `<div id="page-*">` sections are defined (grep: `grep -n 'id="page-' connected-frontend/index.html | head -20`). Insert the following as a new page section:

```html
<!-- ── Service Desk page ── -->
<div id="page-service-desk" class="page" style="display:none">
  <div class="page-header" style="display:flex;align-items:center;justify-content:space-between;margin-bottom:var(--sp-md)">
    <h1>Service Desk</h1>
    <button class="btn btn-primary" onclick="sdOpenModal(S && S.role==='sqn_admin' ? S.squadron_id : null)">
      Submit a Ticket
    </button>
  </div>
  <div class="sd-filter-bar" id="sd-filter-bar">
    <button class="active" onclick="sdSetFilter('all', this)">All</button>
    <button onclick="sdSetFilter('open', this)">Open</button>
    <button onclick="sdSetFilter('in_progress', this)">In Progress</button>
    <button onclick="sdSetFilter('resolved', this)">Resolved</button>
  </div>
  <div class="sd-layout">
    <div class="sd-list" id="sd-list-container">
      <table class="tbl" id="sd-table" style="width:100%">
        <thead>
          <tr>
            <th>Date</th>
            <th>Submitted By</th>
            <th>Unit</th>
            <th>Issue</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody id="sd-tbody"></tbody>
      </table>
      <div id="sd-empty" style="display:none;text-align:center;padding:var(--sp-xl);color:var(--muted);font-size:13px">
        No tickets
      </div>
    </div>
    <div class="sd-detail" id="sd-detail">
      <div style="display:flex;justify-content:flex-end">
        <button class="btn btn-secondary" style="font-size:11px;padding:2px 8px" onclick="sdCloseDetail()">✕</button>
      </div>
      <div id="sd-detail-content"></div>
    </div>
  </div>
</div>
```

- [ ] **Step 3: Add nav entries to NAV_BY_SCOPE**

Find `NAV_BY_SCOPE` in the JS section (grep: `grep -n "NAV_BY_SCOPE\|navByScope" connected-frontend/index.html | head -5`).

In the `squadron`, `wing`, `national`, and `system_admin` scope arrays, add an entry for Service Desk. The SVG icon below uses a speech-bubble path. Find the existing nav entry format (e.g., `{ id: 'activities', label: 'Activities', icon: '...' }`) and match it:

```javascript
{ id: 'service-desk', label: 'Service Desk', icon: '<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M13 1H3a1 1 0 00-1 1v8a1 1 0 001 1h2l3 3 3-3h2a1 1 0 001-1V2a1 1 0 00-1-1z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/></svg>' }
```

Add this entry to the nav arrays for: `squadron`, `wing`, `national`, `system_admin`.

**Note:** Check the exact object shape used by other nav entries in the SPA. If icons are passed differently (e.g. as a CSS class string, an emoji, or an inline SVG string), match that pattern exactly. The icon SVG above is the intended design — adapt only the property name if needed.

- [ ] **Step 4: Wire up the nav() function for service-desk**

Find the `nav(id)` function (grep: `grep -n "function nav\b" connected-frontend/index.html`). Inside the `switch` or `if/else` block that handles page transitions, add a case for `'service-desk'`:

```javascript
case 'service-desk':
  loadServiceDesk();
  break;
```

(Or if `nav()` uses a different dispatch mechanism, follow that pattern exactly.)

- [ ] **Step 5: Add the loadServiceDesk and sdSave JS functions**

Before the closing `</script>`, add:

```javascript
// ── Service Desk page ────────────────────────────────────────────────────────
let _sdAllTickets = [];
let _sdActiveFilter = 'all';
let _sdSelectedTicketId = null;

function sdFmtDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
}

function sdStatusBadge(status) {
  const labels = {open: 'Open', in_progress: 'In Progress', resolved: 'Resolved'};
  const cls = 'badge-' + status;
  return `<span class="badge ${cls}" style="font-size:9px;padding:2px 6px;border-radius:4px;font-weight:700">${esc(labels[status] || status)}</span>`;
}

async function loadServiceDesk() {
  const tbody = document.getElementById('sd-tbody');
  const empty = document.getElementById('sd-empty');
  tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--muted);font-size:12px">Loading…</td></tr>';
  empty.style.display = 'none';
  sdCloseDetail();

  try {
    const r = await api('GET', '/api/service-desk/tickets');
    _sdAllTickets = r;
    sdRenderList();
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="5" style="color:var(--red);font-size:12px">${esc(apiErr(e))}</td></tr>`;
  }
}

function sdSetFilter(filter, btn) {
  _sdActiveFilter = filter;
  document.querySelectorAll('#sd-filter-bar button').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  sdRenderList();
  sdCloseDetail();
}

function sdRenderList() {
  const tbody = document.getElementById('sd-tbody');
  const empty = document.getElementById('sd-empty');
  const filtered = _sdActiveFilter === 'all'
    ? _sdAllTickets
    : _sdAllTickets.filter(t => t.status === _sdActiveFilter);

  if (filtered.length === 0) {
    tbody.innerHTML = '';
    empty.style.display = 'block';
    document.getElementById('sd-table').style.display = 'none';
    return;
  }
  document.getElementById('sd-table').style.display = '';
  empty.style.display = 'none';

  tbody.innerHTML = filtered.map(t => {
    const desc = t.description.length > 60
      ? esc(t.description.slice(0, 60)) + '…'
      : esc(t.description);
    const active = t.ticket_id === _sdSelectedTicketId ? ' class="sd-row-active"' : '';
    return `<tr${active} style="cursor:pointer" onclick="sdOpenDetail('${esc(t.ticket_id)}')">
      <td style="font-size:12px;white-space:nowrap">${sdFmtDate(t.created_at)}</td>
      <td style="font-size:12px">${esc(t.rank)} ${esc(t.first_name)} ${esc(t.last_name)}</td>
      <td style="font-size:12px">${esc(t.squadron_name || '')}</td>
      <td style="font-size:12px">${desc}</td>
      <td>${sdStatusBadge(t.status)}</td>
    </tr>`;
  }).join('');
}

function sdOpenDetail(ticketId) {
  _sdSelectedTicketId = ticketId;
  sdRenderList(); // re-render to show active row highlight
  const t = _sdAllTickets.find(x => x.ticket_id === ticketId);
  if (!t) return;
  const detail = document.getElementById('sd-detail');
  const isSysAdmin = S && S.role === 'system_admin';
  const notesHtml = isSysAdmin
    ? `<textarea id="sd-notes-input" class="ff-input" rows="3" style="width:100%;box-sizing:border-box;font-size:12px;font-family:inherit;padding:6px 8px;border:1px solid var(--border);border-radius:var(--radius)">${esc(t.admin_notes || '')}</textarea>`
    : `<div style="font-size:12px;color:var(--text)">${t.admin_notes ? esc(t.admin_notes) : '<span style="color:var(--muted)">No notes yet</span>'}</div>`;

  const statusButtons = isSysAdmin
    ? `<div style="display:flex;gap:var(--sp-xs);margin-top:var(--sp-xs)">
        ${['open','in_progress','resolved'].map(s => {
          const labels = {open:'Open', in_progress:'In Progress', resolved:'Resolved'};
          const active = t.status === s ? 'btn-primary' : 'btn-secondary';
          return `<button class="btn ${active}" id="sd-status-${s}" style="font-size:11px;padding:4px 10px" onclick="sdSelectStatus('${s}')">${labels[s]}</button>`;
        }).join('')}
      </div>`
    : sdStatusBadge(t.status);

  const saveBtn = isSysAdmin
    ? `<div style="text-align:right;margin-top:var(--sp-md)"><button class="btn btn-primary" style="font-size:12px" onclick="sdSave('${esc(ticketId)}')">Save Changes</button></div><div id="sd-save-err" style="display:none;color:var(--red);font-size:11px;margin-top:4px"></div>`
    : '';

  document.getElementById('sd-detail-content').innerHTML = `
    <div style="font-size:12px;color:var(--muted)">${sdFmtDate(t.created_at)}</div>
    <div style="font-size:13px;font-weight:600;margin:var(--sp-xs) 0">${esc(t.squadron_name || '')}</div>
    <div style="font-size:12px;margin-bottom:2px">${esc(t.rank)} ${esc(t.first_name)} ${esc(t.last_name)}</div>
    <div style="font-size:12px;color:var(--muted)">${esc(t.email)}</div>
    <div class="sd-detail-section">Description</div>
    <hr>
    <div style="font-size:12px;line-height:1.5">${esc(t.description)}</div>
    <div class="sd-detail-section">Admin Notes</div>
    <hr>
    ${notesHtml}
    <div class="sd-detail-section">Status</div>
    <hr>
    ${statusButtons}
    ${saveBtn}
  `;

  // Store current editable status selection
  if (isSysAdmin) detail._editStatus = t.status;
  detail.classList.add('open');
}

function sdSelectStatus(status) {
  const detail = document.getElementById('sd-detail');
  detail._editStatus = status;
  ['open','in_progress','resolved'].forEach(s => {
    const btn = document.getElementById('sd-status-' + s);
    if (btn) {
      btn.className = 'btn ' + (s === status ? 'btn-primary' : 'btn-secondary');
      btn.style.cssText = 'font-size:11px;padding:4px 10px';
    }
  });
}

async function sdSave(ticketId) {
  const detail = document.getElementById('sd-detail');
  const errEl = document.getElementById('sd-save-err');
  if (errEl) errEl.style.display = 'none';

  const notesInput = document.getElementById('sd-notes-input');
  const body = {
    status: detail._editStatus,
    admin_notes: notesInput ? notesInput.value : undefined,
  };

  try {
    await api('PATCH', `/api/service-desk/tickets/${ticketId}`, body);
    // Update local cache
    const t = _sdAllTickets.find(x => x.ticket_id === ticketId);
    if (t) {
      if (body.status) t.status = body.status;
      if (body.admin_notes !== undefined) t.admin_notes = body.admin_notes;
      if (body.status === 'resolved') t.resolved_at = new Date().toISOString();
      else if (body.status) t.resolved_at = null;
    }
    sdRenderList();
    sdOpenDetail(ticketId); // re-render panel
    showToast('Ticket updated.');
  } catch (e) {
    if (errEl) {
      errEl.textContent = apiErr(e);
      errEl.style.display = 'block';
    }
  }
}

function sdCloseDetail() {
  _sdSelectedTicketId = null;
  document.getElementById('sd-detail').classList.remove('open');
  sdRenderList(); // clear active highlight
}
```

- [ ] **Step 6: Manual verification**

With backend and frontend servers running:

1. Log in as `ADMIN703` — Service Desk should appear in nav.
2. Navigate to Service Desk — list loads; only 703 SQN tickets visible.
3. Click a row — detail panel slides in from right; close with ✕ and Escape.
4. Click "Submit a Ticket" — modal opens with unit pre-filled and disabled.
5. Filter buttons hide/show rows client-side without re-fetching.
6. Log in as `SYSADMIN2026` — all tickets visible; Save Changes updates status and notes; badge updates in list.
7. Log in as `ADMIN7WG` — wing-scoped tickets visible; no Save Changes in detail panel.
8. Log in with `AUDITOR2026` — no Service Desk nav item visible.
9. On the login screen (before login) — "Report an Issue" link visible; opens modal; submit works without being logged in.

- [ ] **Step 7: Run full backend tests one final time**

```bash
cd backend && source .venv/bin/activate && python -m pytest tests/ -q --tb=short
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add connected-frontend/index.html
git commit -m "feat(service-desk): add Service Desk page — nav, ticket list, detail panel, filter bar"
```

---

## Self-Review

**Spec coverage check:**

| Spec section | Covered by |
|---|---|
| §2 Scope — `service_tickets` table, 4 endpoints, one migration | Task 1 + Task 2 |
| §2 Rate limiting (per-IP, existing middleware) | Inherited — no action needed |
| §2 Audit log on PATCH | Task 2 — `audit()` call in `update_ticket` |
| §2 B-DS tokens | Tasks 3 + 4 — CSS uses `--sp-*`, `--radius`, `--blue`, `--surface`, `--border` |
| §3 Data model (all columns, FK SET NULL) | Task 1 — `service_ticket.py` |
| §4.0 GET /api/public/squadrons | Task 2 — `public_squadrons()` |
| §4.1 POST /api/service-desk/tickets | Task 2 — `create_ticket()` |
| §4.2 GET /api/service-desk/tickets (role scoping) | Task 2 — `list_tickets()` with wing/sqn/all branches |
| §4.3 PATCH system_admin only, resolved_at stamp | Task 2 — `update_ticket()` |
| §5.1 Pre-login link | Task 3 — `.login-report-link` below login card |
| §5.2 Nav entry + "Submit a Ticket" button | Task 4 — `NAV_BY_SCOPE` + page header button |
| §5.3 Modal — both entry points, squadron cache | Task 3 — `sdOpenModal()` with `preselectedSquadronId` |
| §5.3 Modal — 201 toast / 422 inline / 429 message | Task 3 — `sdSubmit()` branches |
| §5.4 Page — filter bar, ticket list, detail panel | Task 4 — `loadServiceDesk()` + `sdRenderList()` + `sdOpenDetail()` |
| §5.4 Save Changes (system_admin) / read-only (others) | Task 4 — `isSysAdmin` check in `sdOpenDetail()` |
| §6 Role access matrix | Task 2 — 403 for auditor/sqn_general in `list_tickets`; Task 4 — NAV_BY_SCOPE excludes those roles |
| §7 All 16 backend tests | Task 2 — all listed in test file |

**Potential gap:** `email-validator` is a new dependency. Steps include `pip install email-validator>=2.0` and adding it to `requirements.txt`. If the staging Docker image doesn't pick it up automatically, the implementer should verify `requirements.txt` is committed and the container rebuilds.

**Type consistency check:** `ticket_id` (not `id`) used consistently in API responses via `_ticket_out()`, and all test assertions use `t["ticket_id"]`. `sdSave(ticketId)` and `sdOpenDetail(ticketId)` both receive the same `ticket_id` string. Consistent throughout.
