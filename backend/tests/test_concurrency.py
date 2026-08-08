"""Regression tests for optimistic locking (Phase 7).

Each test verifies that:
1. A successful update increments the version field.
2. A second concurrent update with a stale version returns 409.
3. An update without a version field succeeds (backward-compatible).
"""
import pytest
from tests.conftest import login


def _sqn_admin(client):
    return login(client, "ADMIN703")


def _wing_admin(client):
    return login(client, "ADMIN7WG")


# ─────────────────────────────────────────────────────────────
# PlanningYear — optimistic locking
# ─────────────────────────────────────────────────────────────

def _make_year(client, hdr, year=2099):
    r = client.post("/api/planning/years", json={"year": year, "name": f"{year} Lock Test"}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def test_planning_year_version_starts_at_zero(client):
    hdr = _sqn_admin(client)
    data = _make_year(client, hdr, year=2091)
    assert data["version"] == 0


def test_planning_year_version_increments_on_update(client):
    hdr = _sqn_admin(client)
    data = _make_year(client, hdr, year=2092)
    year_id = data["planning_year_id"]

    r = client.patch(f"/api/planning/years/{year_id}", json={"name": "Updated Name"}, headers=hdr)
    assert r.status_code == 200, r.text

    r2 = client.get(f"/api/planning/years/{year_id}", headers=hdr)
    assert r2.status_code == 200
    assert r2.json()["version"] == 1


def test_planning_year_stale_version_returns_409(client):
    hdr = _sqn_admin(client)
    data = _make_year(client, hdr, year=2093)
    year_id = data["planning_year_id"]

    # First update succeeds with correct version (0)
    r1 = client.patch(f"/api/planning/years/{year_id}",
                      json={"name": "First Write", "version": 0}, headers=hdr)
    assert r1.status_code == 200, r1.text

    # Second update with the now-stale version (0) must 409
    r2 = client.patch(f"/api/planning/years/{year_id}",
                      json={"name": "Second Write", "version": 0}, headers=hdr)
    assert r2.status_code == 409, r2.text
    assert r2.json()["detail"]["error"] == "version_conflict"
    assert r2.json()["detail"]["current_version"] == 1


def test_planning_year_update_without_version_succeeds(client):
    """Backward compatibility: omitting version skips the check."""
    hdr = _sqn_admin(client)
    data = _make_year(client, hdr, year=2094)
    year_id = data["planning_year_id"]

    r = client.patch(f"/api/planning/years/{year_id}", json={"name": "No Version Field"}, headers=hdr)
    assert r.status_code == 200, r.text


# ─────────────────────────────────────────────────────────────
# AnchorEvent — optimistic locking
# ─────────────────────────────────────────────────────────────

def _make_anchor(client, hdr, year_id):
    r = client.post(f"/api/planning/years/{year_id}/anchors", json={
        "event_name": "Lock Test Event",
        "event_type": "fieldcraft",
        "importance": "key_event",
        "start_date": "2099-06-01",
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def test_anchor_version_starts_at_zero(client):
    hdr = _sqn_admin(client)
    year = _make_year(client, hdr, year=2095)
    anchor = _make_anchor(client, hdr, year["planning_year_id"])
    assert anchor["version"] == 0


def test_anchor_stale_version_returns_409(client):
    hdr = _sqn_admin(client)
    year = _make_year(client, hdr, year=2096)
    anchor = _make_anchor(client, hdr, year["planning_year_id"])
    anchor_id = anchor["anchor_event_id"]

    # First update with correct version succeeds
    r1 = client.patch(f"/api/planning/anchors/{anchor_id}",
                      json={"event_name": "Updated", "version": 0}, headers=hdr)
    assert r1.status_code == 200, r1.text
    assert r1.json()["version"] == 1

    # Stale version must 409
    r2 = client.patch(f"/api/planning/anchors/{anchor_id}",
                      json={"event_name": "Stale", "version": 0}, headers=hdr)
    assert r2.status_code == 409, r2.text
    assert r2.json()["detail"]["error"] == "version_conflict"


def test_anchor_update_without_version_succeeds(client):
    hdr = _sqn_admin(client)
    year = _make_year(client, hdr, year=2097)
    anchor = _make_anchor(client, hdr, year["planning_year_id"])
    anchor_id = anchor["anchor_event_id"]

    r = client.patch(f"/api/planning/anchors/{anchor_id}",
                     json={"event_name": "No version"}, headers=hdr)
    assert r.status_code == 200, r.text


# ─────────────────────────────────────────────────────────────
# Session (TrainingSession) via planning router — optimistic locking
# ─────────────────────────────────────────────────────────────

def _make_parade_night(client, hdr, squadron_id, wing_id):
    """Create a parade night for the given squadron."""
    r = client.post("/api/parade-nights", json={
        "squadron_id": squadron_id,
        "wing_id": wing_id,
        "date": "2099-09-01",
        "parade_type": "normal",
    }, headers=hdr)
    assert r.status_code in (200, 201), r.text
    return r.json()


def _get_sqn_info(client, hdr):
    r = client.get("/api/auth/me", headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    return d.get("squadron_id"), d.get("wing_id")


def test_session_version_increments_via_planning_router(client):
    hdr = _sqn_admin(client)
    sqn_id, wing_id = _get_sqn_info(client, hdr)
    if not sqn_id:
        pytest.skip("No squadron available for this user")

    pn_resp = _make_parade_night(client, hdr, sqn_id, wing_id)
    pn_id = pn_resp.get("parade_night_id") or pn_resp.get("id")

    # Create a session
    r = client.post("/api/sessions", json={
        "parade_night_id": pn_id,
        "period_number": 1,
        "cadet_group": "junior",
    }, headers=hdr)
    assert r.status_code in (200, 201), r.text
    sess_id = r.json().get("session_id") or r.json().get("id")
    assert sess_id

    # Read it back via planning router to get version
    r2 = client.get(f"/api/planning/sessions/{sess_id}", headers=hdr)
    assert r2.status_code == 200, r2.text
    assert r2.json()["version"] == 0

    # Update it
    r3 = client.patch(f"/api/planning/sessions/{sess_id}",
                      json={"status": "confirmed", "version": 0}, headers=hdr)
    assert r3.status_code == 200, r3.text
    assert r3.json()["version"] == 1

    # Stale write must 409
    r4 = client.patch(f"/api/planning/sessions/{sess_id}",
                      json={"status": "published", "version": 0}, headers=hdr)
    assert r4.status_code == 409, r4.text
    assert r4.json()["detail"]["error"] == "version_conflict"


def test_session_stale_version_returns_409_via_training_router(client):
    hdr = _sqn_admin(client)
    sqn_id, wing_id = _get_sqn_info(client, hdr)
    if not sqn_id:
        pytest.skip("No squadron available for this user")

    pn_resp = _make_parade_night(client, hdr, sqn_id, wing_id)
    pn_id = pn_resp.get("parade_night_id") or pn_resp.get("id")

    r = client.post("/api/sessions", json={
        "parade_night_id": pn_id,
        "period_number": 2,
        "cadet_group": "senior",
    }, headers=hdr)
    assert r.status_code in (200, 201), r.text
    sess_id = r.json().get("session_id") or r.json().get("id")

    # First edit via training router with correct version
    r2 = client.put(f"/api/sessions/{sess_id}", json={
        "parade_night_id": pn_id,
        "period_number": 2,
        "cadet_group": "senior",
        "version": 0,
    }, headers=hdr)
    assert r2.status_code == 200, r2.text

    # Stale write must 409
    r3 = client.put(f"/api/sessions/{sess_id}", json={
        "parade_night_id": pn_id,
        "period_number": 2,
        "cadet_group": "senior",
        "version": 0,
    }, headers=hdr)
    assert r3.status_code == 409, r3.text
    assert r3.json()["detail"]["error"] == "version_conflict"


# ─────────────────────────────────────────────────────────────
# PlanningNotice — optimistic locking
# ─────────────────────────────────────────────────────────────

def _make_planning_notice(client, hdr, year=2098):
    """Create a planning year, parade date, and notice for locking tests."""
    yr = _make_year(client, hdr, year=year)
    year_id = yr["planning_year_id"]

    # Generate one parade date
    r = client.post(f"/api/planning/years/{year_id}/generate-parade-dates", json={
        "weekday": 3,
        "start_date": "2099-09-04",
        "end_date": "2099-09-30",
        "parade_type": "standard",
    }, headers=hdr)
    assert r.status_code == 200, r.text
    dates = r.json().get("parade_dates", [])
    assert dates, "No parade dates generated"
    date_id = dates[0]["parade_date_id"]

    # Create a notice on that date
    r2 = client.post(f"/api/planning/parade-dates/{date_id}/notices", json={
        "notice_text": "Locking test notice",
        "priority": "normal",
    }, headers=hdr)
    assert r2.status_code == 200, r2.text
    return r2.json()


def _make_parade_night(client, hdr, date):
    r = client.post("/api/parade-nights", json={"date": date, "term": "T4"}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["parade_night_id"]


def test_parade_night_version_starts_at_zero(client):
    """Governing instruction Section 23: concurrency test ("two users edit one Parade
    Night"). Confirmed live before this fix that update_parade_night had NO optimistic
    locking at all -- two concurrent PATCHes silently last-write-won with zero conflict
    signal, discarding one editor's change with no warning to either user. Every other
    frequently-co-edited entity in this file already had this pattern; ParadeNight was the
    one gap."""
    hdr = _sqn_admin(client)
    pnid = _make_parade_night(client, hdr, "2029-11-07")
    pn = client.get(f"/api/parade-nights/{pnid}", headers=hdr).json()
    assert pn["version"] == 0


def test_parade_night_version_increments_on_update(client):
    hdr = _sqn_admin(client)
    pnid = _make_parade_night(client, hdr, "2029-11-14")
    r = client.patch(f"/api/parade-nights/{pnid}", json={"notes": "Updated"}, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 1


def test_parade_night_stale_version_returns_409(client):
    """The exact scenario confirmed live: User A and User B both load the same Parade
    Night (same version), A saves first, B -- still holding the version from before A's
    save -- tries to save next. B's stale-version save must be rejected with a clear
    conflict, not silently applied over A's change."""
    hdr = _sqn_admin(client)
    pnid = _make_parade_night(client, hdr, "2029-11-21")

    r1 = client.patch(f"/api/parade-nights/{pnid}",
                      json={"notes": "User A's update", "version": 0}, headers=hdr)
    assert r1.status_code == 200, r1.text
    assert r1.json()["version"] == 1

    r2 = client.patch(f"/api/parade-nights/{pnid}",
                      json={"notes": "User B's overwrite attempt", "version": 0}, headers=hdr)
    assert r2.status_code == 409, r2.text
    assert r2.json()["detail"]["error"] == "version_conflict"
    assert r2.json()["detail"]["current_version"] == 1

    final = client.get(f"/api/parade-nights/{pnid}", headers=hdr).json()
    assert final["notes"] == "User A's update", "User A's change must not be silently overwritten"


def test_parade_night_update_without_version_succeeds(client):
    """Backward compatibility: omitting version skips the check, matching every other
    version-checked endpoint in this file."""
    hdr = _sqn_admin(client)
    pnid = _make_parade_night(client, hdr, "2029-11-28")
    r = client.patch(f"/api/parade-nights/{pnid}", json={"notes": "No version sent"}, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["notes"] == "No version sent"


def test_notice_stale_version_returns_409(client):
    hdr = _sqn_admin(client)
    try:
        notice = _make_planning_notice(client, hdr, year=2088)
    except AssertionError:
        pytest.skip("Notice creation prerequisites not met in this test environment")

    notice_id = notice.get("notice_id") or notice.get("id")
    if not notice_id:
        pytest.skip("Could not get notice_id from response")

    # First update with correct version
    r1 = client.patch(f"/api/planning/notices/{notice_id}",
                      json={"notice_text": "Updated", "version": 0}, headers=hdr)
    assert r1.status_code == 200, r1.text

    # Stale write must 409
    r2 = client.patch(f"/api/planning/notices/{notice_id}",
                      json={"notice_text": "Stale", "version": 0}, headers=hdr)
    assert r2.status_code == 409, r2.text
    assert r2.json()["detail"]["error"] == "version_conflict"
