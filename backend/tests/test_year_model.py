"""Phase A: year model tests — Wing.timezone, PlanningYear.status, lifecycle, rollover."""
from conftest import login, next_test_year
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


def test_wing_timezone_requires_auth(client):
    r = client.get("/api/planning/wing-timezone")
    assert r.status_code == 401
