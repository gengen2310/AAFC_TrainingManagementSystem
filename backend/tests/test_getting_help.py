"""Tests for GET/PUT /api/activities/getting-help -- the Activities tab's
admin-editable "Getting Help" content section (risk-register submission,
2026-08-05: "the Activities tab needs an editable Getting Help section that
system admin can add text to").
"""
from tests.conftest import login

URL = "/api/activities/getting-help"


def _sysadmin(client):
    return login(client, "SYSADMIN2026")


def _sqn_admin(client):
    return login(client, "ADMIN703")


def _nat_admin(client):
    return login(client, "ADMINNATIONAL")


def test_get_requires_auth(client):
    assert client.get(URL).status_code == 401


def test_put_requires_auth(client):
    assert client.put(URL, json={"content": "x"}).status_code == 401


def test_get_returns_empty_content_by_default(client):
    hdrs = _sqn_admin(client)
    r = client.get(URL, headers=hdrs)
    assert r.status_code == 200
    assert r.json()["content"] == ""


def test_sysadmin_can_set_content(client):
    hdrs = _sysadmin(client)
    r = client.put(URL, json={"content": "Call the Wing Training Officer for support."}, headers=hdrs)
    assert r.status_code == 200, r.text
    assert r.json()["content"] == "Call the Wing Training Officer for support."

    # Any authenticated role can then read the updated content.
    hdrs2 = _sqn_admin(client)
    r2 = client.get(URL, headers=hdrs2)
    assert r2.status_code == 200
    assert r2.json()["content"] == "Call the Wing Training Officer for support."


def test_sqn_admin_cannot_set_content(client):
    hdrs = _sqn_admin(client)
    r = client.put(URL, json={"content": "attempted edit"}, headers=hdrs)
    assert r.status_code == 403


def test_nat_admin_cannot_set_content(client):
    hdrs = _nat_admin(client)
    r = client.put(URL, json={"content": "attempted edit"}, headers=hdrs)
    assert r.status_code == 403


def test_update_is_audited(client):
    hdrs = _sysadmin(client)
    client.put(URL, json={"content": "audited content"}, headers=hdrs)
    rows = client.get("/api/audit?object_type=system_setting", headers=hdrs).json()
    matches = [a for a in rows if a["action"] == "getting_help_content_updated"]
    assert len(matches) >= 1
