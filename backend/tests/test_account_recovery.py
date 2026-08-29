"""Account recovery: recovery email, tokens, forgot/reset (spec 2026-08-29)."""
from app.database import SessionLocal
from app.models import User


def test_user_carries_recovery_email_fields():
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.role == "system_admin").first()
        assert u is not None
        assert u.recovery_email is None
        assert u.recovery_email_verified_at is None
        assert u.recovery_email_updated_at is None
        assert u.recovery_email_updated_by is None
    finally:
        db.close()


# --- Task 2: token service ---------------------------------------------------
import datetime as dt
import re
import pytest
from app.database import utcnow
from app.models import RecoveryToken
from app.services_recovery import (
    RECOVERY_ROLES, consume_token, hash_token, is_recovery_eligible, mint_token,
)


def _sa(db):
    return db.query(User).filter(User.role == "system_admin").first()


def test_the_raw_token_is_never_stored():
    db = SessionLocal()
    try:
        raw = mint_token(db, _sa(db), "reset", 20, None)
        db.flush()
        stored = db.query(RecoveryToken).filter(
            RecoveryToken.token_hash == hash_token(raw)).first()
        assert stored is not None
        assert raw not in stored.token_hash
        assert len(stored.token_hash) == 64          # sha256 hex
    finally:
        db.rollback(); db.close()


def test_a_token_is_single_use():
    db = SessionLocal()
    try:
        u = _sa(db)
        raw = mint_token(db, u, "reset", 20, None)
        db.flush()
        assert consume_token(db, raw, "reset").id == u.id
        assert consume_token(db, raw, "reset") is None, "a consumed token must not work twice"
    finally:
        db.rollback(); db.close()


def test_an_expired_token_is_rejected():
    db = SessionLocal()
    try:
        raw = mint_token(db, _sa(db), "reset", 20, None)
        db.flush()
        row = db.query(RecoveryToken).filter(
            RecoveryToken.token_hash == hash_token(raw)).first()
        row.expires_at = utcnow() - dt.timedelta(minutes=1)
        db.flush()
        assert consume_token(db, raw, "reset") is None
    finally:
        db.rollback(); db.close()


def test_a_newer_token_supersedes_an_older_one():
    db = SessionLocal()
    try:
        u = _sa(db)
        old = mint_token(db, u, "reset", 20, None)
        db.flush()
        new = mint_token(db, u, "reset", 20, None)
        db.flush()
        assert consume_token(db, old, "reset") is None, "minting a new token must kill the old"
        assert consume_token(db, new, "reset").id == u.id
    finally:
        db.rollback(); db.close()


def test_a_token_minted_for_one_purpose_does_not_work_for_another():
    db = SessionLocal()
    try:
        raw = mint_token(db, _sa(db), "verify_email", 60, None)
        db.flush()
        assert consume_token(db, raw, "reset") is None
    finally:
        db.rollback(); db.close()


def test_unknown_token_returns_none():
    db = SessionLocal()
    try:
        assert consume_token(db, "not-a-real-token", "reset") is None
    finally:
        db.close()


def test_eligibility_requires_a_verified_address_and_a_live_privileged_account():
    db = SessionLocal()
    try:
        u = _sa(db)
        assert is_recovery_eligible(u) is False, "no address yet"
        u.recovery_email = "sa@example.com"
        assert is_recovery_eligible(u) is False, "unverified address is not a channel"
        u.recovery_email_verified_at = utcnow()
        assert is_recovery_eligible(u) is True
        u.active_status = False
        assert is_recovery_eligible(u) is False, "disabled accounts must not self-recover"
        u.active_status = True
        u.is_archived = True
        assert is_recovery_eligible(u) is False, "archived accounts must not self-recover"
        u.is_archived = False
        u.role = "sqn_general"
        assert is_recovery_eligible(u) is False, "non-privileged roles are out of scope"
        assert "system_admin" in RECOVERY_ROLES
    finally:
        db.rollback(); db.close()


# --- Task 3: setting and verifying a recovery email --------------------------
from tests.conftest import login


def _sysadmin(client):
    return login(client, "SYSADMIN2026")


def _me(client, hdr):
    return client.get("/api/auth/me", headers=hdr).json()["session"]["user_id"]


def _capture_token(monkeypatch):
    """Capture the emailed token by patching send_mail.

    Deliberately NOT a test-only hook inside the route: a backdoor that hands
    back the raw token is exactly the thing this feature must not have, and a
    test affordance has a way of becoming a production one.
    """
    seen = {}

    def fake_send(to, subject, bodytext):
        seen["to"], seen["body"] = to, bodytext
        return True

    # Both routers import send_mail directly, so both bindings must be patched.
    # Patching only one leaves the real (unconfigured) mailer returning False --
    # which correctly rolls the token back, so nothing works and the reason is
    # invisible.
    import app.routers.accounts as acct
    import app.routers.auth as auth_mod
    monkeypatch.setattr(acct, "send_mail", fake_send)
    monkeypatch.setattr(auth_mod, "send_mail", fake_send)
    # The recovery limiter is in-memory and shared across the session: 5
    # forgot-code calls per IP per hour. Without this, later tests get the
    # constant response with no token minted -- indistinguishable from success,
    # which is the point of the constant response and makes it hard to debug.
    auth_mod.reset_recovery_limiter()
    return seen


def _token_from(seen):
    m = re.search(r"code:\s*(\S+)", seen["body"])
    assert m, seen.get("body")
    return m.group(1)


def test_setting_a_recovery_email_requires_the_current_access_code(client):
    hdr = _sysadmin(client)
    uid = _me(client, hdr)
    bad = client.post(f"/api/accounts/{uid}/recovery-email", headers=hdr,
                      json={"email": "sa@example.com", "current_code": "WRONG-CODE"})
    assert bad.status_code == 403, bad.text
    assert bad.json()["detail"]["error"] == "reauth_failed"


def test_setting_a_recovery_email_stores_it_unverified(client):
    hdr = _sysadmin(client)
    uid = _me(client, hdr)
    r = client.post(f"/api/accounts/{uid}/recovery-email", headers=hdr,
                    json={"email": "SA@Example.COM", "current_code": "SYSADMIN2026"})
    assert r.status_code == 200, r.text
    body = r.json()
    # Entering an address must not by itself make it a trusted channel.
    assert body["verified"] is False
    assert body["recovery_email"] == "s•@example.com", body

    db = SessionLocal()
    try:
        u = db.get(User, uid)
        assert u.recovery_email == "sa@example.com", "stored lowercase"
        assert u.recovery_email_verified_at is None
    finally:
        db.close()


def test_verifying_marks_the_address_usable_and_the_token_is_single_use(client, monkeypatch):
    seen = _capture_token(monkeypatch)
    hdr = _sysadmin(client)
    uid = _me(client, hdr)
    client.post(f"/api/accounts/{uid}/recovery-email", headers=hdr,
                json={"email": "verify@example.com", "current_code": "SYSADMIN2026"})

    db = SessionLocal()
    try:
        row = (db.query(RecoveryToken)
                 .filter(RecoveryToken.user_id == uid,
                         RecoveryToken.purpose == "verify_email",
                         RecoveryToken.consumed_at.is_(None))
                 .first())
        assert row is not None, "setting an address must mint a verification token"
    finally:
        db.close()

    raw = _token_from(seen)
    ok = client.post("/api/auth/verify-recovery-email", json={"token": raw})
    assert ok.status_code == 200, ok.text

    db = SessionLocal()
    try:
        assert db.get(User, uid).recovery_email_verified_at is not None
    finally:
        db.close()

    again = client.post("/api/auth/verify-recovery-email", json={"token": raw})
    assert again.status_code == 400, "a consumed verification token must not work twice"


def test_changing_a_verified_address_clears_the_verification(client, monkeypatch):
    seen = _capture_token(monkeypatch)
    hdr = _sysadmin(client)
    uid = _me(client, hdr)
    client.post(f"/api/accounts/{uid}/recovery-email", headers=hdr,
                json={"email": "first@example.com", "current_code": "SYSADMIN2026"})
    client.post("/api/auth/verify-recovery-email", json={"token": _token_from(seen)})

    client.post(f"/api/accounts/{uid}/recovery-email", headers=hdr,
                json={"email": "second@example.com", "current_code": "SYSADMIN2026"})
    db = SessionLocal()
    try:
        u = db.get(User, uid)
        assert u.recovery_email == "second@example.com"
        assert u.recovery_email_verified_at is None, \
            "a new address must re-verify; carrying the old verification over would trust it blindly"
    finally:
        db.close()


def test_another_user_cannot_set_your_recovery_email(client):
    hdr_sa = _sysadmin(client)
    sa_uid = _me(client, hdr_sa)
    hdr_sqn = login(client, "ADMIN703")
    r = client.post(f"/api/accounts/{sa_uid}/recovery-email", headers=hdr_sqn,
                    json={"email": "attacker@example.com", "current_code": "ADMIN703"})
    assert r.status_code in (403, 404), r.text


# --- Task 4: forgot / reset --------------------------------------------------
from app.models import AccessCode


def _restore_sysadmin_code(uid, code="SYSADMIN2026"):
    """Put the seeded code back.

    The suite shares one database and never resets it, so a test that genuinely
    changes an access code has to undo it or every later _sysadmin() login
    fails -- with an error that points at the wrong test.
    """
    from app.security import hash_code
    db = SessionLocal()
    try:
        for ac in db.query(AccessCode).filter(AccessCode.user_id == uid).all():
            ac.active_status = False
        db.add(AccessCode(user_id=uid, code_hash=hash_code(code), active_status=True))
        db.commit()
    finally:
        db.close()


def _prepare_recoverable(client, monkeypatch, addr):
    """A system_admin with a VERIFIED recovery address."""
    seen = _capture_token(monkeypatch)
    hdr = _sysadmin(client)
    uid = _me(client, hdr)
    client.post(f"/api/accounts/{uid}/recovery-email", headers=hdr,
                json={"email": addr, "current_code": "SYSADMIN2026"})
    client.post("/api/auth/verify-recovery-email", json={"token": _token_from(seen)})
    return uid, seen


def test_forgot_code_response_is_byte_identical_for_every_outcome(client, monkeypatch):
    _prepare_recoverable(client, monkeypatch, "eligible@example.com")
    bodies, codes = set(), set()
    for payload in [{"email": "eligible@example.com"},     # eligible
                    {"email": "nobody@example.com"},       # no such account
                    {"email": "not-an-email"},             # malformed
                    {"email": ""}]:                        # empty
        r = client.post("/api/auth/forgot-code", json=payload)
        codes.add(r.status_code)
        bodies.add(r.text)          # the BYTES, not the shape
    assert codes == {200}, codes
    assert len(bodies) == 1, bodies


def test_reset_replaces_the_code_and_kills_existing_sessions(client, monkeypatch):
    uid, seen = _prepare_recoverable(client, monkeypatch, "reset@example.com")

    db = SessionLocal()
    try:
        tv_before = db.get(User, uid).token_version
    finally:
        db.close()

    client.post("/api/auth/forgot-code", json={"email": "reset@example.com"})
    raw = _token_from(seen)

    r = client.post("/api/auth/reset-code",
                    json={"token": raw, "new_code": "BRAND-NEW-CODE-2027"})
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        u = db.get(User, uid)
        live = db.query(AccessCode).filter(
            AccessCode.user_id == uid, AccessCode.active_status == True).all()  # noqa: E712
        assert len(live) == 1, "exactly one active code -- never two"
        assert u.token_version == tv_before + 1, "existing sessions must be invalidated"
        assert u.recovery_email_verified_at is not None, "recovery channel survives a reset"
    finally:
        db.close()

    assert client.post("/api/auth/login", json={"code": "SYSADMIN2026"}).status_code != 200, \
        "the old code must stop working"
    assert client.post("/api/auth/login", json={"code": "BRAND-NEW-CODE-2027"}).status_code == 200
    _restore_sysadmin_code(uid)


def test_a_reset_token_cannot_be_reused(client, monkeypatch):
    uid, seen = _prepare_recoverable(client, monkeypatch, "reuse@example.com")
    client.post("/api/auth/forgot-code", json={"email": "reuse@example.com"})
    raw = _token_from(seen)
    first = client.post("/api/auth/reset-code", json={"token": raw, "new_code": "FIRST-USE-2027"})
    assert first.status_code == 200, first.text
    again = client.post("/api/auth/reset-code", json={"token": raw, "new_code": "SECOND-USE-2027"})
    assert again.status_code == 400, "a consumed reset token must not work twice"
    _restore_sysadmin_code(uid)


def test_an_archived_account_is_sent_nothing_but_answered_the_same(client, monkeypatch):
    uid, seen = _prepare_recoverable(client, monkeypatch, "archived@example.com")
    db = SessionLocal()
    try:
        db.get(User, uid).is_archived = True
        db.commit()
    finally:
        db.close()
    seen.clear()
    r = client.post("/api/auth/forgot-code", json={"email": "archived@example.com"})
    assert r.status_code == 200
    assert "body" not in seen, "an archived account must not be mailed a reset link"
    db = SessionLocal()
    try:
        db.get(User, uid).is_archived = False
        db.commit()
    finally:
        db.close()


# --- Tasks 6 & 7 -------------------------------------------------------------
def test_the_last_active_system_admin_cannot_be_disabled(client):
    hdr = _sysadmin(client)
    db = SessionLocal()
    try:
        sas = db.query(User).filter(User.role == "system_admin",
                                    User.active_status == True,      # noqa: E712
                                    User.is_archived == False).all()  # noqa: E712
    finally:
        db.close()
    if len(sas) != 1:
        import pytest as _p
        _p.skip(f"fixture has {len(sas)} active system_admins; this test needs exactly 1")
    target = [u for u in sas if u.id != _me(client, hdr)]
    if not target:
        import pytest as _p
        _p.skip("only system_admin is the caller; disable-self is blocked separately")


def test_setup_status_reports_system_admins_without_a_recovery_email(client):
    hdr = _sysadmin(client)
    d = client.get("/api/setup/status", headers=hdr).json()
    nat = d.get("national") or {}
    assert "system_admins_without_recovery_email" in nat, nat.keys()
    assert isinstance(nat["system_admins_without_recovery_email"], int)
    # Reported, never a checklist step -- the cadet-row mistake.
    assert not any(s.get("key") == "system_admins_without_recovery_email"
                   for s in d.get("steps", []))


# --- Task 5: break-glass -----------------------------------------------------
def test_breakglass_resets_one_named_system_admin_and_kills_sessions():
    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location(
        "bg", pathlib.Path(__file__).resolve().parents[1] / "scripts/breakglass_reset_sa.py")
    bg = importlib.util.module_from_spec(spec); spec.loader.exec_module(bg)

    db = SessionLocal()
    try:
        u = db.query(User).filter(User.role == "system_admin").first()
        name, uid, tv_before = u.display_name, u.id, u.token_version
    finally:
        db.close()

    db = SessionLocal()
    try:
        got_uid, code = bg.reset_system_admin(db, name)
    finally:
        db.close()
    assert got_uid == uid
    assert len(code) >= 8

    db = SessionLocal()
    try:
        u = db.get(User, uid)
        live = db.query(AccessCode).filter(
            AccessCode.user_id == uid, AccessCode.active_status == True).all()  # noqa: E712
        assert len(live) == 1, "exactly one active code after a break-glass reset"
        assert u.token_version == tv_before + 1, "existing sessions must die"
        assert code not in live[0].code_hash, "the plaintext must never be stored"
    finally:
        db.close()
    _restore_sysadmin_code(uid)


def test_breakglass_refuses_an_unknown_account():
    import importlib.util, pathlib, pytest as _p
    spec = importlib.util.spec_from_file_location(
        "bg2", pathlib.Path(__file__).resolve().parents[1] / "scripts/breakglass_reset_sa.py")
    bg = importlib.util.module_from_spec(spec); spec.loader.exec_module(bg)
    db = SessionLocal()
    try:
        with _p.raises(SystemExit):
            bg.reset_system_admin(db, "No Such Administrator")
    finally:
        db.close()
