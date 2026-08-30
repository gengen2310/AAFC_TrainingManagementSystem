"""Part 51 — Proxy / Delegated Intervention must resolve the target squadron.

Principal carries two scopes: the base identity (who you are) and the acting
scope (whose data you are working on while proxied). Authorisation correctly
uses the base identity via can_write_squadron. Data SELECTION must use the
acting scope -- and endpoints that default a squadron from `p.squadron_id`
alone get None for a wing or national caller, because those accounts have no
home squadron.

POST /api/planning/locations did exactly that. With no unit_id in the body the
default resolved to None, which skipped the `if unit_id:` block containing
require_can_write_squadron entirely, and the insert then failed on a NOT NULL
constraint -- surfacing a 500 instead of the "enter Proxy Mode" message the
guard exists to produce.
"""
from conftest import login


def _sqn_id(client, headers, code="703"):
    r = client.get("/api/squadrons", headers=headers)
    assert r.status_code == 200, r.text
    for s in r.json():
        if s.get("code") == code:
            return s.get("squadron_id") or s.get("id")
    raise AssertionError(f"squadron {code} not found in {r.text[:300]}")


def test_wing_admin_without_proxy_gets_a_message_not_a_crash(client):
    """No proxy, no unit_id: the caller must be told to enter Proxy Mode."""
    h = login(client, "ADMIN7WG")
    r = client.post("/api/planning/locations", headers=h,
                    json={"name": "Wing Hall", "location_type": "indoor"})
    assert r.status_code != 500, (
        f"unscoped create crashed instead of refusing: {r.status_code} {r.text[:300]}"
    )
    assert r.status_code in (400, 403), f"unexpected: {r.status_code} {r.text[:300]}"


def test_national_admin_without_intervention_gets_a_message_not_a_crash(client):
    h = login(client, "ADMINNATIONAL")
    r = client.post("/api/planning/locations", headers=h,
                    json={"name": "National Hall", "location_type": "indoor"})
    assert r.status_code != 500, (
        f"unscoped create crashed instead of refusing: {r.status_code} {r.text[:300]}"
    )
    assert r.status_code in (400, 403), f"unexpected: {r.status_code} {r.text[:300]}"


def test_wing_admin_in_proxy_creates_in_the_proxied_squadron(client):
    """With Proxy Mode active and no unit_id, the target is the proxied squadron."""
    h = login(client, "ADMIN7WG")
    sqn = _sqn_id(client, h, "703")
    enter = client.post(f"/api/proxy/enter/{sqn}", headers=h,
                        json={"reason": "Part 51 scope check"})
    assert enter.status_code == 200, enter.text
    try:
        r = client.post("/api/planning/locations", headers=h,
                        json={"name": "Proxied Hall", "location_type": "indoor"})
        assert r.status_code == 200, f"proxied create failed: {r.status_code} {r.text[:300]}"
        assert r.json().get("unit_id") == sqn, (
            f"created against the wrong squadron: {r.json().get('unit_id')} != {sqn}"
        )
    finally:
        client.post("/api/proxy/exit", headers=h)


def test_sqn_admin_default_is_unchanged(client):
    """The existing behaviour for a squadron admin must not move."""
    h = login(client, "ADMIN703")
    sqn = _sqn_id(client, h, "703")
    r = client.post("/api/planning/locations", headers=h,
                    json={"name": "Home Hall", "location_type": "indoor"})
    assert r.status_code == 200, r.text
    assert r.json().get("unit_id") == sqn
