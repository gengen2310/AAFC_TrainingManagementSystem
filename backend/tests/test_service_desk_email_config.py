"""Service Desk notification address: validation, audit trail, wing scope.

Audit 2026-10-02 (brief §21-29). Proven defects:
- notification_email was a plain str: "admin@" or "not an email" saved with
  200, and every later ticket notification to it failed silently (SMTP errors
  are only logged), so the unit simply stopped hearing about tickets.
- the config-change audit row always had old={}: the previous address was
  lost, so a redirected notification address could not be reconstructed.
An empty string is still accepted: it is the only way to clear an address
(recipients skip blanks; there is no DELETE endpoint).
"""
from app.database import SessionLocal
from app.models import AuditLog, Wing
from tests.conftest import login


def _put(client, hdr, **body):
    return client.put("/api/service-desk/email-config", json=body, headers=hdr)


def test_invalid_notification_address_is_rejected(client):
    h = login(client, "SYSADMIN2026")
    for bad in ["admin@", "not an email", "a@b", "x@y.com, evil@z.com"]:
        r = _put(client, h, scope="system", notification_email=bad)
        assert r.status_code == 422, (bad, r.status_code)


def test_blank_address_still_clears(client):
    h = login(client, "SYSADMIN2026")
    assert _put(client, h, scope="national", notification_email="nat-desk@example.com").status_code == 200
    assert _put(client, h, scope="national", notification_email="").status_code == 200
    cfg = [c for c in client.get("/api/service-desk/email-config", headers=h).json() if c["scope"] == "national"]
    assert cfg and cfg[0]["notification_email"] == ""


def test_audit_records_the_previous_address(client):
    h = login(client, "SYSADMIN2026")
    assert _put(client, h, scope="system", notification_email="first-desk@example.com").status_code == 200
    assert _put(client, h, scope="system", notification_email="second-desk@example.com").status_code == 200
    db = SessionLocal()
    try:
        row = (db.query(AuditLog).filter(AuditLog.object_type == "service_desk_email_config",
                                         AuditLog.object_id == "system:")
               .order_by(AuditLog.timestamp.desc()).first())
        assert row is not None
        assert "first-desk@example.com" in (row.old_value or ""), row.old_value
        assert "second-desk@example.com" in (row.new_value or ""), row.new_value
    finally:
        db.close()


def test_wing_admin_sets_own_wing_and_is_refused_for_another(client):
    h = login(client, "ADMIN7WG")
    me = client.get("/api/auth/me", headers=h).json()["session"]
    own = me["wing_id"]
    db = SessionLocal()
    try:
        other = db.query(Wing).filter(Wing.id != own, Wing.is_archived == False).first()  # noqa: E712
        other_id = other.id if other else None
    finally:
        db.close()
    assert _put(client, h, scope="wing", wing_id=own, notification_email="7wg-desk@example.com").status_code == 200
    if other_id:
        assert _put(client, h, scope="wing", wing_id=other_id,
                    notification_email="x@example.com").status_code == 403
    assert _put(client, h, scope="national", notification_email="x@example.com").status_code == 403
