"""Credential-onboarding regressions added after the post-PR65 audit.

These tests distinguish auto-generated bootstrap codes from an explicitly
provided initial credential, enforce the System Administrator recovery-channel
invariant, and prove recovery addresses cannot ambiguously identify two users.
"""
import uuid

from conftest import login


def _squadron_id(client, headers, code="703"):
    rows = client.get("/api/squadrons", headers=headers)
    assert rows.status_code == 200, rows.text
    return next(
        row["squadron_id"]
        for row in rows.json()
        if row.get("code") == code or row.get("short_name") == code
    )


def test_generated_initial_code_requires_rotation_before_app_access(client):
    admin = login(client, "SYSADMIN2026")
    squadron_id = _squadron_id(client, admin)
    created = client.post("/api/accounts", headers=admin, json={
        "display_name": f"Generated Code Rotation {uuid.uuid4().hex[:8]}",
        "role": "sqn_general",
        "squadron_id": squadron_id,
    })
    assert created.status_code == 200, created.text
    temporary_code = created.json()["new_code"]

    signed_in = client.post("/api/auth/login", json={"code": temporary_code})
    assert signed_in.status_code == 200, signed_in.text
    assert signed_in.json()["session"]["must_change_code"] is True
    temporary_headers = {"Authorization": f"Bearer {signed_in.json()['token']}"}

    blocked = client.get("/api/parade-nights", headers=temporary_headers)
    assert blocked.status_code == 403, blocked.text
    assert blocked.json()["detail"]["error"] == "code_change_required"

    replacement = "R-" + uuid.uuid4().hex
    changed = client.post("/api/auth/change-code", headers=temporary_headers, json={
        "current_code": temporary_code,
        "new_code": replacement,
    })
    assert changed.status_code == 200, changed.text

    signed_in_again = client.post("/api/auth/login", json={"code": replacement})
    assert signed_in_again.status_code == 200, signed_in_again.text
    assert signed_in_again.json()["session"]["must_change_code"] is False
    normal_headers = {"Authorization": f"Bearer {signed_in_again.json()['token']}"}
    assert client.get("/api/parade-nights", headers=normal_headers).status_code == 200


def test_explicit_initial_code_is_not_treated_as_generated_temporary_code(client):
    admin = login(client, "SYSADMIN2026")
    squadron_id = _squadron_id(client, admin)
    chosen = "C-" + uuid.uuid4().hex
    created = client.post("/api/accounts", headers=admin, json={
        "display_name": f"Explicit Initial Code {uuid.uuid4().hex[:8]}",
        "role": "sqn_general",
        "squadron_id": squadron_id,
        "new_code": chosen,
    })
    assert created.status_code == 200, created.text

    signed_in = client.post("/api/auth/login", json={"code": chosen})
    assert signed_in.status_code == 200, signed_in.text
    assert signed_in.json()["session"]["must_change_code"] is False


def test_system_admin_creation_requires_recovery_email(client):
    admin = login(client, "SYSADMIN2026")
    created = client.post("/api/accounts", headers=admin, json={
        "display_name": f"No Recovery Sysadmin {uuid.uuid4().hex[:8]}",
        "role": "system_admin",
    })
    assert created.status_code == 422, created.text
    assert created.json()["detail"]["error"] == "recovery_email_required"


def test_recovery_email_cannot_identify_two_accounts(client):
    admin = login(client, "SYSADMIN2026")
    squadron_id = _squadron_id(client, admin)
    address = f"recovery-{uuid.uuid4().hex}@example.test"

    first = client.post("/api/accounts", headers=admin, json={
        "display_name": f"Recovery One {uuid.uuid4().hex[:8]}",
        "role": "sqn_admin",
        "squadron_id": squadron_id,
        "new_code": "A-" + uuid.uuid4().hex,
        "recovery_email": address,
    })
    assert first.status_code == 200, first.text

    second = client.post("/api/accounts", headers=admin, json={
        "display_name": f"Recovery Two {uuid.uuid4().hex[:8]}",
        "role": "sqn_admin",
        "squadron_id": squadron_id,
        "new_code": "B-" + uuid.uuid4().hex,
        "recovery_email": address,
    })
    assert second.status_code == 409, second.text
    assert second.json()["detail"]["error"] == "recovery_email_in_use"
