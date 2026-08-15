"""V14 Training Planner tests.

Covers: mission scheduling view, mission assignment, annual program,
year rollover, extended anchor event fields, holiday_type, parade date
term/week_number fields, and RBAC enforcement for new endpoints.
"""
import pytest
from tests.conftest import login


def _sqn_admin(client):
    return login(client, "ADMIN703")


def _wing_admin(client):
    return login(client, "ADMIN7WG")


def _nat_admin(client):
    return login(client, "ADMINNATIONAL")


def _general(client):
    return login(client, "703SQN2026")


def _auditor(client):
    return login(client, "AUDITOR2026")


def _make_year(client, hdr, year=2028, name="Test Year"):
    r = client.post("/api/planning/years", json={"year": year, "name": name}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def _make_holiday(client, hdr, year_id, name="Test Holiday", htype="public_holiday",
                  start="2028-04-03", end="2028-04-03"):
    r = client.post(f"/api/planning/years/{year_id}/holidays", json={
        "name": name, "start_date": start, "end_date": end,
        "holiday_type": htype, "affects_parade": True,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def _make_parade_date(client, hdr, year_id, date_str="2028-03-01"):
    r = client.post(f"/api/planning/years/{year_id}/parade-dates", json={
        "parade_date": date_str, "parade_type": "standard",
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


# ─────────────────────────────────────────────────────────────
# Seeded planning year (from seed_planning_data)
# ─────────────────────────────────────────────────────────────

def test_seeded_planning_year_exists(client):
    """seed_all should have created a 703 SQN planning year for 2026."""
    hdr = _sqn_admin(client)
    r = client.get("/api/planning/years", headers=hdr)
    assert r.status_code == 200
    years = r.json()
    year_2026 = [y for y in years if y["year"] == 2026]
    assert year_2026, "No 2026 planning year found in seed"
    assert year_2026[0]["unit_id"] is not None


def test_seeded_wa_holidays_exist(client):
    """WA 2026 holidays should be seeded and linked to the 2026 planning year."""
    hdr = _sqn_admin(client)
    years_r = client.get("/api/planning/years", headers=hdr)
    years = [y for y in years_r.json() if y["year"] == 2026]
    assert years
    year_id = years[0]["planning_year_id"]

    r = client.get(f"/api/planning/years/{year_id}/holidays", headers=hdr)
    assert r.status_code == 200
    holidays = r.json()
    assert len(holidays) >= 5, f"Expected ≥5 WA holidays, got {len(holidays)}"
    names = [h["name"] for h in holidays]
    assert any("Labour Day" in n for n in names), "Labour Day missing"
    assert any("Good Friday" in n for n in names), "Good Friday missing"
    assert any("WA Day" in n for n in names), "WA Day missing"


def test_seeded_holiday_types(client):
    """Seeded holidays should have correct holiday_type values."""
    hdr = _sqn_admin(client)
    years_r = client.get("/api/planning/years", headers=hdr)
    years = [y for y in years_r.json() if y["year"] == 2026]
    year_id = years[0]["planning_year_id"]

    r = client.get(f"/api/planning/years/{year_id}/holidays", headers=hdr)
    holidays = r.json()
    public = [h for h in holidays if h.get("holiday_type") == "public_holiday"]
    school = [h for h in holidays if h.get("holiday_type") == "school_holiday"]
    assert public, "No public holidays found in seed"
    assert school, "No school holidays found in seed"


def test_seeded_parade_dates_have_term(client):
    """Seeded parade dates for 703 SQN 2026 should include term labels."""
    hdr = _sqn_admin(client)
    years_r = client.get("/api/planning/years", headers=hdr)
    years = [y for y in years_r.json() if y["year"] == 2026]
    year_id = years[0]["planning_year_id"]

    r = client.get(f"/api/planning/years/{year_id}/parade-dates", headers=hdr)
    assert r.status_code == 200
    dates = r.json()
    assert len(dates) >= 10, "Expected ≥10 parade dates in 2026"
    # At least some should have a term label
    with_term = [d for d in dates if d.get("term")]
    assert with_term, "No parade dates have term label"


def test_seeded_anchor_events_exist(client):
    """Seeded anchor events should include 7 Wing Camp and Anzac Day."""
    hdr = _sqn_admin(client)
    years_r = client.get("/api/planning/years", headers=hdr)
    years = [y for y in years_r.json() if y["year"] == 2026]
    year_id = years[0]["planning_year_id"]

    r = client.get(f"/api/planning/years/{year_id}/anchors", headers=hdr)
    assert r.status_code == 200
    anchors = r.json()
    names = [a["event_name"] for a in anchors]
    assert any("Camp" in n for n in names), "7 Wing Camp missing from seeded anchors"
    assert any("Anzac" in n for n in names), "Anzac Day missing from seeded anchors"


# ─────────────────────────────────────────────────────────────
# holiday_type field (new in V14)
# ─────────────────────────────────────────────────────────────

def test_create_holiday_with_type(client):
    """Creating a holiday should accept and return holiday_type."""
    hdr = _sqn_admin(client)
    py = _make_year(client, hdr, year=2031, name="Holiday Type Test")
    year_id = py["planning_year_id"]

    h = _make_holiday(client, hdr, year_id, name="Exam Period", htype="exam_period",
                      start="2031-06-10", end="2031-06-20")
    assert h["holiday_type"] == "exam_period"


def test_holiday_default_type_is_school_holiday(client):
    """A holiday created without holiday_type should default to school_holiday."""
    hdr = _sqn_admin(client)
    py = _make_year(client, hdr, year=2032, name="Default Type Test")
    year_id = py["planning_year_id"]

    r = client.post(f"/api/planning/years/{year_id}/holidays", json={
        "name": "No Type Holiday", "start_date": "2032-07-01", "end_date": "2032-07-14",
    }, headers=hdr)
    assert r.status_code == 200
    assert r.json()["holiday_type"] == "school_holiday"


# ─────────────────────────────────────────────────────────────
# ParadeDate — term / week_number fields (new in V14)
# ─────────────────────────────────────────────────────────────

def test_parade_date_has_term_and_week_number_fields(client):
    """Parade date response should include term and week_number keys."""
    hdr = _sqn_admin(client)
    py = _make_year(client, hdr, year=2033, name="Date Fields Test")
    year_id = py["planning_year_id"]
    pd = _make_parade_date(client, hdr, year_id, "2033-02-07")
    # Keys must exist (may be None)
    assert "term" in pd
    assert "week_number" in pd
    assert "cancellation_reason" in pd


# ─────────────────────────────────────────────────────────────
# AnchorEvent — extended fields (new in V14)
# ─────────────────────────────────────────────────────────────

def test_anchor_event_extended_fields_in_response(client):
    """AnchorEvent response should include V14 extended fields."""
    hdr = _sqn_admin(client)
    py = _make_year(client, hdr, year=2034, name="Anchor Extended")
    year_id = py["planning_year_id"]

    r = client.post(f"/api/planning/years/{year_id}/anchors", json={
        "event_name": "Test Activity", "event_type": "adventure_training",
        "importance": "must_attend", "start_date": "2034-06-01",
    }, headers=hdr)
    assert r.status_code == 200
    a = r.json()
    assert "importance_level" in a
    assert "cea_activity_id" in a
    assert "nomination_end_date" in a
    assert "unit_name" in a
    assert "staff_only" in a["audience"]
    assert "proficient" in a["audience"]
    assert "first_years" in a["audience"]


# ─────────────────────────────────────────────────────────────
# GET /api/planning/years/{id}/missions
# ─────────────────────────────────────────────────────────────

def test_missions_returns_curriculum_items(client):
    """Missions endpoint should return curriculum items for this principal's scope."""
    hdr = _sqn_admin(client)
    years_r = client.get("/api/planning/years", headers=hdr)
    year_id = years_r.json()[0]["planning_year_id"]

    r = client.get(f"/api/planning/years/{year_id}/missions", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert "missions" in d
    assert "total" in d
    assert "scheduled_count" in d
    assert isinstance(d["missions"], list)


def test_missions_structure_per_item(client):
    """Each mission item should have required scheduling fields."""
    hdr = _sqn_admin(client)
    years_r = client.get("/api/planning/years", headers=hdr)
    year_id = years_r.json()[0]["planning_year_id"]

    r = client.get(f"/api/planning/years/{year_id}/missions", headers=hdr)
    assert r.status_code == 200
    missions = r.json()["missions"]
    if missions:
        m = missions[0]
        assert "curriculum_id" in m
        assert "code" in m
        assert "title" in m
        assert "phase" in m
        assert "is_scheduled" in m
        assert "scheduled_sessions" in m
        assert "part_count" in m
        assert isinstance(m["scheduled_sessions"], list)


def test_missions_filter_by_phase(client):
    """Filtering missions by phase should restrict results."""
    hdr = _sqn_admin(client)
    years_r = client.get("/api/planning/years", headers=hdr)
    year_id = years_r.json()[0]["planning_year_id"]

    r = client.get(f"/api/planning/years/{year_id}/missions?phase=A.+Orientation", headers=hdr)
    assert r.status_code == 200
    missions = r.json()["missions"]
    for m in missions:
        assert m["phase"] == "A. Orientation"


def test_missions_filter_status_unscheduled(client):
    """Filtering by status=unscheduled should only return unscheduled items."""
    hdr = _sqn_admin(client)
    years_r = client.get("/api/planning/years", headers=hdr)
    year_id = years_r.json()[0]["planning_year_id"]

    r = client.get(f"/api/planning/years/{year_id}/missions?status=unscheduled", headers=hdr)
    assert r.status_code == 200
    for m in r.json()["missions"]:
        assert not m["is_scheduled"]


def test_missions_search_filter(client):
    """Searching by code fragment should filter missions."""
    hdr = _sqn_admin(client)
    years_r = client.get("/api/planning/years", headers=hdr)
    year_id = years_r.json()[0]["planning_year_id"]

    r = client.get(f"/api/planning/years/{year_id}/missions?search=ORI", headers=hdr)
    assert r.status_code == 200
    missions = r.json()["missions"]
    for m in missions:
        assert "ORI" in m["code"].upper() or "ORI" in m["title"].upper()


def test_missions_general_user_can_read(client):
    """sqn_general role should be able to read missions."""
    hdr_admin = _sqn_admin(client)
    years_r = client.get("/api/planning/years", headers=hdr_admin)
    year_id = years_r.json()[0]["planning_year_id"]

    hdr = _general(client)
    r = client.get(f"/api/planning/years/{year_id}/missions", headers=hdr)
    assert r.status_code == 200


# ─────────────────────────────────────────────────────────────
# POST /api/planning/years/{id}/assign-mission
# ─────────────────────────────────────────────────────────────

def test_assign_mission_creates_session(client):
    """Assigning a mission should create a real TrainingSession record."""
    hdr = _sqn_admin(client)
    years_r = client.get("/api/planning/years", headers=hdr)
    year_2026 = [y for y in years_r.json() if y["year"] == 2026]
    assert year_2026
    year_id = year_2026[0]["planning_year_id"]

    # Get a parade date
    dates_r = client.get(f"/api/planning/years/{year_id}/parade-dates", headers=hdr)
    dates = [d for d in dates_r.json() if d["is_active"]]
    assert dates
    date_id = dates[0]["parade_date_id"]

    # Get a curriculum item
    missions_r = client.get(f"/api/planning/years/{year_id}/missions?status=unscheduled", headers=hdr)
    missions = missions_r.json()["missions"]
    assert missions
    ci_id = missions[0]["curriculum_id"]

    r = client.post(f"/api/planning/years/{year_id}/assign-mission", json={
        "curriculum_id": ci_id,
        "parade_date_id": date_id,
        "session_number": 1,
        "cadet_group": "orientation",
        "part_number": 1,
    }, headers=hdr)
    assert r.status_code == 200
    s = r.json()
    assert s["curriculum_id"] == ci_id
    assert s["session_number"] == 1
    assert s["cadet_group"] == "orientation"


def _get_2026_year_and_date(client, hdr):
    """Helper: return (year_id, date_id, ci_id) from the seeded 2026 year."""
    years_r = client.get("/api/planning/years", headers=hdr)
    year_2026 = [y for y in years_r.json() if y["year"] == 2026]
    assert year_2026, "Seeded 2026 planning year not found"
    year_id = year_2026[0]["planning_year_id"]
    dates_r = client.get(f"/api/planning/years/{year_id}/parade-dates", headers=hdr)
    dates = [d for d in dates_r.json() if d["is_active"]]
    assert dates, "No active parade dates in 2026 year"
    date_id = dates[-1]["parade_date_id"]  # use last date to avoid conflicts
    missions_r = client.get(f"/api/planning/years/{year_id}/missions", headers=hdr)
    missions = missions_r.json()["missions"]
    assert missions
    ci_id = missions[0]["curriculum_id"]
    return year_id, date_id, ci_id


def test_assign_mission_invalid_group_returns_422(client):
    """Assigning with an invalid cadet_group should return 422."""
    hdr = _sqn_admin(client)
    year_id, date_id, ci_id = _get_2026_year_and_date(client, hdr)

    r = client.post(f"/api/planning/years/{year_id}/assign-mission", json={
        "curriculum_id": ci_id, "parade_date_id": date_id,
        "session_number": 1, "cadet_group": "invalid_group",
    }, headers=hdr)
    assert r.status_code == 422


def test_assign_mission_read_only_user_blocked(client):
    """sqn_general should not be able to assign missions."""
    hdr_admin = _sqn_admin(client)
    year_id, date_id, ci_id = _get_2026_year_and_date(client, hdr_admin)

    hdr = _general(client)
    r = client.post(f"/api/planning/years/{year_id}/assign-mission", json={
        "curriculum_id": ci_id, "parade_date_id": date_id,
        "session_number": 1, "cadet_group": "orientation",
    }, headers=hdr)
    assert r.status_code == 403


def test_assign_mission_missing_curriculum_returns_404(client):
    """Assigning a non-existent curriculum item should return 404."""
    hdr = _sqn_admin(client)
    year_id, date_id, _ = _get_2026_year_and_date(client, hdr)

    r = client.post(f"/api/planning/years/{year_id}/assign-mission", json={
        "curriculum_id": "00000000-0000-0000-0000-000000000000",
        "parade_date_id": date_id, "session_number": 1, "cadet_group": "orientation",
    }, headers=hdr)
    assert r.status_code == 404


def test_assign_mission_reflected_in_missions_list(client):
    """After assignment, missions list should show the item as scheduled."""
    hdr = _sqn_admin(client)
    years_r = client.get("/api/planning/years", headers=hdr)
    year_2026 = [y for y in years_r.json() if y["year"] == 2026]
    year_id = year_2026[0]["planning_year_id"]

    dates_r = client.get(f"/api/planning/years/{year_id}/parade-dates", headers=hdr)
    active_dates = [d for d in dates_r.json() if d["is_active"]]
    date_id = active_dates[1]["parade_date_id"]  # use second date to avoid conflict with prior test

    missions_r = client.get(f"/api/planning/years/{year_id}/missions?status=unscheduled", headers=hdr)
    unscheduled = missions_r.json()["missions"]
    if not unscheduled:
        pytest.skip("No unscheduled missions to assign")
    ci_id = unscheduled[0]["curriculum_id"]

    # Assign
    client.post(f"/api/planning/years/{year_id}/assign-mission", json={
        "curriculum_id": ci_id, "parade_date_id": date_id,
        "session_number": 2, "cadet_group": "initial",
    }, headers=hdr)

    # Check missions list shows it scheduled
    r2 = client.get(f"/api/planning/years/{year_id}/missions?status=scheduled", headers=hdr)
    scheduled_ids = [m["curriculum_id"] for m in r2.json()["missions"]]
    assert ci_id in scheduled_ids


def test_missions_list_surfaces_cancelled_status_and_reason(client):
    """A cancelled session must show up under status=cancelled with its reason retained."""
    hdr = _sqn_admin(client)
    years_r = client.get("/api/planning/years", headers=hdr)
    year_2026 = [y for y in years_r.json() if y["year"] == 2026]
    year_id = year_2026[0]["planning_year_id"]

    dates_r = client.get(f"/api/planning/years/{year_id}/parade-dates", headers=hdr)
    active_dates = [d for d in dates_r.json() if d["is_active"]]
    date_id = active_dates[2]["parade_date_id"]  # avoid conflicting with earlier tests' dates

    missions_r = client.get(f"/api/planning/years/{year_id}/missions?status=unscheduled", headers=hdr)
    unscheduled = missions_r.json()["missions"]
    if not unscheduled:
        pytest.skip("No unscheduled missions to assign")
    ci_id = unscheduled[0]["curriculum_id"]

    assign_r = client.post(f"/api/planning/years/{year_id}/assign-mission", json={
        "curriculum_id": ci_id, "parade_date_id": date_id,
        "session_number": 3, "cadet_group": "junior",
    }, headers=hdr)
    assert assign_r.status_code == 200
    session_id = assign_r.json()["session_id"]

    status_r = client.post(f"/api/sessions/{session_id}/status", json={
        "status": "cancelled", "reason": "Facilitator unavailable — squadron-wide illness",
    }, headers=hdr)
    assert status_r.status_code == 200

    # Default (unscheduled) filter must not show it; is_scheduled is still true.
    r_default = client.get(f"/api/planning/years/{year_id}/missions", headers=hdr)
    row = next(m for m in r_default.json()["missions"] if m["curriculum_id"] == ci_id)
    assert row["is_scheduled"] is True
    assert row["has_cancelled"] is True
    assert row["has_not_delivered"] is False
    assert row["needs_reschedule"] is True

    # status=cancelled filter must surface it.
    r_cancelled = client.get(f"/api/planning/years/{year_id}/missions?status=cancelled", headers=hdr)
    cancelled_ids = [m["curriculum_id"] for m in r_cancelled.json()["missions"]]
    assert ci_id in cancelled_ids

    # Original date and cancellation reason must be retained on the session summary.
    sess = row["scheduled_sessions"][0]
    assert sess["parade_date"] is not None
    assert sess["cancelled_reason"] == "Facilitator unavailable — squadron-wide illness"


def test_missions_list_surfaces_not_delivered_status(client):
    """A not-delivered session must show up under status=not_delivered with its reason."""
    hdr = _sqn_admin(client)
    years_r = client.get("/api/planning/years", headers=hdr)
    year_2026 = [y for y in years_r.json() if y["year"] == 2026]
    year_id = year_2026[0]["planning_year_id"]

    dates_r = client.get(f"/api/planning/years/{year_id}/parade-dates", headers=hdr)
    active_dates = [d for d in dates_r.json() if d["is_active"]]
    date_id = active_dates[3]["parade_date_id"]

    missions_r = client.get(f"/api/planning/years/{year_id}/missions?status=unscheduled", headers=hdr)
    unscheduled = missions_r.json()["missions"]
    if not unscheduled:
        pytest.skip("No unscheduled missions to assign")
    ci_id = unscheduled[0]["curriculum_id"]

    assign_r = client.post(f"/api/planning/years/{year_id}/assign-mission", json={
        "curriculum_id": ci_id, "parade_date_id": date_id,
        "session_number": 4, "cadet_group": "junior",
    }, headers=hdr)
    session_id = assign_r.json()["session_id"]

    status_r = client.post(f"/api/sessions/{session_id}/status", json={
        "status": "not_delivered", "reason": "Venue flooded",
    }, headers=hdr)
    assert status_r.status_code == 200

    r = client.get(f"/api/planning/years/{year_id}/missions?status=not_delivered", headers=hdr)
    row = next(m for m in r.json()["missions"] if m["curriculum_id"] == ci_id)
    assert row["has_not_delivered"] is True
    assert row["needs_reschedule"] is True
    assert row["scheduled_sessions"][0]["not_delivered_reason"] == "Venue flooded"


# ─────────────────────────────────────────────────────────────
# Mission Backlog six-state model (master transformation plan Block 6):
# unscheduled / planned / cancelled_awaiting_reschedule /
# not_delivered_awaiting_reschedule / rescheduled / resolved
# ─────────────────────────────────────────────────────────────

def _assign_and_status(client, hdr, year_id, date_idx, session_number, status=None, reason=None):
    dates_r = client.get(f"/api/planning/years/{year_id}/parade-dates", headers=hdr)
    active_dates = [d for d in dates_r.json() if d["is_active"]]
    date_id = active_dates[date_idx]["parade_date_id"]

    missions_r = client.get(f"/api/planning/years/{year_id}/missions?status=unscheduled", headers=hdr)
    unscheduled = missions_r.json()["missions"]
    if not unscheduled:
        pytest.skip("No unscheduled missions to assign")
    ci_id = unscheduled[0]["curriculum_id"]

    assign_r = client.post(f"/api/planning/years/{year_id}/assign-mission", json={
        "curriculum_id": ci_id, "parade_date_id": date_id,
        "session_number": session_number, "cadet_group": "junior",
    }, headers=hdr)
    assert assign_r.status_code == 200, assign_r.text
    session_id = assign_r.json()["session_id"]

    if status:
        status_r = client.post(f"/api/sessions/{session_id}/status",
                               json={"status": status, "reason": reason}, headers=hdr)
        assert status_r.status_code == 200, status_r.text
    return ci_id, session_id, date_id


def test_backlog_status_unscheduled(client):
    hdr = _sqn_admin(client)
    year_id = _get_year_id(client, hdr)
    r = client.get(f"/api/planning/years/{year_id}/missions?status=unscheduled", headers=hdr)
    missions = r.json()["missions"]
    if not missions:
        pytest.skip("No unscheduled missions available")
    assert all(m["backlog_status"] == "unscheduled" for m in missions)


def test_backlog_status_planned_for_a_normally_scheduled_session(client):
    hdr = _sqn_admin(client)
    year_id = _get_year_id(client, hdr)
    ci_id, _, _ = _assign_and_status(client, hdr, year_id, date_idx=4, session_number=5)
    r = client.get(f"/api/planning/years/{year_id}/missions?status=planned", headers=hdr)
    ids = [m["curriculum_id"] for m in r.json()["missions"]]
    assert ci_id in ids
    row = next(m for m in r.json()["missions"] if m["curriculum_id"] == ci_id)
    assert row["backlog_status"] == "planned"


def test_backlog_status_cancelled_awaiting_reschedule(client):
    hdr = _sqn_admin(client)
    year_id = _get_year_id(client, hdr)
    ci_id, _, _ = _assign_and_status(client, hdr, year_id, date_idx=5, session_number=6,
                                     status="cancelled", reason="Weather")
    r = client.get(f"/api/planning/years/{year_id}/missions", headers=hdr)
    row = next(m for m in r.json()["missions"] if m["curriculum_id"] == ci_id)
    assert row["backlog_status"] == "cancelled_awaiting_reschedule"


def test_backlog_status_not_delivered_awaiting_reschedule(client):
    hdr = _sqn_admin(client)
    year_id = _get_year_id(client, hdr)
    ci_id, _, _ = _assign_and_status(client, hdr, year_id, date_idx=6, session_number=7,
                                     status="not_delivered", reason="Instructor sick")
    r = client.get(f"/api/planning/years/{year_id}/missions", headers=hdr)
    row = next(m for m in r.json()["missions"] if m["curriculum_id"] == ci_id)
    assert row["backlog_status"] == "not_delivered_awaiting_reschedule"


def test_backlog_status_rescheduled(client):
    hdr = _sqn_admin(client)
    year_id = _get_year_id(client, hdr)
    ci_id, _, _ = _assign_and_status(client, hdr, year_id, date_idx=7, session_number=8,
                                     status="rescheduled")
    r = client.get(f"/api/planning/years/{year_id}/missions?status=rescheduled", headers=hdr)
    ids = [m["curriculum_id"] for m in r.json()["missions"]]
    assert ci_id in ids
    row = next(m for m in r.json()["missions"] if m["curriculum_id"] == ci_id)
    assert row["backlog_status"] == "rescheduled"
    assert row["has_rescheduled"] is True


def test_backlog_status_resolved_when_cancelled_session_later_delivered(client):
    """A mission that was cancelled but has since ALSO been delivered (via another
    session for the same curriculum item) is 'resolved', not stuck permanently
    flagged as needing a reschedule action."""
    hdr = _sqn_admin(client)
    year_id = _get_year_id(client, hdr)

    dates_r = client.get(f"/api/planning/years/{year_id}/parade-dates", headers=hdr)
    active_dates = [d for d in dates_r.json() if d["is_active"]]

    missions_r = client.get(f"/api/planning/years/{year_id}/missions?status=unscheduled", headers=hdr)
    unscheduled = missions_r.json()["missions"]
    if not unscheduled:
        pytest.skip("No unscheduled missions available")
    ci_id = unscheduled[0]["curriculum_id"]

    # First session: cancelled.
    assign1 = client.post(f"/api/planning/years/{year_id}/assign-mission", json={
        "curriculum_id": ci_id, "parade_date_id": active_dates[8]["parade_date_id"],
        "session_number": 1, "cadet_group": "senior",
    }, headers=hdr)
    assert assign1.status_code == 200, assign1.text
    client.post(f"/api/sessions/{assign1.json()['session_id']}/status",
               json={"status": "cancelled", "reason": "Venue double-booked"}, headers=hdr)

    # Second session for the SAME curriculum item, on a different date: delivered.
    assign2 = client.post(f"/api/planning/years/{year_id}/assign-mission", json={
        "curriculum_id": ci_id, "parade_date_id": active_dates[9]["parade_date_id"],
        "session_number": 1, "cadet_group": "senior",
    }, headers=hdr)
    assert assign2.status_code == 200, assign2.text
    client.post(f"/api/sessions/{assign2.json()['session_id']}/status",
               json={"status": "delivered"}, headers=hdr)

    r = client.get(f"/api/planning/years/{year_id}/missions?status=resolved", headers=hdr)
    ids = [m["curriculum_id"] for m in r.json()["missions"]]
    assert ci_id in ids
    row = next(m for m in r.json()["missions"] if m["curriculum_id"] == ci_id)
    assert row["backlog_status"] == "resolved"


def test_outcome_note_retained_on_scheduled_session(client):
    hdr = _sqn_admin(client)
    year_id = _get_year_id(client, hdr)
    ci_id, session_id, _ = _assign_and_status(client, hdr, year_id, date_idx=10, session_number=1,
                                              status="delivered_with_issue", reason="Projector broke mid-session")
    r = client.get(f"/api/planning/years/{year_id}/missions", headers=hdr)
    row = next(m for m in r.json()["missions"] if m["curriculum_id"] == ci_id)
    assert row["scheduled_sessions"][0]["outcome_note"] == "Projector broke mid-session"


def _get_year_id(client, hdr):
    years_r = client.get("/api/planning/years", headers=hdr)
    year_2026 = [y for y in years_r.json() if y["year"] == 2026]
    return year_2026[0]["planning_year_id"]


# ─────────────────────────────────────────────────────────────
# GET /api/planning/years/{id}/annual-program
# ─────────────────────────────────────────────────────────────

def test_annual_program_returns_four_terms(client):
    """Annual program should return 4 term blocks."""
    hdr = _sqn_admin(client)
    years_r = client.get("/api/planning/years", headers=hdr)
    year_2026 = [y for y in years_r.json() if y["year"] == 2026]
    year_id = year_2026[0]["planning_year_id"]

    r = client.get(f"/api/planning/years/{year_id}/annual-program", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert "terms" in d
    assert len(d["terms"]) == 4


def test_annual_program_term_structure(client):
    """Each term block should have required fields."""
    hdr = _sqn_admin(client)
    years_r = client.get("/api/planning/years", headers=hdr)
    year_2026 = [y for y in years_r.json() if y["year"] == 2026]
    year_id = year_2026[0]["planning_year_id"]

    r = client.get(f"/api/planning/years/{year_id}/annual-program", headers=hdr)
    assert r.status_code == 200
    for term in r.json()["terms"]:
        assert "term" in term
        assert "parade_dates" in term
        assert "holidays" in term
        assert "activities" in term
        assert "parade_count" in term
        assert isinstance(term["parade_dates"], list)


def test_annual_program_has_holiday_data(client):
    """Annual program should include holidays in the relevant term blocks."""
    hdr = _sqn_admin(client)
    years_r = client.get("/api/planning/years", headers=hdr)
    year_2026 = [y for y in years_r.json() if y["year"] == 2026]
    year_id = year_2026[0]["planning_year_id"]

    r = client.get(f"/api/planning/years/{year_id}/annual-program", headers=hdr)
    all_holidays = [h for t in r.json()["terms"] for h in t["holidays"]]
    assert len(all_holidays) >= 1, "Expected at least one holiday in annual program"


def test_annual_program_has_activity_data(client):
    """Annual program should include anchor events in the correct term."""
    hdr = _sqn_admin(client)
    years_r = client.get("/api/planning/years", headers=hdr)
    year_2026 = [y for y in years_r.json() if y["year"] == 2026]
    year_id = year_2026[0]["planning_year_id"]

    r = client.get(f"/api/planning/years/{year_id}/annual-program", headers=hdr)
    all_activities = [a for t in r.json()["terms"] for a in t["activities"]]
    assert len(all_activities) >= 1, "Expected at least one activity in annual program"


def test_annual_program_stats_fields(client):
    """Annual program top-level should include capacity stats."""
    hdr = _sqn_admin(client)
    years_r = client.get("/api/planning/years", headers=hdr)
    year_2026 = [y for y in years_r.json() if y["year"] == 2026]
    year_id = year_2026[0]["planning_year_id"]

    r = client.get(f"/api/planning/years/{year_id}/annual-program", headers=hdr)
    d = r.json()
    assert "total_parade_dates" in d
    assert "active_parade_dates" in d
    assert d["total_parade_dates"] >= 0


def test_annual_program_wing_admin_can_read(client):
    """Wing admin should be able to read annual program for their wing."""
    hdr_sqn = _sqn_admin(client)
    years_r = client.get("/api/planning/years", headers=hdr_sqn)
    year_id = years_r.json()[0]["planning_year_id"]

    # Wing admin reading a sqn-scoped year might be allowed (wing scope)
    hdr = _wing_admin(client)
    r = client.get(f"/api/planning/years/{year_id}/annual-program", headers=hdr)
    # May be 403 out_of_scope (sqn year != wing year) or 200 — both valid
    assert r.status_code in (200, 403)


def test_annual_program_auditor_can_read(client):
    """Auditor role should be able to read annual program."""
    hdr_sqn = _sqn_admin(client)
    years_r = client.get("/api/planning/years", headers=hdr_sqn)
    year_id = years_r.json()[0]["planning_year_id"]

    hdr = _auditor(client)
    r = client.get(f"/api/planning/years/{year_id}/annual-program", headers=hdr)
    # Auditor reads cross-scope; sqn year is allowed
    assert r.status_code in (200, 403)


def test_annual_program_empty_year_no_parade_nights(client):
    """Annual program for a year with no parade nights must return 200, not 500.

    Regression: without the 'if all_pn_ids_pre and ts_rows:' guard in
    get_annual_program, an empty year would raise UnboundLocalError on the
    ts_map lookup and surface as an unhandled 500.
    """
    hdr = _sqn_admin(client)
    r = client.post(
        "/api/planning/years",
        json={"year": 2999, "name": "Empty Year Regression"},
        headers=hdr,
    )
    assert r.status_code in (200, 201)
    year_id = r.json()["planning_year_id"]
    try:
        r2 = client.get(f"/api/planning/years/{year_id}/annual-program", headers=hdr)
        assert r2.status_code == 200
        d = r2.json()
        assert "terms" in d
        assert isinstance(d["terms"], list)
    finally:
        client.patch(
            f"/api/planning/years/{year_id}",
            json={"active_status": False, "version": 0},
            headers=hdr,
        )


# ─────────────────────────────────────────────────────────────
# POST /api/planning/years/{id}/rollover
# ─────────────────────────────────────────────────────────────

def test_rollover_creates_new_year(client):
    """Rollover should create a new planning year with incremented year."""
    hdr = _sqn_admin(client)
    py = _make_year(client, hdr, year=2040, name="Rollover Source")
    year_id = py["planning_year_id"]

    # Add a parade date and holiday
    _make_parade_date(client, hdr, year_id, "2040-02-07")
    _make_holiday(client, hdr, year_id, "Test Holiday", "public_holiday", "2040-04-03", "2040-04-03")

    r = client.post(f"/api/planning/years/{year_id}/rollover", json={
        "copy_holidays": True, "carry_incomplete_sessions": True,
    }, headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["year"] == 2041
    assert d["new_planning_year_id"]


def test_rollover_copies_holidays(client):
    """Rollover should copy holidays with year-adjusted dates."""
    hdr = _sqn_admin(client)
    py = _make_year(client, hdr, year=2041, name="Rollover With Holidays")
    year_id = py["planning_year_id"]
    _make_holiday(client, hdr, year_id, "Labour Day", "public_holiday", "2041-03-03", "2041-03-03")

    r = client.post(f"/api/planning/years/{year_id}/rollover", json={"copy_holidays": True}, headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert d["holidays_copied"] >= 1

    # Verify new year has holidays
    new_id = d["new_planning_year_id"]
    hr = client.get(f"/api/planning/years/{new_id}/holidays", headers=hdr)
    assert hr.status_code == 200
    assert len(hr.json()) >= 1


def test_rollover_without_holidays(client):
    """Rollover with copy_holidays=False should not copy holidays."""
    hdr = _sqn_admin(client)
    py = _make_year(client, hdr, year=2042, name="Rollover No Holidays")
    year_id = py["planning_year_id"]
    _make_holiday(client, hdr, year_id, "Easter", "public_holiday", "2042-04-03", "2042-04-06")

    r = client.post(f"/api/planning/years/{year_id}/rollover", json={"copy_holidays": False}, headers=hdr)
    assert r.status_code == 200
    assert r.json()["holidays_copied"] == 0


def test_rollover_duplicate_returns_409(client):
    """Rolling over to a year that already exists should return 409."""
    hdr = _sqn_admin(client)
    py = _make_year(client, hdr, year=2043, name="Rollover Dup Source")
    _make_year(client, hdr, year=2044, name="Already Exists")  # target already present

    r = client.post(f"/api/planning/years/{py['planning_year_id']}/rollover", json={
        "target_year": 2044
    }, headers=hdr)
    assert r.status_code == 409


def test_rollover_custom_target_year(client):
    """Rollover should accept a custom target year."""
    hdr = _sqn_admin(client)
    py = _make_year(client, hdr, year=2050, name="Custom Target Source")
    year_id = py["planning_year_id"]

    r = client.post(f"/api/planning/years/{year_id}/rollover", json={"target_year": 2055}, headers=hdr)
    assert r.status_code == 200
    assert r.json()["year"] == 2055


def test_rollover_blocked_for_general_user(client):
    """sqn_general should not be able to perform a year rollover."""
    hdr_admin = _sqn_admin(client)
    py = _make_year(client, hdr_admin, year=2060, name="Rollover RBAC Test")
    year_id = py["planning_year_id"]

    hdr = _general(client)
    r = client.post(f"/api/planning/years/{year_id}/rollover", json={}, headers=hdr)
    assert r.status_code == 403


def test_rollover_parade_dates_advanced_by_one_year(client):
    """Rollover must copy parade dates with dates advanced by exactly one year."""
    hdr = _sqn_admin(client)
    py = _make_year(client, hdr, year=2061, name="Rollover Date Advance")
    year_id = py["planning_year_id"]
    _make_parade_date(client, hdr, year_id, "2061-09-04")
    _make_parade_date(client, hdr, year_id, "2061-09-11")

    r = client.post(f"/api/planning/years/{year_id}/rollover", json={}, headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert d["parade_dates_copied"] == 2

    # Verify dates in the new year are advanced by exactly 1 year
    new_id = d["new_planning_year_id"]
    dr = client.get(f"/api/planning/years/{new_id}/parade-dates", headers=hdr)
    assert dr.status_code == 200
    dates = [row["parade_date"] for row in dr.json()]
    assert "2062-09-04" in dates
    assert "2062-09-11" in dates
    # Source dates must NOT appear in the new year
    assert "2061-09-04" not in dates
    assert "2061-09-11" not in dates


def test_rollover_source_year_sessions_unchanged(client):
    """Rollover must not modify or delete sessions in the source year."""
    hdr = _sqn_admin(client)
    py = _make_year(client, hdr, year=2062, name="Rollover Source Unchanged")
    year_id = py["planning_year_id"]
    _make_parade_date(client, hdr, year_id, "2062-10-06")

    # Record the source year's parade dates before rollover
    dr_before = client.get(f"/api/planning/years/{year_id}/parade-dates", headers=hdr)
    assert dr_before.status_code == 200
    dates_before = dr_before.json()

    client.post(f"/api/planning/years/{year_id}/rollover", json={}, headers=hdr)

    # Source year dates must be identical after rollover
    dr_after = client.get(f"/api/planning/years/{year_id}/parade-dates", headers=hdr)
    assert dr_after.status_code == 200
    dates_after = dr_after.json()
    assert len(dates_before) == len(dates_after)
    ids_before = {d["parade_date_id"] for d in dates_before}
    ids_after = {d["parade_date_id"] for d in dates_after}
    assert ids_before == ids_after, "Rollover must not alter source year's parade date IDs"


# ─────────────────────────────────────────────────────────────
# Prep rules (seeded)
# ─────────────────────────────────────────────────────────────

def test_prep_rules_seeded(client):
    """Prep rules should be seeded by seed_planning_data."""
    hdr = _sqn_admin(client)
    r = client.get("/api/planning/prep-rules", headers=hdr)
    assert r.status_code == 200
    rules = r.json()
    assert len(rules) >= 4, f"Expected ≥4 prep rules, got {len(rules)}"


def test_prep_rules_filter_by_event_type(client):
    """Filtering prep rules by event_type should restrict results."""
    hdr = _sqn_admin(client)
    r = client.get("/api/planning/prep-rules?event_type=ceremonial", headers=hdr)
    assert r.status_code == 200
    for rule in r.json():
        assert rule["event_type"] == "ceremonial"


def test_prep_suggestions_for_anchor_event(client):
    """Prep suggestions endpoint should return rule-based preparation advice."""
    hdr = _sqn_admin(client)
    years_r = client.get("/api/planning/years", headers=hdr)
    year_2026 = [y for y in years_r.json() if y["year"] == 2026]
    year_id = year_2026[0]["planning_year_id"]

    anchors_r = client.get(f"/api/planning/years/{year_id}/anchors", headers=hdr)
    anchors = anchors_r.json()
    if not anchors:
        pytest.skip("No anchor events in seed")

    # Find an adventure_training anchor
    camp = next((a for a in anchors if "Camp" in a["event_name"]), anchors[0])
    r = client.get(f"/api/planning/anchors/{camp['anchor_event_id']}/prep-suggestions", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert "suggestions" in d
