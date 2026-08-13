"""Tests for GET /api/dashboard/adoption.

Covers: auth, scope enforcement (squadron → 400), period validation,
response shape for wing and national scopes, correct field presence.
"""
import pytest
from conftest import login

URL = "/api/dashboard/adoption"

def _sqn_admin(client):   return login(client, "ADMIN703")
def _wing_admin(client):  return login(client, "ADMIN7WG")
def _wing_viewer(client): return login(client, "7WG2026")
def _national(client):    return login(client, "ADMINNATIONAL")
def _sysadmin(client):    return login(client, "SYSADMIN2026")


def test_adoption_requires_auth(client):
    assert client.get(URL).status_code == 401


def test_squadron_scope_rejected(client):
    h = _sqn_admin(client)
    r = client.get(URL, headers=h)
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "not_applicable"


def test_wing_admin_returns_200(client):
    h = _wing_admin(client)
    r = client.get(URL, headers=h)
    assert r.status_code == 200


def test_wing_viewer_returns_200(client):
    h = _wing_viewer(client)
    r = client.get(URL, headers=h)
    assert r.status_code == 200


def test_national_admin_returns_200(client):
    h = _national(client)
    r = client.get(URL, headers=h)
    assert r.status_code == 200


def test_system_admin_returns_200(client):
    h = _sysadmin(client)
    r = client.get(URL, headers=h)
    assert r.status_code == 200


def test_response_shape_wing(client):
    h = _wing_admin(client)
    r = client.get(URL, headers=h)
    body = r.json()
    assert body["scope"] == "wing"
    assert "period" in body
    assert "since" in body
    assert "generated_at" in body
    assert "total_units" in body
    assert "active_units" in body
    assert "units" in body
    assert isinstance(body["units"], list)


def test_unit_row_shape(client):
    h = _wing_admin(client)
    r = client.get(URL, headers=h)
    units = r.json()["units"]
    if not units:
        pytest.skip("No squadrons in Wing — cannot check unit row shape")
    u = units[0]
    for field in [
        "squadron_id", "code", "name", "active_users", "total_meaningful_actions",
        "sessions_scheduled", "outcomes_recorded", "programs_published",
        "facilitators_maintained", "last_activity",
    ]:
        assert field in u, f"Missing field: {field}"


def test_period_7d(client):
    h = _wing_admin(client)
    r = client.get(URL, params={"period": "7d"}, headers=h)
    assert r.status_code == 200
    assert r.json()["period"] == "7d"


def test_period_term(client):
    h = _wing_admin(client)
    r = client.get(URL, params={"period": "term"}, headers=h)
    assert r.status_code == 200
    assert r.json()["period"] == "term"


def test_period_year(client):
    h = _wing_admin(client)
    r = client.get(URL, params={"period": "year"}, headers=h)
    assert r.status_code == 200


def test_invalid_period_rejected(client):
    h = _wing_admin(client)
    r = client.get(URL, params={"period": "invalid"}, headers=h)
    assert r.status_code == 422


def test_active_units_lte_total_units(client):
    h = _wing_admin(client)
    r = client.get(URL, headers=h)
    body = r.json()
    assert body["active_units"] <= body["total_units"]


def test_unit_counts_are_non_negative(client):
    h = _wing_admin(client)
    r = client.get(URL, headers=h)
    for u in r.json()["units"]:
        assert u["active_users"] >= 0
        assert u["total_meaningful_actions"] >= 0
        assert u["sessions_scheduled"] >= 0
        assert u["outcomes_recorded"] >= 0
        assert u["programs_published"] >= 0
