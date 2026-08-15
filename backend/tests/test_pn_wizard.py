"""Tests for PN-WIZ-01 guided session builder — exercises POST /api/sessions
with all fields the wizard collects: period, curriculum, facilitator, room."""
import pytest
from tests.conftest import login


def _hdr(client):
    return login(client, "ADMIN703")


def _pnid(client, hdr, date="2038-01-09", term="T1"):
    r = client.post("/api/parade-nights", json={"date": date, "term": term}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["parade_night_id"]


def _fac_id(client, hdr, name="WizFac"):
    r = client.post(
        "/api/facilitators",
        json={"last_name": name, "first_name": "W", "type": "Staff",
              "current_rank": "SGT", "active_status": True, "subject_areas": []},
        headers=hdr,
    )
    assert r.status_code == 200, r.text
    return r.json()["facilitator_id"]


def _room_id(client, hdr, name="Wizard Room A"):
    r = client.post(
        "/api/training-areas",
        json={"name": name, "type": "Classroom", "capacity": 20},
        headers=hdr,
    )
    assert r.status_code == 200, r.text
    return r.json()["training_area_id"]


def _curr_id(client, hdr):
    r = client.get("/api/curriculum", headers=hdr)
    assert r.status_code == 200, r.text
    items = r.json().get("items", [])
    return items[0]["curriculum_id"] if items else None


# ── Happy path ────────────────────────────────────────────────────────────────

def test_wizard_minimal_session_creates_ok(client):
    """Wizard minimum: just a parade night + period (no curriculum, fac, room)."""
    hdr = _hdr(client)
    pnid = _pnid(client, hdr, "2038-01-09")
    r = client.post(
        "/api/sessions",
        json={"parade_night_id": pnid, "period_number": 1},
        headers=hdr,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert "id" in d or "session_id" in d


def test_wizard_full_fields_creates_ok(client):
    """Wizard with all fields: period, curriculum, facilitator, training area."""
    hdr = _hdr(client)
    pnid = _pnid(client, hdr, "2038-01-16")
    fac = _fac_id(client, hdr, "WizFacFull")
    room = _room_id(client, hdr, "Wizard Room Full")
    curr = _curr_id(client, hdr)
    body = {
        "parade_night_id": pnid,
        "period_number": 2,
        "curriculum_item_id": curr,
        "facilitator_id": fac,
        "training_area_id": room,
    }
    r = client.post("/api/sessions", json=body, headers=hdr)
    assert r.status_code == 200, r.text
    sid = r.json().get("id") or r.json().get("session_id")
    assert sid


def test_wizard_custom_title_without_curriculum(client):
    """Wizard 'custom title' path — curriculum_item_id=null, custom_title set."""
    hdr = _hdr(client)
    pnid = _pnid(client, hdr, "2038-01-23")
    r = client.post(
        "/api/sessions",
        json={"parade_night_id": pnid, "period_number": 1,
              "curriculum_item_id": None, "custom_title": "Special Skills Night"},
        headers=hdr,
    )
    assert r.status_code == 200, r.text


def test_wizard_audience_assignment_after_create(client):
    """After creating the session the wizard POSTs audience via PUT .../audience."""
    hdr = _hdr(client)
    pnid = _pnid(client, hdr, "2038-02-06")
    r = client.post(
        "/api/sessions",
        json={"parade_night_id": pnid, "period_number": 1},
        headers=hdr,
    )
    assert r.status_code == 200, r.text
    sid = r.json().get("id") or r.json().get("session_id")
    # Audience update with empty class_ids (safe no-op)
    aud = client.put(f"/api/sessions/{sid}/audience",
                     json={"training_class_ids": []}, headers=hdr)
    assert aud.status_code == 200, aud.text


def test_wizard_different_periods_same_night(client):
    """Wizard can add sessions to multiple periods on the same night."""
    hdr = _hdr(client)
    pnid = _pnid(client, hdr, "2038-02-13")
    for p in (1, 2, 3):
        r = client.post(
            "/api/sessions",
            json={"parade_night_id": pnid, "period_number": p},
            headers=hdr,
        )
        assert r.status_code == 200, r.text


def test_wizard_unauthenticated_returns_401(client):
    r = client.post(
        "/api/sessions",
        json={"parade_night_id": "00000000-0000-0000-0000-000000000001", "period_number": 1},
    )
    assert r.status_code == 401


def test_wizard_missing_parade_night_returns_error(client):
    hdr = _hdr(client)
    r = client.post(
        "/api/sessions",
        json={"parade_night_id": "00000000-0000-0000-0000-000000000000", "period_number": 1},
        headers=hdr,
    )
    assert r.status_code in (400, 404, 422)
