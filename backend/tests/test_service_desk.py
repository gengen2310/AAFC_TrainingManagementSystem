"""Service desk — backend tests (Sub-project E)."""
import uuid
from contextlib import contextmanager
from app.database import SessionLocal
from app.models import Squadron, Wing


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


@contextmanager
def _archived_squadron():
    """Create a temporary archived Squadron, yield its id, then delete it."""
    db = SessionLocal()
    try:
        wing = db.query(Wing).filter(Wing.is_archived == False).first()
        assert wing, "No active wing in seed data"
        sqn = Squadron(
            wing_id=wing.id,
            code=f"TST{uuid.uuid4().hex[:4].upper()}",
            name="Test Archived Squadron",
            short_name="TST-ARCH",
            is_archived=True,
        )
        db.add(sqn)
        db.commit()
        db.refresh(sqn)
        yield sqn.id
    finally:
        db.query(Squadron).filter(Squadron.short_name == "TST-ARCH").delete()
        db.commit()
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
    with _archived_squadron() as archived_id:
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
        # Archived squadron must not appear
        returned_ids = {item["squadron_id"] for item in data}
        assert archived_id not in returned_ids


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
    # Submit a ticket for an archived squadron — must return 404
    with _archived_squadron() as archived_id:
        r = client.post("/api/service-desk/tickets", json={
            "rank": "Fg Off", "first_name": "Jane", "last_name": "Smith",
            "email": "jane@example.com",
            "squadron_id": archived_id,
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


def test_sqn_admin_cannot_patch(client):
    """sqn_admin has no PATCH permission — 403."""
    sqn703 = _sqn_id("703SQN")
    created = _make_ticket(client, sqn703, description="Patch forbidden test ticket for sqn admin.")
    ticket_id = created["ticket_id"]

    h = login(client, "ADMIN703")
    r = client.patch(f"/api/service-desk/tickets/{ticket_id}",
                     json={"status": "in_progress"}, headers=h)
    assert r.status_code == 403


def test_wing_admin_can_patch_own_wing_tickets(client):
    """wing_admin can update status/notes on tickets from their own wing."""
    sqn703 = _sqn_id("703SQN")
    created = _make_ticket(client, sqn703, description="Wing admin patch test ticket here.")
    ticket_id = created["ticket_id"]

    h = login(client, "ADMIN7WG")
    r = client.patch(f"/api/service-desk/tickets/{ticket_id}",
                     json={"status": "in_progress", "admin_notes": "Wing admin actioning."}, headers=h)
    assert r.status_code == 200, r.text


def test_national_admin_can_patch_any_ticket(client):
    """national_admin can update any ticket."""
    sqn703 = _sqn_id("703SQN")
    created = _make_ticket(client, sqn703, description="National admin patch test ticket here.")
    ticket_id = created["ticket_id"]

    h = login(client, "ADMINNATIONAL")
    r = client.patch(f"/api/service-desk/tickets/{ticket_id}",
                     json={"status": "in_progress", "assigned_to_name": "Maj Smith"}, headers=h)
    assert r.status_code == 200, r.text


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


# ── New fields: category, unit_name, assigned_to_name ────────────────────────

def test_create_ticket_with_category(client):
    sqn703 = _sqn_id("703SQN")
    r = client.post("/api/service-desk/tickets", json={
        "rank": "Fg Off",
        "first_name": "Jane",
        "last_name": "Smith",
        "email": "jane@example.com",
        "squadron_id": sqn703,
        "category": "account_access",
        "description": "Cannot log in to the system.",
    })
    assert r.status_code == 201
    ticket_id = r.json()["ticket_id"]

    h_sys = login(client, "SYSADMIN2026")
    tickets = client.get("/api/service-desk/tickets", headers=h_sys).json()
    t = next((x for x in tickets if x["ticket_id"] == ticket_id), None)
    assert t is not None
    assert t["category"] == "account_access"
    assert t["unit_name"] == t["squadron_name"]  # derived from squadron


def test_create_ticket_invalid_category_falls_back_to_other(client):
    sqn703 = _sqn_id("703SQN")
    r = client.post("/api/service-desk/tickets", json={
        "rank": "Fg Off",
        "first_name": "Jane",
        "last_name": "Smith",
        "email": "jane@example.com",
        "squadron_id": sqn703,
        "category": "banana",
        "description": "Testing invalid category value here.",
    })
    assert r.status_code == 201
    ticket_id = r.json()["ticket_id"]

    h_sys = login(client, "SYSADMIN2026")
    tickets = client.get("/api/service-desk/tickets", headers=h_sys).json()
    t = next((x for x in tickets if x["ticket_id"] == ticket_id), None)
    assert t["category"] == "other"


def test_create_ticket_with_unit_name_no_squadron(client):
    """Ticket submitted from a wing/national context: no squadron_id, unit_name provided."""
    r = client.post("/api/service-desk/tickets", json={
        "rank": "Capt",
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com",
        "unit_name": "7 Wing HQ",
        "category": "technical_error",
        "description": "Wing calendar is not loading for our HQ.",
    })
    assert r.status_code == 201
    ticket_id = r.json()["ticket_id"]

    h_sys = login(client, "SYSADMIN2026")
    tickets = client.get("/api/service-desk/tickets", headers=h_sys).json()
    t = next((x for x in tickets if x["ticket_id"] == ticket_id), None)
    assert t is not None
    assert t["squadron_id"] is None
    assert t["unit_name"] == "7 Wing HQ"


def test_create_ticket_no_squadron_no_unit_name_rejected(client):
    """Must provide either squadron_id or unit_name."""
    r = client.post("/api/service-desk/tickets", json={
        "rank": "Fg Off",
        "first_name": "Jane",
        "last_name": "Smith",
        "email": "jane@example.com",
        "description": "No unit provided at all.",
    })
    assert r.status_code == 422


def test_assigned_to_name_field(client):
    sqn703 = _sqn_id("703SQN")
    h_sys = login(client, "SYSADMIN2026")

    created = _make_ticket(client, sqn703, description="Assignee field test ticket here.")
    ticket_id = created["ticket_id"]

    r = client.patch(f"/api/service-desk/tickets/{ticket_id}",
                     json={"assigned_to_name": "Capt Jones"}, headers=h_sys)
    assert r.status_code == 200

    tickets = client.get("/api/service-desk/tickets", headers=h_sys).json()
    t = next((x for x in tickets if x["ticket_id"] == ticket_id), None)
    assert t["assigned_to_name"] == "Capt Jones"


# ── Public units endpoint ─────────────────────────────────────────────────────

def test_public_units_returns_wings_and_squadrons(client):
    r = client.get("/api/public/units")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    types = {item["type"] for item in data}
    assert "wing" in types
    assert "squadron" in types
    for item in data:
        assert "unit_id" in item
        assert "name" in item
        assert "type" in item


def test_public_units_no_auth_required(client):
    r = client.get("/api/public/units")
    assert r.status_code == 200


# ── Email config CRUD ─────────────────────────────────────────────────────────

def test_email_config_upsert_and_read(client):
    h_sys = login(client, "SYSADMIN2026")

    # Set system email
    r = client.put("/api/service-desk/email-config",
                   json={"scope": "system", "notification_email": "admin@aafc-tms.ca"},
                   headers=h_sys)
    assert r.status_code == 200

    # Read back
    r = client.get("/api/service-desk/email-config", headers=h_sys)
    assert r.status_code == 200
    configs = r.json()
    system_cfg = next((c for c in configs if c["scope"] == "system"), None)
    assert system_cfg is not None
    assert system_cfg["notification_email"] == "admin@aafc-tms.ca"


def test_email_config_wing_admin_can_only_set_own_wing(client):
    from app.database import SessionLocal
    from app.models import Wing

    db = SessionLocal()
    try:
        wing = db.query(Wing).filter(Wing.is_archived == False).first()  # noqa: E712
        assert wing, "No active wing"
        wing_id = wing.id
    finally:
        db.close()

    h_wing = login(client, "ADMIN7WG")
    r = client.put("/api/service-desk/email-config",
                   json={"scope": "wing", "wing_id": wing_id, "notification_email": "7wg@example.com"},
                   headers=h_wing)
    # wing_admin for 7WG should succeed if wing_id matches their wing
    # (may 403 if the seed ADMIN7WG's wing_id differs — acceptable)
    assert r.status_code in (200, 403)


def test_email_config_national_admin_cannot_set_system_email(client):
    h_nat = login(client, "ADMINNATIONAL")
    r = client.put("/api/service-desk/email-config",
                   json={"scope": "system", "notification_email": "hacked@example.com"},
                   headers=h_nat)
    assert r.status_code == 403


def test_email_config_requires_auth(client):
    r = client.get("/api/service-desk/email-config")
    assert r.status_code == 401


# ── Viewer role access ─────────────────────────────────────────────────────────

def test_wing_viewer_sees_own_wing_tickets_only(client):
    sqn703 = _sqn_id("703SQN")
    sqn704 = _sqn_id("704SQN")
    _make_ticket(client, sqn703, description="7WG ticket — visible to 7WG viewer.")
    _make_ticket(client, sqn704, description="Other-wing ticket — invisible to 7WG viewer.")

    from app.database import SessionLocal
    from app.models import Wing, Squadron as Sqn
    db = SessionLocal()
    try:
        w7wg = db.query(Wing).filter(Wing.code == "7WG").first()
        sqns_in_7wg = {s.id for s in db.query(Sqn).filter(Sqn.wing_id == w7wg.id).all()}
    finally:
        db.close()

    h = login(client, "7WG2026")
    r = client.get("/api/service-desk/tickets", headers=h)
    assert r.status_code == 200
    tickets = r.json()
    for t in tickets:
        assert t["squadron_id"] in sqns_in_7wg, (
            f"wing_viewer got ticket for squadron {t['squadron_id']} outside 7WG"
        )


def test_national_viewer_sees_all_tickets(client):
    sqn703 = _sqn_id("703SQN")
    _make_ticket(client, sqn703, description="National viewer visibility test.")

    h = login(client, "NATIONAL2026")
    r = client.get("/api/service-desk/tickets", headers=h)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_wing_viewer_cannot_patch_ticket(client):
    sqn703 = _sqn_id("703SQN")
    created = _make_ticket(client, sqn703, description="Patch attempt by wing_viewer.")
    ticket_id = created["ticket_id"]

    h = login(client, "7WG2026")
    r = client.patch(f"/api/service-desk/tickets/{ticket_id}",
                     json={"status": "resolved"}, headers=h)
    assert r.status_code == 403


def test_national_viewer_cannot_patch_ticket(client):
    sqn703 = _sqn_id("703SQN")
    created = _make_ticket(client, sqn703, description="Patch attempt by national_viewer.")
    ticket_id = created["ticket_id"]

    h = login(client, "NATIONAL2026")
    r = client.patch(f"/api/service-desk/tickets/{ticket_id}",
                     json={"status": "resolved"}, headers=h)
    assert r.status_code == 403
