"""R10 (owner decision 2026-10-13): read-only Squadron users (sqn_general) see
audit actions in /api/system/audit-summary but not who made them by user id or
from which IP address. Administrators of the same Squadron still see both."""
import uuid

from app.database import SessionLocal
from app.models import AuditLog, Squadron
from tests.conftest import login

IP = "203.0.113.77"


def _seed_row():
    db = SessionLocal()
    try:
        sqn = db.query(Squadron).filter(Squadron.code == "703").one()
        actor = str(uuid.uuid4())
        row = AuditLog(user_id=actor, role="sqn_admin", scope="squadron", wing_id=sqn.wing_id,
                       squadron_id=sqn.id, object_type="parade_night", object_id=str(uuid.uuid4()),
                       action="r10_probe", ip_address=IP)
        db.add(row)
        db.commit()
        return actor
    finally:
        db.close()


def _probe_rows(client, code):
    r = client.get("/api/system/audit-summary?action=r10_probe&limit=500", headers=login(client, code))
    assert r.status_code == 200, r.text
    rows = r.json()["logs"]
    assert rows, "the seeded in-scope row must be visible, or the check is vacuous"
    return rows


def test_sqn_general_sees_actions_without_ip_or_user_id(client):
    _seed_row()
    for row in _probe_rows(client, "703SQN2026"):
        assert row["action"] == "r10_probe"
        assert row["ip_address"] is None
        assert row["user_id"] is None


def test_sqn_admin_and_system_admin_still_see_ip_and_user_id(client):
    actor = _seed_row()
    for code in ("ADMIN703", "SYSADMIN2026"):
        rows = _probe_rows(client, code)
        assert any(r["ip_address"] == IP and r["user_id"] == actor for r in rows), code
