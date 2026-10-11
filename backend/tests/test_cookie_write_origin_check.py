"""D13 (2026-10-11): cross-site request forgery through the session cookie.

Login sets `aafc_session` with SameSite=None (load-bearing: the Planning
Workspace handoff opens a fresh cross-origin tab that has only the cookie).
`dependencies._token_from_request` falls back to that cookie when there is no
Bearer header, and nothing checked where a state-changing request came from.
So any web page could make a signed-in administrator's browser send, e.g., a
body-less `POST /api/accounts/{uid}/disable` (an auto-submitting form needs no
CORS permission) and the server would act on it.

Rule now: a POST/PUT/PATCH/DELETE authenticated only by the cookie must carry
an Origin (or, failing that, Referer) that is one of the configured CORS
origins. Bearer-authenticated requests are unaffected: a cross-site page cannot
attach an Authorization header without a CORS preflight the server refuses.
"""
from fastapi.testclient import TestClient

from app.config import settings
from app.database import SessionLocal
from app.main import app
from app.models import User
from tests.conftest import login

ALLOWED = settings.cors_origins[0]


def _cookie_client():
    """A fresh client holding only the session cookie of a System Admin."""
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"code": "SYSADMIN2026"})
    assert r.status_code == 200, r.text
    assert c.cookies.get(settings.COOKIE_NAME)
    return c


def _target_id(client):
    h = login(client, "SYSADMIN2026")
    accts = client.get("/api/accounts", headers=h, params={"role": "sqn_general"}).json()
    return accts[0]["user_id"], h


def _active(uid):
    db = SessionLocal()
    try:
        return db.get(User, uid).active_status
    finally:
        db.close()


def test_cross_site_cookie_write_is_refused_and_changes_nothing(client):
    uid, h = _target_id(client)
    c = _cookie_client()
    try:
        r = c.post(f"/api/accounts/{uid}/disable", headers={"Origin": "https://evil.example"})
        assert r.status_code == 403, r.text
        assert r.json()["detail"]["error"] == "origin_not_allowed"
        assert _active(uid) is True
    finally:
        client.post(f"/api/accounts/{uid}/reactivate", headers=h)


def test_cookie_write_without_any_origin_is_refused(client):
    uid, h = _target_id(client)
    c = _cookie_client()
    try:
        r = c.post(f"/api/accounts/{uid}/disable")
        assert r.status_code == 403, r.text
        assert _active(uid) is True
    finally:
        client.post(f"/api/accounts/{uid}/reactivate", headers=h)


def test_cookie_write_from_an_allowed_origin_still_works(client):
    uid, h = _target_id(client)
    c = _cookie_client()
    try:
        r = c.post(f"/api/accounts/{uid}/disable", headers={"Origin": ALLOWED})
        assert r.status_code == 200, r.text
        assert _active(uid) is False
    finally:
        client.post(f"/api/accounts/{uid}/reactivate", headers=h)


def test_referer_is_the_fallback_when_origin_is_absent(client):
    uid, h = _target_id(client)
    c = _cookie_client()
    try:
        r = c.post(f"/api/accounts/{uid}/disable", headers={"Referer": ALLOWED + "/index.html"})
        assert r.status_code == 200, r.text
    finally:
        client.post(f"/api/accounts/{uid}/reactivate", headers=h)


def test_bearer_requests_are_unaffected_by_origin(client):
    uid, h = _target_id(client)
    try:
        r = client.post(f"/api/accounts/{uid}/disable", headers={**h, "Origin": "https://evil.example"})
        assert r.status_code == 200, r.text
    finally:
        client.post(f"/api/accounts/{uid}/reactivate", headers=h)


def test_cookie_reads_are_unaffected(client):
    c = _cookie_client()
    r = c.get("/api/auth/me", headers={"Origin": "https://evil.example"})
    assert r.status_code == 200, r.text


def test_routes_without_a_principal_ignore_a_stale_cookie():
    """Login and public ticket submission never use the cookie as a credential."""
    c = _cookie_client()
    assert c.post("/api/auth/login", json={"code": "SYSADMIN2026"}).status_code == 200


def test_authenticated_auth_routes_stay_guarded():
    c = _cookie_client()
    r = c.post("/api/auth/refresh", headers={"Origin": "https://evil.example"})
    assert r.status_code == 403, r.text


def test_public_ticket_submission_ignores_a_stale_cookie():
    c = _cookie_client()
    db = SessionLocal()
    try:
        from app.models import Squadron
        sqn = db.query(Squadron).filter(Squadron.code == "703").first()
    finally:
        db.close()
    r = c.post("/api/service-desk/tickets", json={
        "rank": "Cdt", "first_name": "Stale", "last_name": "Cookie", "email": "stale@example.org",
        "squadron_id": sqn.id, "category": "other", "description": "D13 public submission check."})
    assert r.status_code == 201, r.text
