"""Tests for POST /api/system/provision-wing (DEF-06 / DOC-12).

Verifies auth gates, happy-path Wing + Squadron + account creation,
idempotency, the no-accounts flag, and audit log entries.

Each test uses a unique wing_code to avoid collisions in the shared
session-scoped test database.
"""
import pytest
from tests.conftest import login
from app.database import SessionLocal
from app.models import AuditLog


def _sysadmin(client):
    return login(client, "SYSADMIN2026")


def _wing_admin(client):
    return login(client, "ADMIN7WG")


def _sqn_admin(client):
    return login(client, "ADMIN703")


URL = "/api/system/provision-wing"


def _body(wing_code: str, sqn_code: str) -> dict:
    return {
        "wing_code": wing_code,
        "wing_name": f"{wing_code} Wing AAFC",
        "wing_short": wing_code,
        "squadrons": [
            {
                "code": sqn_code,
                "name": f"{sqn_code} Squadron AAFC",
                "short_name": f"{sqn_code} SQN",
                "parade_day": "Wednesday",
                "start_time": "18:00",
                "end_time": "21:00",
            }
        ],
    }


def test_provision_wing_unauthenticated(client):
    r = client.post(URL, json=_body("PW1WG", "PW101"))
    assert r.status_code == 401


def test_provision_wing_forbidden_sqn_admin(client):
    hdrs = _sqn_admin(client)
    r = client.post(URL, json=_body("PW2WG", "PW201"), headers=hdrs)
    assert r.status_code == 403


def test_provision_wing_forbidden_wing_admin(client):
    hdrs = _wing_admin(client)
    r = client.post(URL, json=_body("PW3WG", "PW301"), headers=hdrs)
    assert r.status_code == 403


def test_provision_wing_happy_path(client):
    hdrs = _sysadmin(client)
    r = client.post(URL, json=_body("PW4WG", "PW401"), headers=hdrs)
    assert r.status_code == 200
    d = r.json()
    assert d["wing"]["code"] == "PW4WG"
    assert d["wing"]["name"] == "PW4WG Wing AAFC"
    results = d["results"]
    types = [x["type"] for x in results]
    assert "wing" in types
    assert "squadron" in types
    assert "account" in types
    wing_result = next(x for x in results if x["type"] == "wing")
    assert wing_result["created"] is True
    sqn_result = next(x for x in results if x["type"] == "squadron")
    assert sqn_result["code"] == "PW401"
    assert sqn_result["created"] is True


def test_provision_wing_creates_accounts(client):
    hdrs = _sysadmin(client)
    r = client.post(URL, json=_body("PW5WG", "PW501"), headers=hdrs)
    assert r.status_code == 200
    d = r.json()
    assert len(d["accounts_created"]) > 0
    roles = {a["role"] for a in d["accounts_created"]}
    assert "wing_admin" in roles
    assert "sqn_admin" in roles
    for acct in d["accounts_created"]:
        assert acct["new_code"]
        assert len(acct["new_code"]) >= 8


def test_provision_wing_no_accounts_flag(client):
    hdrs = _sysadmin(client)
    body = {**_body("PW6WG", "PW601"), "create_accounts": False}
    r = client.post(URL, json=body, headers=hdrs)
    assert r.status_code == 200
    d = r.json()
    assert d["accounts_created"] == []
    results = d["results"]
    assert not any(x["type"] == "account" for x in results)


def test_provision_wing_idempotent(client):
    hdrs = _sysadmin(client)
    body = _body("PW7WG", "PW701")
    # First call creates
    r1 = client.post(URL, json=body, headers=hdrs)
    assert r1.status_code == 200
    d1 = r1.json()
    wing_id_first = d1["wing"]["id"]

    # Second call is idempotent — same Wing and Squadron; no new accounts
    r2 = client.post(URL, json=body, headers=hdrs)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["wing"]["id"] == wing_id_first
    wing_result = next(x for x in d2["results"] if x["type"] == "wing")
    sqn_result = next(x for x in d2["results"] if x["type"] == "squadron")
    assert wing_result["created"] is False
    assert sqn_result["created"] is False
    assert d2["accounts_created"] == []


def test_provision_wing_audit_logged(client):
    import json
    hdrs = _sysadmin(client)
    r = client.post(URL, json=_body("PW8WG", "PW801"), headers=hdrs)
    assert r.status_code == 200
    db = SessionLocal()
    try:
        entries = db.query(AuditLog).filter(
            AuditLog.object_type == "wing",
            AuditLog.action == "create",
        ).all()
        wing_entries = [e for e in entries if
                        e.new_value and json.loads(e.new_value).get("code") == "PW8WG"]
        assert len(wing_entries) >= 1
    finally:
        db.close()


def test_provision_wing_default_squadron_if_none_specified(client):
    hdrs = _sysadmin(client)
    body = {"wing_code": "PW9WG", "wing_name": "PW9WG Wing AAFC"}
    r = client.post(URL, json=body, headers=hdrs)
    assert r.status_code == 200
    d = r.json()
    sqn_results = [x for x in d["results"] if x["type"] == "squadron"]
    assert len(sqn_results) >= 1


def test_provision_wing_notice_present(client):
    hdrs = _sysadmin(client)
    r = client.post(URL, json=_body("PWAAWG", "PWA01"), headers=hdrs)
    assert r.status_code == 200
    d = r.json()
    assert "notice" in d
    assert "NOT be retrievable" in d["notice"]
