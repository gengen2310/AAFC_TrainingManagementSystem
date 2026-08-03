"""Dependency-gated permanent delete for Account/Wing/Squadron and Planning Year.

Additive to the existing archive/restore soft-delete path (which remains the
default whenever any dependent exists): DELETE succeeds only when a
dependency check -- real foreign keys via services.fk_dependents() plus a
few explicit policy checks (Activity's denormalized wing/squadron_id,
AuditLog's deliberately-unconstrained user_id) -- shows zero linked records.
"""
from tests.conftest import login


def _sysadmin(client):
    return login(client, "SYSADMIN2026")


def _nat_admin(client):
    return login(client, "ADMINNATIONAL")


def _wing_admin_7wg(client):
    return login(client, "ADMIN7WG")


def _general(client):
    return login(client, "703SQN2026")


def _make_wing(client, hdr, code):
    r = client.post("/api/wings", json={"code": code, "name": code + " Test Wing"}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["wing_id"]


def _make_sqn(client, hdr, wing_id, code):
    r = client.post("/api/squadrons", json={"wing_id": wing_id, "code": code, "name": code + " Test Unit"}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["squadron_id"]


def _sqn_id_by_code(client, hdr, code):
    r = client.get("/api/squadrons", headers=hdr)
    for s in r.json():
        if s["code"] == code:
            return s["squadron_id"]
    raise AssertionError(f"squadron {code} not found")


# ─────────────────────────────────────────────────────────────
# Wing
# ─────────────────────────────────────────────────────────────

def test_delete_wing_requires_archived_first(client):
    hdr = _sysadmin(client)
    wing_id = _make_wing(client, hdr, "HDW01")
    r = client.delete(f"/api/wings/{wing_id}", headers=hdr)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["error"] == "not_archived"


def test_delete_empty_archived_wing_succeeds(client):
    hdr = _sysadmin(client)
    wing_id = _make_wing(client, hdr, "HDW02")
    client.post(f"/api/wings/{wing_id}/archive", headers=hdr)
    r = client.delete(f"/api/wings/{wing_id}", headers=hdr)
    assert r.status_code == 200, r.text
    assert client.get("/api/wings", headers=hdr).status_code == 200
    assert not any(w["wing_id"] == wing_id for w in client.get("/api/wings", headers=hdr).json())


def test_delete_wing_blocked_by_subordinate_squadron(client):
    hdr = _sysadmin(client)
    wing_id = _make_wing(client, hdr, "HDW03")
    sqn_id = _make_sqn(client, hdr, wing_id, "HD301")
    # Squadron itself must be archived before the wing can even be archived
    # (has_active_squadrons), so archive it first to isolate what we're
    # testing: the wing delete's own fk_dependents block on the (now
    # archived-but-still-existing) squadron row.
    client.post(f"/api/squadrons/{sqn_id}/archive", headers=hdr)
    client.post(f"/api/wings/{wing_id}/archive", headers=hdr)

    r = client.delete(f"/api/wings/{wing_id}", headers=hdr)
    assert r.status_code == 409, r.text
    body = r.json()["detail"]
    assert body["error"] == "has_dependents"
    assert body["dependents"].get("squadrons.wing_id") == 1


def test_delete_wing_forbidden_for_wing_admin(client):
    hdr = _wing_admin_7wg(client)
    wing_id = _sysadmin_make_and_archive_wing(client, "HDW04")
    r = client.delete(f"/api/wings/{wing_id}", headers=hdr)
    assert r.status_code == 403


def _sysadmin_make_and_archive_wing(client, code):
    hdr = login(client, "SYSADMIN2026")
    wing_id = _make_wing(client, hdr, code)
    client.post(f"/api/wings/{wing_id}/archive", headers=hdr)
    return wing_id


def test_delete_wing_unauthenticated(client):
    r = client.delete("/api/wings/some-id")
    assert r.status_code == 401


def test_delete_wing_is_audited(client):
    hdr = _sysadmin(client)
    wing_id = _make_wing(client, hdr, "HDW05")
    client.post(f"/api/wings/{wing_id}/archive", headers=hdr)
    client.delete(f"/api/wings/{wing_id}", headers=hdr)
    audit = client.get("/api/audit", headers=hdr).json()
    assert any(a.get("object_id") == wing_id and a.get("action") == "delete" for a in audit)


# ─────────────────────────────────────────────────────────────
# Squadron
# ─────────────────────────────────────────────────────────────

def test_delete_squadron_requires_archived_first(client):
    hdr = _sysadmin(client)
    wing_id = _make_wing(client, hdr, "HDS01")
    sqn_id = _make_sqn(client, hdr, wing_id, "HDS101")
    r = client.delete(f"/api/squadrons/{sqn_id}", headers=hdr)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["error"] == "not_archived"


def test_delete_empty_archived_squadron_succeeds(client):
    hdr = _sysadmin(client)
    wing_id = _make_wing(client, hdr, "HDS02")
    sqn_id = _make_sqn(client, hdr, wing_id, "HDS201")
    client.post(f"/api/squadrons/{sqn_id}/archive", headers=hdr)
    r = client.delete(f"/api/squadrons/{sqn_id}", headers=hdr)
    assert r.status_code == 200, r.text
    assert client.get(f"/api/squadrons/{sqn_id}", headers=hdr).status_code == 404


def test_delete_squadron_blocked_by_facilitator(client):
    hdr = _sysadmin(client)
    wing_id = _make_wing(client, hdr, "HDS03")
    sqn_id = _make_sqn(client, hdr, wing_id, "HDS301")
    # Creating a Facilitator for a squadron requires direct write authority
    # (sqn_admin) or an active Delegated Intervention for system_admin --
    # matches the rest of this app's proxy/intervention design.
    enter = client.post(f"/api/proxy/enter/{sqn_id}", json={"reason": "test setup"}, headers=hdr)
    assert enter.status_code == 200, enter.text
    fac = client.post("/api/facilitators", json={
        "first_name": "Blocker", "last_name": "Fac", "squadron_id": sqn_id,
    }, headers=hdr)
    assert fac.status_code == 200, fac.text
    client.post("/api/proxy/exit", headers=hdr)
    client.post(f"/api/squadrons/{sqn_id}/archive", headers=hdr)

    r = client.delete(f"/api/squadrons/{sqn_id}", headers=hdr)
    assert r.status_code == 409, r.text
    body = r.json()["detail"]
    assert body["error"] == "has_dependents"
    assert body["dependents"].get("facilitators.squadron_id") == 1


def test_delete_squadron_blocked_by_account(client):
    """The real, seeded 703 squadron -- has active accounts, must be
    archive-blocked long before hard-delete is even reachable."""
    hdr = _sysadmin(client)
    sqn_id = _sqn_id_by_code(client, hdr, "703")
    r = client.post(f"/api/squadrons/{sqn_id}/archive", headers=hdr)
    assert r.status_code == 409  # has_active_accounts blocks archive itself


def test_delete_squadron_forbidden_for_general(client):
    hdr = _general(client)
    sqn_id = _sqn_id_by_code(client, login(client, "SYSADMIN2026"), "703")
    r = client.delete(f"/api/squadrons/{sqn_id}", headers=hdr)
    assert r.status_code == 403


def test_delete_squadron_unauthenticated(client):
    r = client.delete("/api/squadrons/some-id")
    assert r.status_code == 401


def test_delete_squadron_is_audited(client):
    hdr = _sysadmin(client)
    wing_id = _make_wing(client, hdr, "HDS04")
    sqn_id = _make_sqn(client, hdr, wing_id, "HDS401")
    client.post(f"/api/squadrons/{sqn_id}/archive", headers=hdr)
    client.delete(f"/api/squadrons/{sqn_id}", headers=hdr)
    audit = client.get("/api/audit", headers=hdr).json()
    assert any(a.get("object_id") == sqn_id and a.get("action") == "delete" for a in audit)


# ─────────────────────────────────────────────────────────────
# Account
# ─────────────────────────────────────────────────────────────

def _create_and_archive_account(client, hdr, sqn_id, name="Hard Delete Target"):
    r = client.post("/api/accounts", json={
        "display_name": name, "role": "sqn_general", "squadron_id": sqn_id,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    uid = r.json()["user_id"]
    client.post(f"/api/accounts/{uid}/archive", headers=hdr)
    return uid


def test_delete_account_requires_archived_first(client):
    hdr = _nat_admin(client)
    sqn_id = _sqn_id_by_code(client, _wing_admin_7wg(client), "703")
    r = client.post("/api/accounts", json={
        "display_name": "Not Archived Yet", "role": "sqn_general", "squadron_id": sqn_id,
    }, headers=hdr)
    uid = r.json()["user_id"]
    dr = client.delete(f"/api/accounts/{uid}", headers=hdr)
    assert dr.status_code == 409
    assert dr.json()["detail"]["error"] == "not_archived"


def test_delete_never_logged_in_archived_account_succeeds(client):
    hdr = _nat_admin(client)
    sqn_id = _sqn_id_by_code(client, _wing_admin_7wg(client), "703")
    uid = _create_and_archive_account(client, hdr, sqn_id)
    r = client.delete(f"/api/accounts/{uid}", headers=hdr)
    assert r.status_code == 200, r.text
    assert client.get(f"/api/accounts/{uid}", headers=hdr).status_code == 404


def test_delete_account_blocked_once_logged_in(client):
    hdr = _nat_admin(client)
    sqn_id = _sqn_id_by_code(client, _wing_admin_7wg(client), "703")
    r = client.post("/api/accounts", json={
        "display_name": "Login Then Delete Target", "role": "sqn_general", "squadron_id": sqn_id,
    }, headers=hdr)
    uid = r.json()["user_id"]
    code = r.json()["new_code"]
    login(client, code)  # real login -- sets last_login_at
    client.post(f"/api/accounts/{uid}/archive", headers=hdr)

    dr = client.delete(f"/api/accounts/{uid}", headers=hdr)
    assert dr.status_code == 409, dr.text
    assert dr.json()["detail"]["dependents"].get("has_logged_in") == 1


def test_delete_account_not_blocked_by_own_lifecycle_audit_entries(client):
    """Archiving is a required precondition for hard-delete, and archiving
    itself writes an account_archived audit row targeting this account -- if
    that counted as a blocker, hard-delete would be unreachable for every
    account. Only the account's own audit_log_as_actor entries (privileged
    actions it performed on OTHER records) and login history should block."""
    hdr = _nat_admin(client)
    sqn_id = _sqn_id_by_code(client, _wing_admin_7wg(client), "703")
    uid = _create_and_archive_account(client, hdr, sqn_id)
    audit = client.get("/api/audit", headers=hdr).json()
    assert any(a.get("object_id") == uid and a.get("action") == "account_archived" for a in audit)

    r = client.delete(f"/api/accounts/{uid}", headers=hdr)
    assert r.status_code == 200, r.text


def test_delete_account_forbidden_for_general(client):
    hdr_nat = _nat_admin(client)
    sqn_id = _sqn_id_by_code(client, _wing_admin_7wg(client), "703")
    uid = _create_and_archive_account(client, hdr_nat, sqn_id)
    hdr_general = _general(client)
    r = client.delete(f"/api/accounts/{uid}", headers=hdr_general)
    assert r.status_code == 403


def test_delete_account_unauthenticated(client):
    r = client.delete("/api/accounts/some-id")
    assert r.status_code == 401
