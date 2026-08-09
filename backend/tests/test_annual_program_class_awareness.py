"""Tests for CLASS-06 pt.3: GET /api/planning/years/{id}/annual-program
becoming class-aware.

This is the 4th distinct session serializer found across this program
(separate from _real_session_out, _sess_dict, and list_missions's own
_sess_summary) -- it powers ALL of Planning Workspace's calendar-level
views (YearView, TermView, TwoWeekView, EightWeekView, ListView, all via
ParadeNightBlock/fromNightSummary), not just the single-night grid view
already made class-aware in CLASS-06 pt.1/2. Each session's new
training_classes field is attached inline where sessions_summary is built,
reading CLASS-03's existing SessionAudience linkage via one bulk query for
the whole year (matching this endpoint's own existing avoid-N+1 discipline
for parade nights/sessions/conflicts/notices).

Uses POST /api/planning/years/{id}/parade-dates (year-scoped, not subject
to REM-129's "auto-link to highest active year" behaviour) with a date
inside Term 3's real WA date range for the created year -- get_annual_program()
builds its 4 term blocks from the PlanningYear's own `year` field
(_WA_TERM_RANGES), so a date whose calendar year doesn't match the
PlanningYear's `year` falls outside every term block entirely (the same
lesson learned building parade-night-grid-classes.spec.ts).
"""
import uuid

from tests.conftest import login


def _sqn_admin_hdr(client):
    return login(client, "ADMIN703")


def _make_year(client, hdr, year):
    r = client.post("/api/planning/years", json={"year": year, "name": f"{year} CLASS-06 Annual Program Test"}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def _deactivate_year(client, hdr, py):
    """A plain ParadeNight-create (used by other test files' own fixtures,
    e.g. test_planning.py's REM-129 regression test and
    test_mission_backlog_class_awareness.py) auto-links to whichever active
    PlanningYear has the highest `year` for the squadron -- a year created
    here with a high `year` value would otherwise sit there indefinitely
    and silently steal that link from a later test file (confirmed: this
    is exactly what happened here before this cleanup was added, the same
    class of bug test_mission_backlog_class_awareness.py already
    documented). Archive it at the end of every test."""
    r = client.patch(f"/api/planning/years/{py['planning_year_id']}",
                      json={"active_status": False, "version": py["version"]}, headers=hdr)
    assert r.status_code == 200, r.text


def _make_stage(client, hdr, squadron_id):
    name = f"CLASS-06-AP-TEST-{uuid.uuid4().hex[:10]}"
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


def _make_parade_date(client, hdr, year_id, date_str):
    r = client.post(f"/api/planning/years/{year_id}/parade-dates", json={"parade_date": date_str}, headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["parade_night_id"], "parade-dates create must auto-link a real ParadeNight"
    return body


def _make_session(client, hdr, pn_id, cadet_group="senior", period_number=1):
    r = client.post("/api/sessions", json={
        "parade_night_id": pn_id, "period_number": period_number, "cadet_group": cadet_group,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def _get_annual_program(client, hdr, year_id):
    r = client.get(f"/api/planning/years/{year_id}/annual-program", headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def _find_session_summary(annual_program, session_id):
    for term in annual_program["terms"]:
        for pd in term["parade_dates"]:
            for s in pd["sessions_summary"]:
                if s["session_id"] == session_id:
                    return s
    return None


def test_session_with_no_audience_has_empty_training_classes(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2620)
    pd = _make_parade_date(client, hdr, year["planning_year_id"], "2620-08-01")
    sid = _make_session(client, hdr, pd["parade_night_id"])

    ap = _get_annual_program(client, hdr, year["planning_year_id"])
    summary = _find_session_summary(ap, sid)
    assert summary is not None, "session must appear somewhere in the annual program"
    assert summary["training_classes"] == []
    _deactivate_year(client, hdr, year)


def test_session_shows_its_real_training_class_assignment(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2621)
    yr_id = year["planning_year_id"]
    stage_id = _make_stage(client, hdr, year["unit_id"])
    c1 = _make_class(client, hdr, yr_id, stage_id, "Annual Program Class 1")

    pd = _make_parade_date(client, hdr, yr_id, "2621-08-02")
    sid = _make_session(client, hdr, pd["parade_night_id"])
    aud = client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [c1]}, headers=hdr)
    assert aud.status_code == 200, aud.text

    ap = _get_annual_program(client, hdr, yr_id)
    summary = _find_session_summary(ap, sid)
    assert summary["training_classes"] == [{"training_class_id": c1, "display_name": "Annual Program Class 1"}]
    _deactivate_year(client, hdr, year)


def test_session_assigned_to_two_classes_shows_both(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2622)
    yr_id = year["planning_year_id"]
    stage_id = _make_stage(client, hdr, year["unit_id"])
    c1 = _make_class(client, hdr, yr_id, stage_id, "AP Combined A")
    c2 = _make_class(client, hdr, yr_id, stage_id, "AP Combined B")

    pd = _make_parade_date(client, hdr, yr_id, "2622-08-03")
    sid = _make_session(client, hdr, pd["parade_night_id"])
    aud = client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [c1, c2]}, headers=hdr)
    assert aud.status_code == 200, aud.text

    ap = _get_annual_program(client, hdr, yr_id)
    summary = _find_session_summary(ap, sid)
    names = {c["display_name"] for c in summary["training_classes"]}
    assert names == {"AP Combined A", "AP Combined B"}
    _deactivate_year(client, hdr, year)


def test_sessions_in_different_terms_dont_leak_each_others_classes(client):
    """Cross-checks the bulk-query-once-for-the-whole-year approach doesn't
    accidentally merge classes across unrelated sessions."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2623)
    yr_id = year["planning_year_id"]
    stage_id = _make_stage(client, hdr, year["unit_id"])
    c1 = _make_class(client, hdr, yr_id, stage_id, "AP Term1 Class")
    c2 = _make_class(client, hdr, yr_id, stage_id, "AP Term3 Class")

    pd1 = _make_parade_date(client, hdr, yr_id, "2623-02-03")  # Term 1
    pd3 = _make_parade_date(client, hdr, yr_id, "2623-08-04")  # Term 3
    sid1 = _make_session(client, hdr, pd1["parade_night_id"])
    sid3 = _make_session(client, hdr, pd3["parade_night_id"])
    client.put(f"/api/sessions/{sid1}/audience", json={"training_class_ids": [c1]}, headers=hdr)
    client.put(f"/api/sessions/{sid3}/audience", json={"training_class_ids": [c2]}, headers=hdr)

    ap = _get_annual_program(client, hdr, yr_id)
    s1 = _find_session_summary(ap, sid1)
    s3 = _find_session_summary(ap, sid3)
    assert [c["display_name"] for c in s1["training_classes"]] == ["AP Term1 Class"]
    assert [c["display_name"] for c in s3["training_classes"]] == ["AP Term3 Class"]
    _deactivate_year(client, hdr, year)


def test_general_user_can_read_training_classes_on_annual_program(client):
    hdr_admin = _sqn_admin_hdr(client)
    year = _make_year(client, hdr_admin, 2624)
    yr_id = year["planning_year_id"]
    stage_id = _make_stage(client, hdr_admin, year["unit_id"])
    c1 = _make_class(client, hdr_admin, yr_id, stage_id, "AP General Read Class")
    pd = _make_parade_date(client, hdr_admin, yr_id, "2624-08-05")
    sid = _make_session(client, hdr_admin, pd["parade_night_id"])
    client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [c1]}, headers=hdr_admin)

    hdr_general = login(client, "703SQN2026")
    ap = _get_annual_program(client, hdr_general, yr_id)
    summary = _find_session_summary(ap, sid)
    assert summary["training_classes"] == [{"training_class_id": c1, "display_name": "AP General Read Class"}]
    _deactivate_year(client, hdr_admin, year)
