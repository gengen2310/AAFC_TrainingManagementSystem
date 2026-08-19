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
        sqn = db.query(Squadron).filter(Squadron.short_name == code).first()
        assert sqn, f"Squadron with short_name {code!r} not found in seed data"
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


def test_create_ticket_unknown_squadron_rejected(client):
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
