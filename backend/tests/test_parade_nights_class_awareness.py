"""Tests for CLASS-06 (connected-frontend side): GET /api/parade-nights
becoming class-aware.

connected-frontend's real, live Weekly Program page (renderWP(), reached via
nav('weekly-program')) reads its session data from S.pns, which is populated
entirely from this endpoint's embedded `sessions` -- NOT from
GET /api/planning/parade-dates/{id}/weekly-program (that endpoint backs the
React Planning Workspace's own Weekly Program view, and a second, unrelated
connected-frontend code path -- loadWeeklyProgram()/loadPWDates(), targeting
#pw-card/#pw-preview-section/etc -- that was found to be dead code during
this task: those container IDs have zero matches anywhere in this file's
static or dynamically-generated HTML, the same CLASS-18 pattern). This file
tests the endpoint connected-frontend's Weekly Program page actually uses.

Each session dict's new `training_classes` field is attached directly in
list_parades() (training.py), not folded into the shared _sess_dict() raw
column-reflection helper, which has no DB access of its own and 8 call
sites across this file -- scoping the change to this one endpoint matches
the same additive-not-shared approach used for CLASS-05/06's other pieces.
"""
import uuid
from datetime import date, timedelta

from tests.conftest import login


def _sqn_admin_hdr(client):
    return login(client, "ADMIN703")


def _make_stage(client, hdr, squadron_id):
    name = f"CLASS-06-PN-TEST-{uuid.uuid4().hex[:10]}"
    r = client.post("/api/curriculum/phases", json={
        "name": name, "display_name": name, "scope_level": "squadron", "squadron_id": squadron_id,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["phase_id"]


def _make_class(client, hdr, year_id, stage_id, name):
    r = client.post("/api/training-classes", json={
        "training_year_id": year_id, "training_stage_id": stage_id, "display_name": name,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["training_class_id"]


_next_day_offset = [700]  # a range this file owns exclusively, clear of every other file's literals


def _make_parade_night(client, hdr, sqn_id, wing_id):
    offset = _next_day_offset[0]
    _next_day_offset[0] += 3
    candidate = date(2050, 1, 1) + timedelta(days=offset)
    if candidate.weekday() == 4:
        candidate += timedelta(days=1)
    target_date = candidate.isoformat()
    r = client.post("/api/parade-nights", json={
        "squadron_id": sqn_id, "wing_id": wing_id, "date": target_date, "parade_type": "normal",
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["parade_night_id"]


def _make_session(client, hdr, pn_id, cadet_group="senior", period_number=1):
    r = client.post("/api/sessions", json={
        "parade_night_id": pn_id, "period_number": period_number, "cadet_group": cadet_group,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def _get_pn_from_list(client, hdr, pn_id):
    r = client.get("/api/parade-nights", headers=hdr)
    assert r.status_code == 200, r.text
    pn = next(x for x in r.json() if x["parade_night_id"] == pn_id)
    return pn


def _sess_id_key(sess: dict) -> str:
    # _sess_dict() aliases the primary key as both "id" and "session_id".
    return sess.get("session_id") or sess["id"]


def test_session_with_no_audience_has_empty_training_classes(client):
    hdr = _sqn_admin_hdr(client)
    me = client.get("/api/auth/me", headers=hdr).json()["session"]
    pn_id = _make_parade_night(client, hdr, me["squadron_id"], me["wing_id"])
    _make_session(client, hdr, pn_id)

    pn = _get_pn_from_list(client, hdr, pn_id)
    assert len(pn["sessions"]) == 1
    assert pn["sessions"][0]["training_classes"] == []


def test_session_shows_its_real_training_class_assignment(client):
    hdr = _sqn_admin_hdr(client)
    me = client.get("/api/auth/me", headers=hdr).json()["session"]
    sqn_id, wing_id = me["squadron_id"], me["wing_id"]

    years_r = client.get("/api/planning/years", headers=hdr)
    year_id = years_r.json()[0]["planning_year_id"]
    stage_id = _make_stage(client, hdr, sqn_id)
    c1 = _make_class(client, hdr, year_id, stage_id, "PN List Class 1")

    pn_id = _make_parade_night(client, hdr, sqn_id, wing_id)
    sid = _make_session(client, hdr, pn_id)
    aud = client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [c1]}, headers=hdr)
    assert aud.status_code == 200, aud.text

    pn = _get_pn_from_list(client, hdr, pn_id)
    sess = next(s for s in pn["sessions"] if _sess_id_key(s) == sid)
    assert sess["training_classes"] == [{"training_class_id": c1, "display_name": "PN List Class 1"}]


def test_sessions_on_different_nights_dont_leak_each_others_classes(client):
    hdr = _sqn_admin_hdr(client)
    me = client.get("/api/auth/me", headers=hdr).json()["session"]
    sqn_id, wing_id = me["squadron_id"], me["wing_id"]

    years_r = client.get("/api/planning/years", headers=hdr)
    year_id = years_r.json()[0]["planning_year_id"]
    stage_id = _make_stage(client, hdr, sqn_id)
    c1 = _make_class(client, hdr, year_id, stage_id, "PN List Night A Class")
    c2 = _make_class(client, hdr, year_id, stage_id, "PN List Night B Class")

    pn1 = _make_parade_night(client, hdr, sqn_id, wing_id)
    pn2 = _make_parade_night(client, hdr, sqn_id, wing_id)
    sid1 = _make_session(client, hdr, pn1)
    sid2 = _make_session(client, hdr, pn2)
    client.put(f"/api/sessions/{sid1}/audience", json={"training_class_ids": [c1]}, headers=hdr)
    client.put(f"/api/sessions/{sid2}/audience", json={"training_class_ids": [c2]}, headers=hdr)

    r = client.get("/api/parade-nights", headers=hdr)
    all_pns = {x["parade_night_id"]: x for x in r.json()}
    sess1 = next(s for s in all_pns[pn1]["sessions"] if _sess_id_key(s) == sid1)
    sess2 = next(s for s in all_pns[pn2]["sessions"] if _sess_id_key(s) == sid2)
    assert [c["display_name"] for c in sess1["training_classes"]] == ["PN List Night A Class"]
    assert [c["display_name"] for c in sess2["training_classes"]] == ["PN List Night B Class"]


def test_general_user_can_read_training_classes_on_parade_nights_list(client):
    hdr_admin = _sqn_admin_hdr(client)
    me = client.get("/api/auth/me", headers=hdr_admin).json()["session"]
    sqn_id, wing_id = me["squadron_id"], me["wing_id"]

    years_r = client.get("/api/planning/years", headers=hdr_admin)
    year_id = years_r.json()[0]["planning_year_id"]
    stage_id = _make_stage(client, hdr_admin, sqn_id)
    c1 = _make_class(client, hdr_admin, year_id, stage_id, "PN List General Read Class")
    pn_id = _make_parade_night(client, hdr_admin, sqn_id, wing_id)
    sid = _make_session(client, hdr_admin, pn_id)
    client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [c1]}, headers=hdr_admin)

    hdr_general = login(client, "703SQN2026")
    pn = _get_pn_from_list(client, hdr_general, pn_id)
    sess = next(s for s in pn["sessions"] if _sess_id_key(s) == sid)
    assert sess["training_classes"] == [{"training_class_id": c1, "display_name": "PN List General Read Class"}]
