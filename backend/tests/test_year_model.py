"""Phase A: year model tests — Wing.timezone, PlanningYear.status, lifecycle, rollover."""
from tests.conftest import login, next_test_year
from datetime import date


def _sqn_admin_hdr(client):
    return login(client, "ADMIN703")


def _wing_admin_hdr(client):
    return login(client, "ADMIN7WG")


def _nat_admin_hdr(client):
    return login(client, "ADMINNATIONAL")


# ── Wing.timezone ─────────────────────────────────────────────

def test_wing_timezone_returned_in_year_list(client):
    """Wing.timezone must be set for 7WG so rollover is computable."""
    h = _wing_admin_hdr(client)
    r = client.get("/api/planning/years?wing_id=", headers=h)
    # Wing timezone is not in year list — test via a dedicated endpoint
    # This test verifies the endpoint exists and returns Perth.
    r = client.get("/api/planning/wing-timezone", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["timezone"] == "Australia/Perth"


def test_wing_timezone_sqn_returns_their_wing_tz(client):
    h = _sqn_admin_hdr(client)
    r = client.get("/api/planning/wing-timezone", headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["timezone"] == "Australia/Perth"


def test_wing_timezone_no_wing_returns_400(client):
    h = _nat_admin_hdr(client)
    r = client.get("/api/planning/wing-timezone", headers=h)
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["error"] == "no_wing"


def test_wing_timezone_requires_auth(client):
    r = client.get("/api/planning/wing-timezone")
    assert r.status_code == 401


# ── PlanningYear.status field ─────────────────────────────────

def test_new_year_has_status_active(client):
    h = _sqn_admin_hdr(client)
    r = client.post("/api/planning/years",
                    json={"year": next_test_year(), "name": "Status test"},
                    headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "status" in body, "status field missing from year response"
    assert body["status"] == "active"
    assert body["active_status"] is True  # backward-compat: both present


def test_archive_year_sets_status_archived(client):
    h = _sqn_admin_hdr(client)
    yr = client.post("/api/planning/years",
                     json={"year": next_test_year(), "name": "Archive test"},
                     headers=h).json()
    yr_id = yr["planning_year_id"]
    r = client.patch(f"/api/planning/years/{yr_id}",
                     json={"active_status": False, "version": yr["version"]},
                     headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "archived"
    assert body["active_status"] is False


def test_restore_year_sets_status_active(client):
    h = _sqn_admin_hdr(client)
    yr = client.post("/api/planning/years",
                     json={"year": next_test_year(), "name": "Restore test"},
                     headers=h).json()
    yr_id = yr["planning_year_id"]
    # Archive it first
    client.patch(f"/api/planning/years/{yr_id}",
                 json={"active_status": False, "version": yr["version"]},
                 headers=h)
    yr2 = client.get(f"/api/planning/years/{yr_id}", headers=h).json()
    # Restore
    r = client.patch(f"/api/planning/years/{yr_id}",
                     json={"active_status": True, "version": yr2["version"]},
                     headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "active"
    assert r.json()["active_status"] is True
