"""Security paths the 2026-10-11 coverage map found unproven or only weakly proven.

Each test pins a behaviour that docs/stabilisation/operational-workflow-audit.md
already claims; none changes product behaviour. Where a claim fails, it is a
defect and gets a D-number rather than an edited expectation.
"""
from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import RecoveryToken, ServiceTicket
from tests.conftest import login
from tests.test_account_recovery import (_capture_token, _me, _prepare_recoverable,
                                         _restore_sysadmin_code, _sysadmin, _token_from)
from tests.test_service_desk import _make_ticket, _sqn_id


# ── Recovery ─────────────────────────────────────────────────────────────────

def test_a_session_issued_before_recovery_is_rejected_after_it(client, monkeypatch):
    uid, seen = _prepare_recoverable(client, monkeypatch, "replay@example.com")
    old = _sysadmin(client)                                  # a live session
    assert client.get("/api/auth/me", headers=old).status_code == 200
    client.post("/api/auth/forgot-code", json={"email": "replay@example.com"})
    r = client.post("/api/auth/reset-code",
                    json={"token": _token_from(seen), "new_code": "REPLAY-NEW-CODE-27"})
    assert r.status_code == 200, r.text
    try:
        r = client.get("/api/auth/me", headers=old)          # replay the old JWT
        assert r.status_code == 401, r.text
        assert r.json()["detail"]["error"] == "session_revoked"
    finally:
        _restore_sysadmin_code(uid)


def test_recovery_mail_goes_to_the_verified_recovery_address(client, monkeypatch):
    _, seen = _prepare_recoverable(client, monkeypatch, "routing@example.com")
    seen.clear()
    client.post("/api/auth/forgot-code", json={"email": "routing@example.com"})
    assert seen.get("to") == "routing@example.com"


def test_an_unverified_recovery_address_is_sent_nothing(client, monkeypatch):
    uid, seen = _prepare_recoverable(client, monkeypatch, "verified-first@example.com")
    hdr = _sysadmin(client)
    # Changing the address clears its verification (and mails a verify link).
    client.post(f"/api/accounts/{uid}/recovery-email", headers=hdr,
                json={"email": "unverified-now@example.com", "current_code": "SYSADMIN2026"})
    seen.clear()
    r = client.post("/api/auth/forgot-code", json={"email": "unverified-now@example.com"})
    assert r.status_code == 200
    assert seen == {}, "an unverified address must never receive a reset token"


def test_the_fourth_request_for_one_address_in_an_hour_sends_nothing(client, monkeypatch):
    _, seen = _prepare_recoverable(client, monkeypatch, "perlimit@example.com")
    import app.routers.auth as auth_mod
    auth_mod.reset_recovery_limiter()
    sent = 0
    for _ in range(4):
        seen.clear()
        client.post("/api/auth/forgot-code", json={"email": "perlimit@example.com"})
        sent += bool(seen)
    assert sent == 3, f"{sent} reset mails for one address (limit 3 per hour)"


def test_the_sixth_request_from_one_ip_in_an_hour_sends_nothing(client, monkeypatch):
    _, seen = _prepare_recoverable(client, monkeypatch, "iplimit@example.com")
    import app.routers.auth as auth_mod
    auth_mod.reset_recovery_limiter()
    for i in range(5):
        client.post("/api/auth/forgot-code", json={"email": f"nobody{i}@example.com"})
    seen.clear()
    r = client.post("/api/auth/forgot-code", json={"email": "iplimit@example.com"})
    assert r.status_code == 200                      # same constant response
    assert seen == {}, "the sixth request from one IP must not mail a token"


def test_a_failed_reset_mail_leaves_no_usable_token(client, monkeypatch):
    uid, _ = _prepare_recoverable(client, monkeypatch, "smtpdown@example.com")
    import app.routers.auth as auth_mod
    auth_mod.reset_recovery_limiter()
    attempts = []
    monkeypatch.setattr(auth_mod, "send_mail", lambda to, subject, body: attempts.append(to) or False)
    db = SessionLocal()
    try:
        before = db.query(RecoveryToken).filter(RecoveryToken.user_id == uid,
                                                RecoveryToken.purpose == "reset").count()
    finally:
        db.close()
    r = client.post("/api/auth/forgot-code", json={"email": "smtpdown@example.com"})
    assert r.status_code == 200
    db = SessionLocal()
    try:
        after = db.query(RecoveryToken).filter(RecoveryToken.user_id == uid,
                                               RecoveryToken.purpose == "reset",
                                               RecoveryToken.consumed_at.is_(None)).count()
    finally:
        db.close()
    assert attempts == ["smtpdown@example.com"], "the mail path was not exercised"
    assert after <= before, "a token whose mail failed must not stay redeemable"


# ── Service Desk mail failure ────────────────────────────────────────────────

def test_a_ticket_is_kept_when_the_notification_mail_fails(client, monkeypatch):
    import app.routers.service_desk as sd

    calls = []

    def boom(*_a, **_k):
        calls.append(1)
        raise ConnectionRefusedError("SMTP down")
    monkeypatch.setattr(sd, "send_ticket_notification", boom)
    created = _make_ticket(client, _sqn_id("703SQN"), description="SMTP failure persistence check.")
    assert calls, "the notification path was not exercised"
    db = SessionLocal()
    try:
        assert db.get(ServiceTicket, created["ticket_id"]) is not None
    finally:
        db.close()


def test_a_ticket_update_is_kept_when_the_submitter_mail_fails(client, monkeypatch):
    import app.routers.service_desk as sd

    calls = []

    def boom(*_a, **_k):
        calls.append(1)
        raise ConnectionRefusedError("SMTP down")
    monkeypatch.setattr(sd, "send_ticket_update_notification", boom)
    tid = _make_ticket(client, _sqn_id("703SQN"), description="SMTP failure on update.")["ticket_id"]
    h = login(client, "SYSADMIN2026")
    r = client.patch(f"/api/service-desk/tickets/{tid}", json={"status": "in_progress"}, headers=h)
    assert r.status_code == 200, r.text
    assert calls, "the submitter notification path was not exercised"
    db = SessionLocal()
    try:
        assert db.get(ServiceTicket, tid).status == "in_progress"
    finally:
        db.close()


# ── Audit immutability and configuration redaction ───────────────────────────

def _all_routes():
    """(path, methods) for every route. FastAPI 0.141 wraps included routers as
    _IncludedRouter, so app.routes shows only '/': iterating it made the first
    version of the test below pass vacuously (found 2026-10-12)."""
    for r in app.router.routes:
        ctx = getattr(r, "effective_route_contexts", None)
        if ctx is None:
            if getattr(r, "path", None):
                yield r.path, set(getattr(r, "methods", None) or ())
            continue
        for c in (ctx() if callable(ctx) else ctx):
            yield c.path, set(c.methods or ())


def test_no_route_can_modify_or_delete_audit_records():
    routes = list(_all_routes())
    assert len(routes) > 300, f"route enumeration found only {len(routes)}; the check would be vacuous"
    audit = [(path, m) for path, m in routes if "audit" in path]
    assert {path for path, _ in audit} >= {"/api/audit", "/api/system/audit-summary"}
    offenders = [f"{sorted(m)} {path}" for path, m in audit if m & {"PUT", "PATCH", "DELETE"}]
    assert offenders == [], offenders


def test_system_endpoints_never_return_secrets(client):
    h = login(client, "SYSADMIN2026")
    secrets = [s for s in (settings.DATABASE_URL, settings.JWT_SECRET, settings.SECRET_KEY) if s]
    for path in ("/api/system/overview", "/api/system/migrations", "/api/health",
                 "/api/health/ready", "/api/health/ui-config"):
        r = client.get(path, headers=h)
        assert r.status_code == 200, (path, r.text)
        for s in secrets:
            assert s not in r.text, f"{path} leaks a configured secret"
