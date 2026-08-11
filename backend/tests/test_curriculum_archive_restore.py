"""REM-133: Curriculum-item archive (DELETE /api/curriculum/{id}) has existed
for a long time and correctly soft-deletes (is_archived=True), but there was
no restore counterpart and no include_archived param on the list endpoint --
once archived, a curriculum item was reachable in the database but
permanently unreachable through the product. Follows the same archive/
restore pattern already proven for Facilitator and Wing HQ Event.
"""
import uuid

from tests.conftest import login

ADM703 = "ADMIN703"
ADM704 = "ADMIN704"


def _create_curr(client, hdr, title="Restore Test Item"):
    r = client.post("/api/curriculum", json={
        "code": f"RESTORETEST-{uuid.uuid4().hex[:8]}", "title": title,
        "phase": "A. Orientation", "duration_minutes": 60,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["curriculum_id"]


def test_restore_reverses_archive_and_is_visible_via_include_archived(client):
    h = login(client, ADM703)
    cid = _create_curr(client, h)

    archive_r = client.delete(f"/api/curriculum/{cid}", headers=h)
    assert archive_r.status_code == 200, archive_r.text

    default_list = client.get("/api/curriculum", headers=h).json()["items"]
    assert not any(i["curriculum_id"] == cid for i in default_list)

    archived_list = client.get("/api/curriculum?include_archived=true", headers=h).json()["items"]
    entry = next((i for i in archived_list if i["curriculum_id"] == cid), None)
    assert entry is not None
    assert entry["is_archived"] is True

    restore_r = client.post(f"/api/curriculum/{cid}/restore", headers=h)
    assert restore_r.status_code == 200, restore_r.text

    restored_list = client.get("/api/curriculum", headers=h).json()["items"]
    restored_entry = next((i for i in restored_list if i["curriculum_id"] == cid), None)
    assert restored_entry is not None
    assert restored_entry["is_archived"] is False


def test_restore_rejects_already_active_item(client):
    h = login(client, ADM703)
    cid = _create_curr(client, h, "Not Archived Item")
    r = client.post(f"/api/curriculum/{cid}/restore", headers=h)
    assert r.status_code == 409, r.text


def test_restore_scoped_out_for_other_squadron_admin(client):
    h703 = login(client, ADM703)
    cid = _create_curr(client, h703, "Scope Test Item")
    assert client.delete(f"/api/curriculum/{cid}", headers=h703).status_code == 200

    h704 = login(client, ADM704)
    r = client.post(f"/api/curriculum/{cid}/restore", headers=h704)
    assert r.status_code == 403, r.text


def test_restore_requires_authentication(client):
    h = login(client, ADM703)
    cid = _create_curr(client, h, "Auth Test Item")
    assert client.delete(f"/api/curriculum/{cid}", headers=h).status_code == 200
    # login() also sets the aafc_session cookie fallback (architecture.md) on
    # this same TestClient -- clear it so this call is genuinely unauthenticated,
    # not just missing the Authorization header.
    client.cookies.clear()
    r = client.post(f"/api/curriculum/{cid}/restore")
    assert r.status_code == 401, r.text


def test_restore_nonexistent_item_returns_404(client):
    h = login(client, ADM703)
    r = client.post("/api/curriculum/does-not-exist/restore", headers=h)
    assert r.status_code == 404, r.text


def test_archived_item_still_excluded_from_default_list_by_default(client):
    """Regression guard for the include_archived param itself -- confirms the
    default (no query param) behaviour is unchanged from before this change."""
    h = login(client, ADM703)
    cid = _create_curr(client, h, "Default Filter Item")
    assert client.delete(f"/api/curriculum/{cid}", headers=h).status_code == 200
    default_list = client.get("/api/curriculum", headers=h).json()["items"]
    assert not any(i["curriculum_id"] == cid for i in default_list)
    explicit_false_list = client.get("/api/curriculum?include_archived=false", headers=h).json()["items"]
    assert not any(i["curriculum_id"] == cid for i in explicit_false_list)
