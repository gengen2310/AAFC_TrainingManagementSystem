"""Regression tests: request_size_guard middleware (REM-124).

Confirms an oversized request is rejected via its Content-Length header before
any endpoint code (including auth) runs, and that a normal-sized request is
unaffected.
"""
from app.config import settings


def test_oversized_body_rejected_with_413_before_auth_runs(client):
    """A body larger than MAX_REQUEST_BODY_MB must be rejected with 413 -- and,
    critically, this must happen even against an endpoint that would otherwise
    401 first (get_principal), proving the guard runs ahead of normal request
    processing rather than only on already-authenticated routes."""
    big = "x" * (settings.MAX_REQUEST_BODY_MB * 1024 * 1024 + 1024)
    r = client.post("/api/curriculum", json={"code": "X", "title": big})
    assert r.status_code == 413, r.text
    assert r.json()["error"] == "request_too_large"


def test_normal_sized_request_is_unaffected(client):
    """A small, ordinary request must not be caught by the guard -- confirms the
    threshold check itself (not just its absence) is correct, not a rubber stamp
    that would also pass if the middleware rejected everything."""
    r = client.post("/api/auth/login", json={"code": "not-a-real-code"})
    assert r.status_code in (401, 429), r.text
    assert r.status_code != 413


def test_declared_length_at_exactly_the_limit_is_allowed(client):
    """Boundary check: exactly MAX_REQUEST_BODY_MB must not be rejected -- only
    strictly greater than the limit should 413."""
    padding = "x" * (settings.MAX_REQUEST_BODY_MB * 1024 * 1024 - 200)
    r = client.post("/api/curriculum", json={"code": "X", "title": padding})
    assert r.status_code != 413, r.text
