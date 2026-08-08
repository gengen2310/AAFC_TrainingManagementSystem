"""Regression tests: real_client_ip (REM-125).

This app is only ever reachable through Railway's edge, which terminates TLS and
forwards over plain HTTP -- so request.client.host was always Railway's own
internal proxy address, identical for every real end user. Every per-IP control
(login lockout, API rate limiter, access log) keyed off that raw peer therefore
shared ONE bucket across the entire user base: confirmed live via the staging
access log, every request logged the same "client":"100.64.0.2" regardless of
the real caller. In practice this meant 5 failed login attempts by anyone,
anywhere, within a 5-minute window locked out login for every user of the
deployed app for 15 minutes.
"""
from app.dependencies import real_client_ip
from conftest import login


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    def __init__(self, headers, client_host="testclient"):
        self.headers = headers
        self.client = _FakeClient(client_host) if client_host else None


def test_prefers_leftmost_x_forwarded_for_entry_over_raw_peer():
    """The raw peer (Railway's own edge address in production) must never win
    over a forwarded header -- that's the exact bug this closes."""
    req = _FakeRequest({"X-Forwarded-For": "203.0.113.7, 100.64.0.2"}, client_host="100.64.0.2")
    assert real_client_ip(req) == "203.0.113.7"


def test_falls_back_to_raw_peer_when_header_absent():
    """Local dev / tests / any environment with no proxy in front must be
    completely unaffected -- this is the fallback every existing test
    (e.g. test_rate_limiting.py's "testclient" assumption) depends on."""
    req = _FakeRequest({}, client_host="testclient")
    assert real_client_ip(req) == "testclient"


def test_falls_back_when_header_present_but_empty():
    req = _FakeRequest({"X-Forwarded-For": ""}, client_host="testclient")
    assert real_client_ip(req) == "testclient"


def test_two_different_forwarded_ips_get_independent_login_lockout_buckets(client):
    """End-to-end proof, not just a unit test of the helper: two different
    X-Forwarded-For values must not share a login-lockout bucket. Before this
    fix, both would collapse onto the TestClient's single raw peer and the
    first IP's failures would lock out the second IP too."""
    from app.config import settings

    for _ in range(settings.LOGIN_MAX_ATTEMPTS):
        r = client.post("/api/auth/login", json={"code": "WRONGCODE"},
                        headers={"X-Forwarded-For": "203.0.113.10"})
    r = client.post("/api/auth/login", json={"code": "WRONGCODE"},
                    headers={"X-Forwarded-For": "203.0.113.10"})
    assert r.status_code == 429, "the attacking IP should now be locked out"

    r = client.post("/api/auth/login", json={"code": "703SQN2026"},
                    headers={"X-Forwarded-For": "203.0.113.99"})
    assert r.status_code == 200, (
        "a different X-Forwarded-For IP must not be collaterally locked out "
        f"by another IP's failed attempts: {r.text}"
    )
