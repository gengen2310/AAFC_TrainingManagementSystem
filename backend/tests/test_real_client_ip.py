"""Regression tests: real_client_ip (REM-125, hardened after a background security review).

This app is only ever reachable through Railway's edge, which terminates TLS and
forwards over plain HTTP -- so request.client.host was always Railway's own
internal proxy address, identical for every real end user. Every per-IP control
(login lockout, API rate limiter, access log) keyed off that raw peer therefore
shared ONE bucket across the entire user base: confirmed live via the staging
access log, every request logged the same "client":"100.64.0.2" regardless of
the real caller. In practice this meant 5 failed login attempts by anyone,
anywhere, within a 5-minute window locked out login for every user of the
deployed app for 15 minutes.

The first version of this fix trusted X-Forwarded-For unconditionally, which a
background security review correctly flagged: (1) nothing verified the request
actually came through a trusted proxy hop, and (2) the extracted value fed
unescaped into main.py's hand-built access-log line, an injection path. Both are
covered below.
"""
from fastapi.testclient import TestClient

from app.dependencies import real_client_ip
from app.main import app
from conftest import login


class _FakeClient:
    def __init__(self, host):
        self.host = host


class _FakeRequest:
    def __init__(self, headers, client_host="testclient"):
        self.headers = headers
        self.client = _FakeClient(client_host) if client_host else None


def test_prefers_leftmost_x_forwarded_for_entry_when_peer_is_trusted():
    """The raw peer is Railway's own edge address (CGNAT range) here -- exactly
    the condition under which the header must be trusted."""
    req = _FakeRequest({"X-Forwarded-For": "203.0.113.7, 100.64.0.2"}, client_host="100.64.0.2")
    assert real_client_ip(req) == "203.0.113.7"


def test_ignores_x_forwarded_for_when_peer_is_not_a_trusted_proxy():
    """Security-review hardening #1: a request whose raw peer does NOT look like
    Railway's own infrastructure must not have its X-Forwarded-For trusted at
    all -- otherwise anything that can reach this process directly could inject
    an arbitrary IP and bypass every per-IP control."""
    req = _FakeRequest({"X-Forwarded-For": "203.0.113.7"}, client_host="8.8.8.8")
    assert real_client_ip(req) == "8.8.8.8"


def test_rejects_non_ip_forwarded_value_even_from_a_trusted_peer():
    """Security-review hardening #2: a non-IP value must never be returned, even
    from a trusted-range peer -- this is what closed the log-injection path
    (the value feeds unescaped into main.py's access-log line)."""
    req = _FakeRequest({"X-Forwarded-For": '1.2.3.4", "injected":"true'}, client_host="100.64.0.2")
    assert real_client_ip(req) == "100.64.0.2"
    assert '"' not in real_client_ip(req)


def test_falls_back_to_raw_peer_when_header_absent():
    """Local dev / tests / any environment with no proxy in front must be
    completely unaffected -- this is the fallback every existing test
    (e.g. test_rate_limiting.py's "testclient" assumption) depends on."""
    req = _FakeRequest({}, client_host="testclient")
    assert real_client_ip(req) == "testclient"


def test_falls_back_when_header_present_but_empty():
    req = _FakeRequest({"X-Forwarded-For": ""}, client_host="100.64.0.2")
    assert real_client_ip(req) == "100.64.0.2"


def test_default_test_client_peer_is_not_in_the_trusted_cgnat_range():
    """Sanity check underpinning every other test in this suite that uses the
    plain `client` fixture: TestClient's default reported peer ("testclient")
    must NOT be trusted-proxy-shaped, or the untrusted-peer test above would be
    asserting nothing."""
    req = _FakeRequest({"X-Forwarded-For": "203.0.113.7"}, client_host="testclient")
    assert real_client_ip(req) == "testclient"


def test_two_different_forwarded_ips_get_independent_login_lockout_buckets(client):
    """End-to-end proof: from a peer that looks like Railway's own edge (CGNAT
    range), two different X-Forwarded-For values must not share a login-lockout
    bucket. Uses a dedicated TestClient with client=(...) set to a trusted-range
    address, since the default `client` fixture's peer ("testclient") is
    deliberately NOT trusted (see the sanity check above) and would make this
    test assert nothing -- but still depends on the `client` fixture parameter
    for its per-test DB/rate-limiter cleanup side effect."""
    from app.config import settings

    trusted_client = TestClient(app, client=("100.64.0.9", 12345))

    for _ in range(settings.LOGIN_MAX_ATTEMPTS):
        trusted_client.post("/api/auth/login", json={"code": "WRONGCODE"},
                            headers={"X-Forwarded-For": "203.0.113.10"})
    r = trusted_client.post("/api/auth/login", json={"code": "WRONGCODE"},
                            headers={"X-Forwarded-For": "203.0.113.10"})
    assert r.status_code == 429, "the attacking IP should now be locked out"

    r = trusted_client.post("/api/auth/login", json={"code": "703SQN2026"},
                            headers={"X-Forwarded-For": "203.0.113.99"})
    assert r.status_code == 200, (
        "a different X-Forwarded-For IP must not be collaterally locked out "
        f"by another IP's failed attempts: {r.text}"
    )
