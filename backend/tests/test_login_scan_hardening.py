"""Code-only login must not scan every account outside development/test.

Audit finding (P1): POST /api/auth/login without user_id ("legacy scan-all",
commented "test-only" but unenforced) ran PBKDF2 against EVERY active access
code until one matched -- N slow hashes per unauthenticated guess -- and
checked per-account lockout only AFTER a match, so failed guesses never locked
any account (IP throttle only). Every production caller (Main TMS, Planning
Workspace, deploy scripts) already sends user_id from /api/auth/lookup.

Contract now: code-only login is allowed only when ENVIRONMENT is development
or test; anywhere else it is refused with 422 user_id_required BEFORE any hash
is computed. The scoped path (user_id) is unchanged and is pinned here too.
"""
import pytest

from app.config import settings
from tests.conftest import login


@pytest.fixture
def hash_counter(monkeypatch):
    import app.routers.auth as auth_mod
    real = auth_mod.verify_code
    calls = {"n": 0}

    def counting(code, h):
        calls["n"] += 1
        return real(code, h)
    monkeypatch.setattr(auth_mod, "verify_code", counting)
    return calls


@pytest.fixture(autouse=True)
def _fresh_ip_bucket(client):
    # IP throttle is shared across the suite; start each case clean.
    from app.database import SessionLocal
    from app.models import IpLoginAttempt
    db = SessionLocal()
    try:
        db.query(IpLoginAttempt).delete()
        db.commit()
    finally:
        db.close()


@pytest.mark.parametrize("env", ["production", "prod", "staging", "STAGING"])
def test_code_only_login_is_refused_before_any_hash_outside_dev(client, monkeypatch, hash_counter, env):
    monkeypatch.setattr(settings, "ENVIRONMENT", env)
    r = client.post("/api/auth/login", json={"code": "ADMIN703"})       # a VALID code
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["error"] == "user_id_required"
    assert hash_counter["n"] == 0, "no access-code hash may be evaluated on the refused path"


@pytest.mark.parametrize("env", ["development", "test"])
def test_code_only_login_still_works_for_local_tooling(client, monkeypatch, env):
    monkeypatch.setattr(settings, "ENVIRONMENT", env)
    assert client.post("/api/auth/login", json={"code": "ADMIN703"}).status_code == 200


def _uid(client, unit_type, ident, role):
    body = {"unit_type": unit_type, "role": role}
    if ident:
        body["identifier"] = ident
    r = client.post("/api/auth/lookup", json=body)
    assert r.status_code == 200, r.text
    return r.json()["user_id"]


def test_scoped_login_works_in_production(client, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    uid = _uid(client, "squadron", "703", "sqn_admin")
    assert client.post("/api/auth/login", json={"user_id": uid, "code": "ADMIN703"}).status_code == 200


def test_scoped_wrong_code_hashes_only_the_unit_role_scope(client, monkeypatch, hash_counter):
    """A wrong code on the scoped path costs 1 + (same unit+role siblings)
    verifications -- never one per account in the system."""
    from app.database import SessionLocal
    from app.models import AccessCode, User
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    uid = _uid(client, "squadron", "703", "sqn_admin")
    db = SessionLocal()
    try:
        me = db.get(User, uid)
        scope = db.query(User).filter(User.squadron_id == me.squadron_id, User.role == me.role,
                                      User.active_status == True).count()  # noqa: E712
        total = db.query(AccessCode).filter(AccessCode.active_status == True).count()  # noqa: E712
    finally:
        db.close()
    assert total > scope, "fixture must make the scan-all cost visibly larger"
    r = client.post("/api/auth/login", json={"user_id": uid, "code": "WRONG-CODE-1"})
    assert r.status_code == 401
    assert hash_counter["n"] <= scope, (hash_counter["n"], scope, total)
    # Restore the primary account's failure counter for later tests.
    db = SessionLocal()
    try:
        for ac in db.query(AccessCode).filter(AccessCode.user_id == uid).all():
            ac.failed_attempts = 0
            ac.locked_until = None
        db.commit()
    finally:
        db.close()


def test_scoped_repeated_wrong_codes_lock_the_account_even_for_the_right_code(client, monkeypatch):
    """Per-account lockout really applies on the production path."""
    from app.database import SessionLocal
    from app.models import AccessCode
    from app.routers import auth as auth_mod
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    uid = _uid(client, "wing", "7WG", "wing_viewer")
    try:
        for _ in range(auth_mod._LOCKOUT_THRESHOLD):
            assert client.post("/api/auth/login", json={"user_id": uid, "code": "NOPE-1234"}).status_code in (401, 429)
            _fresh_ip(client)
        r = client.post("/api/auth/login", json={"user_id": uid, "code": "7WG2026"})
        assert r.status_code == 429, "a locked account must refuse even its correct code"
        assert r.json()["detail"]["error"] == "locked_out"
    finally:
        db = SessionLocal()
        try:
            for ac in db.query(AccessCode).filter(AccessCode.user_id == uid).all():
                ac.failed_attempts = 0
                ac.locked_until = None
            db.commit()
        finally:
            db.close()


def _fresh_ip(client):
    from app.database import SessionLocal
    from app.models import IpLoginAttempt
    db = SessionLocal()
    try:
        db.query(IpLoginAttempt).delete()
        db.commit()
    finally:
        db.close()


def test_refused_code_only_attempt_still_counts_against_the_ip(client, monkeypatch):
    """Refusing early must not create a free, unthrottled probe."""
    from app.database import SessionLocal
    from app.models import IpLoginAttempt
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    client.post("/api/auth/login", json={"code": "ANY-GUESS-1"})
    db = SessionLocal()
    try:
        assert db.query(IpLoginAttempt).count() == 1
    finally:
        db.close()


def test_login_helper_contract_unchanged(client):
    # The suite's own login() helper (code-only, ENVIRONMENT=test) keeps working.
    assert login(client, "ADMIN703")
