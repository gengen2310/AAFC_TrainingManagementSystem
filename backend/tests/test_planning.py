"""Tests for the TRGO Planning Module (V11).

Covers: planning years, parade dates, holidays, anchor events,
term planner, parade night builder, scheduled sessions, locations,
facilitators (planning view), conflict detection, weekly program,
long-range view, decision guide, and RBAC enforcement.
"""
import pytest
from tests.conftest import login


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _sqn_admin_hdr(client):
    return login(client, "ADMIN703")


def _wing_admin_hdr(client):
    return login(client, "ADMIN7WG")


def _nat_admin_hdr(client):
    return login(client, "ADMINNATIONAL")


def _general_hdr(client):
    return login(client, "703SQN2026")


def _auditor_hdr(client):
    return login(client, "AUDITOR2026")


def _make_year(client, hdr):
    r = client.post("/api/planning/years", json={"year": 2026, "name": "2026 Training Year"}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


# ─────────────────────────────────────────────────────────────
# Planning Years — RBAC
# ─────────────────────────────────────────────────────────────

def test_sqn_admin_can_create_planning_year(client):
    hdr = _sqn_admin_hdr(client)
    r = client.post("/api/planning/years", json={"year": 2027, "name": "2027 Year"}, headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert d["year"] == 2027
    assert d["planning_year_id"]
    assert d["unit_id"] is not None


def test_wing_admin_can_create_planning_year(client):
    hdr = _wing_admin_hdr(client)
    r = client.post("/api/planning/years", json={"year": 2027, "name": "Wing 2027"}, headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert d["wing_id"] is not None


def test_nat_admin_can_create_planning_year(client):
    hdr = _nat_admin_hdr(client)
    r = client.post("/api/planning/years", json={"year": 2027, "name": "NAT 2027"}, headers=hdr)
    assert r.status_code == 200


def test_general_cannot_create_planning_year(client):
    hdr = _general_hdr(client)
    r = client.post("/api/planning/years", json={"year": 2027, "name": "x"}, headers=hdr)
    assert r.status_code == 403


def test_auditor_cannot_create_planning_year(client):
    hdr = _auditor_hdr(client)
    r = client.post("/api/planning/years", json={"year": 2027, "name": "x"}, headers=hdr)
    assert r.status_code == 403


def test_sqn_admin_can_list_own_planning_years(client):
    hdr = _sqn_admin_hdr(client)
    r = client.get("/api/planning/years", headers=hdr)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)


def test_sqn_admin_can_patch_own_planning_year(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.patch(f"/api/planning/years/{yr_id}", json={"name": "Updated Name"}, headers=hdr)
    assert r.status_code == 200
    assert r.json()["name"] == "Updated Name"


def test_get_nonexistent_year_returns_404(client):
    hdr = _sqn_admin_hdr(client)
    r = client.get("/api/planning/years/nonexistent-id", headers=hdr)
    assert r.status_code == 404


# ─────────────────────────────────────────────────────────────
# Parade Dates
# ─────────────────────────────────────────────────────────────

def test_sqn_admin_can_add_parade_date(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.post(
        f"/api/planning/years/{yr_id}/parade-dates",
        json={"parade_date": "2026-09-11", "parade_type": "standard"},
        headers=hdr,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["parade_date"] == "2026-09-11"
    assert d["parade_date_id"]


def test_can_list_parade_dates(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    client.post(f"/api/planning/years/{yr_id}/parade-dates",
                json={"parade_date": "2026-10-02"}, headers=hdr)
    r = client.get(f"/api/planning/years/{yr_id}/parade-dates", headers=hdr)
    assert r.status_code == 200
    rows = r.json()
    assert any(x["parade_date"] == "2026-10-02" for x in rows)


def test_generate_parade_dates(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.post(
        f"/api/planning/years/{yr_id}/generate-parade-dates",
        json={
            "weekday": 4,          # Friday
            "start_date": "2026-08-01",
            "end_date": "2026-10-31",
            "exclude_holidays": False,
        },
        headers=hdr,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert d["created"] > 0
    assert all(len(dt) == 10 for dt in d["dates"])


def test_generate_parade_dates_invalid_format(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.post(
        f"/api/planning/years/{yr_id}/generate-parade-dates",
        json={"weekday": 4, "start_date": "not-a-date", "end_date": "2026-10-31"},
        headers=hdr,
    )
    assert r.status_code == 400


def test_general_cannot_delete_parade_date(client):
    sqn_hdr = _sqn_admin_hdr(client)
    year = _make_year(client, sqn_hdr)
    yr_id = year["planning_year_id"]
    rp = client.post(f"/api/planning/years/{yr_id}/parade-dates",
                     json={"parade_date": "2026-11-06"}, headers=sqn_hdr)
    pd_id = rp.json()["parade_date_id"]
    r = client.delete(f"/api/planning/parade-dates/{pd_id}", headers=_general_hdr(client))
    assert r.status_code == 403


def test_sqn_admin_can_delete_parade_date(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    rp = client.post(f"/api/planning/years/{yr_id}/parade-dates",
                     json={"parade_date": "2026-12-04"}, headers=hdr)
    pd_id = rp.json()["parade_date_id"]
    r = client.delete(f"/api/planning/parade-dates/{pd_id}", headers=hdr)
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ─────────────────────────────────────────────────────────────
# Holidays
# ─────────────────────────────────────────────────────────────

def test_sqn_admin_can_add_holiday(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.post(
        f"/api/planning/years/{yr_id}/holidays",
        json={"name": "Christmas", "start_date": "2026-12-21", "end_date": "2027-01-11"},
        headers=hdr,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["name"] == "Christmas"
    assert d["holiday_id"]


def test_holidays_listed_for_year(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    client.post(f"/api/planning/years/{yr_id}/holidays",
                json={"name": "Easter", "start_date": "2026-04-02", "end_date": "2026-04-17"},
                headers=hdr)
    r = client.get(f"/api/planning/years/{yr_id}/holidays", headers=hdr)
    assert r.status_code == 200
    assert any(h["name"] == "Easter" for h in r.json())


def test_holiday_conflict_flagged_on_parade_date(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    # Add holiday
    client.post(f"/api/planning/years/{yr_id}/holidays",
                json={"name": "School Hols", "start_date": "2026-09-18",
                      "end_date": "2026-10-02", "affects_parade": True},
                headers=hdr)
    # Add parade date inside holiday window
    rp = client.post(f"/api/planning/years/{yr_id}/parade-dates",
                     json={"parade_date": "2026-09-25"}, headers=hdr)
    pd_id = rp.json()["parade_date_id"]
    # Run checks
    client.post(f"/api/planning/years/{yr_id}/run-checks", headers=hdr)
    # Confirm conflict exists
    r = client.get(f"/api/planning/years/{yr_id}/conflicts", headers=hdr)
    assert r.status_code == 200
    types = [c["conflict_type"] for c in r.json()]
    assert "holiday_conflict" in types


# ─────────────────────────────────────────────────────────────
# Anchor Events
# ─────────────────────────────────────────────────────────────

def test_sqn_admin_can_create_anchor_event(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.post(
        f"/api/planning/years/{yr_id}/anchors",
        json={
            "event_name": "Annual Inspection",
            "event_type": "inspection",
            "importance": "must_attend",
            "start_date": "2026-11-15",
        },
        headers=hdr,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["event_name"] == "Annual Inspection"
    assert d["importance"] == "must_attend"
    assert d["anchor_event_id"]


def test_anchor_events_listed(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    client.post(f"/api/planning/years/{yr_id}/anchors",
                json={"event_name": "Wing Day", "event_type": "ceremonial",
                      "importance": "key_event", "start_date": "2026-10-10"},
                headers=hdr)
    r = client.get(f"/api/planning/years/{yr_id}/anchors", headers=hdr)
    assert r.status_code == 200
    names = [a["event_name"] for a in r.json()]
    assert "Wing Day" in names


def test_anchor_event_update(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    ra = client.post(f"/api/planning/years/{yr_id}/anchors",
                     json={"event_name": "Initial Event", "event_type": "community",
                           "importance": "optional", "start_date": "2026-08-20"},
                     headers=hdr)
    ae_id = ra.json()["anchor_event_id"]
    r = client.patch(f"/api/planning/anchors/{ae_id}",
                     json={"importance": "key_event"}, headers=hdr)
    assert r.status_code == 200
    assert r.json()["importance"] == "key_event"


def test_anchor_event_archive(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    ra = client.post(f"/api/planning/years/{yr_id}/anchors",
                     json={"event_name": "To Archive", "event_type": "other",
                           "importance": "optional", "start_date": "2026-07-01"},
                     headers=hdr)
    ae_id = ra.json()["anchor_event_id"]
    r = client.delete(f"/api/planning/anchors/{ae_id}", headers=hdr)
    assert r.status_code == 200
    # Should not appear in listing
    r2 = client.get(f"/api/planning/years/{yr_id}/anchors", headers=hdr)
    ids = [a["anchor_event_id"] for a in r2.json()]
    assert ae_id not in ids


def test_general_cannot_create_anchor_event(client):
    sqn_hdr = _sqn_admin_hdr(client)
    year = _make_year(client, sqn_hdr)
    yr_id = year["planning_year_id"]
    r = client.post(f"/api/planning/years/{yr_id}/anchors",
                    json={"event_name": "X", "event_type": "other",
                          "importance": "optional", "start_date": "2026-08-01"},
                    headers=_general_hdr(client))
    assert r.status_code == 403


def test_prep_suggestions_returned(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    ra = client.post(f"/api/planning/years/{yr_id}/anchors",
                     json={"event_name": "Fieldcraft Weekend", "event_type": "fieldcraft",
                           "importance": "key_event", "start_date": "2026-10-03"},
                     headers=hdr)
    ae_id = ra.json()["anchor_event_id"]
    r = client.get(f"/api/planning/anchors/{ae_id}/prep-suggestions", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert "anchor_event_id" in d
    assert isinstance(d["suggestions"], list)


# ─────────────────────────────────────────────────────────────
# Term Planner
# ─────────────────────────────────────────────────────────────

def test_term_planner_returns_structure(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.get(f"/api/planning/years/{yr_id}/term-planner", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert "parade_dates" in d
    assert "anchors" in d
    assert "sessions_by_parade_date" in d
    assert "session_capacity" in d


def test_term_planner_accepts_term_param(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.get(f"/api/planning/years/{yr_id}/term-planner?term=2", headers=hdr)
    assert r.status_code == 200
    assert r.json()["term"] == 2


# ─────────────────────────────────────────────────────────────
# Locations
# ─────────────────────────────────────────────────────────────

def test_sqn_admin_can_create_location(client):
    hdr = _sqn_admin_hdr(client)
    r = client.post("/api/planning/locations",
                    json={"name": "Main Hall", "location_type": "indoor", "capacity": 60},
                    headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert d["name"] == "Main Hall"
    assert d["location_id"]


def test_general_cannot_create_location(client):
    r = client.post("/api/planning/locations",
                    json={"name": "X", "location_type": "indoor"},
                    headers=_general_hdr(client))
    assert r.status_code == 403


def test_locations_listed(client):
    hdr = _sqn_admin_hdr(client)
    client.post("/api/planning/locations",
                json={"name": "Gym", "location_type": "indoor", "capacity": 80}, headers=hdr)
    r = client.get("/api/planning/locations", headers=hdr)
    assert r.status_code == 200
    names = [l["name"] for l in r.json()]
    assert "Gym" in names


def test_location_update(client):
    hdr = _sqn_admin_hdr(client)
    rl = client.post("/api/planning/locations",
                     json={"name": "Old Room", "location_type": "indoor"}, headers=hdr)
    loc_id = rl.json()["location_id"]
    r = client.patch(f"/api/planning/locations/{loc_id}",
                     json={"capacity": 40}, headers=hdr)
    assert r.status_code == 200
    assert r.json()["capacity"] == 40


# ─────────────────────────────────────────────────────────────
# Parade Night Builder / Scheduled Sessions
# ─────────────────────────────────────────────────────────────

def _setup_year_with_date(client, hdr):
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    rp = client.post(f"/api/planning/years/{yr_id}/parade-dates",
                     json={"parade_date": "2026-09-04"}, headers=hdr)
    pd_id = rp.json()["parade_date_id"]
    return yr_id, pd_id


def test_sqn_admin_can_create_scheduled_session(client):
    hdr = _sqn_admin_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, hdr)
    r = client.post(
        f"/api/planning/parade-dates/{pd_id}/sessions",
        json={"cadet_group": "junior", "session_number": 1,
              "activity_title": "Drill Practice"},
        headers=hdr,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["cadet_group"] == "junior"
    assert d["activity_title"] == "Drill Practice"


def test_invalid_cadet_group_returns_422(client):
    hdr = _sqn_admin_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, hdr)
    r = client.post(
        f"/api/planning/parade-dates/{pd_id}/sessions",
        json={"cadet_group": "not_a_real_group", "session_number": 1},
        headers=hdr,
    )
    assert r.status_code == 422


def test_session_with_notes_succeeds(client):
    """Sessions can be created with notes (replaces legacy override_conflict validation)."""
    hdr = _sqn_admin_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, hdr)
    r = client.post(
        f"/api/planning/parade-dates/{pd_id}/sessions",
        json={"cadet_group": "senior", "session_number": 2,
              "notes": "CO directed combined run"},
        headers=hdr,
    )
    assert r.status_code == 200


def test_general_cannot_create_scheduled_session(client):
    sqn_hdr = _sqn_admin_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, sqn_hdr)
    r = client.post(
        f"/api/planning/parade-dates/{pd_id}/sessions",
        json={"cadet_group": "initial", "session_number": 1},
        headers=_general_hdr(client),
    )
    assert r.status_code == 403


def test_scheduled_session_update(client):
    hdr = _sqn_admin_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, hdr)
    rs = client.post(f"/api/planning/parade-dates/{pd_id}/sessions",
                     json={"cadet_group": "initial", "session_number": 1}, headers=hdr)
    sess_id = rs.json()["session_id"]
    r = client.patch(f"/api/planning/sessions/{sess_id}",
                     json={"activity_title": "Map Reading"}, headers=hdr)
    assert r.status_code == 200
    assert r.json()["activity_title"] == "Map Reading"


def test_scheduled_session_soft_delete(client):
    hdr = _sqn_admin_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, hdr)
    rs = client.post(f"/api/planning/parade-dates/{pd_id}/sessions",
                     json={"cadet_group": "orientation", "session_number": 3}, headers=hdr)
    sess_id = rs.json()["session_id"]
    r = client.delete(f"/api/planning/sessions/{sess_id}", headers=hdr)
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_builder_endpoint_returns_sessions_and_conflicts(client):
    hdr = _sqn_admin_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, hdr)
    r = client.get(f"/api/planning/parade-dates/{pd_id}/builder", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert "sessions" in d
    assert "conflicts" in d
    assert "cadet_groups" in d
    assert len(d["cadet_groups"]) == 5


# ─────────────────────────────────────────────────────────────
# Weekly Program
# ─────────────────────────────────────────────────────────────

def test_weekly_program_endpoint(client):
    hdr = _sqn_admin_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, hdr)
    r = client.get(f"/api/planning/parade-dates/{pd_id}/weekly-program", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert "sessions" in d
    assert "timing_blocks" in d
    assert "has_unresolved_conflicts" in d


def test_auditor_can_view_weekly_program(client):
    sqn_hdr = _sqn_admin_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, sqn_hdr)
    r = client.get(f"/api/planning/parade-dates/{pd_id}/weekly-program",
                   headers=_auditor_hdr(client))
    assert r.status_code == 200


# ─────────────────────────────────────────────────────────────
# Long Range View
# ─────────────────────────────────────────────────────────────

def test_long_range_view_returns_structure(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.get(f"/api/planning/years/{yr_id}/long-range?weeks=4", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert "parade_dates" in d
    assert "anchors" in d
    assert "from_date" in d
    assert d["weeks"] == 4


def test_long_range_accepts_from_date(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.get(f"/api/planning/years/{yr_id}/long-range?from_date=2026-09-01&weeks=8",
                   headers=hdr)
    assert r.status_code == 200
    assert r.json()["from_date"] == "2026-09-01"


# ─────────────────────────────────────────────────────────────
# Conflict Detection
# ─────────────────────────────────────────────────────────────

def test_facilitator_double_booking_detected(client):
    hdr = _sqn_admin_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, hdr)
    # Get a facilitator from backend
    facs = client.get("/api/planning/facilitators", headers=hdr).json()
    if not facs:
        pytest.skip("No facilitators seeded")
    fac_id = facs[0]["facilitator_id"]
    # Assign same facilitator to two groups in session 1
    client.post(f"/api/planning/parade-dates/{pd_id}/sessions",
                json={"cadet_group": "junior", "session_number": 1,
                      "facilitator_id": fac_id}, headers=hdr)
    client.post(f"/api/planning/parade-dates/{pd_id}/sessions",
                json={"cadet_group": "initial", "session_number": 1,
                      "facilitator_id": fac_id}, headers=hdr)
    r = client.get(f"/api/planning/years/{yr_id}/conflicts", headers=hdr)
    assert r.status_code == 200
    types = [c["conflict_type"] for c in r.json()]
    assert "facilitator_double_booked" in types


def test_run_checks_returns_count(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.post(f"/api/planning/years/{yr_id}/run-checks", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert "conflicts_detected" in d
    assert isinstance(d["conflicts_detected"], int)


def test_conflict_override_requires_reason(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    client.post(f"/api/planning/years/{yr_id}/parade-dates",
                json={"parade_date": "2026-10-09"}, headers=hdr)
    client.post(f"/api/planning/years/{yr_id}/run-checks", headers=hdr)
    conflicts = client.get(f"/api/planning/years/{yr_id}/conflicts", headers=hdr).json()
    if not conflicts:
        pytest.skip("No conflicts to override")
    c_id = conflicts[0]["conflict_id"]
    r = client.post(f"/api/planning/conflicts/{c_id}/override",
                    json={"override_reason": ""}, headers=hdr)
    assert r.status_code == 422


def test_conflict_override_with_reason(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    client.post(f"/api/planning/years/{yr_id}/parade-dates",
                json={"parade_date": "2026-10-16"}, headers=hdr)
    client.post(f"/api/planning/years/{yr_id}/run-checks", headers=hdr)
    conflicts = client.get(f"/api/planning/years/{yr_id}/conflicts", headers=hdr).json()
    if not conflicts:
        pytest.skip("No conflicts present")
    c_id = conflicts[0]["conflict_id"]
    r = client.post(f"/api/planning/conflicts/{c_id}/override",
                    json={"override_reason": "CO approved, public holiday observed elsewhere"},
                    headers=hdr)
    assert r.status_code == 200
    assert r.json()["ok"] is True


# ─────────────────────────────────────────────────────────────
# Decision Guide
# ─────────────────────────────────────────────────────────────

def test_decision_guide_returns_checks(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.get(f"/api/planning/years/{yr_id}/decision-guide", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert "checks" in d
    assert isinstance(d["checks"], list)
    rules = [c["rule"] for c in d["checks"]]
    assert 10 in rules  # readiness check


def test_decision_guide_with_date_id(client):
    hdr = _sqn_admin_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, hdr)
    r = client.get(f"/api/planning/years/{yr_id}/decision-guide?date_id={pd_id}",
                   headers=hdr)
    assert r.status_code == 200
    d = r.json()
    rules = [c["rule"] for c in d["checks"]]
    assert 3 in rules  # unscheduled groups check


# ─────────────────────────────────────────────────────────────
# Facilitators (planning view)
# ─────────────────────────────────────────────────────────────

def test_facilitators_planning_view(client):
    hdr = _sqn_admin_hdr(client)
    r = client.get("/api/planning/facilitators", headers=hdr)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    if data:
        f = data[0]
        assert "facilitator_id" in f
        assert "display_name" in f
        assert "subject_areas" in f
        assert "max_sessions_per_night" in f


def test_wing_admin_sees_wing_facilitators(client):
    hdr = _wing_admin_hdr(client)
    r = client.get("/api/planning/facilitators", headers=hdr)
    assert r.status_code == 200


# ─────────────────────────────────────────────────────────────
# Prep Rules
# ─────────────────────────────────────────────────────────────

def test_prep_rules_listed(client):
    hdr = _sqn_admin_hdr(client)
    r = client.get("/api/planning/prep-rules", headers=hdr)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_prep_rules_filtered_by_event_type(client):
    hdr = _sqn_admin_hdr(client)
    r = client.get("/api/planning/prep-rules?event_type=fieldcraft", headers=hdr)
    assert r.status_code == 200
    data = r.json()
    for rule in data:
        assert rule["event_type"] == "fieldcraft"


# ─────────────────────────────────────────────────────────────
# Wing admin RBAC scope enforcement
# ─────────────────────────────────────────────────────────────

def test_wing_admin_can_view_sqn_planning_years(client):
    sqn_hdr = _sqn_admin_hdr(client)
    year = _make_year(client, sqn_hdr)
    wing_hdr = _wing_admin_hdr(client)
    # wing admin lists all their wing's years — should not error
    r = client.get("/api/planning/years", headers=wing_hdr)
    assert r.status_code == 200


def test_nat_admin_can_list_all_years(client):
    r = client.get("/api/planning/years", headers=_nat_admin_hdr(client))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_unauthenticated_request_rejected(client):
    r = client.get("/api/planning/years")
    assert r.status_code in (401, 403)


# ─────────────────────────────────────────────────────────────
# V12 Integration Tests: planning ↔ real parade nights/sessions
# ─────────────────────────────────────────────────────────────

def test_add_parade_date_creates_parade_night_link(client):
    """Adding a parade date must create and link a real ParadeNight record."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.post(f"/api/planning/years/{yr_id}/parade-dates",
                    json={"parade_date": "2026-11-06"}, headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert d["parade_night_id"] is not None, "parade_night_id must be set after creation"


def test_generate_parade_dates_links_parade_nights(client):
    """Generated parade dates must all carry a parade_night_id."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.post(f"/api/planning/years/{yr_id}/generate-parade-dates",
                    json={"weekday": 4, "start_date": "2026-09-01", "end_date": "2026-10-31"},
                    headers=hdr)
    assert r.status_code == 200
    assert r.json()["created"] > 0
    dates = client.get(f"/api/planning/years/{yr_id}/parade-dates", headers=hdr).json()
    for d in dates:
        assert d["parade_night_id"] is not None, f"Date {d['parade_date']} missing parade_night_id"


def test_planning_session_creates_real_session(client):
    """Session created via planning builder must appear in the real parade night."""
    hdr = _sqn_admin_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, hdr)
    # Get the linked parade night id
    pd_data = client.get(f"/api/planning/years/{yr_id}/parade-dates", headers=hdr).json()
    linked = next((d for d in pd_data if d["parade_date_id"] == pd_id), None)
    assert linked and linked["parade_night_id"], "Parade date must be linked to a real parade night"
    pnid = linked["parade_night_id"]
    # Create a session via planning
    rs = client.post(f"/api/planning/parade-dates/{pd_id}/sessions",
                     json={"cadet_group": "junior", "session_number": 1,
                           "activity_title": "Navigation"}, headers=hdr)
    assert rs.status_code == 200
    sess_id = rs.json()["session_id"]
    # Session must appear in the real parade night endpoint
    pn_resp = client.get(f"/api/parade-nights/{pnid}", headers=hdr)
    assert pn_resp.status_code == 200
    sessions_in_pn = [s["id"] for s in pn_resp.json().get("sessions", [])]
    assert sess_id in sessions_in_pn, "Session created via planning must appear in real parade night"


def test_builder_returns_real_sessions(client):
    """Builder grid must contain sessions created via planning API."""
    hdr = _sqn_admin_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, hdr)
    client.post(f"/api/planning/parade-dates/{pd_id}/sessions",
                json={"cadet_group": "initial", "session_number": 2,
                      "activity_title": "First Aid"}, headers=hdr)
    r = client.get(f"/api/planning/parade-dates/{pd_id}/builder", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    sessions = d["sessions"]
    assert any(s["cadet_group"] == "initial" and s["activity_title"] == "First Aid"
               for s in sessions), "Builder must show the session in the grid"


def test_weekly_program_uses_real_sessions(client):
    """Weekly program must show sessions from the real parade night."""
    hdr = _sqn_admin_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, hdr)
    client.post(f"/api/planning/parade-dates/{pd_id}/sessions",
                json={"cadet_group": "senior", "session_number": 1,
                      "activity_title": "Leadership Study"}, headers=hdr)
    r = client.get(f"/api/planning/parade-dates/{pd_id}/weekly-program", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    sessions = d["sessions"]
    assert any(s["cadet_group"] == "senior" and s["activity_title"] == "Leadership Study"
               for s in sessions), "Weekly program must show the real session"


def test_parade_night_builder_endpoint_returns_timing_blocks(client):
    """GET /api/parade-nights/{id}/builder returns timing blocks and sessions."""
    hdr = _sqn_admin_hdr(client)
    # Create a parade night directly
    pn_r = client.post("/api/parade-nights",
                       json={"date": "2027-02-05", "term": "T4"}, headers=hdr)
    assert pn_r.status_code == 200
    pnid = pn_r.json()["parade_night_id"]
    r = client.get(f"/api/parade-nights/{pnid}/builder", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert "session_count" in d
    assert "cadet_groups" in d
    assert "sessions" in d
    assert "timing_blocks" in d
    assert d["parade_night_id"] == pnid


def test_wing_curriculum_visible_to_sqn(client):
    """Wing curriculum created by wing admin must be visible to squadron users."""
    wing_hdr = _wing_admin_hdr(client)
    sqn_hdr = _sqn_admin_hdr(client)
    r = client.post("/api/curriculum/wing",
                    json={"code": "7WG-TEST-V12", "title": "V12 Wing Integration Test",
                          "phase": "B. Initial", "element": "Ground School",
                          "duration_minutes": 60},
                    headers=wing_hdr)
    assert r.status_code == 200
    curr_list = client.get("/api/curriculum", headers=sqn_hdr).json()
    codes = [c["code"] for c in curr_list.get("items", [])]
    assert "7WG-TEST-V12" in codes, "Wing curriculum must be visible to squadron admin"


def test_national_curriculum_visible_to_wing_and_sqn(client):
    """National curriculum must be visible to both wing and squadron users."""
    nat_hdr = _nat_admin_hdr(client)
    wing_hdr = _wing_admin_hdr(client)
    sqn_hdr = _sqn_admin_hdr(client)
    r = client.post("/api/curriculum/national",
                    json={"code": "NAT-V12-TEST", "title": "V12 National Visibility Test",
                          "phase": "C. Junior", "duration_minutes": 90},
                    headers=nat_hdr)
    assert r.status_code == 200
    for role_hdr in [wing_hdr, sqn_hdr]:
        curr_list = client.get("/api/curriculum", headers=role_hdr).json()
        codes = [c["code"] for c in curr_list.get("items", [])]
        assert "NAT-V12-TEST" in codes, "National curriculum must be visible to all roles"


# ─────────────────────────────────────────────────────────────
# V12 Seed & Timing Template Tests
# ─────────────────────────────────────────────────────────────

def test_703_default_timing_template_seeded(client):
    """seed_all must create an active default timing template for 703 SQN."""
    hdr = _sqn_admin_hdr(client)
    r = client.get("/api/timing-templates", headers=hdr)
    assert r.status_code == 200
    templates = r.json() if isinstance(r.json(), list) else r.json().get("templates", [])
    defaults = [t for t in templates if t.get("is_default")]
    assert len(defaults) >= 1, "At least one default timing template must exist for 703 SQN"
    t = defaults[0]
    assert t["active_status"] is True
    assert t["effective_from"] <= "2026-01-01"


def test_703_timing_template_has_three_instructional_periods(client):
    """The seeded 703 timing template must have exactly 3 instructional periods (Period 1, 2, 3)."""
    hdr = _sqn_admin_hdr(client)
    r = client.get("/api/timing-templates", headers=hdr)
    assert r.status_code == 200
    templates = r.json() if isinstance(r.json(), list) else r.json().get("templates", [])
    defaults = [t for t in templates if t.get("is_default")]
    assert defaults, "No default template found"
    blocks = defaults[0].get("blocks", [])
    ips = [b for b in blocks if b.get("is_instructional_period")]
    assert len(ips) == 3, f"Expected 3 instructional periods, got {len(ips)}"
    ip_names = {b["block_name"] for b in ips}
    assert "Period 1" in ip_names
    assert "Period 2" in ip_names
    assert "Period 3" in ip_names


def test_703_timing_template_period_numbers_correct(client):
    """Instructional periods must have period_number 1, 2, 3 respectively."""
    hdr = _sqn_admin_hdr(client)
    r = client.get("/api/timing-templates", headers=hdr)
    assert r.status_code == 200
    templates = r.json() if isinstance(r.json(), list) else r.json().get("templates", [])
    defaults = [t for t in templates if t.get("is_default")]
    assert defaults, "No default template found"
    blocks = defaults[0].get("blocks", [])
    ips = sorted([b for b in blocks if b.get("is_instructional_period")], key=lambda b: b.get("period_number") or 0)
    assert [b["period_number"] for b in ips] == [1, 2, 3]


def test_parade_night_links_timing_template_after_seed(client):
    """Creating a parade night for 703 on a fresh seeded DB links to the default timing template."""
    hdr = _sqn_admin_hdr(client)
    pn_r = client.post("/api/parade-nights",
                       json={"date": "2027-01-15", "term": "T3"}, headers=hdr)
    assert pn_r.status_code == 200
    pnid = pn_r.json()["parade_night_id"]
    r = client.get(f"/api/parade-nights/{pnid}/builder", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert d["timing_template_id"] is not None, "timing_template_id must be set for 703 SQN parade nights"
    assert d["session_count"] == 3


def test_builder_returns_nonempty_timing_blocks(client):
    """Builder for a 703 parade night must return all 12 timing blocks."""
    hdr = _sqn_admin_hdr(client)
    pn_r = client.post("/api/parade-nights",
                       json={"date": "2027-01-22", "term": "T3"}, headers=hdr)
    assert pn_r.status_code == 200
    pnid = pn_r.json()["parade_night_id"]
    r = client.get(f"/api/parade-nights/{pnid}/builder", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    blocks = d["timing_blocks"]
    assert len(blocks) == 12, f"Expected 12 timing blocks, got {len(blocks)}"
    ips = [b for b in blocks if b.get("is_instructional_period")]
    assert len(ips) == 3
    assert all(b.get("period_number") is not None for b in ips), "Instructional blocks must have period_number"
    assert all(b.get("start_time") is not None for b in ips), "Instructional blocks must have start_time"
    assert all(b.get("end_time") is not None for b in ips), "Instructional blocks must have end_time"


def test_planning_session_persists_in_weekly_program(client):
    """Session created via planning API must appear in the Weekly Program for that date."""
    hdr = _sqn_admin_hdr(client)
    year_r = client.post("/api/planning/years",
                         json={"year": 2026, "name": "V12 Timing Test Year"}, headers=hdr)
    assert year_r.status_code == 200
    year_id = year_r.json()["planning_year_id"]
    date_r = client.post(f"/api/planning/years/{year_id}/parade-dates",
                         json={"parade_date": "2026-11-20"}, headers=hdr)
    assert date_r.status_code == 200
    d = date_r.json()
    pd_id = d["parade_date_id"]
    assert d.get("parade_night_id") is not None, "parade_night_id must be set after adding parade date"
    sess_r = client.post(f"/api/planning/parade-dates/{pd_id}/sessions",
                         json={"cadet_group": "junior", "session_number": 1,
                               "activity_title": "V12 Nav Test"},
                         headers=hdr)
    assert sess_r.status_code == 200
    wp = client.get(f"/api/planning/parade-dates/{pd_id}/weekly-program", headers=hdr).json()
    assert any(s.get("activity_title") == "V12 Nav Test" for s in wp.get("sessions", [])), \
        "Session must appear in Weekly Program"


def test_planning_session_appears_in_long_range(client):
    """Session created via planning API must appear in the Long Range View for the same year."""
    from datetime import date, timedelta
    hdr = _sqn_admin_hdr(client)
    year_r = client.post("/api/planning/years",
                         json={"year": 2026, "name": "V12 Long Range Test"}, headers=hdr)
    assert year_r.status_code == 200
    year_id = year_r.json()["planning_year_id"]
    # Use a date 4 weeks from today so it's always within the 20-week long-range window
    target_date = (date.today() + timedelta(weeks=4)).isoformat()
    date_r = client.post(f"/api/planning/years/{year_id}/parade-dates",
                         json={"parade_date": target_date}, headers=hdr)
    assert date_r.status_code == 200
    pd_id = date_r.json()["parade_date_id"]
    client.post(f"/api/planning/parade-dates/{pd_id}/sessions",
                json={"cadet_group": "senior", "session_number": 2, "activity_title": "V12 Long Range Sess"},
                headers=hdr)
    lr = client.get(f"/api/planning/years/{year_id}/long-range?weeks=8", headers=hdr).json()
    all_sessions = [s for row in lr.get("parade_dates", []) for s in row.get("sessions", [])]
    assert any(s.get("activity_title") == "V12 Long Range Sess" for s in all_sessions), \
        "Session must appear in Long Range View"


# ─────────────────────────────────────────────────────────────
# V12 auth/me wing_code tests
# ────────────────────���───────────────────────────��────────────

def test_wing_admin_auth_me_returns_wing_id(client):
    """GET /api/auth/me for wing_admin must return wing_id (not None)."""
    hdr = _wing_admin_hdr(client)
    r = client.get("/api/auth/me", headers=hdr)
    assert r.status_code == 200
    session = r.json()["session"]
    assert session["wing_id"] is not None, "wing_id must be set for wing_admin"
    assert session["role"] == "wing_admin"


def test_wing_admin_auth_me_returns_wing_code(client):
    """GET /api/auth/me for wing_admin must return wing_code = '7WG'."""
    hdr = _wing_admin_hdr(client)
    r = client.get("/api/auth/me", headers=hdr)
    assert r.status_code == 200
    session = r.json()["session"]
    assert session.get("wing_code") == "7WG", \
        f"wing_code must be '7WG' for ADMIN7WG, got {session.get('wing_code')}"


def test_sqn_admin_auth_me_returns_wing_code(client):
    """GET /api/auth/me for sqn_admin must also return the wing_code of their wing."""
    hdr = _sqn_admin_hdr(client)
    r = client.get("/api/auth/me", headers=hdr)
    assert r.status_code == 200
    session = r.json()["session"]
    assert session.get("wing_code") == "7WG", \
        f"wing_code must be '7WG' for ADMIN703 (under 7 Wing), got {session.get('wing_code')}"
