"""REM-133: Training area and equipment archive (DELETE endpoints) already
correctly soft-deleted (is_archived=True), but had no restore counterpart
and no include_archived param on the list endpoints -- once archived, records
were reachable in the database but permanently unreachable through the product.

Also corrects the gap register's misidentification of parade dates as a
soft-archive: delete_parade_date uses db.delete() (genuine hard delete), so
no restore is possible or needed. That case is NOT tested here.

Follows the same archive/restore pattern already proven for Facilitator,
WingHQEvent, CurriculumItem, TrainingSession, PlanningFacilitatorLeave.
"""
from tests.conftest import login

ADM703 = "ADMIN703"
ADM704 = "ADMIN704"


# ─── Training Areas ───────────────────────────────────────────────────────────

def _create_room(client, hdr, name="Restore Test Room"):
    r = client.post("/api/training-areas", json={"name": name, "type": "classroom"}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["training_area_id"]


def test_room_restore_reverses_archive_and_visible_via_include_archived(client):
    h = login(client, ADM703)
    rid = _create_room(client, h)

    assert client.delete(f"/api/training-areas/{rid}", headers=h).status_code == 200

    default_list = client.get("/api/training-areas", headers=h).json()
    assert not any(r["training_area_id"] == rid for r in default_list)

    archived_list = client.get("/api/training-areas?include_archived=true", headers=h).json()
    entry = next((r for r in archived_list if r["training_area_id"] == rid), None)
    assert entry is not None
    assert entry["is_archived"] is True

    assert client.post(f"/api/training-areas/{rid}/restore", headers=h).status_code == 200

    restored_list = client.get("/api/training-areas", headers=h).json()
    restored = next((r for r in restored_list if r["training_area_id"] == rid), None)
    assert restored is not None
    assert restored["is_archived"] is False


def test_room_restore_rejects_already_active(client):
    h = login(client, ADM703)
    rid = _create_room(client, h, "Not Archived Room")
    r = client.post(f"/api/training-areas/{rid}/restore", headers=h)
    assert r.status_code == 409, r.text


def test_room_restore_scoped_out_for_other_squadron(client):
    h703 = login(client, ADM703)
    rid = _create_room(client, h703, "Scope Test Room")
    assert client.delete(f"/api/training-areas/{rid}", headers=h703).status_code == 200

    h704 = login(client, ADM704)
    r = client.post(f"/api/training-areas/{rid}/restore", headers=h704)
    assert r.status_code == 403, r.text


def test_room_restore_requires_authentication(client):
    h = login(client, ADM703)
    rid = _create_room(client, h, "Auth Test Room")
    assert client.delete(f"/api/training-areas/{rid}", headers=h).status_code == 200
    client.cookies.clear()
    r = client.post(f"/api/training-areas/{rid}/restore")
    assert r.status_code == 401, r.text


def test_room_restore_nonexistent_returns_404(client):
    h = login(client, ADM703)
    r = client.post("/api/training-areas/does-not-exist/restore", headers=h)
    assert r.status_code == 404, r.text


def test_archived_room_excluded_from_default_list(client):
    h = login(client, ADM703)
    rid = _create_room(client, h, "Default Filter Room")
    assert client.delete(f"/api/training-areas/{rid}", headers=h).status_code == 200
    default_list = client.get("/api/training-areas", headers=h).json()
    assert not any(r["training_area_id"] == rid for r in default_list)
    explicit_false = client.get("/api/training-areas?include_archived=false", headers=h).json()
    assert not any(r["training_area_id"] == rid for r in explicit_false)


# ─── Equipment ───────────────────────────────────────────────────────────────

def _create_equip(client, hdr, name="Restore Test Equipment"):
    r = client.post("/api/equipment", json={"name": name, "quantity": 2}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["equipment_id"]


def test_equip_restore_reverses_archive_and_visible_via_include_archived(client):
    h = login(client, ADM703)
    eid = _create_equip(client, h)

    assert client.delete(f"/api/equipment/{eid}", headers=h).status_code == 200

    default_list = client.get("/api/equipment", headers=h).json()
    assert not any(e["equipment_id"] == eid for e in default_list)

    archived_list = client.get("/api/equipment?include_archived=true", headers=h).json()
    entry = next((e for e in archived_list if e["equipment_id"] == eid), None)
    assert entry is not None
    assert entry["is_archived"] is True

    assert client.post(f"/api/equipment/{eid}/restore", headers=h).status_code == 200

    restored_list = client.get("/api/equipment", headers=h).json()
    restored = next((e for e in restored_list if e["equipment_id"] == eid), None)
    assert restored is not None
    assert restored["is_archived"] is False


def test_equip_restore_rejects_already_active(client):
    h = login(client, ADM703)
    eid = _create_equip(client, h, "Not Archived Equipment")
    r = client.post(f"/api/equipment/{eid}/restore", headers=h)
    assert r.status_code == 409, r.text


def test_equip_restore_scoped_out_for_other_squadron(client):
    h703 = login(client, ADM703)
    eid = _create_equip(client, h703, "Scope Test Equipment")
    assert client.delete(f"/api/equipment/{eid}", headers=h703).status_code == 200

    h704 = login(client, ADM704)
    r = client.post(f"/api/equipment/{eid}/restore", headers=h704)
    assert r.status_code == 403, r.text


def test_equip_restore_requires_authentication(client):
    h = login(client, ADM703)
    eid = _create_equip(client, h, "Auth Test Equipment")
    assert client.delete(f"/api/equipment/{eid}", headers=h).status_code == 200
    client.cookies.clear()
    r = client.post(f"/api/equipment/{eid}/restore")
    assert r.status_code == 401, r.text


def test_equip_restore_nonexistent_returns_404(client):
    h = login(client, ADM703)
    r = client.post("/api/equipment/does-not-exist/restore", headers=h)
    assert r.status_code == 404, r.text


def test_archived_equip_excluded_from_default_list(client):
    h = login(client, ADM703)
    eid = _create_equip(client, h, "Default Filter Equipment")
    assert client.delete(f"/api/equipment/{eid}", headers=h).status_code == 200
    default_list = client.get("/api/equipment", headers=h).json()
    assert not any(e["equipment_id"] == eid for e in default_list)
    explicit_false = client.get("/api/equipment?include_archived=false", headers=h).json()
    assert not any(e["equipment_id"] == eid for e in explicit_false)
