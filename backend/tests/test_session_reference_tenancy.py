"""Cross-squadron tenancy on the ids a Session denormalises.

create_session, edit_session and assign_mission resolve caller-supplied
curriculum_id, facilitator_id and location/training_area_id with a bare
db.get(Model, id) and copy the resulting names onto the session. None of them
compared the row's squadron to the session's, so 703 could reference 705's
facilitator or room and have 705's names written into 703's record -- a
cross-tenant read surfaced as a write (Part 82: no cross-squadron IDOR).

The same bug class was fixed for TrainingArea *edits* under REM-45 (see the
comment at planning.py's location-update endpoint: "previously ... could edit
ANY squadron's Training Area with zero scope check at all"). These are the
session-write paths, which that fix did not cover.

Facilitator.squadron_id and TrainingArea.squadron_id are non-nullable FKs --
strictly squadron-owned, never shared -- so the rule is exact equality.
CurriculumItem is deliberately different: it is national/wing/squadron
inheritable, so the rule there is visibility, not ownership, and a national
item must keep working for every squadron.
"""
from datetime import date

from tests.conftest import login, next_test_year


def _pn_for(client, hdr, iso_date):
    me = client.get("/api/auth/me", headers=hdr).json()["session"]
    r = client.post("/api/parade-nights", json={
        "squadron_id": me["squadron_id"], "wing_id": me["wing_id"],
        "date": iso_date, "parade_type": "normal",
    }, headers=hdr)
    assert r.status_code in (200, 201), r.text
    return r.json().get("parade_night_id") or r.json().get("id")


def _create_session(client, hdr, pn_id, **extra):
    body = {"session_number": 1, "cadet_group": "senior"}
    body.update(extra)
    return client.post(f"/api/planning/parade-dates/{pn_id}/sessions", json=body, headers=hdr)


def _stored(client, hdr, _pn_id, sid):
    """Read the session back from the server.

    Asserting on the CREATE RESPONSE was a false pass: the response does not
    carry every denormalised field, so `resp.get("training_area_id") != foreign`
    was satisfied by None while the row had been written anyway. Assert on what
    was persisted, not on what the create call happened to echo.
    """
    # NOTE the field names. The GET returns curriculum_id / curriculum_title /
    # location_id / location_name / facilitator_name -- NOT the *_at_time column
    # names used internally, and not training_area_id. Asserting on the internal
    # names made three of these tests pass against a value of None while the
    # cross-tenant row had been written. Read the response, do not assume it
    # mirrors the model.
    r = client.get(f"/api/planning/sessions/{sid}", headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def test_cannot_reference_another_squadrons_facilitator(client):
    a703, a705 = login(client, "ADMIN703"), login(client, "ADMIN705")
    foreign = client.post("/api/facilitators",
                          json={"last_name": "Foreign705", "current_rank": "CIV"},
                          headers=a705)
    assert foreign.status_code in (200, 201), foreign.text
    fid = foreign.json()["facilitator_id"]

    pn = _pn_for(client, a703, "2041-04-03")
    r = _create_session(client, a703, pn, facilitator_id=fid)
    assert r.status_code in (200, 201, 400, 403, 422), r.text
    if r.status_code not in (200, 201):
        return
    sid = r.json().get("session_id") or r.json().get("id")
    row = _stored(client, a703, pn, sid)
    assert row.get("facilitator_id") != fid, "703's session references 705's facilitator"
    assert "Foreign705" not in (row.get("facilitator_name") or ""), \
        "705's facilitator name was denormalised onto 703's session"


def test_cannot_reference_another_squadrons_training_area(client):
    a703, a705 = login(client, "ADMIN703"), login(client, "ADMIN705")
    foreign = client.post("/api/training-areas", json={"name": "Foreign705 Room"}, headers=a705)
    assert foreign.status_code in (200, 201), foreign.text
    taid = foreign.json()["training_area_id"]

    pn = _pn_for(client, a703, "2041-04-10")
    r = _create_session(client, a703, pn, location_id=taid)
    assert r.status_code in (200, 201, 400, 403, 422), r.text
    if r.status_code not in (200, 201):
        return
    sid = r.json().get("session_id") or r.json().get("id")
    row = _stored(client, a703, pn, sid)
    assert row.get("location_id") != taid, "703's session references 705's training area"
    assert "Foreign705" not in (row.get("location_name") or ""), \
        "705's room name was denormalised onto 703's session"


def test_cannot_reference_another_squadrons_curriculum_item(client):
    """CurriculumItem is inheritable, so the rule is VISIBILITY, not ownership.
    A squadron-owned item of 705 is not visible to 703 and must be refused."""
    a703, a705 = login(client, "ADMIN703"), login(client, "ADMIN705")
    made = client.post("/api/curriculum", json={
        "code": "SQN705-X1", "title": "705 Local Only", "phase": "E. Senior",
        "element": "Service", "owning_level": "squadron", "duration_minutes": 60,
    }, headers=a705)
    if made.status_code not in (200, 201):
        import pytest; pytest.skip(f"could not create a squadron-owned item: {made.text}")
    cid = made.json().get("curriculum_id") or made.json().get("curriculum_item_id")

    pn = _pn_for(client, a703, "2041-04-24")
    r = _create_session(client, a703, pn, curriculum_id=cid)
    assert r.status_code in (200, 201, 400, 403, 422), r.text
    if r.status_code not in (200, 201):
        return
    sid = r.json().get("session_id") or r.json().get("id")
    row = _stored(client, a703, pn, sid)
    assert row.get("curriculum_id") != cid, "703's session references 705's local curriculum item"
    assert "705 Local Only" not in (row.get("curriculum_title") or ""), \
        "705's local curriculum title was denormalised onto 703's session"


def test_national_curriculum_item_still_usable(client):
    """The positive control. A NATIONAL item belongs to no squadron and must
    remain usable by every squadron -- scoping must not break inheritance."""
    a703 = login(client, "ADMIN703")
    listed = client.get("/api/curriculum", headers=a703)
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    items = payload["items"] if isinstance(payload, dict) else payload
    national = next((i for i in items
                     if (i.get("owning_level") or "national") == "national"), None)
    assert national is not None, "seed has no national curriculum item to test with"
    cid = national.get("curriculum_id") or national.get("curriculum_item_id")

    pn = _pn_for(client, a703, "2041-05-01")
    r = _create_session(client, a703, pn, curriculum_id=cid)
    assert r.status_code in (200, 201), r.text
    sid = r.json().get("session_id") or r.json().get("id")
    row = _stored(client, a703, pn, sid)
    assert row.get("curriculum_id") == cid, \
        "a national curriculum item must remain usable by any squadron"


def test_edit_cannot_swap_in_another_squadrons_facilitator(client):
    """create_session was covered by the tests above; PATCH is a separate path
    with its own copy of the same three lookups, so it needs its own proof.
    A guard with no failing test behind it is an assumption."""
    a703, a705 = login(client, "ADMIN703"), login(client, "ADMIN705")
    foreign = client.post("/api/facilitators",
                          json={"last_name": "EditForeign705", "current_rank": "CIV"},
                          headers=a705)
    assert foreign.status_code in (200, 201), foreign.text
    fid = foreign.json()["facilitator_id"]

    pn = _pn_for(client, a703, "2041-05-08")
    created = _create_session(client, a703, pn)
    assert created.status_code in (200, 201), created.text
    sid = created.json().get("session_id") or created.json().get("id")
    version = _stored(client, a703, pn, sid).get("version")

    r = client.patch(f"/api/planning/sessions/{sid}",
                     json={"facilitator_id": fid, "version": version}, headers=a703)
    assert r.status_code in (200, 201, 400, 403, 409, 422), r.text

    row = _stored(client, a703, pn, sid)
    assert row.get("facilitator_id") != fid, \
        "PATCH swapped 705's facilitator onto 703's session"
    assert "EditForeign705" not in (row.get("facilitator_name") or ""), \
        "705's facilitator name was denormalised onto 703's session via PATCH"
