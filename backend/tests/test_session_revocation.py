"""Regression tests: JWT token_version-based session revocation.

When a user's access code is reset (via either change_code or accounts reset-code),
any previously issued tokens must be rejected with 401 session_revoked.
"""
from tests.conftest import login
from app.security import create_token


def _get_sqn_admin_id(client) -> str:
    """Get the user_id for the seeded sqn_admin (703SQN2026 code → ADMIN703 user)."""
    sysadmin_hdr = login(client, "SYSADMIN2026")
    r = client.get("/api/accounts/accounts?limit=100", headers=sysadmin_hdr)
    assert r.status_code == 200
    users = r.json()
    for u in users:
        if u.get("role") == "sqn_admin" and "703" in (u.get("display_name") or ""):
            return u["user_id"]
    raise ValueError("sqn_admin for 703 not found in accounts list")


def test_token_still_valid_before_code_change(client):
    """Baseline: a token obtained before any code change is valid."""
    hdr = login(client, "ADMIN703")
    r = client.get("/api/health", headers=hdr)
    assert r.status_code == 200


def test_own_token_revoked_after_change_code(client):
    """After a user changes their own code, their old token must return 401 session_revoked."""
    old_hdr = login(client, "ADMIN703")

    me = client.get("/api/auth/me", headers=old_hdr)
    assert me.status_code == 200
    uid = me.json()["session"]["user_id"]

    r = client.post("/api/auth/change-code",
                    json={"user_id": uid, "new_code": "NEWCODE99"},
                    headers=old_hdr)
    assert r.status_code == 200

    # Old token must now be revoked
    r2 = client.get("/api/auth/me", headers=old_hdr)
    assert r2.status_code == 401
    assert r2.json()["detail"]["error"] == "session_revoked"

    # Restore original code so other tests are not affected
    new_hdr = login(client, "NEWCODE99")
    me2 = client.get("/api/auth/me", headers=new_hdr)
    uid2 = me2.json()["session"]["user_id"]
    client.post("/api/auth/change-code",
                json={"user_id": uid2, "new_code": "ADMIN703"},
                headers=new_hdr)


def test_token_revoked_after_admin_resets_code(client):
    """When sqn_admin resets sqn_general code, the sqn_general old token must be rejected."""
    admin_hdr = login(client, "ADMIN703")
    old_general_hdr = login(client, "703SQN2026")

    # Get sqn_general user_id
    me = client.get("/api/auth/me", headers=old_general_hdr)
    assert me.status_code == 200
    gen_uid = me.json()["session"]["user_id"]

    # sqn_admin resets sqn_general code
    r = client.post(f"/api/accounts/{gen_uid}/reset-code",
                    json={"new_code": "RESETGEN1"},
                    headers=admin_hdr)
    assert r.status_code == 200

    # Old sqn_general token must now be rejected
    r2 = client.get("/api/auth/me", headers=old_general_hdr)
    assert r2.status_code == 401
    assert r2.json()["detail"]["error"] == "session_revoked"

    # Restore original code
    client.post(f"/api/accounts/{gen_uid}/reset-code",
                json={"new_code": "703SQN2026"},
                headers=admin_hdr)


def test_new_token_valid_after_code_reset(client):
    """After code reset, a NEW login with the new code must succeed."""
    admin_hdr = login(client, "ADMIN703")

    me = client.get("/api/auth/me", headers=login(client, "703SQN2026"))
    gen_uid = me.json()["session"]["user_id"]

    client.post(f"/api/accounts/{gen_uid}/reset-code",
                json={"new_code": "FRESHCODE1"},
                headers=admin_hdr)

    new_hdr = login(client, "FRESHCODE1")
    r = client.get("/api/auth/me", headers=new_hdr)
    assert r.status_code == 200

    # Restore
    client.post(f"/api/accounts/{gen_uid}/reset-code",
                json={"new_code": "703SQN2026"},
                headers=admin_hdr)


def test_time_expired_token_rejected(client):
    """A token whose exp claim has already passed must be rejected with 401,
    independent of token_version revocation (covers section 7's 'expired
    sessions' RBAC-matrix requirement, previously only covered for
    version-based revocation, not literal time expiry)."""
    hdr = login(client, "ADMIN703")
    me = client.get("/api/auth/me", headers=hdr)
    uid = me.json()["session"]["user_id"]

    expired_token = create_token(uid, {"role": "sqn_admin"}, ttl_min=-1)
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert r.status_code == 401


def test_unrelated_user_token_not_revoked(client):
    """Resetting one user's code must NOT revoke another user's active token."""
    admin_hdr = login(client, "ADMIN703")
    other_hdr = login(client, "ADMIN703")  # second token for sqn_admin

    # Get sqn_general id and reset their code
    me = client.get("/api/auth/me", headers=login(client, "703SQN2026"))
    gen_uid = me.json()["session"]["user_id"]
    client.post(f"/api/accounts/{gen_uid}/reset-code",
                json={"new_code": "UNRELATED1"},
                headers=admin_hdr)

    # The sqn_admin's other token must still work
    r = client.get("/api/auth/me", headers=other_hdr)
    assert r.status_code == 200

    # Restore
    client.post(f"/api/accounts/{gen_uid}/reset-code",
                json={"new_code": "703SQN2026"},
                headers=admin_hdr)
