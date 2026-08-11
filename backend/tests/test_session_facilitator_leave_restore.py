"""REM-133: TrainingSession delete (DELETE /api/planning/sessions/{id}) and
PlanningFacilitatorLeave removal (DELETE /api/planning/facilitator-leave/{id})
have existed for a long time and correctly soft-delete (is_archived=True),
but neither had a restore counterpart or any way to see the archived record
through the product. Follows the same archive/restore pattern already proven
for Facilitator, Wing HQ Event, and Curriculum Item.
"""
from tests.conftest import login

ADM703 = "ADMIN703"
ADM704 = "ADMIN704"


def _sqn_hdr(client):
    return login(client, ADM703)


def _setup_year_with_date(client, hdr):
    r = client.post("/api/planning/years", json={"year": 2026, "name": "2026 Training Year"}, headers=hdr)
    assert r.status_code == 200, r.text
    yr_id = r.json()["planning_year_id"]
    rp = client.post(f"/api/planning/years/{yr_id}/parade-dates",
                     json={"parade_date": "2026-09-04"}, headers=hdr)
    assert rp.status_code == 200, rp.text
    return yr_id, rp.json()["parade_date_id"]


def _create_session(client, hdr, pd_id):
    r = client.post(f"/api/planning/parade-dates/{pd_id}/sessions",
                    json={"cadet_group": "junior", "session_number": 1}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def _create_fac(client, hdr, last_name="Leave Restore Test Fac"):
    r = client.post("/api/facilitators", json={"last_name": last_name}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["facilitator_id"]


def _create_leave(client, hdr, fac_id):
    r = client.post(f"/api/planning/facilitators/{fac_id}/leave",
                    json={"start_date": "2026-09-01", "end_date": "2026-09-08"}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["leave"]["id"]


# ─────────────────────────────────────────────────────────────
# Session restore
# ─────────────────────────────────────────────────────────────

def test_session_restore_reverses_delete_and_is_visible_via_archived_sessions(client):
    hdr = _sqn_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, hdr)
    sess_id = _create_session(client, hdr, pd_id)

    assert client.delete(f"/api/planning/sessions/{sess_id}", headers=hdr).status_code == 200

    weekly = client.get(f"/api/planning/parade-dates/{pd_id}/weekly-program", headers=hdr).json()
    assert not any(s["session_id"] == sess_id for s in weekly["sessions"])

    archived = client.get(f"/api/planning/parade-dates/{pd_id}/archived-sessions", headers=hdr).json()
    assert any(s["session_id"] == sess_id for s in archived["sessions"])

    r = client.post(f"/api/planning/sessions/{sess_id}/restore", headers=hdr)
    assert r.status_code == 200, r.text

    weekly_after = client.get(f"/api/planning/parade-dates/{pd_id}/weekly-program", headers=hdr).json()
    assert any(s["session_id"] == sess_id for s in weekly_after["sessions"])
    archived_after = client.get(f"/api/planning/parade-dates/{pd_id}/archived-sessions", headers=hdr).json()
    assert not any(s["session_id"] == sess_id for s in archived_after["sessions"])


def test_session_restore_rejects_already_active_session(client):
    hdr = _sqn_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, hdr)
    sess_id = _create_session(client, hdr, pd_id)
    r = client.post(f"/api/planning/sessions/{sess_id}/restore", headers=hdr)
    assert r.status_code == 409, r.text


def test_session_restore_scoped_out_for_other_squadron_admin(client):
    hdr703 = _sqn_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, hdr703)
    sess_id = _create_session(client, hdr703, pd_id)
    assert client.delete(f"/api/planning/sessions/{sess_id}", headers=hdr703).status_code == 200

    hdr704 = login(client, ADM704)
    r = client.post(f"/api/planning/sessions/{sess_id}/restore", headers=hdr704)
    assert r.status_code == 403, r.text


def test_session_restore_requires_authentication(client):
    hdr = _sqn_hdr(client)
    yr_id, pd_id = _setup_year_with_date(client, hdr)
    sess_id = _create_session(client, hdr, pd_id)
    assert client.delete(f"/api/planning/sessions/{sess_id}", headers=hdr).status_code == 200
    client.cookies.clear()
    r = client.post(f"/api/planning/sessions/{sess_id}/restore")
    assert r.status_code == 401, r.text


def test_session_restore_nonexistent_returns_404(client):
    hdr = _sqn_hdr(client)
    r = client.post("/api/planning/sessions/does-not-exist/restore", headers=hdr)
    assert r.status_code == 404, r.text


# ─────────────────────────────────────────────────────────────
# Facilitator-leave restore
# ─────────────────────────────────────────────────────────────

def test_leave_restore_reverses_delete_and_is_visible_via_include_archived(client):
    hdr = _sqn_hdr(client)
    fac_id = _create_fac(client, hdr)
    leave_id = _create_leave(client, hdr, fac_id)

    assert client.delete(f"/api/planning/facilitator-leave/{leave_id}", headers=hdr).status_code == 200

    default_list = client.get(f"/api/planning/facilitators/{fac_id}/leave", headers=hdr).json()["leave"]
    assert not any(l["id"] == leave_id for l in default_list)

    archived_list = client.get(f"/api/planning/facilitators/{fac_id}/leave?include_archived=true", headers=hdr).json()["leave"]
    entry = next((l for l in archived_list if l["id"] == leave_id), None)
    assert entry is not None
    assert entry["is_archived"] is True

    r = client.post(f"/api/planning/facilitator-leave/{leave_id}/restore", headers=hdr)
    assert r.status_code == 200, r.text

    restored_list = client.get(f"/api/planning/facilitators/{fac_id}/leave", headers=hdr).json()["leave"]
    assert any(l["id"] == leave_id for l in restored_list)


def test_leave_restore_rejects_already_active_leave(client):
    hdr = _sqn_hdr(client)
    fac_id = _create_fac(client, hdr, "Not Archived Leave Fac")
    leave_id = _create_leave(client, hdr, fac_id)
    r = client.post(f"/api/planning/facilitator-leave/{leave_id}/restore", headers=hdr)
    assert r.status_code == 409, r.text


def test_leave_restore_scoped_out_for_other_squadron_admin(client):
    hdr703 = _sqn_hdr(client)
    fac_id = _create_fac(client, hdr703, "Scope Test Leave Fac")
    leave_id = _create_leave(client, hdr703, fac_id)
    assert client.delete(f"/api/planning/facilitator-leave/{leave_id}", headers=hdr703).status_code == 200

    hdr704 = login(client, ADM704)
    r = client.post(f"/api/planning/facilitator-leave/{leave_id}/restore", headers=hdr704)
    assert r.status_code == 403, r.text


def test_leave_restore_requires_authentication(client):
    hdr = _sqn_hdr(client)
    fac_id = _create_fac(client, hdr, "Auth Test Leave Fac")
    leave_id = _create_leave(client, hdr, fac_id)
    assert client.delete(f"/api/planning/facilitator-leave/{leave_id}", headers=hdr).status_code == 200
    client.cookies.clear()
    r = client.post(f"/api/planning/facilitator-leave/{leave_id}/restore")
    assert r.status_code == 401, r.text


def test_leave_restore_nonexistent_returns_404(client):
    hdr = _sqn_hdr(client)
    r = client.post("/api/planning/facilitator-leave/does-not-exist/restore", headers=hdr)
    assert r.status_code == 404, r.text
