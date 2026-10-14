"""D16 (2026-10-11): scheduling a session against a national-scope phase 500s.

planning._phase_visible_to calls resolve_national_id for a national phase
with a scope_id, but planning.py never imported it, so the branch raised
NameError (found by the C5 extraction review). Every national phase created
since v61 carries a scope_id, so adding one as a session audience failed.
"""
from tests.conftest import login
from tests.test_session_custom_phase_audience import _make_session


def test_a_squadron_can_schedule_against_its_own_national_phase(client):
    nat = login(client, "ADMINNATIONAL")
    ph = client.post("/api/custom-training-phases", headers=nat, json={
        "name": "D16 national phase", "scope_type": "national", "applies_from": "2041-01-01"})
    assert ph.status_code == 200, ph.text
    assert ph.json()["scope_id"]                       # post-v61: pinned to the national
    hdr = login(client, "ADMIN703")
    sid = _make_session(client, hdr, days_ahead=613)
    r = client.post(f"/api/planning/sessions/{sid}/custom-phase-audiences",
                    json={"custom_phase_id": ph.json()["custom_phase_id"]}, headers=hdr)
    assert r.status_code == 200, r.text
    assert ph.json()["custom_phase_id"] in [a["custom_phase_id"] for a in r.json()["custom_phase_audiences"]]
