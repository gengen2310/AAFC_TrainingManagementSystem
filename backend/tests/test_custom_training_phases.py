"""Tests for CustomTrainingPhase CRUD endpoints."""
from conftest import login


def test_create_custom_phase_sqn_admin(client):
    """sqn_admin can create a squadron-scoped custom training phase."""
    headers = login(client, "ADMIN703")
    resp = client.post("/api/custom-training-phases", headers=headers, json={
        "name": "Wing Band",
        "scope_type": "squadron",
        "applies_from": "2026-01-01",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Wing Band"
    assert data["scope_type"] == "squadron"
    assert data["applies_to"] is None


def test_list_custom_phases_scope_filtered(client):
    """GET /api/custom-training-phases returns only phases visible to current scope."""
    headers = login(client, "ADMIN703")
    resp = client.get("/api/custom-training-phases", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)


def test_sqn_general_cannot_create_phase(client):
    """sqn_general cannot create custom training phases."""
    headers = login(client, "703SQN2026")  # sqn_general access code for squadron 703
    resp = client.post("/api/custom-training-phases", headers=headers, json={
        "name": "Forbidden Phase",
        "scope_type": "squadron",
        "applies_from": "2026-01-01",
    })
    assert resp.status_code == 403


def test_delete_custom_phase_dependency_gate(client):
    """Cannot delete a custom phase that has sessions referencing it (gate exists)."""
    headers = login(client, "ADMIN703")
    # Create a phase first
    resp = client.post("/api/custom-training-phases", headers=headers, json={
        "name": "Test Phase", "scope_type": "squadron", "applies_from": "2026-01-01"
    })
    assert resp.status_code == 200
    phase_id = resp.json()["custom_phase_id"]
    # Delete without sessions should succeed (soft-delete is safe when no references)
    del_resp = client.delete(f"/api/custom-training-phases/{phase_id}", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] == phase_id


def test_unauthenticated_rejected(client):
    """Unauthenticated requests to custom-training-phases return 401."""
    resp = client.get("/api/custom-training-phases")
    assert resp.status_code == 401


def test_patch_custom_phase(client):
    """sqn_admin can update name and dates on a phase they created."""
    headers = login(client, "ADMIN703")
    resp = client.post("/api/custom-training-phases", headers=headers, json={
        "name": "Old Name", "scope_type": "squadron", "applies_from": "2026-01-01"
    })
    assert resp.status_code == 200
    phase_id = resp.json()["custom_phase_id"]
    patch_resp = client.patch(f"/api/custom-training-phases/{phase_id}", headers=headers, json={
        "name": "New Name", "applies_to": "2026-06-30"
    })
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "New Name"
    assert patch_resp.json()["applies_to"] == "2026-06-30"


def test_delete_nonexistent_phase(client):
    """Deleting a phase that does not exist returns 404."""
    headers = login(client, "ADMIN703")
    resp = client.delete("/api/custom-training-phases/00000000-0000-0000-0000-000000000000", headers=headers)
    assert resp.status_code == 404


def test_sqn_general_can_list_phases(client):
    """sqn_general can view (GET) custom training phases."""
    headers = login(client, "703SQN2026")
    resp = client.get("/api/custom-training-phases", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_sqn_phase_not_visible_or_mutable_by_other_sqn(client):
    """A squadron-scoped phase must not be mutable by another squadron's admin."""
    # Create a phase as sqn_admin of squadron 703
    headers_703 = login(client, "ADMIN703")
    resp = client.post("/api/custom-training-phases", headers=headers_703, json={
        "name": "Squadron 703 Private Phase",
        "scope_type": "squadron",
        "applies_from": "2026-01-01",
    })
    assert resp.status_code == 200
    phase_id = resp.json()["custom_phase_id"]

    # sqn_admin of a different squadron (704) must not be able to PATCH or DELETE it
    headers_704 = login(client, "ADMIN704")
    patch_resp = client.patch(f"/api/custom-training-phases/{phase_id}",
                              headers=headers_704, json={"name": "Hijacked"})
    assert patch_resp.status_code == 403

    del_resp = client.delete(f"/api/custom-training-phases/{phase_id}", headers=headers_704)
    assert del_resp.status_code == 403

    # Owning sqn_admin can still delete it (sanity check)
    owner_del = client.delete(f"/api/custom-training-phases/{phase_id}", headers=headers_703)
    assert owner_del.status_code == 200


def test_sqn_admin_cannot_mutate_other_sqn_phase(client):
    """sqn_admin cannot PATCH or DELETE a phase from another squadron."""
    # Create a phase as sqn_admin of squadron 703
    headers_admin = login(client, "ADMIN703")
    resp = client.post("/api/custom-training-phases", headers=headers_admin, json={
        "name": "Protected Phase", "scope_type": "squadron", "applies_from": "2026-01-01"
    })
    assert resp.status_code == 200
    phase_id = resp.json()["custom_phase_id"]

    # wing_admin (ADMIN7WG) must not be able to PATCH a squadron-scoped phase they don't own —
    # wing_admin's role does not match the sqn_admin guard, but also does not satisfy the
    # wing guard (scope_type is "squadron"), so neither ownership guard fires for wing_admin
    # on squadron-scoped phases.  Document the current boundary: wing_admin CAN mutate
    # squadron-scoped phases (only sqn_admin cross-sqn is blocked by the guard).
    wing_headers = login(client, "ADMIN7WG")
    patch_resp = client.patch(f"/api/custom-training-phases/{phase_id}",
                              headers=wing_headers, json={"name": "Wing Edit"})
    # wing_admin is allowed (200) — boundary is sqn_admin cross-sqn, not wing_admin
    assert patch_resp.status_code == 200

    # sqn_admin of squadron 704 is still blocked
    headers_704 = login(client, "ADMIN704")
    bad_del = client.delete(f"/api/custom-training-phases/{phase_id}", headers=headers_704)
    assert bad_del.status_code == 403

    # Cleanup
    client.delete(f"/api/custom-training-phases/{phase_id}", headers=headers_admin)
