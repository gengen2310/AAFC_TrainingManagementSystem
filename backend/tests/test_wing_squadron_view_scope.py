"""Tests for the master transformation plan Block 8 fix: a wing/national viewer
must be able to VIEW a specific squadron's Facilitators/Training Areas/Equipment/
Activities/Curriculum data via an explicit squadron_id query param, WITHOUT needing
Proxy/Delegated Intervention Mode (viewing is broad by design — only writing is
proxy-gated). Before this fix, only /api/parade-nights and /api/dashboard/charts
supported this pattern; the other four endpoints silently returned nothing (or the
caller's own empty squadron scope) for a wing/national viewer, forcing an
inconsistent "some squadron pages work without proxy, some don't" experience.
"""
from tests.conftest import login

ADM703 = "ADMIN703"
ADM7WG = "ADMIN7WG"
ADMNAT = "ADMINNATIONAL"


def _get_squadron_id(client, hdr):
    r = client.get("/api/auth/me", headers=hdr)
    return r.json()["session"]["squadron_id"]


def test_wing_admin_can_view_facilitators_via_squadron_id_without_proxy(client):
    hdr_sqn = login(client, ADM703)
    sqn_id = _get_squadron_id(client, hdr_sqn)

    hdr_wing = login(client, ADM7WG)
    # No proxy entered — this must still succeed and return 703's facilitators.
    r = client.get("/api/facilitators", params={"squadron_id": sqn_id}, headers=hdr_wing)
    assert r.status_code == 200, r.text
    # Compare against what 703's own admin sees, to confirm it's genuinely the same data.
    r_own = client.get("/api/facilitators", headers=hdr_sqn)
    assert r_own.status_code == 200
    assert len(r.json()) == len(r_own.json())


def test_wing_admin_without_squadron_id_falls_back_to_active_squadron(client):
    """Omitting squadron_id must behave exactly as before (backward compatible) —
    a wing_admin with no proxy and no squadron_id gets an empty/home-scope result,
    not an error."""
    hdr_wing = login(client, ADM7WG)
    r = client.get("/api/facilitators", headers=hdr_wing)
    assert r.status_code == 200, r.text


def test_wing_admin_cannot_view_a_squadron_outside_their_wing(client):
    """squadron_id must still be validated by require_can_view_squadron — a wing
    viewer cannot use this param to see a squadron in a DIFFERENT wing."""
    hdr_wing = login(client, ADM7WG)
    # A squadron_id that doesn't exist / isn't in this wing should 403, not leak data.
    r = client.get("/api/facilitators", params={"squadron_id": "00000000-0000-0000-0000-000000000000"}, headers=hdr_wing)
    assert r.status_code in (403, 404), r.text


def test_national_admin_can_view_training_areas_via_squadron_id_without_proxy(client):
    hdr_sqn = login(client, ADM703)
    sqn_id = _get_squadron_id(client, hdr_sqn)

    hdr_nat = login(client, ADMNAT)
    r = client.get("/api/training-areas", params={"squadron_id": sqn_id}, headers=hdr_nat)
    assert r.status_code == 200, r.text


def test_wing_admin_can_view_equipment_via_squadron_id_without_proxy(client):
    hdr_sqn = login(client, ADM703)
    sqn_id = _get_squadron_id(client, hdr_sqn)

    hdr_wing = login(client, ADM7WG)
    r = client.get("/api/equipment", params={"squadron_id": sqn_id}, headers=hdr_wing)
    assert r.status_code == 200, r.text


def test_wing_admin_can_view_activities_via_squadron_id_without_proxy(client):
    hdr_sqn = login(client, ADM703)
    sqn_id = _get_squadron_id(client, hdr_sqn)

    hdr_wing = login(client, ADM7WG)
    r = client.get("/api/activities", params={"squadron_id": sqn_id}, headers=hdr_wing)
    assert r.status_code == 200, r.text


def test_wing_admin_can_view_curriculum_via_squadron_id_without_proxy(client):
    hdr_sqn = login(client, ADM703)
    sqn_id = _get_squadron_id(client, hdr_sqn)

    hdr_wing = login(client, ADM7WG)
    r = client.get("/api/curriculum", params={"squadron_id": sqn_id}, headers=hdr_wing)
    assert r.status_code == 200, r.text


def test_wing_admin_can_view_facilitator_load_report_via_squadron_id_without_proxy(client):
    hdr_sqn = login(client, ADM703)
    sqn_id = _get_squadron_id(client, hdr_sqn)

    hdr_wing = login(client, ADM7WG)
    r = client.get("/api/reports/facilitator-load", params={"squadron_id": sqn_id}, headers=hdr_wing)
    assert r.status_code == 200, r.text


def test_national_admin_can_view_summary_report_via_squadron_id_without_proxy(client):
    hdr_sqn = login(client, ADM703)
    sqn_id = _get_squadron_id(client, hdr_sqn)

    hdr_nat = login(client, ADMNAT)
    r = client.get("/api/reports/summary", params={"squadron_id": sqn_id}, headers=hdr_nat)
    assert r.status_code == 200, r.text


def test_wing_admin_can_view_not_delivered_report_via_squadron_id_without_proxy(client):
    hdr_sqn = login(client, ADM703)
    sqn_id = _get_squadron_id(client, hdr_sqn)

    hdr_wing = login(client, ADM7WG)
    r = client.get("/api/reports/not-delivered", params={"squadron_id": sqn_id}, headers=hdr_wing)
    assert r.status_code == 200, r.text


def test_wing_admin_dashboard_charts_squadron_id_returns_full_squadron_chart_set(client):
    """Master transformation plan Block 8: selecting a squadron on the Dashboard
    must return the SAME chart set a squadron_admin gets for their own squadron
    (tonight/upcoming_readiness/etc.), not the smaller subset this endpoint used
    to merge in — the doctrine is "inherit, don't diverge"."""
    hdr_sqn = login(client, ADM703)
    sqn_id = _get_squadron_id(client, hdr_sqn)
    r_own = client.get("/api/dashboard/charts", headers=hdr_sqn)
    assert r_own.status_code == 200
    own_chart_ids = set(r_own.json()["charts"].keys())

    hdr_wing = login(client, ADM7WG)
    r = client.get("/api/dashboard/charts", params={"squadron_id": sqn_id}, headers=hdr_wing)
    assert r.status_code == 200, r.text
    body = r.json()
    # Caller's own scope is still "wing" — this is a viewer looking at a squadron,
    # not becoming squadron-scoped themselves.
    assert body["scope"] == "wing"
    # Every chart a squadron_admin sees for their own squadron must also be present
    # here — no reduced subset.
    for chart_id in own_chart_ids:
        assert chart_id in body["charts"], f"missing {chart_id} in wing-viewer's squadron-selected charts"
    # Plus the wing's own comparison charts, layered on top.
    assert "squadron_readiness" in body["charts"]


def test_national_admin_dashboard_charts_squadron_id_returns_full_squadron_chart_set(client):
    """Same as above, for national scope — previously squadron_id was silently
    ignored entirely for national callers."""
    hdr_sqn = login(client, ADM703)
    sqn_id = _get_squadron_id(client, hdr_sqn)

    hdr_nat = login(client, ADMNAT)
    r = client.get("/api/dashboard/charts", params={"squadron_id": sqn_id}, headers=hdr_nat)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["scope"] == "national"
    assert "tonight" in body["charts"]
    assert "wing_readiness" in body["charts"]


def test_wing_admin_dashboard_charts_cannot_select_squadron_outside_their_wing(client):
    hdr_wing = login(client, ADM7WG)
    r = client.get("/api/dashboard/charts", params={"squadron_id": "00000000-0000-0000-0000-000000000000"}, headers=hdr_wing)
    assert r.status_code == 404, r.text


def test_squadron_id_view_does_not_grant_write_access(client):
    """Viewing via squadron_id must not be confused with write authorisation —
    a wing_admin with no active proxy still cannot WRITE to the squadron even
    while successfully viewing it via squadron_id."""
    hdr_sqn = login(client, ADM703)
    sqn_id = _get_squadron_id(client, hdr_sqn)

    hdr_wing = login(client, ADM7WG)
    view_r = client.get("/api/facilitators", params={"squadron_id": sqn_id}, headers=hdr_wing)
    assert view_r.status_code == 200

    write_r = client.post("/api/facilitators", json={
        "last_name": "Should not be created", "type": "Staff",
    }, headers=hdr_wing)
    assert write_r.status_code == 403, write_r.text
