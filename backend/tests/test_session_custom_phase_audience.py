"""Tests for POST/DELETE /api/planning/sessions/{id}/custom-phase-audiences.

Verifies that:
- sqn_admin can link and unlink a custom phase to/from a session
- sqn_general (read-only) cannot mutate links
- Linking a non-existent or out-of-scope phase returns 404
- Duplicate link returns 409
- Deleting a link that does not exist returns 404
- custom_phase_audiences appears in GET /sessions/{id} response
"""
from datetime import date, timedelta

from tests.conftest import login, next_test_year


def _admin_hdr(client):
    return login(client, "ADMIN703")


def _general_hdr(client):
    return login(client, "703SQN2026")


def _make_parade_night(client, hdr, days_ahead=0):
    """Create a parade night for 703's squadron, avoiding Fridays."""
    base = date(2041, 3, 1) + timedelta(days=days_ahead)
    if base.weekday() == 4:
        base += timedelta(days=1)
    target = base.isoformat()
    r = client.get("/api/auth/me", headers=hdr)
    info = r.json()["session"]
    pn = client.post("/api/parade-nights", json={
        "squadron_id": info["squadron_id"],
        "wing_id": info["wing_id"],
        "date": target,
        "parade_type": "normal",
    }, headers=hdr)
    assert pn.status_code in (200, 201), pn.text
    return pn.json().get("parade_night_id") or pn.json().get("id")


def _make_session(client, hdr, days_ahead=0):
    pn_id = _make_parade_night(client, hdr, days_ahead=days_ahead)
    sess = client.post("/api/sessions", json={
        "parade_night_id": pn_id, "period_number": 1, "cadet_group": "senior",
    }, headers=hdr)
    assert sess.status_code in (200, 201), sess.text
    return sess.json()["session_id"]


def _make_phase(client, hdr, name="Test Phase"):
    r = client.post("/api/custom-training-phases", json={
        "name": name, "scope_type": "squadron", "applies_from": "2041-01-01",
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["custom_phase_id"]


# ── Happy path ────────────────────────────────────────────────

def test_add_custom_phase_audience_happy_path(client):
    hdr = _admin_hdr(client)
    sid = _make_session(client, hdr, days_ahead=10)
    phase_id = _make_phase(client, hdr, "Wing Band A")

    r = client.post(f"/api/planning/sessions/{sid}/custom-phase-audiences",
                    json={"custom_phase_id": phase_id}, headers=hdr)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "custom_phase_audiences" in data
    linked = [a["custom_phase_id"] for a in data["custom_phase_audiences"]]
    assert phase_id in linked


def test_remove_custom_phase_audience_happy_path(client):
    hdr = _admin_hdr(client)
    sid = _make_session(client, hdr, days_ahead=20)
    phase_id = _make_phase(client, hdr, "Wing Band B")

    add = client.post(f"/api/planning/sessions/{sid}/custom-phase-audiences",
                      json={"custom_phase_id": phase_id}, headers=hdr)
    assert add.status_code == 200, add.text

    rm = client.delete(f"/api/planning/sessions/{sid}/custom-phase-audiences/{phase_id}",
                       headers=hdr)
    assert rm.status_code == 200, rm.text
    assert rm.json() == {"ok": True}

    get = client.get(f"/api/planning/sessions/{sid}", headers=hdr)
    assert get.status_code == 200
    linked = [a["custom_phase_id"] for a in get.json().get("custom_phase_audiences", [])]
    assert phase_id not in linked


def test_custom_phase_audiences_in_get_session(client):
    """GET /sessions/{id} includes the custom_phase_audiences list."""
    hdr = _admin_hdr(client)
    sid = _make_session(client, hdr, days_ahead=30)
    phase_id = _make_phase(client, hdr, "Biathlon Team C")

    client.post(f"/api/planning/sessions/{sid}/custom-phase-audiences",
                json={"custom_phase_id": phase_id}, headers=hdr)

    r = client.get(f"/api/planning/sessions/{sid}", headers=hdr)
    assert r.status_code == 200
    audiences = r.json().get("custom_phase_audiences", [])
    assert any(a["custom_phase_id"] == phase_id for a in audiences)


# ── Duplicate / not found ──────────────────────────────────────

def test_duplicate_link_returns_409(client):
    hdr = _admin_hdr(client)
    sid = _make_session(client, hdr, days_ahead=40)
    phase_id = _make_phase(client, hdr, "Wing Band D")

    r1 = client.post(f"/api/planning/sessions/{sid}/custom-phase-audiences",
                     json={"custom_phase_id": phase_id}, headers=hdr)
    assert r1.status_code == 200

    r2 = client.post(f"/api/planning/sessions/{sid}/custom-phase-audiences",
                     json={"custom_phase_id": phase_id}, headers=hdr)
    assert r2.status_code == 409
    assert r2.json()["detail"]["error"] == "already_linked"


def test_link_nonexistent_phase_returns_404(client):
    hdr = _admin_hdr(client)
    sid = _make_session(client, hdr, days_ahead=50)

    r = client.post(f"/api/planning/sessions/{sid}/custom-phase-audiences",
                    json={"custom_phase_id": "00000000-0000-0000-0000-000000000000"}, headers=hdr)
    assert r.status_code == 404


def test_delete_nonexistent_link_returns_404(client):
    hdr = _admin_hdr(client)
    sid = _make_session(client, hdr, days_ahead=60)

    r = client.delete(f"/api/planning/sessions/{sid}/custom-phase-audiences/00000000-0000-0000-0000-000000000000",
                      headers=hdr)
    assert r.status_code == 404


# ── RBAC ──────────────────────────────────────────────────────

def test_sqn_general_cannot_add_phase_audience(client):
    hdr_admin = _admin_hdr(client)
    hdr_gen = _general_hdr(client)
    sid = _make_session(client, hdr_admin, days_ahead=70)
    phase_id = _make_phase(client, hdr_admin, "Wing Band E")

    r = client.post(f"/api/planning/sessions/{sid}/custom-phase-audiences",
                    json={"custom_phase_id": phase_id}, headers=hdr_gen)
    assert r.status_code == 403


def test_sqn_general_cannot_remove_phase_audience(client):
    hdr_admin = _admin_hdr(client)
    hdr_gen = _general_hdr(client)
    sid = _make_session(client, hdr_admin, days_ahead=80)
    phase_id = _make_phase(client, hdr_admin, "Wing Band F")

    client.post(f"/api/planning/sessions/{sid}/custom-phase-audiences",
                json={"custom_phase_id": phase_id}, headers=hdr_admin)

    r = client.delete(f"/api/planning/sessions/{sid}/custom-phase-audiences/{phase_id}",
                      headers=hdr_gen)
    assert r.status_code == 403


def test_unauthenticated_add_returns_401(client):
    r = client.post("/api/planning/sessions/fake-id/custom-phase-audiences",
                    json={"custom_phase_id": "fake"})
    assert r.status_code == 401


def test_unauthenticated_delete_returns_401(client):
    r = client.delete("/api/planning/sessions/fake-id/custom-phase-audiences/fake-phase")
    assert r.status_code == 401
