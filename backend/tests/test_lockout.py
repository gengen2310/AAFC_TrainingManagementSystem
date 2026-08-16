"""Per-account and DB-backed IP lockout tests."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from app.database import SessionLocal, engine
from app.models import AccessCode, IpLoginAttempt
from tests.conftest import login


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_ac_id(user_code: str) -> str:
    """Return the primary key of the active AccessCode whose hash matches user_code."""
    from app.security import verify_code
    db = SessionLocal()
    try:
        for ac in db.query(AccessCode).filter(AccessCode.active_status == True).all():  # noqa: E712
            if verify_code(user_code, ac.code_hash):
                return ac.id
    finally:
        db.close()
    raise ValueError(f"No active AccessCode found for code {user_code!r}")


def _set_account_locked(user_code: str, minutes: int = 30) -> None:
    """Directly set locked_until on the AccessCode matching user_code hash.
    Uses raw SQL to bypass the ORM identity map so subsequent requests see fresh state.
    """
    ac_id = _find_ac_id(user_code)
    locked_dt = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE access_codes SET locked_until=:lu, failed_attempts=5 WHERE id=:id"),
            {"lu": locked_dt, "id": ac_id},
        )
    engine.dispose()


def _clear_account_lock(user_code: str) -> None:
    ac_id = _find_ac_id(user_code)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE access_codes SET locked_until=NULL, failed_attempts=0 WHERE id=:id"),
            {"id": ac_id},
        )
    engine.dispose()


def _clear_ip_lock(ip: str = "testclient") -> None:
    """Clear the DB-backed IP lockout row for the given IP.

    Required after the R5-M19/M21 fix that adds record_login_failure_db to the
    scoped login path: 5 scoped-path failures now also trigger IP lockout, so
    tests that verify account-level isolation must reset the IP counter before
    checking that sibling accounts can still log in.
    """
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE ip_login_attempts SET locked_until=NULL, attempt_count=0 WHERE ip=:ip"),
            {"ip": ip},
        )
    engine.dispose()


# ── DB-backed IP lockout ──────────────────────────────────────────────────────

def test_db_ip_lockout_fires_after_five_wrong_codes(client):
    for _ in range(5):
        r = client.post("/api/auth/login", json={"code": "WRONGCODE1"})
        assert r.status_code == 401
    # 6th attempt should be locked
    r = client.post("/api/auth/login", json={"code": "WRONGCODE1"})
    assert r.status_code == 429
    assert r.json()["detail"]["error"] == "locked_out"


def test_db_ip_lockout_persists_in_table(client):
    for _ in range(5):
        client.post("/api/auth/login", json={"code": "WRONGCODEIP"})
    db = SessionLocal()
    try:
        row = db.get(IpLoginAttempt, "testclient")
        assert row is not None
        assert row.locked_until is not None
    finally:
        db.close()


def test_successful_login_clears_ip_lockout(client):
    # Accumulate 4 failures
    for _ in range(4):
        client.post("/api/auth/login", json={"code": "WRONGCODEOK"})
    # Successful login resets counter
    r = client.post("/api/auth/login", json={"code": "ADMIN703"})
    assert r.status_code == 200
    db = SessionLocal()
    try:
        row = db.get(IpLoginAttempt, "testclient")
        # Row may or may not exist; if it does, locked_until must be cleared
        if row:
            assert row.locked_until is None
    finally:
        db.close()


# ── Per-account lockout ───────────────────────────────────────────────────────

def test_account_lockout_blocks_correct_code(client):
    _set_account_locked("703SQN2026")
    try:
        r = client.post("/api/auth/login", json={"code": "703SQN2026"})
        assert r.status_code == 429
        assert r.json()["detail"]["error"] == "locked_out"
    finally:
        _clear_account_lock("703SQN2026")


def test_account_lockout_does_not_affect_other_accounts(client):
    _set_account_locked("703SQN2026")
    try:
        r = client.post("/api/auth/login", json={"code": "ADMIN703"})
        assert r.status_code == 200
    finally:
        _clear_account_lock("703SQN2026")


def test_successful_login_resets_account_lockout(client):
    # Directly set a past locked_until (already expired) so login still succeeds but resets counters
    ac_id = _find_ac_id("ADMIN703")
    expired_dt = datetime.now(timezone.utc) - timedelta(minutes=1)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE access_codes SET locked_until=:lu, failed_attempts=3 WHERE id=:id"),
            {"lu": expired_dt, "id": ac_id},
        )
    engine.dispose()

    # Login should succeed (lock expired)
    r = client.post("/api/auth/login", json={"code": "ADMIN703"})
    assert r.status_code == 200

    # Confirm counters were reset in DB
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT failed_attempts, locked_until FROM access_codes WHERE id=:id"),
            {"id": ac_id},
        ).fetchone()
    assert row.failed_attempts == 0
    assert row.locked_until is None


# ── Unlock endpoint ───────────────────────────────────────────────────────────

def test_wing_admin_can_unlock_sqn_account(client):
    # Create a fresh user so test is not affected by other tests adding sqn_general users
    h_nat = login(client, "ADMINNATIONAL")
    h_wing = login(client, "ADMIN7WG")
    accounts_resp = client.get("/api/accounts", headers=h_wing).json()
    account_list = accounts_resp if isinstance(accounts_resp, list) else accounts_resp.get("accounts", [])
    sqn703 = next((a for a in account_list if a.get("squadron_code") == "703" and a["role"] == "sqn_admin"), None)
    assert sqn703 is not None
    sqn_id = sqn703["squadron_id"]

    create_r = client.post("/api/accounts", headers=h_nat, json={
        "display_name": "Unlock Test User",
        "role": "sqn_general",
        "squadron_id": sqn_id,
    })
    assert create_r.status_code == 200
    uid = create_r.json()["user_id"]
    test_code = create_r.json()["new_code"]

    # Lock via raw SQL using the access code id
    ac_id = _find_ac_id(test_code)
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE access_codes SET locked_until=datetime('now','+30 minutes'), failed_attempts=5 WHERE id=:id"),
            {"id": ac_id},
        )
    engine.dispose()

    # Confirm login is blocked
    r_blocked = client.post("/api/auth/login", json={"code": test_code})
    assert r_blocked.status_code == 429

    # Wing admin unlocks
    r_unlock = client.post(f"/api/accounts/{uid}/unlock", headers=h_wing)
    assert r_unlock.status_code == 200
    assert r_unlock.json()["ok"] is True

    # Confirm lock is cleared
    r2 = client.post("/api/auth/login", json={"code": test_code})
    assert r2.status_code == 200


def test_sqn_general_cannot_unlock(client):
    # Get a user id to attempt to unlock (the sqn_admin account)
    h_wing = login(client, "ADMIN7WG")
    accounts = client.get("/api/accounts", headers=h_wing).json()
    account_list = accounts if isinstance(accounts, list) else accounts.get("accounts", [])
    adm = next((a for a in account_list if a["role"] == "sqn_admin"
                and a.get("squadron_code") == "703"), None)
    assert adm is not None
    uid = adm["user_id"]

    # sqn_general tries to call unlock — should be 403 (_require_write_actor blocks non-write roles)
    h_gen = login(client, "703SQN2026")
    r = client.post(f"/api/accounts/{uid}/unlock", headers=h_gen)
    assert r.status_code == 403


def test_unlock_nonexistent_user_returns_404(client):
    h_wing = login(client, "ADMIN7WG")
    r = client.post("/api/accounts/nonexistent-uuid-1234/unlock", headers=h_wing)
    assert r.status_code == 404


def _find_user_id_for_code(user_code: str) -> str:
    """Return the user_id that owns the active AccessCode matching user_code."""
    ac_id = _find_ac_id(user_code)
    db = SessionLocal()
    try:
        ac = db.get(AccessCode, ac_id)
        return ac.user_id
    finally:
        db.close()


def test_locked_account_visible_in_account_detail(client):
    _set_account_locked("703SQN2026")
    try:
        uid = _find_user_id_for_code("703SQN2026")
        h_wing = login(client, "ADMIN7WG")
        detail = client.get(f"/api/accounts/{uid}", headers=h_wing).json()
        assert detail.get("locked_until") is not None
    finally:
        _clear_account_lock("703SQN2026")


# ── Scoped-path per-account lockout (user_id provided) ───────────────────────

def test_scoped_login_increments_failed_attempts(client):
    uid = _find_user_id_for_code("703SQN2026")
    ac_id = _find_ac_id("703SQN2026")
    with engine.begin() as conn:
        conn.execute(text("UPDATE access_codes SET failed_attempts=0, locked_until=NULL WHERE id=:id"),
                     {"id": ac_id})
    engine.dispose()

    for _ in range(5):
        r = client.post("/api/auth/login", json={"user_id": uid, "code": "WRONGCODE"})
        assert r.status_code == 401

    # 6th attempt with user_id → account locked → 429
    r = client.post("/api/auth/login", json={"user_id": uid, "code": "WRONGCODE"})
    assert r.status_code == 429
    assert r.json()["detail"]["error"] == "locked_out"
    _clear_account_lock("703SQN2026")


def test_scoped_lockout_does_not_affect_sibling_account(client):
    uid_viewer = _find_user_id_for_code("703SQN2026")
    ac_id = _find_ac_id("703SQN2026")
    with engine.begin() as conn:
        conn.execute(text("UPDATE access_codes SET failed_attempts=0, locked_until=NULL WHERE id=:id"),
                     {"id": ac_id})
    engine.dispose()

    for _ in range(5):
        client.post("/api/auth/login", json={"user_id": uid_viewer, "code": "WRONGCODE"})

    # Viewer is now locked
    r = client.post("/api/auth/login", json={"user_id": uid_viewer, "code": "WRONGCODE"})
    assert r.status_code == 429

    # The 5 scoped-path failures above also incremented the IP counter (R5-M19/M21
    # fix) — clear it so the sibling-account test isn't confounded by IP lockout.
    _clear_ip_lock()

    # Admin at the same squadron is unaffected (account-level lockout is isolated)
    h = login(client, "ADMIN703")
    assert h is not None
    _clear_account_lock("703SQN2026")


def test_admin_code_rejected_for_viewer_account(client):
    """Core isolation test: Admin code must not authenticate as the Viewer account."""
    uid_viewer = _find_user_id_for_code("703SQN2026")
    r = client.post("/api/auth/login", json={"user_id": uid_viewer, "code": "ADMIN703"})
    assert r.status_code == 401


def test_viewer_code_rejected_for_admin_account(client):
    """Symmetric isolation: Viewer code must not authenticate as the Admin account."""
    uid_admin = _find_user_id_for_code("ADMIN703")
    r = client.post("/api/auth/login", json={"user_id": uid_admin, "code": "703SQN2026"})
    assert r.status_code == 401


# ── Lookup endpoint ───────────────────────────────────────────────────────────

def test_lookup_squadron_admin(client):
    r = client.post("/api/auth/lookup", json={"unit_type": "squadron", "identifier": "703", "role": "sqn_admin"})
    assert r.status_code == 200
    d = r.json()
    assert "user_id" in d and "display_name" in d


def test_lookup_squadron_viewer(client):
    r = client.post("/api/auth/lookup", json={"unit_type": "squadron", "identifier": "703", "role": "sqn_general"})
    assert r.status_code == 200


def test_lookup_nonexistent_squadron(client):
    r = client.post("/api/auth/lookup", json={"unit_type": "squadron", "identifier": "999", "role": "sqn_admin"})
    assert r.status_code == 404


def test_lookup_wrong_role_for_squadron(client):
    r = client.post("/api/auth/lookup", json={"unit_type": "squadron", "identifier": "703", "role": "wing_admin"})
    assert r.status_code == 404


def test_lookup_wing(client):
    r = client.post("/api/auth/lookup", json={"unit_type": "wing", "identifier": "7WG", "role": "wing_admin"})
    assert r.status_code == 200


def test_lookup_wing_case_insensitive(client):
    r = client.post("/api/auth/lookup", json={"unit_type": "wing", "identifier": "7wg", "role": "wing_admin"})
    assert r.status_code == 200


def test_lookup_national_system_admin(client):
    r = client.post("/api/auth/lookup", json={"unit_type": "national", "role": "system_admin"})
    assert r.status_code == 200


def test_lookup_national_wrong_role(client):
    r = client.post("/api/auth/lookup", json={"unit_type": "national", "role": "sqn_admin"})
    assert r.status_code == 404


def test_lookup_then_login_full_flow(client):
    """End-to-end: lookup resolves user_id, login with user_id + correct code succeeds."""
    r = client.post("/api/auth/lookup", json={"unit_type": "squadron", "identifier": "703", "role": "sqn_admin"})
    assert r.status_code == 200
    uid = r.json()["user_id"]
    r2 = client.post("/api/auth/login", json={"user_id": uid, "code": "ADMIN703"})
    assert r2.status_code == 200
    assert "token" in r2.json()


def test_lookup_user_id_scope_prevents_wrong_code(client):
    """lookup gives admin uid; entering viewer code against it must fail."""
    r = client.post("/api/auth/lookup", json={"unit_type": "squadron", "identifier": "703", "role": "sqn_admin"})
    uid = r.json()["user_id"]
    r2 = client.post("/api/auth/login", json={"user_id": uid, "code": "703SQN2026"})
    assert r2.status_code == 401


def test_lockout_message_is_generic_not_7wg_specific(client):
    """Lockout message must not mention '7 Wing' — it must be Wing-agnostic."""
    _set_account_locked("703SQN2026")
    try:
        r = client.post("/api/auth/login", json={"code": "703SQN2026"})
        assert r.status_code == 429
        detail = r.json().get("detail", {})
        msg = detail.get("message", "")
        assert "7 Wing" not in msg, f"Lockout message is Wing-specific: {msg!r}"
        assert "Wing SOCAD" in msg or "SOCAD" in msg, f"Expected SOCAD contact hint in: {msg!r}"
    finally:
        _clear_account_lock("703SQN2026")


# ── DEF-03: Account immediate access (lookup ambiguity with multiple same-role accounts) ─────────

def _get_sqn_id_703(client):
    """Return the squadron_id for squadron 703 using the wing_admin credentials."""
    h_wg = login(client, "ADMIN7WG")
    sqns = client.get("/api/squadrons", headers=h_wg).json()
    for s in sqns:
        if s["code"] == "703":
            return s["squadron_id"]
    raise ValueError("Squadron 703 not found in seeded data")


def test_new_account_usable_immediately_via_lookup_login(client):
    """Newly created account must be usable immediately via lookup→login even when
    an older account with the same role exists in the same squadron.

    Root cause: lookup used .first() with no ORDER BY on a non-unique
    (squadron_id, role) filter — could return the older account's user_id, causing
    the new holder's code to fail (401) against the wrong AccessCode.

    Fix: lookup orders by created_at DESC (newest wins) + login falls back to a
    bounded sibling scan when the primary user_id's code fails.
    """
    h_nat = login(client, "ADMINNATIONAL")
    sqn_id = _get_sqn_id_703(client)

    # Create a second sqn_admin for squadron 703 (an older account already exists)
    create_r = client.post("/api/accounts", headers=h_nat, json={
        "display_name": "DEF-03 New Admin",
        "role": "sqn_admin",
        "squadron_id": sqn_id,
    })
    assert create_r.status_code == 200, create_r.text
    new_code = create_r.json()["new_code"]
    assert new_code, "Create response must include the one-time initial code"

    # Lookup must now return a user_id that succeeds with the new code.
    # (Returning the old account's user_id would cause 401 here — the regression.)
    lookup_r = client.post("/api/auth/lookup", json={
        "unit_type": "squadron",
        "identifier": "703",
        "role": "sqn_admin",
    })
    assert lookup_r.status_code == 200, lookup_r.text
    uid = lookup_r.json()["user_id"]

    login_r = client.post("/api/auth/login", json={"user_id": uid, "code": new_code})
    assert login_r.status_code == 200, (
        f"New account login must succeed immediately via lookup→login "
        f"(got {login_r.status_code}: {login_r.text})"
    )
    assert "token" in login_r.json(), "Successful login must return a token"


def test_existing_account_still_usable_after_new_sibling_created(client):
    """The original account must remain usable after a newer sibling is created.

    The newer account wins the lookup, but the older account holder can still log
    in via the scoped fallback scan in the login endpoint.
    """
    h_nat = login(client, "ADMINNATIONAL")
    sqn_id = _get_sqn_id_703(client)

    # Create a second sqn_admin (so lookup returns the newest one)
    create_r = client.post("/api/accounts", headers=h_nat, json={
        "display_name": "DEF-03 Sibling Admin",
        "role": "sqn_admin",
        "squadron_id": sqn_id,
    })
    assert create_r.status_code == 200, create_r.text

    # The original seeded admin code must still work via lookup→login
    # (the fallback scan in login picks it up even if lookup returns a sibling uid)
    lookup_r = client.post("/api/auth/lookup", json={
        "unit_type": "squadron",
        "identifier": "703",
        "role": "sqn_admin",
    })
    assert lookup_r.status_code == 200
    uid = lookup_r.json()["user_id"]

    original_login_r = client.post("/api/auth/login", json={"user_id": uid, "code": "ADMIN703"})
    assert original_login_r.status_code == 200, (
        f"Original account must remain usable after a newer sibling is created "
        f"(got {original_login_r.status_code}: {original_login_r.text})"
    )


def test_lookup_user_id_scope_still_prevents_cross_role_code(client):
    """Fallback scan must not allow a sqn_general code to succeed against sqn_admin uid.

    The sibling scan is bounded by role — it must only search users with the same
    role as the primary user_id. A viewer's code must not grant admin access.
    """
    lookup_r = client.post("/api/auth/lookup", json={
        "unit_type": "squadron",
        "identifier": "703",
        "role": "sqn_admin",
    })
    uid = lookup_r.json()["user_id"]
    # "703SQN2026" is the sqn_general code; entering it against sqn_admin uid must fail
    r = client.post("/api/auth/login", json={"user_id": uid, "code": "703SQN2026"})
    assert r.status_code == 401, (
        f"Cross-role fallback must not succeed: got {r.status_code}"
    )
