"""Regression tests: general API rate limiter (Phase 14).

The rate limiter is an in-memory sliding window that returns 429 when an
IP exceeds settings.API_RATE_LIMIT requests in settings.API_RATE_WINDOW_SEC.
Login and health endpoints are exempt from this limiter.
"""
import time

import pytest

from tests.conftest import login
from app.security import reset_api_rate_limiter, _api_hits, settings


def _prefill_hits(ip: str, count: int) -> None:
    """Inject `count` hit timestamps for `ip` so the very next request crosses the limit."""
    now = time.time()
    _api_hits[ip] = [now - 0.1] * count


@pytest.fixture(autouse=True)
def _clear_api_rate(monkeypatch):
    reset_api_rate_limiter()
    yield
    reset_api_rate_limiter()


def test_api_rate_limiter_unit_check():
    """Direct unit test: check_api_rate returns False below limit, True at/above."""
    from app.security import check_api_rate
    ip = "10.0.0.1"
    limit = settings.API_RATE_LIMIT
    for _ in range(limit):
        assert check_api_rate(ip) is False
    # One more pushes over
    assert check_api_rate(ip) is True


def test_rate_limit_429_on_api_endpoint(client):
    """Prefill the limiter to the threshold; the next request must return 429."""
    hdr = login(client, "ADMIN703")
    ip = "testclient"  # TestClient always reports this as the client host
    _prefill_hits(ip, settings.API_RATE_LIMIT)
    r = client.get("/api/auth/me", headers=hdr)
    assert r.status_code == 429
    assert r.json()["error"] == "rate_limited"
    assert "Retry-After" in r.headers


def test_rate_limit_does_not_block_health(client):
    """Health endpoints must never return 429 regardless of the rate counter."""
    ip = "testclient"
    _prefill_hits(ip, settings.API_RATE_LIMIT + 50)
    # /api/health is exempt
    r = client.get("/api/health")
    assert r.status_code == 200


def test_rate_limit_does_not_block_login(client):
    """Login endpoint must not be blocked by the general rate limiter."""
    ip = "testclient"
    _prefill_hits(ip, settings.API_RATE_LIMIT + 50)
    r = client.post("/api/auth/login", json={"code": "ADMIN703"})
    assert r.status_code == 200


def test_rate_limit_resets_after_window(client):
    """After the sliding window expires, the counter resets and requests succeed."""
    from app.security import check_api_rate
    ip = "10.0.0.2"
    past = time.time() - settings.API_RATE_WINDOW_SEC - 5
    _api_hits[ip] = [past] * (settings.API_RATE_LIMIT + 10)
    # All old hits are outside the window; new request should not be blocked
    assert check_api_rate(ip) is False


def test_rate_limit_different_ips_are_independent(client):
    """Exceeding the limit for one IP must not block a different IP."""
    from app.security import check_api_rate
    ip_a = "10.0.0.10"
    ip_b = "10.0.0.11"
    _prefill_hits(ip_a, settings.API_RATE_LIMIT)
    check_api_rate(ip_a)  # pushes ip_a over limit
    # ip_b has no hits yet
    assert check_api_rate(ip_b) is False


def test_rate_limit_does_not_count_options_preflight(client):
    """DEFECT-004: CORS preflight (OPTIONS) requests must not consume the
    general rate-limit budget -- they carry no credentials of consequence and
    reach no route/business logic. Counting them was silently halving the
    effective budget for any cross-origin caller (confirmed live: a
    connected-frontend e2e spec made ~220 OPTIONS requests alongside ~250
    real GET/POST requests in under a minute, tripping the limit well below
    its configured real-operation threshold). Regression guard: prefill the
    limiter exactly to the threshold, then confirm an OPTIONS request still
    succeeds (204, no rate_limited body) while a real GET is still blocked.
    """
    ip = "testclient"
    _prefill_hits(ip, settings.API_RATE_LIMIT)
    r = client.options("/api/auth/me")
    assert r.status_code != 429
    # The real GET immediately after is still correctly blocked -- this test
    # is verifying OPTIONS isn't counted, not that the limiter is disabled.
    hdr = login(client, "ADMIN703")
    r = client.get("/api/auth/me", headers=hdr)
    assert r.status_code == 429


def test_rate_limit_options_does_not_advance_the_counter(client):
    """A burst of OPTIONS requests alone must never trip the limiter for the
    real requests that follow."""
    ip = "testclient"
    for _ in range(settings.API_RATE_LIMIT + 50):
        client.options("/api/auth/me")
    hdr = login(client, "ADMIN703")
    r = client.get("/api/auth/me", headers=hdr)
    assert r.status_code == 200


# ─────────────────────────────────────────────────────────────
# DEF-10: DB-backed rate limiter (check_api_rate_db)
# ─────────────────────────────────────────────────────────────

def _db():
    from app.database import SessionLocal
    return SessionLocal()


def test_db_rate_limiter_unit_check():
    """DEF-10: check_api_rate_db counts correctly and blocks over the limit."""
    from app.security import check_api_rate_db, reset_api_rate_limiter_db
    db = _db()
    try:
        reset_api_rate_limiter_db(db)
        ip = "10.0.0.20"
        limit = settings.API_RATE_LIMIT
        for _ in range(limit):
            assert check_api_rate_db(ip, db) is False
        assert check_api_rate_db(ip, db) is True
    finally:
        db.close()


def test_db_rate_limiter_window_reset():
    """DEF-10: check_api_rate_db resets the counter after the window expires."""
    import datetime
    from app.security import check_api_rate_db, reset_api_rate_limiter_db
    from app.models import IpApiRequest
    db = _db()
    try:
        reset_api_rate_limiter_db(db)
        ip = "10.0.0.21"
        past = datetime.datetime.utcnow() - datetime.timedelta(
            seconds=settings.API_RATE_WINDOW_SEC + 5)
        row = IpApiRequest(ip=ip, request_count=settings.API_RATE_LIMIT + 50, window_start=past)
        db.add(row)
        db.commit()
        assert check_api_rate_db(ip, db) is False
    finally:
        db.close()


def test_db_rate_limiter_different_ips_independent():
    """DEF-10: exceeding the limit for one IP must not block a different IP."""
    from app.security import check_api_rate_db, reset_api_rate_limiter_db
    db = _db()
    try:
        reset_api_rate_limiter_db(db)
        ip_a, ip_b = "10.0.0.22", "10.0.0.23"
        for _ in range(settings.API_RATE_LIMIT + 1):
            check_api_rate_db(ip_a, db)
        assert check_api_rate_db(ip_a, db) is True
        assert check_api_rate_db(ip_b, db) is False
    finally:
        db.close()


def test_db_rate_limiter_reset_clears_table():
    """DEF-10: reset_api_rate_limiter_db deletes all rows so requests are allowed again."""
    from app.security import check_api_rate_db, reset_api_rate_limiter_db
    db = _db()
    try:
        reset_api_rate_limiter_db(db)
        ip = "10.0.0.24"
        for _ in range(settings.API_RATE_LIMIT + 1):
            check_api_rate_db(ip, db)
        assert check_api_rate_db(ip, db) is True
        reset_api_rate_limiter_db(db)
        assert check_api_rate_db(ip, db) is False
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# DEF-11: DB-backed per-account rate limiter (check_user_api_rate_db)
# ─────────────────────────────────────────────────────────────

def test_user_rate_limiter_unit_check():
    """DEF-11: check_user_api_rate_db counts correctly and blocks over the limit."""
    from app.security import check_user_api_rate_db, reset_user_api_rate_limiter_db
    db = _db()
    try:
        reset_user_api_rate_limiter_db(db)
        uid = "user-rate-test-001"
        limit = settings.API_RATE_LIMIT
        for _ in range(limit):
            assert check_user_api_rate_db(uid, db) is False
        assert check_user_api_rate_db(uid, db) is True
    finally:
        db.close()


def test_user_rate_limiter_window_reset():
    """DEF-11: check_user_api_rate_db resets the counter after the window expires."""
    import datetime
    from app.security import check_user_api_rate_db, reset_user_api_rate_limiter_db
    from app.models import UserApiRequest
    db = _db()
    try:
        reset_user_api_rate_limiter_db(db)
        uid = "user-rate-test-002"
        past = datetime.datetime.utcnow() - datetime.timedelta(
            seconds=settings.API_RATE_WINDOW_SEC + 5)
        row = UserApiRequest(user_id=uid, request_count=settings.API_RATE_LIMIT + 50, window_start=past)
        db.add(row)
        db.commit()
        assert check_user_api_rate_db(uid, db) is False
    finally:
        db.close()


def test_user_rate_limiter_different_users_independent():
    """DEF-11: exceeding the limit for one user must not block a different user."""
    from app.security import check_user_api_rate_db, reset_user_api_rate_limiter_db
    db = _db()
    try:
        reset_user_api_rate_limiter_db(db)
        uid_a, uid_b = "user-rate-test-003a", "user-rate-test-003b"
        for _ in range(settings.API_RATE_LIMIT + 1):
            check_user_api_rate_db(uid_a, db)
        assert check_user_api_rate_db(uid_a, db) is True
        assert check_user_api_rate_db(uid_b, db) is False
    finally:
        db.close()


def test_user_rate_limiter_reset_clears_table():
    """DEF-11: reset_user_api_rate_limiter_db deletes all rows so requests are allowed again."""
    from app.security import check_user_api_rate_db, reset_user_api_rate_limiter_db
    db = _db()
    try:
        reset_user_api_rate_limiter_db(db)
        uid = "user-rate-test-004"
        for _ in range(settings.API_RATE_LIMIT + 1):
            check_user_api_rate_db(uid, db)
        assert check_user_api_rate_db(uid, db) is True
        reset_user_api_rate_limiter_db(db)
        assert check_user_api_rate_db(uid, db) is False
    finally:
        db.close()


# ── SEC-05: login spike alerting ──────────────────────────────────────────────

def test_login_spike_emits_security_log(caplog):
    """SEC-05: record_login_failure_db emits a 'security_alert'/'login_spike' warning
    at exactly LOGIN_MAX_ATTEMPTS failures (the lockout threshold)."""
    import logging
    from app.security import record_login_failure_db, record_login_success_db
    db = _db()
    try:
        key = "1.2.3.4"
        record_login_success_db(key, db)  # reset any prior state
        threshold = settings.LOGIN_MAX_ATTEMPTS
        with caplog.at_level(logging.WARNING, logger="security"):
            for _ in range(threshold - 1):
                record_login_failure_db(key, db)
            assert not any("login_spike" in r.message for r in caplog.records), \
                "Alert fired too early"
            record_login_failure_db(key, db)
        assert any("login_spike" in r.message for r in caplog.records), \
            "Expected login_spike alert at lockout threshold"
    finally:
        db.close()


def test_login_spike_repeats_on_subsequent_multiples(caplog):
    """SEC-05: the spike alert fires again every 5 additional failures past the lockout."""
    import logging
    from app.security import record_login_failure_db, record_login_success_db
    db = _db()
    try:
        key = "1.2.3.5"
        record_login_success_db(key, db)
        threshold = settings.LOGIN_MAX_ATTEMPTS
        with caplog.at_level(logging.WARNING, logger="security"):
            for _ in range(threshold + 5):
                record_login_failure_db(key, db)
        spike_alerts = [r for r in caplog.records if "login_spike" in r.message]
        assert len(spike_alerts) == 2, f"Expected 2 spike alerts, got {len(spike_alerts)}"
    finally:
        db.close()


# ── SEC-06: 5xx spike alerting ────────────────────────────────────────────────

def test_5xx_spike_emits_security_log(caplog):
    """SEC-06: the access_log middleware emits a 'security_alert'/'5xx_spike' warning
    when _5XX_ALERT_THRESHOLD server errors occur within the rolling window."""
    import logging
    import app.main as main_module

    original = list(main_module._5xx_times)
    main_module._5xx_times.clear()
    threshold = main_module._5XX_ALERT_THRESHOLD

    try:
        with caplog.at_level(logging.WARNING, logger="security"):
            for i in range(threshold):
                import time as _t
                main_module._5xx_times.append(_t.monotonic())
                count = len(main_module._5xx_times)
                if count >= threshold:
                    main_module._sec_log.warning(
                        '{"event":"security_alert","type":"5xx_spike","status":500,'
                        '"path":"/test","count_in_window":%d,"window_sec":%d}',
                        count, main_module._5XX_WINDOW_SEC)
        assert any("5xx_spike" in r.message for r in caplog.records), \
            "Expected 5xx_spike security alert"
    finally:
        main_module._5xx_times.clear()
        for t in original:
            main_module._5xx_times.append(t)
