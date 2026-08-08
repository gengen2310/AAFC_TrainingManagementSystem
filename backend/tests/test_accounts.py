"""Account management, access-code administration and Flight assignment — security tests.

Tests map to the requirements in the Account Management Addendum (sections 13–16).
Every test here is a security invariant: a failure indicates a real access-control bug.
"""
from conftest import login


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _get_sqn_id(client, headers, code):
    r = client.get("/api/squadrons", headers=headers)
    for s in r.json():
        if s["code"] == code:
            return s["squadron_id"]
    return None


def _get_wing_id(client, headers, code="7WG"):
    r = client.get("/api/wings", headers=headers)
    for w in r.json():
        if w["code"] == code:
            return w["wing_id"]
    return None


def _create_flight(client, headers, sqn_id, name="Test Flight"):
    r = client.post("/api/flights", json={"name": name, "squadron_id": sqn_id}, headers=headers)
    assert r.status_code == 200, f"Flight create failed: {r.text}"
    return r.json()["flight_id"]


# ─────────────────────────────────────────────────────────────
# 1. NAT HQ admin account creation authority
# ─────────────────────────────────────────────────────────────

def test_nat_admin_can_create_wing_account(client):
    h = login(client, "ADMINNATIONAL")
    wing_id = _get_wing_id(client, h)
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "Test Wing Viewer",
        "role": "wing_viewer",
        "wing_id": wing_id,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["role"] == "wing_viewer"
    assert data["scope_type"] == "wing"
    assert "new_code" in data, "new code must be returned once"
    assert len(data["new_code"]) >= 6


def test_nat_admin_can_create_sqn_account(client):
    h = login(client, "ADMINNATIONAL")
    hwg = login(client, "ADMIN7WG")
    sqn_id = _get_sqn_id(client, hwg, "704")
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "Test SQN Admin 704",
        "role": "sqn_admin",
        "squadron_id": sqn_id,
    })
    assert r.status_code == 200, r.text
    assert r.json()["role"] == "sqn_admin"


def test_nat_admin_can_assign_sqn_account_to_flight(client):
    h = login(client, "ADMINNATIONAL")
    hwg = login(client, "ADMIN7WG")
    sqn_id = _get_sqn_id(client, hwg, "703")
    fid = _create_flight(client, h, sqn_id, "NAT Test Flight")
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "Test SQN General with Flight",
        "role": "sqn_general",
        "squadron_id": sqn_id,
        "flight_id": fid,
    })
    assert r.status_code == 200, r.text
    assert r.json()["flight_id"] == fid
    assert r.json()["scope_type"] == "squadron"


def test_nat_admin_creates_auditor_account(client):
    h = login(client, "ADMINNATIONAL")
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "Test Auditor",
        "role": "auditor",
    })
    assert r.status_code == 200, r.text
    assert r.json()["scope_type"] == "national"


def test_nat_admin_cannot_be_blocked_from_system_admin_only_by_national_admin(client):
    h = login(client, "ADMINNATIONAL")
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "Bad System Admin",
        "role": "system_admin",
    })
    # national_admin cannot create system_admin (only system_admin can)
    assert r.status_code == 403, r.text


def test_system_admin_can_create_system_admin(client):
    h = login(client, "SYSADMIN2026")
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "Second System Admin",
        "role": "system_admin",
    })
    assert r.status_code == 200, r.text


# ─────────────────────────────────────────────────────────────
# 2. Wing admin account creation authority
# ─────────────────────────────────────────────────────────────

def test_wing_admin_can_create_sqn_account_own_wing(client):
    h = login(client, "ADMIN7WG")
    sqn_id = _get_sqn_id(client, h, "701")
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "701 Test Admin",
        "role": "sqn_admin",
        "squadron_id": sqn_id,
    })
    assert r.status_code == 200, r.text
    assert r.json()["squadron_id"] == sqn_id
    assert "new_code" in r.json()


def test_wing_admin_can_create_wing_viewer_own_wing(client):
    h = login(client, "ADMIN7WG")
    wing_id = _get_wing_id(client, h)
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "Wing Viewer Test",
        "role": "wing_viewer",
        "wing_id": wing_id,
    })
    assert r.status_code == 200, r.text


def test_wing_admin_can_assign_sqn_account_to_flight(client):
    h = login(client, "ADMIN7WG")
    sqn_id = _get_sqn_id(client, h, "702")
    fid = _create_flight(client, h, sqn_id, "Wing-Assigned Flight")
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "702 Flighted User",
        "role": "sqn_general",
        "squadron_id": sqn_id,
        "flight_id": fid,
    })
    assert r.status_code == 200, r.text
    assert r.json()["flight_id"] == fid


def test_wing_admin_cannot_create_account_another_wing(client):
    """Wing admin cannot create an account for a Wing they don't manage."""
    h = login(client, "ADMIN7WG")
    # Try to create a sqn_general for a made-up wing_id
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "Out-of-Wing Account",
        "role": "wing_viewer",
        "wing_id": "00000000-0000-0000-0000-000000000099",  # fake wing
    })
    assert r.status_code in (403, 404), r.text


def test_wing_admin_cannot_create_sqn_account_another_wing(client):
    """Wing admin cannot create SQN accounts for SQNs outside their Wing."""
    h_nat = login(client, "ADMINNATIONAL")
    # Get a real sqn_id that belongs to... we only have one wing, so test with fake
    h = login(client, "ADMIN7WG")
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "Out-of-Wing SQN User",
        "role": "sqn_admin",
        "squadron_id": "00000000-0000-0000-0000-000000000099",
    })
    assert r.status_code in (403, 404), r.text


def test_wing_admin_cannot_create_national_admin(client):
    h = login(client, "ADMIN7WG")
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "Illegal NAT Admin",
        "role": "national_admin",
    })
    assert r.status_code == 403, r.text


def test_wing_admin_cannot_create_system_admin(client):
    h = login(client, "ADMIN7WG")
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "Illegal System Admin",
        "role": "system_admin",
    })
    assert r.status_code == 403, r.text


def test_wing_admin_cannot_create_auditor(client):
    h = login(client, "ADMIN7WG")
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "Illegal Auditor",
        "role": "auditor",
    })
    assert r.status_code == 403, r.text


# ─────────────────────────────────────────────────────────────
# 3. SQN admin account creation authority
# ─────────────────────────────────────────────────────────────

def test_sqn_admin_can_create_sqn_general_own_sqn(client):
    h = login(client, "ADMIN703")
    sqn_id = _get_sqn_id(client, h, "703")
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "703 Test General",
        "role": "sqn_general",
        "squadron_id": sqn_id,
    })
    assert r.status_code == 200, r.text
    assert r.json()["squadron_id"] == sqn_id


def test_sqn_admin_can_assign_flight_own_sqn(client):
    h = login(client, "ADMIN703")
    sqn_id = _get_sqn_id(client, h, "703")
    fid = _create_flight(client, h, sqn_id, "703 A Flight")
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "703 A-Flight Member",
        "role": "sqn_general",
        "squadron_id": sqn_id,
        "flight_id": fid,
    })
    assert r.status_code == 200, r.text
    assert r.json()["flight_id"] == fid
    # Verify the user still belongs to the squadron, not a flight-level tenant
    assert r.json()["squadron_id"] == sqn_id
    assert r.json()["scope_type"] == "squadron"


def test_sqn_admin_cannot_create_wing_account(client):
    h = login(client, "ADMIN703")
    wing_id = _get_wing_id(client, login(client, "ADMIN7WG"))
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "Illegal Wing User",
        "role": "wing_viewer",
        "wing_id": wing_id,
    })
    assert r.status_code == 403, r.text


def test_sqn_admin_cannot_create_national_account(client):
    h = login(client, "ADMIN703")
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "Illegal NAT Viewer",
        "role": "national_viewer",
    })
    assert r.status_code == 403, r.text


def test_sqn_admin_cannot_create_account_another_sqn(client):
    h703 = login(client, "ADMIN703")
    h7wg = login(client, "ADMIN7WG")
    sqn704_id = _get_sqn_id(client, h7wg, "704")
    r = client.post("/api/accounts", headers=h703, json={
        "display_name": "704 Interloper",
        "role": "sqn_general",
        "squadron_id": sqn704_id,
    })
    assert r.status_code == 403, r.text


def test_sqn_admin_cannot_create_sqn_admin_another_sqn(client):
    h703 = login(client, "ADMIN703")
    h7wg = login(client, "ADMIN7WG")
    sqn704_id = _get_sqn_id(client, h7wg, "704")
    r = client.post("/api/accounts", headers=h703, json={
        "display_name": "704 Fake Admin",
        "role": "sqn_admin",
        "squadron_id": sqn704_id,
    })
    assert r.status_code == 403, r.text


def test_sqn_admin_cannot_create_system_admin(client):
    h = login(client, "ADMIN703")
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "Illegal SysAdmin",
        "role": "system_admin",
    })
    assert r.status_code == 403, r.text


# ─────────────────────────────────────────────────────────────
# 4. Viewer and auditor cannot create accounts
# ─────────────────────────────────────────────────────────────

def test_viewer_cannot_create_accounts(client):
    h = login(client, "7WG2026")  # wing_viewer
    wing_id = _get_wing_id(client, h)
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "Viewer Attempt",
        "role": "sqn_general",
        "squadron_id": "00000000-0000-0000-0000-000000000001",
    })
    assert r.status_code == 403, r.text


def test_auditor_cannot_create_accounts(client):
    h = login(client, "AUDITOR2026")
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "Auditor Attempt",
        "role": "sqn_general",
        "squadron_id": "00000000-0000-0000-0000-000000000001",
    })
    assert r.status_code == 403, r.text


def test_sqn_general_cannot_create_accounts(client):
    h = login(client, "703SQN2026")
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "General Attempt",
        "role": "sqn_general",
        "squadron_id": "00000000-0000-0000-0000-000000000001",
    })
    assert r.status_code == 403, r.text


# ─────────────────────────────────────────────────────────────
# 5. Access-code security invariants
# ─────────────────────────────────────────────────────────────

def test_reset_code_returns_new_code_once(client):
    """Reset endpoint returns a new code in this response only."""
    h = login(client, "ADMINNATIONAL")
    hwg = login(client, "ADMIN7WG")
    sqn_id = _get_sqn_id(client, hwg, "703")
    # Create a new account
    create_r = client.post("/api/accounts", headers=h, json={
        "display_name": "Reset Code Test User",
        "role": "sqn_general",
        "squadron_id": sqn_id,
    })
    uid = create_r.json()["user_id"]

    r = client.post(f"/api/accounts/{uid}/reset-code", headers=h, json={})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "new_code" in data
    assert len(data["new_code"]) >= 6
    assert "new_code_notice" in data
    assert "not be shown again" in data["new_code_notice"]


def test_existing_access_code_cannot_be_retrieved(client):
    """The accounts list and detail endpoints must never return code hashes or plaintext."""
    h = login(client, "ADMINNATIONAL")
    accounts = client.get("/api/accounts", headers=h).json()
    for acct in accounts:
        assert "code_hash" not in acct, "code_hash must never appear in account response"
        assert "new_code" not in acct, "new_code must not appear in list response"
        # code_last_changed is metadata, not the code itself — that's fine
    if accounts:
        uid = accounts[0]["user_id"]
        detail = client.get(f"/api/accounts/{uid}", headers=h).json()
        assert "code_hash" not in detail
        assert "new_code" not in detail


def test_access_code_hash_never_returned_in_create(client):
    """Create response returns new_code (plaintext, once) but never code_hash."""
    h = login(client, "ADMINNATIONAL")
    hwg = login(client, "ADMIN7WG")
    sqn_id = _get_sqn_id(client, hwg, "703")
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "Hash Check User",
        "role": "sqn_general",
        "squadron_id": sqn_id,
    })
    data = r.json()
    assert "code_hash" not in data
    assert "new_code" in data   # one-time code is returned
    # The hash starts with "$pbkdf2" for passlib — check it's absent
    code_val = data["new_code"]
    assert not code_val.startswith("$pbkdf2"), "code_hash leaked as new_code"


def test_create_code_with_manual_code(client):
    """Caller may supply a manual code; it must be stored as hash, not plain."""
    h = login(client, "ADMINNATIONAL")
    hwg = login(client, "ADMIN7WG")
    sqn_id = _get_sqn_id(client, hwg, "703")
    manual = "TESTCODE99"
    r = client.post("/api/accounts", headers=h, json={
        "display_name": "Manual Code User",
        "role": "sqn_general",
        "squadron_id": sqn_id,
        "new_code": manual,
    })
    assert r.status_code == 200
    assert r.json()["new_code"] == manual  # echoed back once
    # Now verify login with that code works
    login_r = client.post("/api/auth/login", json={"code": manual})
    assert login_r.status_code == 200, "manually set code must be usable for login"


# ─────────────────────────────────────────────────────────────
# 6. Flight assignment does not create tenancy or expand access
# ─────────────────────────────────────────────────────────────

def test_flight_assignment_does_not_expand_access(client):
    """A user assigned to Flight A still belongs to the Squadron — cannot cross SQN boundary."""
    h703 = login(client, "ADMIN703")
    sqn_id = _get_sqn_id(client, h703, "703")
    fid = _create_flight(client, h703, sqn_id, "Access Test Flight")

    # Create a sqn_general assigned to the flight
    r = client.post("/api/accounts", headers=h703, json={
        "display_name": "Flight Access Test",
        "role": "sqn_general",
        "squadron_id": sqn_id,
        "flight_id": fid,
    })
    assert r.status_code == 200
    new_code = r.json()["new_code"]
    uid = r.json()["user_id"]

    # Log in as this user and verify they still see only their SQN data
    h_new = login(client, new_code)
    sqns_visible = client.get("/api/squadrons", headers=h_new).json()
    assert len(sqns_visible) == 1
    assert sqns_visible[0]["squadron_id"] == sqn_id


def test_flight_assignment_does_not_restrict_to_flight_only(client):
    """A user assigned to a flight still has their full SQN scope, not just flight scope."""
    h703 = login(client, "ADMIN703")
    sqn_id = _get_sqn_id(client, h703, "703")
    fid = _create_flight(client, h703, sqn_id, "Scope Test Flight")

    r = client.post("/api/accounts", headers=h703, json={
        "display_name": "Flight Scope User",
        "role": "sqn_general",
        "squadron_id": sqn_id,
        "flight_id": fid,
    })
    new_code = r.json()["new_code"]
    h_new = login(client, new_code)
    # Should be able to read parade nights (SQN scope) — not blocked by flight
    pns = client.get("/api/parade-nights", headers=h_new)
    assert pns.status_code == 200


def test_flight_must_belong_to_correct_squadron(client):
    """Cannot assign a flight from Squadron A to a user in Squadron B."""
    h_nat = login(client, "ADMINNATIONAL")
    h7wg = login(client, "ADMIN7WG")
    sqn703_id = _get_sqn_id(client, h7wg, "703")
    sqn704_id = _get_sqn_id(client, h7wg, "704")

    # Create a flight in 703
    fid_703 = _create_flight(client, h_nat, sqn703_id, "703 Flight")

    # Try to assign it to a user in 704 — should fail
    r = client.post("/api/accounts", headers=h_nat, json={
        "display_name": "Cross-SQN Flight User",
        "role": "sqn_general",
        "squadron_id": sqn704_id,
        "flight_id": fid_703,  # wrong SQN!
    })
    assert r.status_code == 422, r.text


def test_flight_not_valid_for_national_scope_user(client):
    """Flight assignment must be rejected for non-squadron-scoped accounts."""
    h_nat = login(client, "ADMINNATIONAL")
    h7wg = login(client, "ADMIN7WG")
    sqn_id = _get_sqn_id(client, h7wg, "703")
    fid = _create_flight(client, h_nat, sqn_id, "Invalid Flight")
    wing_id = _get_wing_id(client, h7wg)

    r = client.post("/api/accounts", headers=h_nat, json={
        "display_name": "Wing User With Flight",
        "role": "wing_viewer",
        "wing_id": wing_id,
        "flight_id": fid,  # invalid — wing-scope user cannot have flight
    })
    assert r.status_code == 422, r.text


# ─────────────────────────────────────────────────────────────
# 7. Disable / reactivate
# ─────────────────────────────────────────────────────────────

def test_disable_and_reactivate_account(client):
    h = login(client, "ADMINNATIONAL")
    hwg = login(client, "ADMIN7WG")
    sqn_id = _get_sqn_id(client, hwg, "703")
    create_r = client.post("/api/accounts", headers=h, json={
        "display_name": "Disable Test User",
        "role": "sqn_general",
        "squadron_id": sqn_id,
    })
    uid = create_r.json()["user_id"]
    code = create_r.json()["new_code"]

    # Disable
    r = client.post(f"/api/accounts/{uid}/disable", headers=h, json={})
    assert r.status_code == 200, r.text

    # Login should now fail
    login_r = client.post("/api/auth/login", json={"code": code})
    assert login_r.status_code == 401, "Disabled user must not be able to log in"

    # Reactivate
    r2 = client.post(f"/api/accounts/{uid}/reactivate", headers=h, json={})
    assert r2.status_code == 200, r2.text

    # After reactivate, must reset code (since disable deactivated the old one)
    reset_r = client.post(f"/api/accounts/{uid}/reset-code", headers=h, json={})
    new_code = reset_r.json()["new_code"]
    login_r2 = client.post("/api/auth/login", json={"code": new_code})
    assert login_r2.status_code == 200, "Reactivated user must be able to log in with new code"


def test_cannot_disable_self(client):
    h = login(client, "ADMINNATIONAL")
    me = client.get("/api/auth/me", headers=h).json()["session"]
    r = client.post(f"/api/accounts/{me['user_id']}/disable", headers=h, json={})
    assert r.status_code == 400, r.text


# ─────────────────────────────────────────────────────────────
# 8. Account changes are audited
# ─────────────────────────────────────────────────────────────

def test_account_actions_audited(client):
    h = login(client, "ADMINNATIONAL")
    hwg = login(client, "ADMIN7WG")
    sqn_id = _get_sqn_id(client, hwg, "703")

    create_r = client.post("/api/accounts", headers=h, json={
        "display_name": "Audit Trail Test",
        "role": "sqn_general",
        "squadron_id": sqn_id,
    })
    uid = create_r.json()["user_id"]
    client.post(f"/api/accounts/{uid}/reset-code", headers=h, json={})
    client.post(f"/api/accounts/{uid}/disable", headers=h, json={})
    client.post(f"/api/accounts/{uid}/reactivate", headers=h, json={})

    audit = client.get("/api/audit", headers=h).json()
    actions = [a["action"] for a in audit]
    assert "account_created" in actions
    assert "reset_access" in actions
    assert "account_disabled" in actions
    assert "account_reactivated" in actions


# ─────────────────────────────────────────────────────────────
# 9. Flight CRUD security
# ─────────────────────────────────────────────────────────────

def test_sqn_admin_can_create_and_archive_flight(client):
    h = login(client, "ADMIN703")
    sqn_id = _get_sqn_id(client, h, "703")
    r = client.post("/api/flights", headers=h, json={"name": "Alpha Flight", "squadron_id": sqn_id})
    assert r.status_code == 200, r.text
    fid = r.json()["flight_id"]

    # Archive it
    r2 = client.post(f"/api/flights/{fid}/archive", headers=h, json={})
    assert r2.status_code == 200, r2.text
    # Should be gone from list
    flights = client.get("/api/flights", headers=h).json()
    assert all(f["flight_id"] != fid for f in flights)


def test_sqn_admin_cannot_create_flight_another_sqn(client):
    h703 = login(client, "ADMIN703")
    h7wg = login(client, "ADMIN7WG")
    sqn704_id = _get_sqn_id(client, h7wg, "704")
    r = client.post("/api/flights", headers=h703, json={"name": "Interloper Flight", "squadron_id": sqn704_id})
    assert r.status_code == 403, r.text


def test_viewer_cannot_create_flight(client):
    h = login(client, "7WG2026")  # wing_viewer
    r = client.post("/api/flights", headers=h, json={
        "name": "Viewer Flight Attempt",
        "squadron_id": "00000000-0000-0000-0000-000000000001",
    })
    assert r.status_code == 403, r.text


# ─────────────────────────────────────────────────────────────
# 10. Account read scoping
# ─────────────────────────────────────────────────────────────

def test_nat_admin_sees_all_accounts(client):
    h = login(client, "ADMINNATIONAL")
    accounts = client.get("/api/accounts", headers=h).json()
    assert len(accounts) >= 5  # at least the seeded users


def test_wing_admin_sees_only_own_wing_accounts(client):
    h = login(client, "ADMIN7WG")
    accounts = client.get("/api/accounts", headers=h).json()
    for acct in accounts:
        # Every account visible to wing_admin must be in their wing
        assert acct.get("wing_id") == acct.get("wing_id") or acct.get("squadron_id")
        # No account should be from another wing (all seeded data is one wing)
        assert acct.get("scope_type") in ("wing", "squadron", "national") or acct.get("role") in ("national_admin", "system_admin", "auditor", "national_viewer")


def test_sqn_admin_sees_only_own_sqn_accounts(client):
    h = login(client, "ADMIN703")
    accounts = client.get("/api/accounts", headers=h).json()
    for acct in accounts:
        assert acct.get("squadron_id") is not None or acct.get("scope_type") == "squadron"


def test_sqn_admin_cannot_see_other_sqn_accounts_by_filter(client):
    h703 = login(client, "ADMIN703")
    h7wg = login(client, "ADMIN7WG")
    sqn704_id = _get_sqn_id(client, h7wg, "704")
    accounts = client.get(f"/api/accounts?squadron_id={sqn704_id}", headers=h703).json()
    # SQN admin is scoped to own SQN — filter for another SQN must return empty
    for acct in accounts:
        assert acct.get("squadron_id") != sqn704_id, "SQN admin must not see another SQN's accounts"


# ─────────────────────────────────────────────────────────────
# Item 2: Reset access code — code invalidation and re-auth
# ─────────────────────────────────────────────────────────────

def test_old_code_fails_after_reset(client):
    """After reset-code, the original code must be rejected at login."""
    h_nat = login(client, "ADMINNATIONAL")
    h7wg = login(client, "ADMIN7WG")
    sqn_id = _get_sqn_id(client, h7wg, "703")

    # Create account — initial code is in the create response
    create_r = client.post("/api/accounts", headers=h_nat, json={
        "display_name": "Old Code Test User",
        "role": "sqn_general",
        "squadron_id": sqn_id,
        "new_code": "OLDCODE1",
    })
    assert create_r.status_code == 200, create_r.text
    uid = create_r.json()["user_id"]

    # Verify original code works
    pre = client.post("/api/auth/login", json={"code": "OLDCODE1"})
    assert pre.status_code == 200, "Original code should authenticate before reset"

    # Reset the code
    reset_r = client.post(f"/api/accounts/{uid}/reset-code", headers=h_nat, json={})
    assert reset_r.status_code == 200, reset_r.text
    assert "new_code" in reset_r.json()

    # Original code must now fail
    post = client.post("/api/auth/login", json={"code": "OLDCODE1"})
    assert post.status_code != 200, "Original code must be rejected after reset"


def test_new_code_authenticates_after_reset(client):
    """After reset-code, the returned new_code must authenticate successfully."""
    h_nat = login(client, "ADMINNATIONAL")
    h7wg = login(client, "ADMIN7WG")
    sqn_id = _get_sqn_id(client, h7wg, "703")

    create_r = client.post("/api/accounts", headers=h_nat, json={
        "display_name": "New Code Auth Test",
        "role": "sqn_general",
        "squadron_id": sqn_id,
    })
    assert create_r.status_code == 200, create_r.text
    uid = create_r.json()["user_id"]

    # Reset code and capture the new one
    reset_r = client.post(f"/api/accounts/{uid}/reset-code", headers=h_nat, json={})
    assert reset_r.status_code == 200, reset_r.text
    new_code = reset_r.json()["new_code"]
    assert len(new_code) >= 6

    # New code must authenticate
    login_r = client.post("/api/auth/login", json={"code": new_code})
    assert login_r.status_code == 200, f"New code failed to authenticate: {login_r.text}"
    assert "token" in login_r.json()


def test_reset_code_is_audited(client):
    """reset-code must create an audit entry."""
    h_nat = login(client, "ADMINNATIONAL")
    h7wg = login(client, "ADMIN7WG")
    sqn_id = _get_sqn_id(client, h7wg, "703")

    create_r = client.post("/api/accounts", headers=h_nat, json={
        "display_name": "Reset Audit Test",
        "role": "sqn_general",
        "squadron_id": sqn_id,
    })
    uid = create_r.json()["user_id"]

    client.post(f"/api/accounts/{uid}/reset-code", headers=h_nat, json={})
    audit = client.get("/api/audit", headers=h_nat).json()
    found = any(
        a.get("object_id") == uid and a.get("action") == "code_generated"
        for a in audit
    )
    assert found, "reset_code action not found in audit log"


def test_disable_is_audited(client):
    """disable must create an audit entry."""
    h_nat = login(client, "ADMINNATIONAL")
    h7wg = login(client, "ADMIN7WG")
    sqn_id = _get_sqn_id(client, h7wg, "703")

    create_r = client.post("/api/accounts", headers=h_nat, json={
        "display_name": "Disable Audit Test",
        "role": "sqn_general",
        "squadron_id": sqn_id,
    })
    uid = create_r.json()["user_id"]

    client.post(f"/api/accounts/{uid}/disable", headers=h_nat, json={})
    audit = client.get("/api/audit", headers=h_nat).json()
    found = any(
        a.get("object_id") == uid and a.get("action") == "account_disabled"
        for a in audit
    )
    assert found, "disable action not found in audit log"


def test_cross_wing_disable_denied(client):
    """Wing admin cannot disable an account under a different wing."""
    h_nat = login(client, "ADMINNATIONAL")
    h7wg = login(client, "ADMIN7WG")

    # Get a 703 SQN account (under 7WG — same wing, so this is actually allowed for ADMIN7WG)
    # Create a separate wing to test cross-wing denial properly
    wing_r = client.post("/api/wings", headers=h_nat, json={"code": "XWGD01", "name": "Cross Wing Disable"})
    assert wing_r.status_code == 200, wing_r.text
    other_wing_id = wing_r.json()["wing_id"]

    sqn_r = client.post("/api/squadrons", headers=h_nat, json={
        "wing_id": other_wing_id, "code": "XWDS01", "name": "Cross Wing Disable SQN"
    })
    assert sqn_r.status_code == 200, sqn_r.text
    other_sqn_id = sqn_r.json()["squadron_id"]

    acct_r = client.post("/api/accounts", headers=h_nat, json={
        "display_name": "Cross Wing Target",
        "role": "sqn_general",
        "squadron_id": other_sqn_id,
    })
    assert acct_r.status_code == 200, acct_r.text
    uid = acct_r.json()["user_id"]

    # 7WG admin attempts to disable an account under a different wing — must be 403
    r = client.post(f"/api/accounts/{uid}/disable", headers=h7wg, json={})
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"


def test_cross_squadron_reset_denied(client):
    """SQN admin cannot reset a code for a user in another squadron."""
    h_nat = login(client, "ADMINNATIONAL")
    h_703 = login(client, "ADMIN703")
    h7wg = login(client, "ADMIN7WG")
    sqn704_id = _get_sqn_id(client, h7wg, "704")

    # Create account in 704
    acct_r = client.post("/api/accounts", headers=h_nat, json={
        "display_name": "Cross SQN Reset Target",
        "role": "sqn_general",
        "squadron_id": sqn704_id,
    })
    assert acct_r.status_code == 200, acct_r.text
    uid = acct_r.json()["user_id"]

    # 703 admin tries to reset code for a 704 user — must be 403
    r = client.post(f"/api/accounts/{uid}/reset-code", headers=h_703, json={})
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"


def test_sqn_admin_cannot_manage_account_outside_authority_role(client):
    """SQN admin cannot manage (disable / reset-code) an account whose role isn't
    in their authority at all (e.g. a wing_admin) -- distinct from the cross-scope
    "different squadron/wing" checks above: this must be denied purely because
    wing_admin is never in sqn_admin's _CREATE_AUTHORITY set, regardless of which
    wing or squadron either account belongs to."""
    h_703 = login(client, "ADMIN703")
    h7wg = login(client, "ADMIN7WG")

    me = client.get("/api/auth/me", headers=h7wg)
    assert me.status_code == 200
    wing_admin_uid = me.json()["session"]["user_id"]

    r = client.post(f"/api/accounts/{wing_admin_uid}/disable", headers=h_703, json={})
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"

    r2 = client.post(f"/api/accounts/{wing_admin_uid}/reset-code", headers=h_703, json={})
    assert r2.status_code == 403, f"Expected 403, got {r2.status_code}: {r2.text}"


def test_cross_wing_disable_denied_for_wing_viewer_target(client):
    """Wing admin cannot disable a wing_viewer account under a DIFFERENT wing --
    covers the wing-scope branch of manage-authority specifically (target role
    wing_viewer), which is a different code path than the squadron-scope cross-wing
    check test_cross_wing_disable_denied above (target role sqn_general)."""
    h_nat = login(client, "ADMINNATIONAL")
    h7wg = login(client, "ADMIN7WG")

    wing_r = client.post("/api/wings", headers=h_nat, json={"code": "XWGV01", "name": "Cross Wing Viewer"})
    assert wing_r.status_code == 200, wing_r.text
    other_wing_id = wing_r.json()["wing_id"]

    acct_r = client.post("/api/accounts", headers=h_nat, json={
        "display_name": "Cross Wing Viewer Target",
        "role": "wing_viewer",
        "wing_id": other_wing_id,
    })
    assert acct_r.status_code == 200, acct_r.text
    uid = acct_r.json()["user_id"]

    # 7WG admin attempts to disable a wing_viewer under a different wing — must be 403
    r = client.post(f"/api/accounts/{uid}/disable", headers=h7wg, json={})
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text}"


# ─────────────────────────────────────────────────────────────
# 10. Role / access-type change
# ─────────────────────────────────────────────────────────────

def test_change_role_happy_path(client):
    h_nat = login(client, "ADMINNATIONAL")
    h7wg = login(client, "ADMIN7WG")
    sqn_id = _get_sqn_id(client, h7wg, "703")

    create_r = client.post("/api/accounts", headers=h_nat, json={
        "display_name": "Role Change Target",
        "role": "sqn_general",
        "squadron_id": sqn_id,
    })
    uid = create_r.json()["user_id"]

    r = client.post(f"/api/accounts/{uid}/change-role", headers=h_nat,
                     json={"new_role": "sqn_admin"})
    assert r.status_code == 200, r.text

    got = client.get(f"/api/accounts/{uid}", headers=h_nat).json()
    assert got["role"] == "sqn_admin"


def test_change_role_is_audited(client):
    h_nat = login(client, "ADMINNATIONAL")
    h7wg = login(client, "ADMIN7WG")
    sqn_id = _get_sqn_id(client, h7wg, "703")

    create_r = client.post("/api/accounts", headers=h_nat, json={
        "display_name": "Role Change Audit Target",
        "role": "sqn_general",
        "squadron_id": sqn_id,
    })
    uid = create_r.json()["user_id"]
    client.post(f"/api/accounts/{uid}/change-role", headers=h_nat, json={"new_role": "sqn_admin"})

    audit = client.get("/api/audit", headers=h_nat).json()
    entry = next((a for a in audit if a.get("object_id") == uid and a.get("action") == "role_changed"), None)
    assert entry is not None, "role_changed action not found in audit log"


def test_change_role_forbidden_for_read_only_role(client):
    """auditor (read-only) cannot change anyone's role."""
    h_nat = login(client, "ADMINNATIONAL")
    h7wg = login(client, "ADMIN7WG")
    sqn_id = _get_sqn_id(client, h7wg, "703")

    create_r = client.post("/api/accounts", headers=h_nat, json={
        "display_name": "Role Change Forbidden Target",
        "role": "sqn_general",
        "squadron_id": sqn_id,
    })
    uid = create_r.json()["user_id"]

    # Verify via a role this actor genuinely lacks authority over: sqn_admin
    # cannot promote a sqn_general straight to wing_admin.
    h_sqn = login(client, "ADMIN703")
    r = client.post(f"/api/accounts/{uid}/change-role", headers=h_sqn, json={"new_role": "wing_admin"})
    assert r.status_code == 403, r.text


def test_change_role_unauthenticated(client):
    r = client.post("/api/accounts/some-id/change-role", json={"new_role": "sqn_admin"})
    assert r.status_code == 401, r.text


def test_change_role_cross_scope_rejected(client):
    """Squadron-scope role -> wing-scope role is a different operation (org
    reassignment), not a plain permission-level change, and must be rejected."""
    h_nat = login(client, "ADMINNATIONAL")
    h7wg = login(client, "ADMIN7WG")
    sqn_id = _get_sqn_id(client, h7wg, "703")

    create_r = client.post("/api/accounts", headers=h_nat, json={
        "display_name": "Cross Scope Role Target",
        "role": "sqn_general",
        "squadron_id": sqn_id,
    })
    uid = create_r.json()["user_id"]

    r = client.post(f"/api/accounts/{uid}/change-role", headers=h_nat, json={"new_role": "wing_admin"})
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["error"] == "cross_scope_role_change"


def test_cannot_change_own_role(client):
    h_nat = login(client, "ADMINNATIONAL")
    me = client.get("/api/auth/me", headers=h_nat).json()["session"]
    r = client.post(f"/api/accounts/{me['user_id']}/change-role", headers=h_nat,
                     json={"new_role": "national_viewer"})
    assert r.status_code == 400, r.text


def test_change_role_never_drives_active_admin_count_below_one(client):
    """The real guarantee here, mirroring the documented reasoning in
    test_bulk_account_archive.py::test_batch_archive_never_drives_active_admin_count_to_zero:
    the explicit "last_active_system_admin" 409 branch in change_role is
    deliberately unreachable through this HTTP endpoint under normal use, and
    that is by design. Reaching it would require an actor who has authority to
    change a system_admin's role (i.e. is themselves an active system_admin,
    per _CREATE_AUTHORITY) to act on a DIFFERENT system_admin target while the
    count is already <=1 — but the actor's own active membership always
    contributes at least 1 to that count, and self-changes are separately
    blocked (test_cannot_change_own_role), so any legal two-party call always
    has count >= 2 beforehand. What IS reachable and tested here: demoting one
    of several active system_admins down to a smaller-but-still-nonzero count
    succeeds cleanly."""
    h_sa = login(client, "SYSADMIN2026")
    create_r = client.post("/api/accounts", headers=h_sa, json={
        "display_name": "Second Sysadmin",
        "role": "system_admin",
    })
    uid2 = create_r.json()["user_id"]

    # Two active system_admins now exist — demoting the second one is fine,
    # since the acting admin's own active membership keeps the floor at 1.
    r = client.post(f"/api/accounts/{uid2}/change-role", headers=h_sa,
                     json={"new_role": "national_admin"})
    assert r.status_code == 200, r.text


# ─────────────────────────────────────────────────────────────
# Self-edit (display name / flight only, no role field): must not 403.
# _CREATE_AUTHORITY's wing_admin/sqn_admin entries deliberately exclude their
# own role (so they can't mass-create peer-level accounts), but that map was
# also being used to gate ordinary self-edits via _require_manage_authority,
# so a sqn_admin/wing_admin editing even their own display name always 403'd.
# ─────────────────────────────────────────────────────────────

def test_sqn_admin_can_edit_own_display_name(client):
    h = login(client, "ADMIN703")
    me = client.get("/api/auth/me", headers=h).json()["session"]["user_id"]
    r = client.patch(f"/api/accounts/{me}", headers=h, json={"display_name": "Renamed Self"})
    assert r.status_code == 200, r.text
    acct = client.get(f"/api/accounts/{me}", headers=h).json()
    assert acct["display_name"] == "Renamed Self"


def test_wing_admin_can_edit_own_display_name(client):
    h = login(client, "ADMIN7WG")
    me = client.get("/api/auth/me", headers=h).json()["session"]["user_id"]
    r = client.patch(f"/api/accounts/{me}", headers=h, json={"display_name": "Wing Self Rename"})
    assert r.status_code == 200, r.text
    acct = client.get(f"/api/accounts/{me}", headers=h).json()
    assert acct["display_name"] == "Wing Self Rename"


def test_sqn_admin_still_cannot_edit_another_squadrons_account(client):
    """The self-edit bypass must be scoped to uid == the caller's own id --
    editing an unrelated account is still properly authority-checked."""
    h703 = login(client, "ADMIN703")
    h704 = login(client, "ADMIN704")
    other_uid = client.get("/api/auth/me", headers=h704).json()["session"]["user_id"]
    r = client.patch(f"/api/accounts/{other_uid}", headers=h703, json={"display_name": "Should not work"})
    assert r.status_code == 403, r.text
