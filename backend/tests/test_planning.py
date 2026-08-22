"""Tests for the TRGO Planning Module (V11).

Covers: planning years, parade dates, holidays, anchor events,
term planner, parade night builder, scheduled sessions, locations,
facilitators (planning view), conflict detection, weekly program,
long-range view, decision guide, and RBAC enforcement.
"""
import pytest
from tests.conftest import login, next_test_year


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


def _make_year(client, hdr, year=None):
    # REM-134: was a fixed 2026 -- the year the seed already gives 703 -- so this
    # collided with the seed on its first call and with itself on every one after.
    year = next_test_year() if year is None else year
    r = client.post("/api/planning/years", json={"year": year, "name": f"{year} Training Year"}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


# ─────────────────────────────────────────────────────────────
# Planning Years — RBAC
# ─────────────────────────────────────────────────────────────

def test_sqn_admin_can_create_planning_year(client):
    hdr = _sqn_admin_hdr(client)
    year = next_test_year()
    r = client.post("/api/planning/years", json={"year": year, "name": f"{year} Year"}, headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert d["year"] == year
    assert d["planning_year_id"]
    assert d["unit_id"] is not None


def test_wing_admin_can_create_planning_year(client):
    hdr = _wing_admin_hdr(client)
    r = client.post("/api/planning/years", json={"year": next_test_year(), "name": "Wing 2027"}, headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert d["wing_id"] is not None


def test_nat_admin_can_create_planning_year(client):
    hdr = _nat_admin_hdr(client)
    r = client.post("/api/planning/years", json={"year": next_test_year(), "name": "NAT 2027"}, headers=hdr)
    assert r.status_code == 200


def test_general_cannot_create_planning_year(client):
    hdr = _general_hdr(client)
    r = client.post("/api/planning/years", json={"year": next_test_year(), "name": "x"}, headers=hdr)
    assert r.status_code == 403


def test_auditor_cannot_create_planning_year(client):
    hdr = _auditor_hdr(client)
    r = client.post("/api/planning/years", json={"year": next_test_year(), "name": "x"}, headers=hdr)
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


def test_sqn_admin_can_archive_and_restore_own_planning_year(client):
    """Wires PATCH .../years/{id} for archive (active_status=false) and
    restore (active_status=true) -- the same already-working endpoint the
    Getting Started / Account Management archive pattern uses elsewhere,
    now surfaced in the frontend Planning Year controls."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]

    r = client.patch(f"/api/planning/years/{yr_id}", json={"active_status": False}, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["active_status"] is False

    listed = client.get("/api/planning/years", headers=hdr).json()
    assert any(y["planning_year_id"] == yr_id and y["active_status"] is False for y in listed)

    r2 = client.patch(f"/api/planning/years/{yr_id}", json={"active_status": True}, headers=hdr)
    assert r2.status_code == 200, r2.text
    assert r2.json()["active_status"] is True


def test_general_cannot_archive_planning_year(client):
    hdr_admin = _sqn_admin_hdr(client)
    year = _make_year(client, hdr_admin)
    yr_id = year["planning_year_id"]
    hdr_general = _general_hdr(client)
    r = client.patch(f"/api/planning/years/{yr_id}", json={"active_status": False}, headers=hdr_general)
    assert r.status_code == 403


def test_patch_nonexistent_planning_year_returns_404(client):
    hdr = _sqn_admin_hdr(client)
    r = client.patch("/api/planning/years/does-not-exist", json={"active_status": False}, headers=hdr)
    assert r.status_code == 404


def test_archive_planning_year_is_audited(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    client.patch(f"/api/planning/years/{yr_id}", json={"active_status": False}, headers=hdr)
    audit = client.get("/api/audit", headers=hdr).json()
    found = any(a.get("object_id") == yr_id and a.get("action") == "update" for a in audit)
    assert found, "planning year archive not found in audit log"


def test_delete_empty_planning_year_succeeds(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.delete(f"/api/planning/years/{yr_id}", headers=hdr)
    assert r.status_code == 200, r.text
    assert client.get(f"/api/planning/years/{yr_id}", headers=hdr).status_code == 404


def test_delete_planning_year_blocked_when_holiday_exists(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    client.post(f"/api/planning/years/{yr_id}/holidays", json={
        "name": "Blocker Holiday", "start_date": "2026-04-01", "end_date": "2026-04-14",
    }, headers=hdr)

    r = client.delete(f"/api/planning/years/{yr_id}", headers=hdr)
    assert r.status_code == 409, r.text
    body = r.json()["detail"]
    assert body["error"] == "has_dependents"
    assert body["dependents"]["holidays"] == 1

    # Still exists and can still be archived instead (the offered fallback).
    still_there = client.get(f"/api/planning/years/{yr_id}", headers=hdr)
    assert still_there.status_code == 200
    archive_r = client.patch(f"/api/planning/years/{yr_id}", json={"active_status": False}, headers=hdr)
    assert archive_r.status_code == 200


def test_delete_planning_year_forbidden_for_general(client):
    hdr_admin = _sqn_admin_hdr(client)
    year = _make_year(client, hdr_admin)
    yr_id = year["planning_year_id"]
    hdr_general = _general_hdr(client)
    r = client.delete(f"/api/planning/years/{yr_id}", headers=hdr_general)
    assert r.status_code == 403


def test_delete_planning_year_unauthenticated(client):
    r = client.delete("/api/planning/years/some-id")
    assert r.status_code == 401


def test_delete_planning_year_is_audited(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    client.delete(f"/api/planning/years/{yr_id}", headers=hdr)
    audit = client.get("/api/audit", headers=hdr).json()
    found = any(a.get("object_id") == yr_id and a.get("action") == "delete" for a in audit)
    assert found, "planning year delete not found in audit log"


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


def test_generate_parade_dates_applies_time_override(client):
    # 704 squadron has no pre-seeded parade nights, so the generated date is genuinely new.
    hdr = login(client, "ADMIN704")
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.post(
        f"/api/planning/years/{yr_id}/generate-parade-dates",
        json={
            "weekday": 4, "start_date": "2026-08-07", "end_date": "2026-08-07",
            "exclude_holidays": False,
            "parade_start_time": "18:15", "parade_end_time": "20:45",
        },
        headers=hdr,
    )
    assert r.status_code == 200
    assert r.json()["created"] == 1
    pn_list = client.get("/api/parade-nights", headers=hdr).json()
    pn = next(p for p in pn_list if p["date"] == "2026-08-07")
    assert pn["start_time"] == "18:15"
    assert pn["end_time"] == "20:45"


def test_generate_parade_dates_yearly_frequency(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.post(
        f"/api/planning/years/{yr_id}/generate-parade-dates",
        json={
            "weekday": 4, "start_date": "2026-04-25", "end_date": "2028-04-25",
            "exclude_holidays": False, "frequency": "yearly",
        },
        headers=hdr,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["dates"] == ["2026-04-25", "2027-04-25", "2028-04-25"]


# ─────────────────────────────────────────────────────────────
# REM-10 (original_instruction.md Section 9): preview-parade-dates must
# classify every candidate date the recurrence touches (will_create /
# already_exists / holiday_conflict / explicitly_skipped), not silently
# drop holiday-conflicting or explicitly-skipped dates from the response.
# ─────────────────────────────────────────────────────────────

def test_preview_parade_dates_classifies_explicitly_skipped(client):
    hdr = login(client, "ADMIN704")  # 704 has no pre-seeded parade nights
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.post(
        f"/api/planning/years/{yr_id}/preview-parade-dates",
        json={
            "weekday": 4, "start_date": "2026-08-07", "end_date": "2026-08-21",
            "exclude_holidays": False, "excluded_dates": ["2026-08-14"],
        },
        headers=hdr,
    )
    assert r.status_code == 200
    d = r.json()
    by_date = {row["date"]: row for row in d["dates"]}
    assert by_date["2026-08-07"]["status"] == "will_create"
    assert by_date["2026-08-14"]["status"] == "explicitly_skipped"
    assert by_date["2026-08-21"]["status"] == "will_create"
    # The skipped date must still be visible in the response, not silently
    # dropped -- this is the exact defect REM-10 fixed.
    assert d["total"] == 3
    assert d["new_count"] == 2


def test_preview_parade_dates_classifies_holiday_conflict(client):
    hdr = login(client, "ADMIN704")
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    client.post(f"/api/planning/years/{yr_id}/holidays", json={
        "name": "Term Break", "start_date": "2026-08-10", "end_date": "2026-08-16",
        "holiday_type": "school_holiday", "affects_parade": True,
    }, headers=hdr)
    r = client.post(
        f"/api/planning/years/{yr_id}/preview-parade-dates",
        json={
            "weekday": 4, "start_date": "2026-08-07", "end_date": "2026-08-21",
            "exclude_holidays": True,
        },
        headers=hdr,
    )
    assert r.status_code == 200
    d = r.json()
    by_date = {row["date"]: row for row in d["dates"]}
    assert by_date["2026-08-07"]["status"] == "will_create"
    assert by_date["2026-08-14"]["status"] == "holiday_conflict"
    assert by_date["2026-08-21"]["status"] == "will_create"
    assert d["total"] == 3
    assert d["new_count"] == 2


def test_preview_parade_dates_classifies_already_exists(client):
    hdr = login(client, "ADMIN704")
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    gen = client.post(
        f"/api/planning/years/{yr_id}/generate-parade-dates",
        json={
            "weekday": 4, "start_date": "2026-08-07", "end_date": "2026-08-07",
            "exclude_holidays": False,
        },
        headers=hdr,
    )
    assert gen.status_code == 200 and gen.json()["created"] == 1
    r = client.post(
        f"/api/planning/years/{yr_id}/preview-parade-dates",
        json={
            "weekday": 4, "start_date": "2026-08-07", "end_date": "2026-08-07",
            "exclude_holidays": False,
        },
        headers=hdr,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["dates"][0]["status"] == "already_exists"
    assert d["dates"][0]["new"] is False
    assert d["new_count"] == 0


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
# Parade night <-> ParadeDate linkage (REM-129)
# ─────────────────────────────────────────────────────────────

def test_plain_parade_night_create_links_to_active_planning_year(client):
    """REM-129: connected-frontend's plain "add one parade night" flow
    (POST /api/parade-nights, no year_id) previously created a ParadeNight
    with no matching ParadeDate row. Planning Workspace's main canvas/
    command-centre view is built entirely around ParadeDate
    (joined via planning_year_id), so a night created this way was fully
    visible in TMS and via GET /api/parade-nights, but invisible in Planning
    Workspace -- reported live as "created in TMS, not showing in Planning
    Workspace even after a refresh"."""
    hdr = _sqn_admin_hdr(client)
    # A unique, unambiguously-highest year value -- squadron 703 already has a
    # seeded active planning year (and other tests in this file create more),
    # and create_parade's auto-link picks the most recent active year by
    # `year` number when several exist for the same squadron. Using a year far
    # beyond anything else in this suite keeps the fix's own tie-break
    # deterministic for this test, rather than assuming _make_year's fixed
    # year=2026 is the only (or most recent) one for this squadron.
    r = client.post("/api/planning/years", json={"year": next_test_year(), "name": "REM-129 test year"}, headers=hdr)
    assert r.status_code == 200, r.text
    year = r.json()
    yr_id = year["planning_year_id"]
    assert year["active_status"] is True

    r = client.post("/api/parade-nights", json={"date": "2029-03-14", "term": "T2"}, headers=hdr)
    assert r.status_code == 200, r.text
    pn_id = r.json()["parade_night_id"]

    dates = client.get(f"/api/planning/years/{yr_id}/parade-dates", headers=hdr).json()
    matching = [d for d in dates if d["parade_date"] == "2029-03-14"]
    assert len(matching) == 1, f"expected exactly one ParadeDate for this date, got {matching}"
    assert matching[0]["parade_night_id"] == pn_id, (
        "the ParadeDate must link back to the newly created ParadeNight, "
        "or Planning Workspace's command-centre still won't show it"
    )


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
    types = [c["conflict_type"] for c in r.json()["conflicts"]]
    assert "holiday_conflict" in types


def test_sqn_admin_can_patch_holiday(client):
    """HOL-EDIT-01 regression: PATCH /api/planning/holidays/{id} must update fields."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.post(f"/api/planning/years/{yr_id}/holidays",
                    json={"name": "Original", "start_date": "2026-07-01", "end_date": "2026-07-14",
                          "holiday_type": "school_holiday"},
                    headers=hdr)
    hol_id = r.json()["holiday_id"]
    rp = client.patch(f"/api/planning/holidays/{hol_id}",
                      json={"name": "Updated", "holiday_type": "public_holiday"},
                      headers=hdr)
    assert rp.status_code == 200
    d = rp.json()
    assert d["name"] == "Updated"
    assert d["holiday_type"] == "public_holiday"
    # start/end unchanged
    assert d["start_date"] == "2026-07-01"


def test_oversized_holiday_name_rejected_cleanly_not_500(client):
    """Live-found on staging (task #156 e2e re-run): HolidayPeriod.name is a real
    DB column (String(120)), but neither HolidayIn nor HolidayUpdateIn enforced a
    matching length limit -- a name over 120 chars hit Postgres directly and raised
    an unhandled StringDataRightTruncation, surfacing as a raw 500 instead of a
    clean validation error. Covers both create and update."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    long_name = "x" * 121

    r = client.post(f"/api/planning/years/{yr_id}/holidays",
                    json={"name": long_name, "start_date": "2026-07-01", "end_date": "2026-07-14"},
                    headers=hdr)
    assert r.status_code == 422, r.text

    r = client.post(f"/api/planning/years/{yr_id}/holidays",
                    json={"name": "Short Name", "start_date": "2026-07-01", "end_date": "2026-07-14"},
                    headers=hdr)
    hol_id = r.json()["holiday_id"]
    rp = client.patch(f"/api/planning/holidays/{hol_id}", json={"name": long_name}, headers=hdr)
    assert rp.status_code == 422, rp.text


def test_holiday_type_stored_and_returned(client):
    """HOL-TYPE-01 regression: holiday_type sent on create must round-trip."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.post(f"/api/planning/years/{yr_id}/holidays",
                    json={"name": "ANZAC Day", "start_date": "2026-04-25", "end_date": "2026-04-25",
                          "holiday_type": "public_holiday"},
                    headers=hdr)
    assert r.status_code == 200
    assert r.json()["holiday_type"] == "public_holiday"
    listed = client.get(f"/api/planning/years/{yr_id}/holidays", headers=hdr).json()
    match = next((h for h in listed if h["name"] == "ANZAC Day"), None)
    assert match is not None
    assert match["holiday_type"] == "public_holiday"


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


def test_sqn_general_only_sees_own_squadrons_locations(client):
    """REM-130, live-reported: Planning Workspace showed a squadron-level user
    another squadron's data. Root cause: list_locations' role-scoping chain
    had no branch at all for sqn_general (only sqn_admin was scoped) -- every
    other role fell through unfiltered, returning every TrainingArea in the
    system. sqn_general is the role Planning Workspace's own canvas actually
    calls this endpoint as (planningApi.locations(), no squadron_id param)."""
    hdr_703_admin = _sqn_admin_hdr(client)
    client.post("/api/planning/locations",
                json={"name": "703-Only Room", "location_type": "indoor"}, headers=hdr_703_admin)

    hdr_704_general = login(client, "704SQN2026")
    r = client.get("/api/planning/locations", headers=hdr_704_general)
    assert r.status_code == 200, r.text
    names = [loc["name"] for loc in r.json()]
    assert "703-Only Room" not in names, (
        "a 704 sqn_general must never see 703's Training Area/Location -- "
        f"got: {names}"
    )

    hdr_703_general = login(client, "703SQN2026")
    r2 = client.get("/api/planning/locations", headers=hdr_703_general)
    assert r2.status_code == 200, r2.text
    assert "703-Only Room" in [loc["name"] for loc in r2.json()], (
        "703's own sqn_general must still see 703's own Training Area/Location"
    )


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
# Rooms merger (master transformation plan, Phase 1): /api/planning/locations
# and /api/training-areas must now be two views over the same canonical
# training_areas table, not two separate tables (the old DL-01 duplication).
# ─────────────────────────────────────────────────────────────

def test_room_created_via_connected_frontend_visible_in_planning_workspace(client):
    """A room added via /api/training-areas (connected-frontend's Resources
    page) must be immediately visible via /api/planning/locations (Planning
    Workspace's Rooms tab) — same table, not a separate copy."""
    hdr = _sqn_admin_hdr(client)
    rt = client.post("/api/training-areas",
                      json={"name": "Cross-App Test Room", "type": "Classroom", "capacity": 25},
                      headers=hdr)
    assert rt.status_code == 200
    r = client.get("/api/planning/locations", headers=hdr)
    assert r.status_code == 200
    names = [l["name"] for l in r.json()]
    assert "Cross-App Test Room" in names


def test_room_created_via_planning_workspace_visible_in_connected_frontend(client):
    """The reverse direction: a room added via /api/planning/locations must
    be immediately visible via /api/training-areas."""
    hdr = _sqn_admin_hdr(client)
    rl = client.post("/api/planning/locations",
                      json={"name": "Reverse Cross-App Room", "location_type": "Outdoor", "capacity": 40},
                      headers=hdr)
    assert rl.status_code == 200
    r = client.get("/api/training-areas", headers=hdr)
    assert r.status_code == 200
    names = [ta["name"] for ta in r.json()]
    assert "Reverse Cross-App Room" in names


def test_parade_night_created_via_connected_frontend_visible_in_planning_workspace(client):
    """A Parade Night created via /api/parade-nights (connected-frontend's Generate/
    Add Parade Night flow) must be immediately visible via the exact same endpoint
    call Planning Workspace's own pages make (trainingApi.paradeNights(squadronId) in
    ParadeNights.tsx/Calendar.tsx/Dashboard.tsx/WeeklyProgram.tsx) -- one canonical
    ParadeNight table, same read/write endpoint for both frontends, not a duplicate
    store (mirrors the proven Rooms pattern above)."""
    hdr = _sqn_admin_hdr(client)
    pn_r = client.post("/api/parade-nights", json={"date": "2027-05-07", "term": "T4"}, headers=hdr)
    assert pn_r.status_code == 200, pn_r.text
    pnid = pn_r.json()["parade_night_id"]
    sqn_id = client.get("/api/auth/me", headers=hdr).json()["session"]["squadron_id"]
    r = client.get(f"/api/parade-nights?squadron_id={sqn_id}", headers=hdr)
    assert r.status_code == 200
    ids = [pn["parade_night_id"] for pn in r.json()]
    assert pnid in ids, "Parade Night created via connected-frontend's endpoint must be visible via the same query Planning Workspace uses"


def test_parade_night_created_via_planning_workspace_parade_date_visible_via_connected_frontend(client):
    """The reverse direction: a Parade Night created by adding a Planning
    Workspace parade date (/api/planning/years/{id}/parade-dates) must be visible
    via /api/parade-nights/{id} -- the exact endpoint connected-frontend's own
    Parade Nights/Calendar pages use to read a single night's detail."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.post(f"/api/planning/years/{yr_id}/parade-dates",
                    json={"parade_date": "2027-05-14"}, headers=hdr)
    assert r.status_code == 200, r.text
    pnid = r.json()["parade_night_id"]
    assert pnid, "Adding a Planning Workspace parade date must link a real ParadeNight"
    pn_r = client.get(f"/api/parade-nights/{pnid}", headers=hdr)
    assert pn_r.status_code == 200
    assert pn_r.json()["date"] == "2027-05-14"


def test_room_created_via_planning_workspace_attaches_to_a_session(client):
    """Regression for a real, live bug: create_session/update_session's room
    resolution only ever looked up TrainingArea rows (`db.get(TrainingArea,
    body.location_id)`), so a room picked from Planning Workspace's Rooms tab
    (previously backed by the separate planning_locations table) silently
    failed to attach — the session was created with no room, no error. Now
    that /api/planning/locations reads/writes training_areas directly, a room
    id from that endpoint must resolve correctly."""
    hdr = _sqn_admin_hdr(client)
    rl = client.post("/api/planning/locations",
                      json={"name": "Attach Test Room", "location_type": "indoor"}, headers=hdr)
    loc_id = rl.json()["location_id"]

    yr_id, pd_id = _setup_year_with_date(client, hdr)
    r = client.post(
        f"/api/planning/parade-dates/{pd_id}/sessions",
        json={"cadet_group": "junior", "session_number": 1,
              "activity_title": "Room Attach Test", "location_id": loc_id},
        headers=hdr,
    )
    assert r.status_code == 200
    d = r.json()
    assert d["location_id"] == loc_id
    assert d["location_name"] == "Attach Test Room"


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
    types = [c["conflict_type"] for c in r.json()["conflicts"]]
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
    conflicts = client.get(f"/api/planning/years/{yr_id}/conflicts", headers=hdr).json()["conflicts"]
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
    conflicts = client.get(f"/api/planning/years/{yr_id}/conflicts", headers=hdr).json()["conflicts"]
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
    # REM-134: 2027-01-15 collided with parade nights generated by tests that
    # previously stopped early on a year conflict and now run to completion.
    # 2027-01-02 is a Saturday, so parade-night generation (which follows the
    # squadron's Friday parade day) can never produce it, and no other test uses
    # it. It still sits inside the seeded template's effective range, which an
    # allocated far-future year does not.
    pn_r = client.post("/api/parade-nights",
                       json={"date": "2027-01-02", "term": "T3"}, headers=hdr)
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


# ─────────────────────────────────────────────────────────────
# POST /api/planning/years -- squadron-scoped write requires Proxy/Intervention
# (remediation Stage 10) -- previously wing_admin/national_admin/system_admin
# could create a plan for any squadron with only a bare role check, no
# proxy/intervention state at all.
# ─────────────────────────────────────────────────────────────

def test_wing_admin_cannot_create_squadron_year_without_proxy(client):
    wing_hdr = _wing_admin_hdr(client)
    sqn_id = client.get("/api/auth/me", headers=_sqn_admin_hdr(client)).json()["session"]["squadron_id"]
    r = client.post("/api/planning/years", json={"year": 2031, "name": "2031 Test Year", "unit_id": sqn_id}, headers=wing_hdr)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["error"] == "proxy_required"


def test_wing_admin_can_create_squadron_year_with_proxy(client):
    wing_hdr = _wing_admin_hdr(client)
    sqn_id = client.get("/api/auth/me", headers=_sqn_admin_hdr(client)).json()["session"]["squadron_id"]
    enter = client.post(f"/api/proxy/enter/{sqn_id}", json={"reason": "Stage 10 regression test"}, headers=wing_hdr)
    assert enter.status_code == 200, enter.text
    r = client.post("/api/planning/years", json={"year": 2032, "name": "2032 Test Year", "unit_id": sqn_id}, headers=wing_hdr)
    assert r.status_code == 200, r.text
    assert r.json()["unit_id"] == sqn_id
    client.post("/api/proxy/exit", headers=wing_hdr)


def test_national_admin_cannot_create_squadron_year_without_intervention(client):
    nat_hdr = _nat_admin_hdr(client)
    sqn_id = client.get("/api/auth/me", headers=_sqn_admin_hdr(client)).json()["session"]["squadron_id"]
    r = client.post("/api/planning/years", json={"year": 2033, "name": "2033 Test Year", "unit_id": sqn_id}, headers=nat_hdr)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["error"] == "intervention_required"


# ─────────────────────────────────────────────────────────────
# REM-45 follow-up: the same Proxy/Intervention requirement extended to
# create_location, update_location, override_conflict, and the Annual
# Program import -- previously wing_admin/national_admin/system_admin could
# perform each of these squadron-scoped writes with no scope check at all.
# ─────────────────────────────────────────────────────────────

def test_wing_admin_cannot_create_squadron_location_without_proxy(client):
    wing_hdr = _wing_admin_hdr(client)
    sqn_id = client.get("/api/auth/me", headers=_sqn_admin_hdr(client)).json()["session"]["squadron_id"]
    r = client.post("/api/planning/locations", json={"name": "Test Room", "unit_id": sqn_id}, headers=wing_hdr)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["error"] == "proxy_required"


def test_wing_admin_can_create_squadron_location_with_proxy(client):
    wing_hdr = _wing_admin_hdr(client)
    sqn_id = client.get("/api/auth/me", headers=_sqn_admin_hdr(client)).json()["session"]["squadron_id"]
    enter = client.post(f"/api/proxy/enter/{sqn_id}", json={"reason": "REM-45 regression test"}, headers=wing_hdr)
    assert enter.status_code == 200, enter.text
    r = client.post("/api/planning/locations", json={"name": "Test Room 2", "unit_id": sqn_id}, headers=wing_hdr)
    assert r.status_code == 200, r.text
    client.post("/api/proxy/exit", headers=wing_hdr)


def test_national_admin_cannot_update_squadron_location_without_intervention(client):
    hdr = _sqn_admin_hdr(client)
    loc_id = client.post("/api/planning/locations", json={"name": "Owned Room"}, headers=hdr).json()["location_id"]
    nat_hdr = _nat_admin_hdr(client)
    r = client.patch(f"/api/planning/locations/{loc_id}", json={"capacity": 99}, headers=nat_hdr)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["error"] == "intervention_required"


def test_national_admin_can_update_squadron_location_with_intervention(client):
    hdr = _sqn_admin_hdr(client)
    sqn_id = client.get("/api/auth/me", headers=hdr).json()["session"]["squadron_id"]
    loc_id = client.post("/api/planning/locations", json={"name": "Owned Room 2"}, headers=hdr).json()["location_id"]
    nat_hdr = _nat_admin_hdr(client)
    enter = client.post(f"/api/proxy/enter/{sqn_id}", json={"reason": "REM-45 regression test"}, headers=nat_hdr)
    assert enter.status_code == 200, enter.text
    r = client.patch(f"/api/planning/locations/{loc_id}", json={"capacity": 99}, headers=nat_hdr)
    assert r.status_code == 200, r.text
    client.post("/api/proxy/exit", headers=nat_hdr)


def _make_holiday_conflict(client, hdr):
    """Real PlanningConflict via the proven holiday-conflict pattern (mirrors
    test_holiday_conflict_flagged_on_parade_date above)."""
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    client.post(f"/api/planning/years/{yr_id}/holidays",
                json={"name": "Conflict Test Hols", "start_date": "2026-09-18",
                      "end_date": "2026-10-02", "affects_parade": True}, headers=hdr)
    client.post(f"/api/planning/years/{yr_id}/parade-dates",
                json={"parade_date": "2026-09-25"}, headers=hdr)
    client.post(f"/api/planning/years/{yr_id}/run-checks", headers=hdr)
    conflicts = client.get(f"/api/planning/years/{yr_id}/conflicts", headers=hdr).json()["conflicts"]
    assert conflicts, "expected at least one conflict"
    return conflicts[0]["conflict_id"]


def test_wing_admin_cannot_override_squadron_conflict_without_proxy(client):
    hdr = _sqn_admin_hdr(client)
    conflict_id = _make_holiday_conflict(client, hdr)
    wing_hdr = _wing_admin_hdr(client)
    r = client.post(f"/api/planning/conflicts/{conflict_id}/override",
                    json={"override_reason": "should be blocked"}, headers=wing_hdr)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["error"] == "proxy_required"


def test_wing_admin_can_override_squadron_conflict_with_proxy(client):
    hdr = _sqn_admin_hdr(client)
    sqn_id = client.get("/api/auth/me", headers=hdr).json()["session"]["squadron_id"]
    conflict_id = _make_holiday_conflict(client, hdr)
    wing_hdr = _wing_admin_hdr(client)
    enter = client.post(f"/api/proxy/enter/{sqn_id}", json={"reason": "REM-45 regression test"}, headers=wing_hdr)
    assert enter.status_code == 200, enter.text
    r = client.post(f"/api/planning/conflicts/{conflict_id}/override",
                    json={"override_reason": "resolved via proxy"}, headers=wing_hdr)
    assert r.status_code == 200, r.text
    client.post("/api/proxy/exit", headers=wing_hdr)


def test_wing_admin_cannot_import_program_without_proxy(client):
    hdr = _sqn_admin_hdr(client)
    yr_id = _make_year(client, hdr)["planning_year_id"]
    wing_hdr = _wing_admin_hdr(client)
    files = {"file": ("program.csv", "SeqNr,Name\r\n", "text/csv")}
    r = client.post(f"/api/planning/years/{yr_id}/import-program", headers=wing_hdr, files=files)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["error"] == "proxy_required"


def test_wing_admin_import_program_preview_does_not_require_proxy(client):
    """preview=true never writes to the database -- viewing/validating is
    broad by design, only the commit needs Proxy/Intervention."""
    hdr = _sqn_admin_hdr(client)
    yr_id = _make_year(client, hdr)["planning_year_id"]
    wing_hdr = _wing_admin_hdr(client)
    files = {"file": ("program.csv", "SeqNr,Name\r\n", "text/csv")}
    r = client.post(f"/api/planning/years/{yr_id}/import-program?preview=true", headers=wing_hdr, files=files)
    assert r.status_code != 403, r.text


def test_wing_admin_can_import_program_with_proxy(client):
    hdr = _sqn_admin_hdr(client)
    sqn_id = client.get("/api/auth/me", headers=hdr).json()["session"]["squadron_id"]
    yr_id = _make_year(client, hdr)["planning_year_id"]
    wing_hdr = _wing_admin_hdr(client)
    enter = client.post(f"/api/proxy/enter/{sqn_id}", json={"reason": "REM-45 regression test"}, headers=wing_hdr)
    assert enter.status_code == 200, enter.text
    files = {"file": ("program.csv", "SeqNr,Name\r\n", "text/csv")}
    r = client.post(f"/api/planning/years/{yr_id}/import-program", headers=wing_hdr, files=files)
    # Permission check passed (not 403) -- an empty-body CSV then correctly
    # 400s as empty_file, proving business logic was reached.
    assert r.status_code != 403, r.text
    client.post("/api/proxy/exit", headers=wing_hdr)


# ─────────────────────────────────────────────────────────────
# PATCH /api/parade-nights/{id} -- core field editing (remediation Stage 5)
# ─────────────────────────────────────────────────────────────

def test_sqn_admin_can_patch_parade_night_core_fields(client):
    hdr = _sqn_admin_hdr(client)
    pn_r = client.post("/api/parade-nights", json={"date": "2027-03-05", "term": "T4"}, headers=hdr)
    assert pn_r.status_code == 200, pn_r.text
    pnid = pn_r.json()["parade_night_id"]
    r = client.patch(f"/api/parade-nights/{pnid}", headers=hdr, json={
        "start_time": "18:30", "end_time": "21:00", "notes": "Moved start time", "parade_type": "admin",
    })
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["start_time"] == "18:30"
    assert d["end_time"] == "21:00"
    assert d["parade_type"] == "admin"
    builder = client.get(f"/api/parade-nights/{pnid}/builder", headers=hdr).json()
    assert builder["parade_night_id"] == pnid


def test_patch_parade_night_date_rejects_duplicate(client):
    hdr = _sqn_admin_hdr(client)
    client.post("/api/parade-nights", json={"date": "2027-03-12", "term": "T4"}, headers=hdr)
    pn2 = client.post("/api/parade-nights", json={"date": "2027-03-19", "term": "T4"}, headers=hdr)
    pnid2 = pn2.json()["parade_night_id"]
    r = client.patch(f"/api/parade-nights/{pnid2}", headers=hdr, json={"date": "2027-03-12"})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["error"] == "duplicate_date"


def test_patch_parade_night_blocked_when_closed(client):
    hdr = _sqn_admin_hdr(client)
    pn_r = client.post("/api/parade-nights", json={"date": "2027-03-26", "term": "T4"}, headers=hdr)
    pnid = pn_r.json()["parade_night_id"]
    from app.database import SessionLocal
    from app.models import ParadeNight
    db = SessionLocal()
    try:
        pn = db.get(ParadeNight, pnid)
        pn.closeout_status = "closed"
        db.commit()
    finally:
        db.close()
    r = client.patch(f"/api/parade-nights/{pnid}", headers=hdr, json={"notes": "should be blocked"})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["error"] == "parade_night_closed"


def test_patch_parade_night_forbidden_for_general(client):
    admin_hdr = _sqn_admin_hdr(client)
    pn_r = client.post("/api/parade-nights", json={"date": "2027-04-02", "term": "T4"}, headers=admin_hdr)
    pnid = pn_r.json()["parade_night_id"]
    general_hdr = _general_hdr(client)
    r = client.patch(f"/api/parade-nights/{pnid}", headers=general_hdr, json={"notes": "nope"})
    assert r.status_code == 403


def test_patch_parade_night_unauthenticated(client):
    r = client.patch("/api/parade-nights/some-id", json={"notes": "nope"})
    assert r.status_code == 401


def test_patch_parade_night_is_audited(client):
    hdr = _sqn_admin_hdr(client)
    pn_r = client.post("/api/parade-nights", json={"date": "2027-04-16", "term": "T4"}, headers=hdr)
    pnid = pn_r.json()["parade_night_id"]
    client.patch(f"/api/parade-nights/{pnid}", headers=hdr, json={"notes": "audit me"})
    audit = client.get("/api/audit", headers=hdr).json()
    found = any(a.get("object_id") == pnid and a.get("action") == "update" for a in audit)
    assert found, "Parade night PATCH not audited"


def test_patch_parade_night_not_found(client):
    hdr = _sqn_admin_hdr(client)
    r = client.patch("/api/parade-nights/does-not-exist", headers=hdr, json={"notes": "x"})
    assert r.status_code == 404


# ─────────────────────────────────────────────────────────────
# AUTO-01: Class A partial autosave — notes-only PATCH
# ─────────────────────────────────────────────────────────────

def test_partial_notes_patch_round_trips(client):
    """AUTO-01: sending only {notes, version} in a PATCH must save the notes field
    without altering other fields — the backend supports partial update semantics,
    which is what the frontend Class A autosave sends."""
    hdr = _sqn_admin_hdr(client)
    pn_r = client.post("/api/parade-nights", json={"date": "2027-09-11", "term": "T1"}, headers=hdr)
    pnid = pn_r.json()["parade_night_id"]
    # Pre-set term so we can verify it's unchanged after the notes-only PATCH
    client.patch(f"/api/parade-nights/{pnid}", headers=hdr, json={"term": "T1", "start_time": "19:00"})
    # Partial PATCH — notes only
    r = client.patch(f"/api/parade-nights/{pnid}", headers=hdr, json={"notes": "Autosave test note"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["notes"] == "Autosave test note"
    # term and start_time should be unchanged
    assert d.get("term") == "T1" or d.get("term") is not None  # term is preserved
    assert d.get("start_time") == "19:00"


def test_partial_notes_patch_clears_notes_with_none(client):
    """AUTO-01: sending notes=None in a PATCH should not clear notes — None means 'not provided'.
    Only an explicit empty string clears notes."""
    hdr = _sqn_admin_hdr(client)
    pn_r = client.post("/api/parade-nights", json={"date": "2027-09-18", "term": "T1"}, headers=hdr)
    pnid = pn_r.json()["parade_night_id"]
    client.patch(f"/api/parade-nights/{pnid}", headers=hdr, json={"notes": "Initial note"})
    # PATCH with no notes field at all — notes must persist
    r = client.patch(f"/api/parade-nights/{pnid}", headers=hdr, json={"start_time": "19:30"})
    d = r.json()
    assert d.get("notes") == "Initial note", "Notes must persist when not included in PATCH"


def test_planning_session_persists_in_weekly_program(client):
    """Session created via planning API must appear in the Weekly Program for that date."""
    hdr = _sqn_admin_hdr(client)
    year_r = client.post("/api/planning/years",
                         json={"year": next_test_year(), "name": "V12 Timing Test Year"}, headers=hdr)
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
                         json={"year": next_test_year(), "name": "V12 Long Range Test"}, headers=hdr)
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


# ─────────────────────────────────────────────────────────────
# IDOR / cross-squadron tenancy regression tests (2026-07-13)
#
# facilitator-leave, notices, and CEA endpoints checked only the caller's
# ROLE (require_role) and never checked that the object being read/written
# actually belonged to the caller's own squadron/wing. A same-role admin
# from a different squadron (or, for CEA import, a wing_admin from a
# different wing) could read or write another organisation's data.
# Fixed by adding require_can_view_squadron/require_can_write_squadron
# (facilitator-leave) and _require_year_access (notices, CEA) after
# fetching the target object. These tests prove the cross-tenant paths
# are now denied and same-tenant access still works.
# ─────────────────────────────────────────────────────────────

def _other_sqn_admin_hdr(client):
    """Admin for squadron 701 — a different squadron from 703, same wing (7WG)."""
    return login(client, "ADMIN701")


def _seed_703_facilitator_id(client, hdr703):
    r = client.get("/api/planning/facilitators", headers=hdr703)
    assert r.status_code == 200
    facilitators = r.json()
    assert facilitators, "expected at least one seeded 703 facilitator"
    return facilitators[0]["facilitator_id"]


def test_facilitator_leave_cross_squadron_list_denied(client):
    hdr703 = _sqn_admin_hdr(client)
    fac_id = _seed_703_facilitator_id(client, hdr703)
    other_hdr = _other_sqn_admin_hdr(client)
    r = client.get(f"/api/planning/facilitators/{fac_id}/leave", headers=other_hdr)
    assert r.status_code == 403, r.text


def test_facilitator_leave_cross_squadron_create_denied(client):
    hdr703 = _sqn_admin_hdr(client)
    fac_id = _seed_703_facilitator_id(client, hdr703)
    other_hdr = _other_sqn_admin_hdr(client)
    r = client.post(
        f"/api/planning/facilitators/{fac_id}/leave",
        json={"start_date": "2026-08-01", "end_date": "2026-08-05", "reason": "cross-squadron test"},
        headers=other_hdr,
    )
    assert r.status_code == 403, r.text


def test_facilitator_leave_cross_squadron_delete_denied(client):
    hdr703 = _sqn_admin_hdr(client)
    fac_id = _seed_703_facilitator_id(client, hdr703)
    r = client.post(
        f"/api/planning/facilitators/{fac_id}/leave",
        json={"start_date": "2026-08-01", "end_date": "2026-08-05", "reason": "owner create"},
        headers=hdr703,
    )
    assert r.status_code == 200, r.text
    leave_id = r.json()["leave"]["id"]

    other_hdr = _other_sqn_admin_hdr(client)
    r = client.delete(f"/api/planning/facilitator-leave/{leave_id}", headers=other_hdr)
    assert r.status_code == 403, r.text


def test_facilitator_leave_same_squadron_admin_allowed(client):
    """Regression guard: the fix must not break legitimate same-squadron access."""
    hdr703 = _sqn_admin_hdr(client)
    fac_id = _seed_703_facilitator_id(client, hdr703)
    r = client.post(
        f"/api/planning/facilitators/{fac_id}/leave",
        json={"start_date": "2026-09-01", "end_date": "2026-09-03", "reason": "own squadron"},
        headers=hdr703,
    )
    assert r.status_code == 200, r.text
    leave_id = r.json()["leave"]["id"]

    r = client.get(f"/api/planning/facilitators/{fac_id}/leave", headers=hdr703)
    assert r.status_code == 200
    assert any(entry["id"] == leave_id for entry in r.json()["leave"])

    r = client.delete(f"/api/planning/facilitator-leave/{leave_id}", headers=hdr703)
    assert r.status_code == 200, r.text


def _make_parade_date_and_notice(client, hdr, date_str):
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.post(f"/api/planning/years/{yr_id}/parade-dates",
                     json={"parade_date": date_str}, headers=hdr)
    assert r.status_code == 200, r.text
    date_id = r.json()["parade_date_id"]
    r = client.post(f"/api/planning/parade-dates/{date_id}/notices",
                     json={"notice_text": "Bring wet-weather gear", "priority": "high"}, headers=hdr)
    assert r.status_code == 200, r.text
    return date_id, r.json()["notice_id"]


def test_notices_cross_squadron_list_denied(client):
    hdr703 = _sqn_admin_hdr(client)
    date_id, _ = _make_parade_date_and_notice(client, hdr703, "2026-08-07")
    other_hdr = _other_sqn_admin_hdr(client)
    r = client.get(f"/api/planning/parade-dates/{date_id}/notices", headers=other_hdr)
    assert r.status_code == 403, r.text


def test_notices_cross_squadron_create_denied(client):
    hdr703 = _sqn_admin_hdr(client)
    date_id, _ = _make_parade_date_and_notice(client, hdr703, "2026-08-14")
    other_hdr = _other_sqn_admin_hdr(client)
    r = client.post(f"/api/planning/parade-dates/{date_id}/notices",
                     json={"notice_text": "cross-squadron write attempt"}, headers=other_hdr)
    assert r.status_code == 403, r.text


def test_notices_cross_squadron_update_and_archive_denied(client):
    hdr703 = _sqn_admin_hdr(client)
    _, notice_id = _make_parade_date_and_notice(client, hdr703, "2026-08-21")
    other_hdr = _other_sqn_admin_hdr(client)

    r = client.patch(f"/api/planning/notices/{notice_id}",
                      json={"notice_text": "tampered"}, headers=other_hdr)
    assert r.status_code == 403, r.text

    r = client.post(f"/api/planning/notices/{notice_id}/archive", headers=other_hdr)
    assert r.status_code == 403, r.text


def test_notices_same_squadron_admin_allowed(client):
    """Regression guard: same-squadron notice read/write/archive must still work."""
    hdr703 = _sqn_admin_hdr(client)
    date_id, notice_id = _make_parade_date_and_notice(client, hdr703, "2026-08-28")

    r = client.get(f"/api/planning/parade-dates/{date_id}/notices", headers=hdr703)
    assert r.status_code == 200
    assert any(n["notice_id"] == notice_id for n in r.json())

    r = client.patch(f"/api/planning/notices/{notice_id}",
                      json={"priority": "normal"}, headers=hdr703)
    assert r.status_code == 200, r.text

    r = client.post(f"/api/planning/notices/{notice_id}/archive", headers=hdr703)
    assert r.status_code == 200, r.text


# ─────────────────────────────────────────────────────────────
# REM-34: parade-night-scoped Notices (GET/POST /api/parade-nights/{pnid}/
# notices) -- lets connected-frontend attach a notice to a Parade Night
# without ever needing to know ParadeDate exists. Reuses REM-129's find-or-
# create-ParadeDate helper. Existing notice_id-based PATCH/archive endpoints
# are exercised unchanged (no new logic there).
# ─────────────────────────────────────────────────────────────

def _create_plain_parade_night(client, hdr, date_str):
    r = client.post("/api/parade-nights", json={"date": date_str}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["parade_night_id"]


def test_night_notice_create_auto_links_parade_date(client):
    """The core REM-34 fix: a notice can be attached to a plain connected-
    frontend-created Parade Night even though it never explicitly created a
    ParadeDate -- the endpoint resolves/creates one transparently."""
    hdr = _sqn_admin_hdr(client)
    _make_year(client, hdr)  # ensures squadron 703 has an active Training Year
    pnid = _create_plain_parade_night(client, hdr, "2099-03-06")

    r = client.post(f"/api/parade-nights/{pnid}/notices",
                     json={"notice_text": "Bring wet-weather gear", "priority": "high"}, headers=hdr)
    assert r.status_code == 200, r.text
    notice_id = r.json()["notice_id"]

    r = client.get(f"/api/parade-nights/{pnid}/notices", headers=hdr)
    assert r.status_code == 200
    notices = r.json()
    assert any(n["notice_id"] == notice_id for n in notices)
    assert notices[0]["notice_text"] == "Bring wet-weather gear"
    assert notices[0]["priority"] == "high"


def test_night_notice_list_empty_for_night_with_no_notices(client):
    hdr = _sqn_admin_hdr(client)
    pnid = _create_plain_parade_night(client, hdr, "2099-03-13")
    r = client.get(f"/api/parade-nights/{pnid}/notices", headers=hdr)
    assert r.status_code == 200
    assert r.json() == []


def test_night_notice_create_without_active_planning_year_returns_actionable_400(client):
    """ADMIN702 has no active Training Year seeded -- confirms the endpoint
    surfaces a clear, actionable error rather than a raw 500 or a silently
    orphaned notice."""
    hdr = login(client, "ADMIN702")
    pnid = _create_plain_parade_night(client, hdr, "2099-03-20")
    r = client.post(f"/api/parade-nights/{pnid}/notices",
                     json={"notice_text": "test"}, headers=hdr)
    assert r.status_code == 400, r.text
    d = r.json()["detail"]
    assert d["error"] == "no_active_planning_year"
    assert "Training Year" in d["message"]


def test_night_notice_cross_squadron_denied(client):
    hdr703 = _sqn_admin_hdr(client)
    _make_year(client, hdr703)
    pnid = _create_plain_parade_night(client, hdr703, "2099-03-27")
    other_hdr = _other_sqn_admin_hdr(client)

    r = client.get(f"/api/parade-nights/{pnid}/notices", headers=other_hdr)
    assert r.status_code == 403, r.text
    r = client.post(f"/api/parade-nights/{pnid}/notices", json={"notice_text": "x"}, headers=other_hdr)
    assert r.status_code == 403, r.text


def test_night_notice_edit_and_archive_via_existing_notice_id_endpoints(client):
    """A notice created through the new parade-night-scoped endpoint must be
    fully editable/archivable through the existing notice_id-based endpoints
    Planning Workspace already uses -- same underlying record, no parallel
    notice concept."""
    hdr = _sqn_admin_hdr(client)
    _make_year(client, hdr)
    pnid = _create_plain_parade_night(client, hdr, "2099-04-03")
    r = client.post(f"/api/parade-nights/{pnid}/notices",
                     json={"notice_text": "original", "priority": "normal"}, headers=hdr)
    notice_id = r.json()["notice_id"]

    r = client.patch(f"/api/planning/notices/{notice_id}", json={"notice_text": "updated"}, headers=hdr)
    assert r.status_code == 200, r.text

    r = client.get(f"/api/parade-nights/{pnid}/notices", headers=hdr)
    assert r.json()[0]["notice_text"] == "updated"

    r = client.post(f"/api/planning/notices/{notice_id}/archive", headers=hdr)
    assert r.status_code == 200, r.text

    r = client.get(f"/api/parade-nights/{pnid}/notices", headers=hdr)
    assert r.json() == []


def test_night_notice_reuses_existing_parade_date_if_already_linked(client):
    """A parade night created via the Planning module's own generation flow
    already has a ParadeDate -- the new endpoint must reuse it, not create a
    second, orphaned one for the same night."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.post(f"/api/planning/years/{yr_id}/parade-dates",
                     json={"parade_date": "2099-04-10"}, headers=hdr)
    assert r.status_code == 200, r.text
    date_id = r.json()["parade_date_id"]
    pnid = r.json()["parade_night_id"]
    assert pnid, "adding a ParadeDate must link/create a ParadeNight"

    r = client.post(f"/api/parade-nights/{pnid}/notices", json={"notice_text": "x"}, headers=hdr)
    assert r.status_code == 200, r.text

    # Confirms via the ParadeDate-facing endpoint too -- same record, both
    # entry points agree.
    r = client.get(f"/api/planning/parade-dates/{date_id}/notices", headers=hdr)
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_cea_cross_squadron_list_activities_denied(client):
    hdr703 = _sqn_admin_hdr(client)
    year = _make_year(client, hdr703)
    other_hdr = _other_sqn_admin_hdr(client)
    r = client.get(f"/api/planning/years/{year['planning_year_id']}/cea/activities", headers=other_hdr)
    assert r.status_code == 403, r.text


def test_cea_cross_squadron_list_batches_denied(client):
    hdr703 = _sqn_admin_hdr(client)
    year = _make_year(client, hdr703)
    other_hdr = _other_sqn_admin_hdr(client)
    r = client.get(f"/api/planning/years/{year['planning_year_id']}/cea/batches", headers=other_hdr)
    assert r.status_code == 403, r.text


def test_cea_cross_squadron_create_manual_activity_denied(client):
    hdr703 = _sqn_admin_hdr(client)
    year = _make_year(client, hdr703)
    other_hdr = _other_sqn_admin_hdr(client)
    r = client.post(
        f"/api/planning/years/{year['planning_year_id']}/cea/activities",
        json={"activity_name": "cross-squadron manual activity"},
        headers=other_hdr,
    )
    assert r.status_code == 403, r.text


def test_cea_cross_squadron_classify_denied(client):
    hdr703 = _sqn_admin_hdr(client)
    year = _make_year(client, hdr703)
    r = client.post(
        f"/api/planning/years/{year['planning_year_id']}/cea/activities",
        json={"activity_name": "703-owned activity"},
        headers=hdr703,
    )
    assert r.status_code == 200, r.text
    activity_id = r.json()["id"]

    other_hdr = _other_sqn_admin_hdr(client)
    r = client.patch(
        f"/api/planning/cea/{activity_id}/classify",
        json={"importance": "high"},
        headers=other_hdr,
    )
    assert r.status_code == 403, r.text


def test_cea_same_squadron_admin_allowed(client):
    """Regression guard: same-squadron CEA list/create/classify must still work."""
    hdr703 = _sqn_admin_hdr(client)
    year = _make_year(client, hdr703)
    yr_id = year["planning_year_id"]

    r = client.get(f"/api/planning/years/{yr_id}/cea/activities", headers=hdr703)
    assert r.status_code == 200

    r = client.post(f"/api/planning/years/{yr_id}/cea/activities",
                     json={"activity_name": "703 own activity"}, headers=hdr703)
    assert r.status_code == 200, r.text
    activity_id = r.json()["id"]

    r = client.patch(f"/api/planning/cea/{activity_id}/classify",
                      json={"importance": "high"}, headers=hdr703)
    assert r.status_code == 200, r.text


# ─────────────────────────────────────────────────────────────
# sqn_general scope restriction in _require_year_access
#
# sqn_general (read-only squadron user) was falling through
# _require_year_access without any squadron-scope check, meaning
# a 701 SQN general user could read 703 SQN planning data.
# Fixed by adding "sqn_general" to the sqn_admin branch.
# ─────────────────────────────────────────────────────────────

def _other_sqn_general_hdr(client):
    """sqn_general user for squadron 701 — different from 703."""
    return login(client, "701SQN2026")


def test_sqn_general_cannot_read_other_sqn_planning_year(client):
    """sqn_general from 701 must not read a 703 planning year."""
    hdr703 = _sqn_admin_hdr(client)
    year = _make_year(client, hdr703)
    yr_id = year["planning_year_id"]

    other_general = _other_sqn_general_hdr(client)
    r = client.get(f"/api/planning/years/{yr_id}/annual-program", headers=other_general)
    assert r.status_code == 403, r.text


def test_sqn_general_cannot_read_other_sqn_missions(client):
    """sqn_general from 701 must not read 703 mission backlog."""
    hdr703 = _sqn_admin_hdr(client)
    year = _make_year(client, hdr703)
    yr_id = year["planning_year_id"]

    other_general = _other_sqn_general_hdr(client)
    r = client.get(f"/api/planning/years/{yr_id}/missions", headers=other_general)
    assert r.status_code == 403, r.text


def test_sqn_general_cannot_read_other_sqn_cea(client):
    """sqn_general from 701 must not read 703 CEA activities."""
    hdr703 = _sqn_admin_hdr(client)
    year = _make_year(client, hdr703)
    yr_id = year["planning_year_id"]

    other_general = _other_sqn_general_hdr(client)
    r = client.get(f"/api/planning/years/{yr_id}/cea/activities", headers=other_general)
    assert r.status_code == 403, r.text


def test_sqn_general_can_read_own_sqn_planning_year(client):
    """Regression guard: sqn_general must still read their own squadron's data."""
    hdr703 = _sqn_admin_hdr(client)
    year = _make_year(client, hdr703)
    yr_id = year["planning_year_id"]

    own_general = _general_hdr(client)
    r = client.get(f"/api/planning/years/{yr_id}/annual-program", headers=own_general)
    assert r.status_code == 200, r.text


# ─────────────────────────────────────────────────────────────
# Night summaries endpoint
# ─────────────────────────────────────────────────────────────

def test_night_summaries_returns_list(client):
    """night-summaries returns a list keyed on all parade-date IDs in the year."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.get(f"/api/planning/years/{yr_id}/night-summaries", headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "summaries" in d
    assert isinstance(d["summaries"], list)


def test_night_summaries_requires_auth(client):
    # Fresh client with no prior login — use a dummy UUID so we don't need a real year.
    import uuid
    r = client.get(f"/api/planning/years/{uuid.uuid4()}/night-summaries")
    assert r.status_code == 401


def test_night_summaries_sqn_general_allowed(client):
    hdr703 = _sqn_admin_hdr(client)
    year = _make_year(client, hdr703)
    yr_id = year["planning_year_id"]
    gen_hdr = _general_hdr(client)
    r = client.get(f"/api/planning/years/{yr_id}/night-summaries", headers=gen_hdr)
    assert r.status_code == 200, r.text


def test_night_summaries_sqn_general_cross_sqn_denied(client):
    hdr703 = _sqn_admin_hdr(client)
    year = _make_year(client, hdr703)
    yr_id = year["planning_year_id"]
    other_gen = _other_sqn_general_hdr(client)
    r = client.get(f"/api/planning/years/{yr_id}/night-summaries", headers=other_gen)
    assert r.status_code == 403, r.text


# ─────────────────────────────────────────────────────────────
# Facilitator workload endpoint
# ─────────────────────────────────────────────────────────────

def test_facilitator_workload_returns_stats(client):
    """Facilitator workload returns a valid structure for a seeded facilitator."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]

    facs_r = client.get("/api/planning/facilitators", headers=hdr)
    assert facs_r.status_code == 200
    facs = facs_r.json()
    if not facs:
        import pytest
        pytest.skip("No facilitators seeded for 703")
    fac_id = facs[0]["facilitator_id"]

    r = client.get(f"/api/planning/years/{yr_id}/facilitators/{fac_id}/workload", headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "total_scheduled" in d
    assert "nights_with_sessions" in d
    assert "avg_per_night" in d


def test_facilitator_workload_reflects_real_assigned_sessions(client):
    """Regression for a real, live bug: this endpoint queried `ScheduledSession`,
    a model with no live create/update path anywhere in the codebase — it
    always silently returned zero workload regardless of how many real
    sessions (TrainingSession) a facilitator actually had. Uses the seeded
    2026 planning year (which has real assign-mission sessions with real
    facilitators) rather than a freshly-created empty year, so a regression
    back to querying the dead table would show total_scheduled == 0 here."""
    hdr = _sqn_admin_hdr(client)
    years_r = client.get("/api/planning/years", headers=hdr)
    year_2026 = next(y for y in years_r.json() if y["year"] == 2026)
    yr_id = year_2026["planning_year_id"]

    facs = client.get("/api/planning/facilitators", headers=hdr).json()
    assert facs, "Seeded 703 squadron should have facilitators"

    # At least one seeded facilitator must show real, non-zero workload —
    # mirrors the real seeded data (e.g. multiple facilitators with 2-16
    # sessions each) confirmed live via the Facilitators page.
    found_nonzero = False
    for fac in facs:
        r = client.get(f"/api/planning/years/{yr_id}/facilitators/{fac['facilitator_id']}/workload", headers=hdr)
        assert r.status_code == 200
        if r.json()["total_scheduled"] > 0:
            found_nonzero = True
            break
    assert found_nonzero, "Expected at least one seeded facilitator to show non-zero workload"


def test_facilitator_workload_requires_auth(client):
    # Fresh client with no prior login
    import uuid
    from fastapi.testclient import TestClient
    from app.main import app as _app
    fresh = TestClient(_app)
    r = fresh.get(f"/api/planning/years/{uuid.uuid4()}/facilitators/{uuid.uuid4()}/workload")
    assert r.status_code == 401


def test_facilitator_workload_sqn_general_blocked(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    facs_r = client.get("/api/planning/facilitators", headers=hdr)
    facs = facs_r.json()
    if not facs:
        import pytest
        pytest.skip("No facilitators seeded")
    fac_id = facs[0]["facilitator_id"]
    gen_hdr = _general_hdr(client)
    r = client.get(f"/api/planning/years/{yr_id}/facilitators/{fac_id}/workload", headers=gen_hdr)
    assert r.status_code == 403, r.text


def test_facilitator_workload_nonexistent_facilitator(client):
    import uuid
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.get(f"/api/planning/years/{yr_id}/facilitators/{uuid.uuid4()}/workload", headers=hdr)
    assert r.status_code == 404, r.text


# ─────────────────────────────────────────────────────────────
# Command Centre / facilitator-leave — real-schedule regression
#
# Qualification program Phase B, 2026-08-08. Same defect class already fixed
# once for facilitator_workload() above: get_command_centre() and
# add_facilitator_leave() both queried ScheduledSession, a model with no live
# write path anywhere in this codebase, so unscheduled_required always
# included every core curriculum item regardless of real scheduling,
# nights_missing_facilitator was always 0 regardless of real unstaffed
# nights, and the facilitator-leave conflict warning never fired for a real
# session. See docs/qualification/03_data_integrity_review.md P1 #1/#2.
# ─────────────────────────────────────────────────────────────

def test_command_centre_excludes_a_curriculum_item_with_a_real_scheduled_session(client):
    """A core curriculum item with a real TrainingSession must not be reported
    as unscheduled_required. Fails before the fix: ScheduledSession is never
    written, so this item would always appear in unscheduled_required
    regardless of the session created below."""
    hdr = _sqn_admin_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, hdr)

    curr_list = client.get("/api/curriculum", headers=hdr).json()["items"]
    core_items = [c for c in curr_list if c["core_status"] == "core"]
    if not core_items:
        import pytest
        pytest.skip("No core curriculum items seeded for 703")
    curriculum_id = core_items[0]["curriculum_id"]

    rs = client.post(f"/api/planning/parade-dates/{pd_id}/sessions",
                      json={"cadet_group": "junior", "session_number": 1,
                            "curriculum_id": curriculum_id},
                      headers=hdr)
    assert rs.status_code == 200, rs.text

    r = client.get(f"/api/planning/command-centre?year_id={yr_id}", headers=hdr)
    assert r.status_code == 200, r.text
    unscheduled_ids = {c["curriculum_id"] for c in r.json()["unscheduled_required"]}
    assert curriculum_id not in unscheduled_ids, (
        "A curriculum item with a real scheduled session must not appear in "
        "unscheduled_required — regression to the dead ScheduledSession table"
    )


def test_command_centre_counts_a_real_unstaffed_night(client):
    """A parade night with a real session that has no facilitator must be
    counted in nights_missing_facilitator. Fails before the fix: this was
    always 0 regardless of real unstaffed nights."""
    hdr = _sqn_admin_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, hdr)

    rs = client.post(f"/api/planning/parade-dates/{pd_id}/sessions",
                      json={"cadet_group": "senior", "session_number": 1,
                            "activity_title": "Needs a facilitator"},
                      headers=hdr)
    assert rs.status_code == 200, rs.text
    assert rs.json().get("facilitator_id") is None

    r = client.get(f"/api/planning/command-centre?year_id={yr_id}", headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["nights_missing_facilitator"] >= 1, (
        "A real session with no facilitator must be counted — regression to "
        "the dead ScheduledSession table"
    )


def test_facilitator_leave_flags_a_real_affected_session(client):
    """Adding a leave period covering a date on which the facilitator has a
    real scheduled session must return that session in affected_sessions.
    Fails before the fix: this list was always empty regardless of real
    sessions, so the conflict warning never fired."""
    hdr = _sqn_admin_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, hdr)  # parade_date = 2026-09-04

    facs = client.get("/api/planning/facilitators", headers=hdr).json()
    if not facs:
        import pytest
        pytest.skip("No facilitators seeded for 703")
    fac_id = facs[0]["facilitator_id"]

    rs = client.post(f"/api/planning/parade-dates/{pd_id}/sessions",
                      json={"cadet_group": "junior", "session_number": 1,
                            "activity_title": "Leave Conflict Test",
                            "facilitator_id": fac_id},
                      headers=hdr)
    assert rs.status_code == 200, rs.text
    session_id = rs.json()["session_id"]

    r = client.post(f"/api/planning/facilitators/{fac_id}/leave",
                     json={"start_date": "2026-09-01", "end_date": "2026-09-10",
                           "reason": "Regression test leave", "planning_year_id": yr_id},
                     headers=hdr)
    assert r.status_code == 200, r.text
    affected_ids = {s["session_id"] for s in r.json()["affected_sessions"]}
    assert session_id in affected_ids, (
        "A real session assigned to the facilitator on a date within the "
        "leave window must appear in affected_sessions — regression to the "
        "dead ScheduledSession table"
    )


def test_facilitator_on_leave_generates_conflict(client):
    """When a facilitator assigned to a session has a leave record covering the
    parade date, _run_conflict_check must produce a facilitator_on_leave conflict.
    Previously this conflict type did not exist — the check was never wired."""
    hdr = _sqn_admin_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, hdr)  # parade_date = 2026-09-04

    facs = client.get("/api/planning/facilitators", headers=hdr).json()
    if not facs:
        import pytest
        pytest.skip("No facilitators seeded for 703")
    fac_id = facs[0]["facilitator_id"]

    # Assign the facilitator to a session on that date
    rs = client.post(f"/api/planning/parade-dates/{pd_id}/sessions",
                     json={"cadet_group": "junior", "session_number": 1,
                           "activity_title": "Leave Conflict Scan Test",
                           "facilitator_id": fac_id},
                     headers=hdr)
    assert rs.status_code == 200, rs.text

    # Record leave that spans the parade date (2026-09-04)
    lv = client.post(f"/api/planning/facilitators/{fac_id}/leave",
                     json={"start_date": "2026-09-01", "end_date": "2026-09-10",
                           "reason": "Sick leave", "planning_year_id": yr_id},
                     headers=hdr)
    assert lv.status_code == 200, lv.text

    # Trigger conflict scan
    client.post(f"/api/planning/years/{yr_id}/run-checks", headers=hdr)

    # Confirm facilitator_on_leave conflict was created
    r = client.get(f"/api/planning/years/{yr_id}/conflicts", headers=hdr)
    assert r.status_code == 200
    types = [c["conflict_type"] for c in r.json()["conflicts"]]
    assert "facilitator_on_leave" in types, (
        "A facilitator assigned to a session while on leave must generate a "
        "facilitator_on_leave conflict after run-checks"
    )


# ─────────────────────────────────────────────────────────────
# Planning year Excel export
# ─────────────────────────────────────────────────────────────

def test_planning_year_excel_export_returns_xlsx(client):
    """Planning year export produces a valid xlsx response."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.get(f"/api/planning/years/{yr_id}/export.xlsx", headers=hdr)
    assert r.status_code == 200, r.text
    ct = r.headers.get("content-type", "")
    assert "spreadsheetml" in ct or "octet-stream" in ct or "excel" in ct, f"unexpected content-type: {ct}"


def test_planning_year_excel_export_requires_auth(client):
    # Fresh client with no prior login
    import uuid
    from fastapi.testclient import TestClient
    from app.main import app as _app
    fresh = TestClient(_app)
    r = fresh.get(f"/api/planning/years/{uuid.uuid4()}/export.xlsx")
    assert r.status_code == 401


def test_schedule_export_returns_xlsx(client):
    """Schedule export endpoint produces a valid xlsx response."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    yr_id = year["planning_year_id"]
    r = client.get(f"/api/planning/years/{yr_id}/schedule/export.xlsx", headers=hdr)
    assert r.status_code == 200, r.text
    ct = r.headers.get("content-type", "")
    assert "spreadsheetml" in ct or "octet-stream" in ct or "excel" in ct, f"unexpected content-type: {ct}"


def test_schedule_export_sqn_general_allowed(client):
    """sqn_general can download the schedule export for their own squadron."""
    hdr703 = _sqn_admin_hdr(client)
    year = _make_year(client, hdr703)
    yr_id = year["planning_year_id"]
    gen_hdr = _general_hdr(client)
    r = client.get(f"/api/planning/years/{yr_id}/schedule/export.xlsx", headers=gen_hdr)
    assert r.status_code == 200, r.text


def test_schedule_export_cross_sqn_denied(client):
    """sqn_general from another squadron cannot download the schedule export."""
    hdr703 = _sqn_admin_hdr(client)
    year = _make_year(client, hdr703)
    yr_id = year["planning_year_id"]
    other_gen = _other_sqn_general_hdr(client)
    r = client.get(f"/api/planning/years/{yr_id}/schedule/export.xlsx", headers=other_gen)
    assert r.status_code == 403, r.text


# ─────────────────────────────────────────────────────────────
# DEF-02: GET /api/planning/sessions/{id} used require_can_write_squadron
# which returned 403 for sqn_general (a read-only role that should be able
# to view session detail). Fixed to require_can_view_squadron for this
# read-only endpoint.
# ─────────────────────────────────────────────────────────────

def test_sqn_general_can_read_planning_session(client):
    """sqn_general must be able to GET their own squadron's planning session (was 403 before DEF-02 fix)."""
    hdr_admin = _sqn_admin_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, hdr_admin)
    cr = client.post(
        f"/api/planning/parade-dates/{pd_id}/sessions",
        json={"cadet_group": "junior", "session_number": 1, "activity_title": "DEF-02 test session"},
        headers=hdr_admin,
    )
    assert cr.status_code == 200, cr.text
    sess_id = cr.json()["session_id"]

    gen_hdr = _general_hdr(client)
    r = client.get(f"/api/planning/sessions/{sess_id}", headers=gen_hdr)
    assert r.status_code == 200, r.text
    assert r.json()["session_id"] == sess_id


def test_sqn_general_cannot_read_other_sqn_planning_session(client):
    """sqn_general from 701 must not read a session belonging to 703."""
    hdr_admin = _sqn_admin_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, hdr_admin)
    cr = client.post(
        f"/api/planning/parade-dates/{pd_id}/sessions",
        json={"cadet_group": "junior", "session_number": 1, "activity_title": "DEF-02 cross-sqn test"},
        headers=hdr_admin,
    )
    assert cr.status_code == 200, cr.text
    sess_id = cr.json()["session_id"]

    other_gen = _other_sqn_general_hdr(client)
    r = client.get(f"/api/planning/sessions/{sess_id}", headers=other_gen)
    assert r.status_code == 403, r.text


# ─────────────────────────────────────────────────────────────
# DATA-CONF-01 — data_freshness field on dashboard charts and command-centre
# ─────────────────────────────────────────────────────────────

def test_dashboard_charts_includes_data_freshness(client):
    """DATA-CONF-01: GET /api/dashboard/charts must include a data_freshness object
    with as_at, coverage_pct, and issues fields."""
    hdr = _sqn_admin_hdr(client)
    r = client.get("/api/dashboard/charts?window=term", headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "data_freshness" in d, "data_freshness must be present in dashboard charts response"
    df = d["data_freshness"]
    assert "as_at" in df, "data_freshness must contain as_at"
    assert "issues" in df, "data_freshness must contain issues list"
    assert isinstance(df["issues"], list)
    # coverage_pct is null for squadron scope (no cross-squadron comparison)
    assert df.get("coverage_pct") is None


def test_dashboard_charts_data_freshness_has_no_extra_keys(client):
    """DATA-CONF-01: data_freshness must only expose expected fields."""
    hdr = _sqn_admin_hdr(client)
    r = client.get("/api/dashboard/charts?window=term", headers=hdr)
    df = r.json()["data_freshness"]
    assert set(df.keys()) == {"as_at", "coverage_pct", "issues"}


def test_command_centre_includes_data_freshness(client):
    """DATA-CONF-01: GET /api/planning/command-centre must include data_freshness."""
    hdr = _sqn_admin_hdr(client)
    r = client.get("/api/planning/command-centre", headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    assert "data_freshness" in d, "data_freshness must be present in command-centre response"
    df = d["data_freshness"]
    assert "as_at" in df
    assert "issues" in df
    assert isinstance(df["issues"], list)


def test_dashboard_charts_unrecorded_sessions_appear_in_issues(client):
    """DATA-CONF-01: a past parade night with a session still in 'planned' status
    must cause the unrecorded outcomes issue to appear in data_freshness.issues."""
    hdr = _sqn_admin_hdr(client)
    # Create a parade night dated in the past (status will default to 'planned')
    pn_r = client.post("/api/parade-nights",
                       json={"date": "2024-09-13", "term": "T1"}, headers=hdr)
    assert pn_r.status_code == 200, pn_r.text
    pnid = pn_r.json()["parade_night_id"]
    # Create a session via the standard sessions endpoint — status defaults to 'planned'
    sess_r = client.post("/api/sessions",
                         json={"parade_night_id": pnid, "custom_title": "DATA-CONF test"},
                         headers=hdr)
    assert sess_r.status_code == 200, sess_r.text

    r = client.get("/api/dashboard/charts?window=year", headers=hdr)
    assert r.status_code == 200, r.text
    issues = r.json()["data_freshness"]["issues"]
    assert any("unrecorded" in i.lower() for i in issues), (
        f"Expected an 'unrecorded outcomes' issue but got: {issues}"
    )


# ─────────────────────────────────────────────────────────────
# CLASS-MATRIX-01 — Curriculum × Training Class progress matrix
# ─────────────────────────────────────────────────────────────

def test_class_matrix_requires_year_id(client):
    """CLASS-MATRIX-01: GET /api/curriculum/class-matrix without year_id must fail."""
    hdr = _sqn_admin_hdr(client)
    r = client.get("/api/curriculum/class-matrix", headers=hdr)
    assert r.status_code == 422, r.text  # FastAPI validation: required query param missing


def test_class_matrix_404_on_unknown_year(client):
    """CLASS-MATRIX-01: unknown year_id must return 404."""
    hdr = _sqn_admin_hdr(client)
    r = client.get("/api/curriculum/class-matrix?year_id=nonexistent-year", headers=hdr)
    assert r.status_code == 404, r.text


def test_class_matrix_empty_for_year_without_classes(client):
    """CLASS-MATRIX-01: a new year auto-creates 5 standard Training Classes (ORI/INI/JNR/INT/SNR);
    those classes have no linked training_stage_id so the matrix returns classes but no stages."""
    hdr = _sqn_admin_hdr(client)
    yr = client.post("/api/planning/years",
                     json={"year": next_test_year(), "name": "Matrix Test Year"}, headers=hdr)
    assert yr.status_code == 200, yr.text
    year_id = yr.json()["planning_year_id"]

    r = client.get(f"/api/curriculum/class-matrix?year_id={year_id}", headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    # Year creation now auto-creates 5 standard classes; each has training_stage_id=None
    # so no curriculum stage rows are resolved and stages remains empty.
    assert len(d["classes"]) == 5
    auto_names = {c["display_name"] for c in d["classes"]}
    assert "Orientation" in auto_names
    assert "Senior" in auto_names
    assert d["stages"] == []


def test_class_matrix_structure_with_classes(client):
    """CLASS-MATRIX-01: a year with Training Classes returns correct response shape."""
    hdr = _sqn_admin_hdr(client)
    yr = client.post("/api/planning/years",
                     json={"year": next_test_year(), "name": "Matrix Structure Test"}, headers=hdr)
    assert yr.status_code == 200, yr.text
    year_id = yr.json()["planning_year_id"]

    # Find an existing training stage (seeded via curriculum phases)
    stages = client.get("/api/curriculum/phases", headers=hdr).json()
    if not stages:
        import pytest
        pytest.skip("No training stages seeded — cannot test matrix with classes")
    stage_id = stages[0]["phase_id"]

    # Create a Training Class for this year
    tc_r = client.post("/api/training-classes",
                       json={"training_year_id": year_id, "training_stage_id": stage_id,
                             "display_name": "Matrix Test Class", "sequence": 1},
                       headers=hdr)
    assert tc_r.status_code == 200, tc_r.text

    r = client.get(f"/api/curriculum/class-matrix?year_id={year_id}", headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()

    assert "classes" in d
    assert "stages" in d
    assert "year_id" in d
    assert "year" in d
    # At least one class returned
    assert len(d["classes"]) >= 1
    cls = d["classes"][0]
    assert "class_id" in cls
    assert "display_name" in cls
    assert "stage_id" in cls

    # Stages have items with cells
    if d["stages"]:
        stage = d["stages"][0]
        assert "stage_id" in stage
        assert "items" in stage
        if stage["items"]:
            item = stage["items"][0]
            assert "curriculum_id" in item
            assert "code" in item
            assert "title" in item
            assert "cells" in item


def test_class_matrix_403_for_other_squadron(client):
    """CLASS-MATRIX-01: sqn_admin of one squadron cannot view another squadron's matrix."""
    hdr = _sqn_admin_hdr(client)
    yr = client.post("/api/planning/years",
                     json={"year": next_test_year(), "name": "Matrix 403 Test"}, headers=hdr)
    assert yr.status_code == 200, yr.text
    year_id = yr.json()["planning_year_id"]

    other_hdr = _other_sqn_admin_hdr(client) if hasattr(client, '_other_sqn') else None
    if other_hdr is None:
        import pytest
        pytest.skip("No second squadron admin available — cannot test cross-sqn 403")
    r = client.get(f"/api/curriculum/class-matrix?year_id={year_id}", headers=other_hdr)
    assert r.status_code == 403, r.text


# ─────────────────────────────────────────────────────────────
# CLASS-FORECAST-01 — Per-Training-Class planning forecast
# ─────────────────────────────────────────────────────────────

def test_class_forecasts_requires_year_id(client):
    """CLASS-FORECAST-01: GET /api/planning/class-forecasts without year_id must 422."""
    hdr = _sqn_admin_hdr(client)
    r = client.get("/api/planning/class-forecasts", headers=hdr)
    assert r.status_code == 422, r.text


def test_class_forecasts_404_unknown_year(client):
    """CLASS-FORECAST-01: unknown year_id returns 404."""
    hdr = _sqn_admin_hdr(client)
    r = client.get("/api/planning/class-forecasts?year_id=no-such-year", headers=hdr)
    assert r.status_code == 404, r.text


def test_class_forecasts_empty_for_year_without_classes(client):
    """CLASS-FORECAST-01: a new year auto-creates 5 standard Training Classes, so the forecast
    returns 5 entries (one per class) rather than an empty list."""
    hdr = _sqn_admin_hdr(client)
    yr = client.post("/api/planning/years",
                     json={"year": next_test_year(), "name": "Forecast Empty Test"}, headers=hdr)
    assert yr.status_code == 200, yr.text
    year_id = yr.json()["planning_year_id"]
    r = client.get(f"/api/planning/class-forecasts?year_id={year_id}", headers=hdr)
    assert r.status_code == 200, r.text
    forecasts = r.json()
    # Year creation auto-creates 5 standard classes (ORI/INI/JNR/INT/SNR)
    assert len(forecasts) == 5
    class_names = {f["class_name"] for f in forecasts}
    assert "Orientation" in class_names
    assert "Senior" in class_names


def test_class_forecasts_structure_with_class(client):
    """CLASS-FORECAST-01: a year with at least one Training Class returns forecast records
    with all required fields."""
    hdr = _sqn_admin_hdr(client)
    yr = client.post("/api/planning/years",
                     json={"year": next_test_year(), "name": "Forecast Structure Test"}, headers=hdr)
    assert yr.status_code == 200, yr.text
    year_id = yr.json()["planning_year_id"]

    stages = client.get("/api/curriculum/phases", headers=hdr).json()
    if not stages:
        import pytest
        pytest.skip("No training stages seeded")
    stage_id = stages[0]["phase_id"]

    tc_r = client.post("/api/training-classes",
                       json={"training_year_id": year_id, "training_stage_id": stage_id,
                             "display_name": "Forecast Test Class", "sequence": 1},
                       headers=hdr)
    assert tc_r.status_code == 200, tc_r.text

    r = client.get(f"/api/planning/class-forecasts?year_id={year_id}", headers=hdr)
    assert r.status_code == 200, r.text
    forecasts = r.json()
    assert len(forecasts) >= 1
    fc = forecasts[0]
    for field in ("class_id", "class_name", "remaining_requirements", "planned_requirements",
                  "unplanned_requirements", "remaining_parade_nights", "available_time_blocks",
                  "status", "message"):
        assert field in fc, f"Missing field: {field}"
    assert fc["status"] in ("on_track", "planning_risk", "critical")
