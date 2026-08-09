"""Tests for CLASS-05: Mission Backlog (GET /api/planning/years/{id}/missions)
becoming class-aware.

Per addendum §44, this reuses the same Stage<->CurriculumItem.phase resolution
and six-state backlog model already proven in training.py's
_class_curriculum_progress (CLASS-04) rather than a new calculation -- these
tests verify the NEW additive `class_breakdown`/`unassigned_session_count`
fields, and confirm every pre-existing item-level field
(is_scheduled/has_cancelled/backlog_status/etc, already covered by
test_planner_v14.py) is untouched by this change.

Every test uses its own dedicated squadron-scoped Training Stage and its own
planning year -- see test_class_curriculum_progress.py's module docstring for
why the shared national catalogue and relative/shared dates both caused real
cross-test pollution in sibling files; the same isolation discipline is used
here.
"""
import uuid
from datetime import date, timedelta

from tests.conftest import login


def _sqn_admin_hdr(client):
    return login(client, "ADMIN703")


def _make_year(client, hdr, year):
    r = client.post("/api/planning/years", json={"year": year, "name": f"{year} CLASS-05 Test Year"}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def _deactivate_year(client, hdr, py):
    """create_parade() (training.py) auto-links a new plain ParadeNight to
    whichever active PlanningYear has the highest `year` for the squadron
    (REM-129) -- a year created here with a high `year` value (needed so
    IT is the one picked, ahead of the seeded 2026 year and any other
    year already created by an earlier-alphabetical test file) would
    otherwise sit there indefinitely and silently steal that link away
    from a later test's own year (confirmed: this broke
    test_planning.py::test_plain_parade_night_create_links_to_active_planning_year
    before this cleanup was added). Archive it at the end of every test
    that creates one, matching this program's established
    create-then-clean-up discipline (REM-128/131)."""
    r = client.patch(f"/api/planning/years/{py['planning_year_id']}",
                      json={"active_status": False, "version": py["version"]}, headers=hdr)
    assert r.status_code == 200, r.text


def _make_stage(client, hdr, squadron_id):
    name = f"CLASS-05-TEST-{uuid.uuid4().hex[:10]}"
    r = client.post("/api/curriculum/phases", json={
        "name": name, "display_name": name, "scope_level": "squadron", "squadron_id": squadron_id,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["phase_id"], name


def _make_class(client, hdr, year_id, stage_id, name):
    r = client.post("/api/training-classes", json={
        "training_year_id": year_id, "training_stage_id": stage_id, "display_name": name,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["training_class_id"]


def _make_curriculum_item(client, hdr, code, phase):
    r = client.post("/api/curriculum", json={
        "code": code, "title": f"{code} title", "phase": phase,
        "learning_hub_url": "https://example.invalid/learning-hub/test-fixture",
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["curriculum_id"]


_next_day_offset = [400]  # a range this file owns exclusively, clear of every other file's literals


def _make_session(client, hdr, curriculum_item_id, status=None, training_class_ids=None):
    offset = _next_day_offset[0]
    _next_day_offset[0] += 3
    candidate = date(2050, 1, 1) + timedelta(days=offset)
    if candidate.weekday() == 4:
        candidate += timedelta(days=1)
    target_date = candidate.isoformat()
    r = client.get("/api/auth/me", headers=hdr)
    session_info = r.json()["session"]
    sqn_id, wing_id = session_info.get("squadron_id"), session_info.get("wing_id")

    pn = client.post("/api/parade-nights", json={
        "squadron_id": sqn_id, "wing_id": wing_id, "date": target_date, "parade_type": "normal",
    }, headers=hdr)
    assert pn.status_code in (200, 201), pn.text
    pn_id = pn.json().get("parade_night_id") or pn.json().get("id")

    sess = client.post("/api/sessions", json={
        "parade_night_id": pn_id, "period_number": 1, "cadet_group": "senior",
        "curriculum_item_id": curriculum_item_id,
    }, headers=hdr)
    assert sess.status_code in (200, 201), sess.text
    sid = sess.json()["session_id"]

    if status:
        body = {
            "parade_night_id": pn_id, "period_number": 1, "cadet_group": "senior",
            "curriculum_item_id": curriculum_item_id, "status": status,
        }
        if status in ("cancelled", "cancelled_late", "not_delivered", "delivered_with_issue"):
            body["reason"] = "test fixture reason"
        edit = client.put(f"/api/sessions/{sid}", json=body, headers=hdr)
        assert edit.status_code == 200, edit.text

    if training_class_ids:
        aud = client.put(f"/api/sessions/{sid}/audience",
                          json={"training_class_ids": training_class_ids}, headers=hdr)
        assert aud.status_code == 200, aud.text

    return sid


def _get_missions(client, hdr, year_id):
    r = client.get(f"/api/planning/years/{year_id}/missions", headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["missions"]


def _find_mission(missions, ci_id):
    m = next((m for m in missions if m["curriculum_id"] == ci_id), None)
    assert m is not None, f"curriculum item {ci_id} not present in missions list"
    return m


# ─────────────────────────────────────────────────────────────
# Shape / backward-compatibility
# ─────────────────────────────────────────────────────────────

def test_mission_item_gains_class_breakdown_and_unassigned_count_fields(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2401)
    _stage_id, stage_name = _make_stage(client, hdr, year["unit_id"])
    ci = _make_curriculum_item(client, hdr, "M05-A", stage_name)

    missions = _get_missions(client, hdr, year["planning_year_id"])
    m = _find_mission(missions, ci)
    assert "class_breakdown" in m
    assert "unassigned_session_count" in m
    assert m["class_breakdown"] == []
    assert m["unassigned_session_count"] == 0
    # Every pre-existing field this program's own tests already assert on
    # must still be present and unaffected.
    for key in ("curriculum_id", "code", "title", "phase", "is_scheduled",
                "has_cancelled", "has_not_delivered", "has_rescheduled",
                "needs_reschedule", "backlog_status", "scheduled_sessions", "scheduled_count"):
        assert key in m
    _deactivate_year(client, hdr, year)


def test_no_classes_for_stage_gives_empty_breakdown_even_when_scheduled(client):
    """A Stage with zero active Training Classes must not error -- the item's
    own backlog_status is unaffected, class_breakdown is just empty."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2402)
    _stage_id, stage_name = _make_stage(client, hdr, year["unit_id"])
    ci = _make_curriculum_item(client, hdr, "M05-B", stage_name)
    _make_session(client, hdr, ci, status="delivered")

    missions = _get_missions(client, hdr, year["planning_year_id"])
    m = _find_mission(missions, ci)
    assert m["class_breakdown"] == []
    assert m["is_scheduled"] is True
    _deactivate_year(client, hdr, year)


# ─────────────────────────────────────────────────────────────
# Per-class breakdown reflects real SessionAudience assignment
# ─────────────────────────────────────────────────────────────

def test_class_breakdown_splits_by_session_audience(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2403)
    stage_id, stage_name = _make_stage(client, hdr, year["unit_id"])
    c1 = _make_class(client, hdr, year["planning_year_id"], stage_id, "M05 Class 1")
    c2 = _make_class(client, hdr, year["planning_year_id"], stage_id, "M05 Class 2")
    ci = _make_curriculum_item(client, hdr, "M05-C", stage_name)

    # Delivered to class 1 only; class 2 has no session at all; one further
    # session is scheduled but deliberately left with no audience assignment.
    _make_session(client, hdr, ci, status="delivered", training_class_ids=[c1])
    _make_session(client, hdr, ci, status="planned", training_class_ids=None)

    missions = _get_missions(client, hdr, year["planning_year_id"])
    m = _find_mission(missions, ci)
    assert m["is_scheduled"] is True
    assert m["scheduled_count"] == 2
    assert m["unassigned_session_count"] == 1

    by_name = {b["display_name"]: b for b in m["class_breakdown"]}
    assert set(by_name) == {"M05 Class 1", "M05 Class 2"}

    assert by_name["M05 Class 1"]["is_scheduled"] is True
    assert by_name["M05 Class 1"]["scheduled_count"] == 1
    assert by_name["M05 Class 1"]["backlog_status"] == "planned"  # delivered but no cancel/not-delivered on record
    assert by_name["M05 Class 1"]["has_cancelled"] is False

    assert by_name["M05 Class 2"]["is_scheduled"] is False
    assert by_name["M05 Class 2"]["scheduled_count"] == 0
    assert by_name["M05 Class 2"]["backlog_status"] == "unscheduled"
    _deactivate_year(client, hdr, year)


def test_class_breakdown_six_state_matches_item_level_logic(client):
    """One class gets a cancelled session followed by a delivered one for the
    same mission -- addendum's six-state model should resolve this to
    "resolved" at the CLASS level, exactly as it would for the whole item."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2404)
    stage_id, stage_name = _make_stage(client, hdr, year["unit_id"])
    c1 = _make_class(client, hdr, year["planning_year_id"], stage_id, "M05 Class Resolved")
    ci = _make_curriculum_item(client, hdr, "M05-D", stage_name)

    _make_session(client, hdr, ci, status="cancelled", training_class_ids=[c1])
    _make_session(client, hdr, ci, status="delivered", training_class_ids=[c1])

    missions = _get_missions(client, hdr, year["planning_year_id"])
    m = _find_mission(missions, ci)
    entry = m["class_breakdown"][0]
    assert entry["display_name"] == "M05 Class Resolved"
    assert entry["has_cancelled"] is True
    assert entry["needs_reschedule"] is True
    assert entry["backlog_status"] == "resolved"
    # Item-level status must independently reflect the same underlying
    # sessions (this pre-existing field is untouched by CLASS-05).
    assert m["backlog_status"] == "resolved"
    _deactivate_year(client, hdr, year)


def test_session_assigned_to_multiple_classes_counts_in_each(client):
    """One combined Session serving two Classes at once (addendum's stated
    use case) must be counted in both classes' breakdown, not just one."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2405)
    stage_id, stage_name = _make_stage(client, hdr, year["unit_id"])
    c1 = _make_class(client, hdr, year["planning_year_id"], stage_id, "M05 Combined A")
    c2 = _make_class(client, hdr, year["planning_year_id"], stage_id, "M05 Combined B")
    ci = _make_curriculum_item(client, hdr, "M05-E", stage_name)

    _make_session(client, hdr, ci, status="delivered", training_class_ids=[c1, c2])

    missions = _get_missions(client, hdr, year["planning_year_id"])
    m = _find_mission(missions, ci)
    assert m["unassigned_session_count"] == 0
    by_name = {b["display_name"]: b for b in m["class_breakdown"]}
    assert by_name["M05 Combined A"]["scheduled_count"] == 1
    assert by_name["M05 Combined B"]["scheduled_count"] == 1
    _deactivate_year(client, hdr, year)


def test_class_breakdown_only_includes_classes_for_the_items_own_stage(client):
    """A class belonging to a different Stage must never appear in another
    Stage's items' class_breakdown."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2406)
    stage_a_id, stage_a_name = _make_stage(client, hdr, year["unit_id"])
    stage_b_id, stage_b_name = _make_stage(client, hdr, year["unit_id"])
    _make_class(client, hdr, year["planning_year_id"], stage_a_id, "M05 Stage A Class")
    _make_class(client, hdr, year["planning_year_id"], stage_b_id, "M05 Stage B Class")
    ci_a = _make_curriculum_item(client, hdr, "M05-F", stage_a_name)

    missions = _get_missions(client, hdr, year["planning_year_id"])
    m = _find_mission(missions, ci_a)
    names = {b["display_name"] for b in m["class_breakdown"]}
    assert names == {"M05 Stage A Class"}
    _deactivate_year(client, hdr, year)


def test_general_user_can_read_class_breakdown(client):
    """sqn_general (read-only) must still be able to read this new field --
    it is a GET, matching every other missions-endpoint RBAC expectation."""
    hdr_admin = _sqn_admin_hdr(client)
    year = _make_year(client, hdr_admin, 2407)
    stage_id, stage_name = _make_stage(client, hdr_admin, year["unit_id"])
    _make_class(client, hdr_admin, year["planning_year_id"], stage_id, "M05 General Read Class")
    ci = _make_curriculum_item(client, hdr_admin, "M05-G", stage_name)

    hdr_general = login(client, "703SQN2026")
    r = client.get(f"/api/planning/years/{year['planning_year_id']}/missions", headers=hdr_general)
    assert r.status_code == 200, r.text
    m = _find_mission(r.json()["missions"], ci)
    assert m["class_breakdown"] == [{
        "training_class_id": m["class_breakdown"][0]["training_class_id"],
        "display_name": "M05 General Read Class",
        "scheduled_count": 0,
        "is_scheduled": False,
        "has_cancelled": False,
        "has_not_delivered": False,
        "has_rescheduled": False,
        "needs_reschedule": False,
        "backlog_status": "unscheduled",
    }]
    _deactivate_year(client, hdr_admin, year)
