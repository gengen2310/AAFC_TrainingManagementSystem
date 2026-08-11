"""REM-133: Facilitator archive (DELETE /api/facilitators/{id}) has existed
for a long time and correctly soft-deletes (is_archived=True), but there was
no restore counterpart and no include_archived param on the list endpoint --
once archived, a facilitator was reachable in the database but permanently
unreachable through the product. Follows the same archive/restore pattern
already proven for Account/Wing/Squadron/PlanningYear/Flight/Activity.
"""
from tests.conftest import login

ADM703 = "ADMIN703"
ADM704 = "ADMIN704"


def _create_fac(client, hdr, last_name="Restore Test Fac"):
    r = client.post("/api/facilitators", json={"last_name": last_name}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["facilitator_id"]


def test_restore_reverses_archive_and_is_visible_via_include_archived(client):
    h = login(client, ADM703)
    fid = _create_fac(client, h)

    archive_r = client.delete(f"/api/facilitators/{fid}", headers=h)
    assert archive_r.status_code == 200, archive_r.text

    default_list = client.get("/api/facilitators", headers=h).json()
    assert not any(f["facilitator_id"] == fid for f in default_list)

    archived_list = client.get("/api/facilitators?include_archived=true", headers=h).json()
    entry = next((f for f in archived_list if f["facilitator_id"] == fid), None)
    assert entry is not None
    assert entry["is_archived"] is True

    restore_r = client.post(f"/api/facilitators/{fid}/restore", headers=h)
    assert restore_r.status_code == 200, restore_r.text

    restored_list = client.get("/api/facilitators", headers=h).json()
    restored_entry = next((f for f in restored_list if f["facilitator_id"] == fid), None)
    assert restored_entry is not None
    assert restored_entry["is_archived"] is False


def test_restore_rejects_already_active_facilitator(client):
    h = login(client, ADM703)
    fid = _create_fac(client, h, "Not Archived Fac")
    r = client.post(f"/api/facilitators/{fid}/restore", headers=h)
    assert r.status_code == 409, r.text


def test_restore_scoped_out_for_other_squadron_admin(client):
    h703 = login(client, ADM703)
    fid = _create_fac(client, h703, "Scope Test Fac")
    assert client.delete(f"/api/facilitators/{fid}", headers=h703).status_code == 200

    h704 = login(client, ADM704)
    r = client.post(f"/api/facilitators/{fid}/restore", headers=h704)
    assert r.status_code == 403, r.text


def test_restore_requires_authentication(client):
    h = login(client, ADM703)
    fid = _create_fac(client, h, "Auth Test Fac")
    assert client.delete(f"/api/facilitators/{fid}", headers=h).status_code == 200
    # login() also sets the aafc_session cookie fallback (architecture.md) on
    # this same TestClient -- clear it so this call is genuinely unauthenticated,
    # not just missing the Authorization header.
    client.cookies.clear()
    r = client.post(f"/api/facilitators/{fid}/restore")
    assert r.status_code == 401, r.text


def test_restore_nonexistent_facilitator_returns_404(client):
    h = login(client, ADM703)
    r = client.post("/api/facilitators/does-not-exist/restore", headers=h)
    assert r.status_code == 404, r.text


def test_archived_facilitator_still_excluded_from_default_list_by_default(client):
    """Regression guard for the include_archived param itself -- confirms the
    default (no query param) behaviour is unchanged from before this change."""
    h = login(client, ADM703)
    fid = _create_fac(client, h, "Default Filter Fac")
    assert client.delete(f"/api/facilitators/{fid}", headers=h).status_code == 200
    default_list = client.get("/api/facilitators", headers=h).json()
    assert not any(f["facilitator_id"] == fid for f in default_list)
    explicit_false_list = client.get("/api/facilitators?include_archived=false", headers=h).json()
    assert not any(f["facilitator_id"] == fid for f in explicit_false_list)
