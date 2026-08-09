"""Tests for CLASS-06: Weekly Program (GET /api/planning/parade-dates/{id}/weekly-program)
becoming class-aware.

Per addendum §44's "no new calculation" discipline, this only reads
CLASS-03's existing SessionAudience linkage -- no new writes, no new model.
The new `training_classes` field is attached directly inside
get_weekly_program() rather than folded into the shared _real_session_out()
helper (which also serialises sessions for 7 other endpoints -- term
planner, builder, session create/get/update, long-range, mission
assignment) -- keeping this change's blast radius to the one endpoint this
task covers, the same additive-not-shared approach CLASS-05 used in
list_missions().

Uses `POST /api/planning/years/{yr_id}/parade-dates` (not the raw
`POST /api/parade-nights`) to create its parade date -- that endpoint takes
the target year explicitly in the URL, so it is not subject to the
REM-129 "auto-links to whichever active PlanningYear has the highest
`year`" behaviour that required the year-value/cleanup workarounds in
test_mission_backlog_class_awareness.py and
frontend/e2e/mission-backlog-classes.spec.ts.
"""
import uuid

from tests.conftest import login


def _sqn_admin_hdr(client):
    return login(client, "ADMIN703")


def _make_year(client, hdr, year):
    r = client.post("/api/planning/years", json={"year": year, "name": f"{year} CLASS-06 Test Year"}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def _setup_year_with_date(client, hdr, year, date_str):
    py = _make_year(client, hdr, year)
    rp = client.post(f"/api/planning/years/{py['planning_year_id']}/parade-dates",
                      json={"parade_date": date_str}, headers=hdr)
    assert rp.status_code == 200, rp.text
    return py, rp.json()["parade_date_id"]


def _make_stage(client, hdr, squadron_id):
    name = f"CLASS-06-TEST-{uuid.uuid4().hex[:10]}"
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


def _create_session(client, hdr, pd_id, cadet_group="senior", session_number=1, activity_title="Test Activity"):
    r = client.post(f"/api/planning/parade-dates/{pd_id}/sessions", json={
        "cadet_group": cadet_group, "session_number": session_number, "activity_title": activity_title,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def _get_weekly_program(client, hdr, pd_id):
    r = client.get(f"/api/planning/parade-dates/{pd_id}/weekly-program", headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def test_session_with_no_audience_has_empty_training_classes(client):
    hdr = _sqn_admin_hdr(client)
    _py, pd_id = _setup_year_with_date(client, hdr, 2500, "2100-05-01")
    _create_session(client, hdr, pd_id)

    wp = _get_weekly_program(client, hdr, pd_id)
    assert len(wp["sessions"]) == 1
    assert wp["sessions"][0]["training_classes"] == []


def test_session_shows_its_real_training_class_assignment(client):
    hdr = _sqn_admin_hdr(client)
    py, pd_id = _setup_year_with_date(client, hdr, 2501, "2100-05-02")
    stage_id = _make_stage(client, hdr, py["unit_id"])
    c1 = _make_class(client, hdr, py["planning_year_id"], stage_id, "Weekly Program Class 1")

    sid = _create_session(client, hdr, pd_id)
    aud = client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [c1]}, headers=hdr)
    assert aud.status_code == 200, aud.text

    wp = _get_weekly_program(client, hdr, pd_id)
    sess = next(s for s in wp["sessions"] if s["session_id"] == sid)
    assert sess["training_classes"] == [{"training_class_id": c1, "display_name": "Weekly Program Class 1"}]


def test_session_assigned_to_two_classes_shows_both(client):
    hdr = _sqn_admin_hdr(client)
    py, pd_id = _setup_year_with_date(client, hdr, 2502, "2100-05-03")
    stage_id = _make_stage(client, hdr, py["unit_id"])
    c1 = _make_class(client, hdr, py["planning_year_id"], stage_id, "WP Combined A")
    c2 = _make_class(client, hdr, py["planning_year_id"], stage_id, "WP Combined B")

    sid = _create_session(client, hdr, pd_id)
    aud = client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [c1, c2]}, headers=hdr)
    assert aud.status_code == 200, aud.text

    wp = _get_weekly_program(client, hdr, pd_id)
    sess = next(s for s in wp["sessions"] if s["session_id"] == sid)
    names = {c["display_name"] for c in sess["training_classes"]}
    assert names == {"WP Combined A", "WP Combined B"}


def test_multiple_sessions_each_get_their_own_correct_classes(client):
    """A per-session assignment must not leak onto a sibling session on the
    same parade night -- the join is scoped by session_id, not parade night."""
    hdr = _sqn_admin_hdr(client)
    py, pd_id = _setup_year_with_date(client, hdr, 2503, "2100-05-04")
    stage_id = _make_stage(client, hdr, py["unit_id"])
    c1 = _make_class(client, hdr, py["planning_year_id"], stage_id, "WP Sibling Class 1")
    c2 = _make_class(client, hdr, py["planning_year_id"], stage_id, "WP Sibling Class 2")

    sid1 = _create_session(client, hdr, pd_id, cadet_group="senior", session_number=1, activity_title="Session One")
    sid2 = _create_session(client, hdr, pd_id, cadet_group="junior", session_number=2, activity_title="Session Two")
    client.put(f"/api/sessions/{sid1}/audience", json={"training_class_ids": [c1]}, headers=hdr)
    client.put(f"/api/sessions/{sid2}/audience", json={"training_class_ids": [c2]}, headers=hdr)

    wp = _get_weekly_program(client, hdr, pd_id)
    by_id = {s["session_id"]: s for s in wp["sessions"]}
    assert [c["display_name"] for c in by_id[sid1]["training_classes"]] == ["WP Sibling Class 1"]
    assert [c["display_name"] for c in by_id[sid2]["training_classes"]] == ["WP Sibling Class 2"]


def test_weekly_program_shape_and_other_fields_unaffected(client):
    hdr = _sqn_admin_hdr(client)
    _py, pd_id = _setup_year_with_date(client, hdr, 2504, "2100-05-05")
    _create_session(client, hdr, pd_id, activity_title="Shape Check Activity")

    wp = _get_weekly_program(client, hdr, pd_id)
    for key in ("parade_date_id", "parade_night_id", "parade_date", "unit_id",
                "timing_blocks", "sessions", "conflicts", "has_unresolved_conflicts"):
        assert key in wp
    s = wp["sessions"][0]
    for key in ("session_id", "cadet_group", "session_number", "activity_title",
                "status", "training_classes"):
        assert key in s


def test_general_user_can_read_training_classes_on_weekly_program(client):
    hdr_admin = _sqn_admin_hdr(client)
    py, pd_id = _setup_year_with_date(client, hdr_admin, 2505, "2100-05-06")
    stage_id = _make_stage(client, hdr_admin, py["unit_id"])
    c1 = _make_class(client, hdr_admin, py["planning_year_id"], stage_id, "WP General Read Class")
    sid = _create_session(client, hdr_admin, pd_id)
    client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [c1]}, headers=hdr_admin)

    hdr_general = login(client, "703SQN2026")
    wp = _get_weekly_program(client, hdr_general, pd_id)
    sess = next(s for s in wp["sessions"] if s["session_id"] == sid)
    assert sess["training_classes"] == [{"training_class_id": c1, "display_name": "WP General Read Class"}]
