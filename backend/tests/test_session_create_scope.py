"""Regression: POST /api/sessions (training.py) scope validation on CREATE.

The CREATE path previously called _denormalise() without validating that the
supplied curriculum_item_id, facilitator_id, and training_area_id belong to
the caller's squadron — allowing a cross-tenant reference to be stored.  The
EDIT path (PUT /api/sessions/{sid}) already had the three scope checks; this
file proves the CREATE path now matches.

Coverage mirrors test_session_reference_tenancy.py which targets the Planning
Workspace endpoint (/api/planning/...) — that endpoint was already safe.
"""
from tests.conftest import login, next_test_year


def _pn(client, hdr, date):
    r = client.post("/api/parade-nights", json={"date": date, "term": "T1"}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["parade_night_id"]


def _create(client, hdr, pn_id, **extra):
    body = {"parade_night_id": pn_id, "period_number": 1, "cadet_group": "senior"}
    body.update(extra)
    return client.post("/api/sessions", json=body, headers=hdr)


def _read(client, hdr, sid):
    r = client.get(f"/api/planning/sessions/{sid}", headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


# ─── facilitator ──────────────────────────────────────────────────────────────

def test_create_rejects_cross_squadron_facilitator(client):
    a703, a705 = login(client, "ADMIN703"), login(client, "ADMIN705")
    fac = client.post("/api/facilitators",
                      json={"last_name": "Scope705Fac", "current_rank": "CIV"},
                      headers=a705)
    assert fac.status_code == 200, fac.text
    fid = fac.json()["facilitator_id"]

    pn = _pn(client, a703, "2042-03-05")
    r = _create(client, a703, pn, facilitator_id=fid)
    # Must either reject outright or accept without storing the foreign reference
    assert r.status_code in (200, 400, 403, 422), r.text
    if r.status_code not in (200,):
        return
    sid = r.json().get("session_id") or r.json().get("id")
    row = _read(client, a703, sid)
    assert row.get("facilitator_id") != fid, \
        "CREATE stored 705's facilitator on 703's session"
    assert "Scope705Fac" not in (row.get("facilitator_name") or ""), \
        "705's facilitator name was denormalised onto 703's session via CREATE"


def test_create_accepts_own_squadron_facilitator(client):
    hdr = login(client, "ADMIN703")
    fac = client.post("/api/facilitators",
                      json={"last_name": "Own703Fac", "current_rank": "CIV"},
                      headers=hdr)
    assert fac.status_code == 200, fac.text
    fid = fac.json()["facilitator_id"]

    pn = _pn(client, hdr, "2042-03-12")
    r = _create(client, hdr, pn, facilitator_id=fid)
    assert r.status_code == 200, r.text
    sid = r.json().get("session_id") or r.json().get("id")
    row = _read(client, hdr, sid)
    assert row.get("facilitator_id") == fid, \
        "CREATE rejected a same-squadron facilitator"


# ─── training area ────────────────────────────────────────────────────────────

def test_create_rejects_cross_squadron_training_area(client):
    a703, a705 = login(client, "ADMIN703"), login(client, "ADMIN705")
    room = client.post("/api/training-areas",
                       json={"name": "Scope705Room"},
                       headers=a705)
    assert room.status_code == 200, room.text
    taid = room.json()["training_area_id"]

    pn = _pn(client, a703, "2042-03-19")
    r = _create(client, a703, pn, training_area_id=taid)
    assert r.status_code in (200, 400, 403, 422), r.text
    if r.status_code not in (200,):
        return
    sid = r.json().get("session_id") or r.json().get("id")
    row = _read(client, a703, sid)
    assert row.get("location_id") != taid, \
        "CREATE stored 705's training area on 703's session"
    assert "Scope705Room" not in (row.get("location_name") or ""), \
        "705's room name was denormalised onto 703's session via CREATE"


def test_create_accepts_own_squadron_training_area(client):
    hdr = login(client, "ADMIN703")
    room = client.post("/api/training-areas",
                       json={"name": "Own703Room"},
                       headers=hdr)
    assert room.status_code == 200, room.text
    taid = room.json()["training_area_id"]

    pn = _pn(client, hdr, "2042-03-26")
    r = _create(client, hdr, pn, training_area_id=taid)
    assert r.status_code == 200, r.text
    sid = r.json().get("session_id") or r.json().get("id")
    row = _read(client, hdr, sid)
    assert row.get("location_id") == taid, \
        "CREATE rejected a same-squadron training area"


# ─── curriculum item ──────────────────────────────────────────────────────────

def test_create_rejects_cross_squadron_curriculum_item(client):
    """A squadron-owned curriculum item of another squadron must be invisible."""
    a703, a705 = login(client, "ADMIN703"), login(client, "ADMIN705")
    item = client.post("/api/curriculum", json={
        "code": "SCP705-C1", "title": "705 Scope Local", "phase": "E. Senior",
        "element": "Service", "owning_level": "squadron", "duration_minutes": 60,
    }, headers=a705)
    if item.status_code not in (200, 201):
        import pytest; pytest.skip(f"could not create squadron-owned item: {item.text}")
    cid = item.json().get("curriculum_id") or item.json().get("curriculum_item_id")

    pn = _pn(client, a703, "2042-04-02")
    r = _create(client, a703, pn, curriculum_item_id=cid)
    assert r.status_code in (200, 400, 403, 422), r.text
    if r.status_code not in (200,):
        return
    sid = r.json().get("session_id") or r.json().get("id")
    row = _read(client, a703, sid)
    assert row.get("curriculum_id") != cid, \
        "CREATE stored 705's squadron-owned curriculum item on 703's session"
    assert "705 Scope Local" not in (row.get("curriculum_title") or ""), \
        "705's curriculum title was denormalised onto 703's session via CREATE"


def test_create_accepts_national_curriculum_item(client):
    """National items are intentionally visible to every squadron — must not be blocked."""
    hdr = login(client, "ADMIN703")
    items = client.get("/api/curriculum", headers=hdr)
    assert items.status_code == 200, items.text
    payload = items.json()
    candidates = payload["items"] if isinstance(payload, dict) else payload
    national = next((i for i in candidates
                     if (i.get("owning_level") or "national") == "national"), None)
    if national is None:
        import pytest; pytest.skip("no national curriculum item in seed data")
    cid = national.get("curriculum_id") or national.get("curriculum_item_id")

    pn = _pn(client, hdr, "2042-04-09")
    r = _create(client, hdr, pn, curriculum_item_id=cid)
    assert r.status_code == 200, r.text
    sid = r.json().get("session_id") or r.json().get("id")
    row = _read(client, hdr, sid)
    assert row.get("curriculum_id") == cid, \
        "CREATE rejected a national curriculum item — inheritance is broken"
