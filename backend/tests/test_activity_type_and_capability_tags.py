"""REM-23 part 3: activity_type_tags and training_area_capability_tags.

Mirrors the pattern from test_facilitator_type_tags.py and
test_tag_archive_restore.py. Covers:
  - List (active only by default, include_archived=true)
  - Create (happy path, blank name, too-long name, duplicate)
  - Archive (DELETE => is_active=False)
  - Restore (POST /restore)
  - Scope guards (sqn can't create global; 403 from wrong sqn)
  - 401 unauthenticated, 404 non-existent
"""
import pytest
from tests.conftest import login

ADM703 = "ADMIN703"
ADM704 = "ADMIN704"
SYSADMIN = "SYSADMIN2026"


# ── Activity Type Tags ────────────────────────────────────────────────────────

class TestActivityTypeTagList:
    def test_list_returns_seeded_global_tags(self, client):
        headers = login(client, ADM703)
        r = client.get("/api/activity-type-tags", headers=headers)
        assert r.status_code == 200
        names = [t["display_name"] for t in r.json()]
        assert "Must Attend" in names
        assert "Key Event" in names
        assert "Optional" in names

    def test_list_excludes_archived_by_default(self, client):
        headers = login(client, SYSADMIN)
        # create and archive a tag
        cr = client.post("/api/activity-type-tags", json={"display_name": "ArchivedType", "scope": "global"}, headers=headers)
        assert cr.status_code == 201
        tid = cr.json()["tag_id"]
        client.delete(f"/api/activity-type-tags/{tid}", headers=headers)
        # default list should not include it
        r = client.get("/api/activity-type-tags", headers=headers)
        names = [t["display_name"] for t in r.json()]
        assert "ArchivedType" not in names

    def test_list_include_archived(self, client):
        headers = login(client, SYSADMIN)
        cr = client.post("/api/activity-type-tags", json={"display_name": "ArchVisibleType", "scope": "global"}, headers=headers)
        assert cr.status_code == 201
        tid = cr.json()["tag_id"]
        client.delete(f"/api/activity-type-tags/{tid}", headers=headers)
        r = client.get("/api/activity-type-tags?include_archived=true", headers=headers)
        names = [t["display_name"] for t in r.json()]
        assert "ArchVisibleType" in names

    def test_list_unauthenticated(self, client):
        r = client.get("/api/activity-type-tags")
        assert r.status_code == 401


class TestActivityTypeTagCreate:
    def test_create_squadron_scoped(self, client):
        headers = login(client, ADM703)
        r = client.post("/api/activity-type-tags", json={"display_name": "Parade Night Special"}, headers=headers)
        assert r.status_code == 201
        assert r.json()["display_name"] == "Parade Night Special"
        assert r.json()["scope"] == "squadron"

    def test_create_global_by_sysadmin(self, client):
        headers = login(client, SYSADMIN)
        r = client.post("/api/activity-type-tags", json={"display_name": "GlobalActType", "scope": "global"}, headers=headers)
        assert r.status_code == 201
        assert r.json()["scope"] == "global"

    def test_create_blank_name_rejected(self, client):
        headers = login(client, ADM703)
        r = client.post("/api/activity-type-tags", json={"display_name": "   "}, headers=headers)
        assert r.status_code == 400

    def test_create_too_long_name_rejected(self, client):
        headers = login(client, ADM703)
        r = client.post("/api/activity-type-tags", json={"display_name": "X" * 81}, headers=headers)
        assert r.status_code == 400

    def test_create_duplicate_returns_409(self, client):
        headers = login(client, ADM703)
        client.post("/api/activity-type-tags", json={"display_name": "DupActType"}, headers=headers)
        r = client.post("/api/activity-type-tags", json={"display_name": "DupActType"}, headers=headers)
        assert r.status_code == 409

    def test_sqn_cannot_create_global(self, client):
        headers = login(client, ADM703)
        r = client.post("/api/activity-type-tags", json={"display_name": "ShouldFail", "scope": "global"}, headers=headers)
        assert r.status_code == 403

    def test_create_unauthenticated(self, client):
        r = client.post("/api/activity-type-tags", json={"display_name": "Unauth"})
        assert r.status_code == 401


class TestActivityTypeTagArchiveRestore:
    def test_archive_and_restore(self, client):
        headers = login(client, ADM703)
        cr = client.post("/api/activity-type-tags", json={"display_name": "ToArchiveActType"}, headers=headers)
        assert cr.status_code == 201
        tid = cr.json()["tag_id"]
        # archive
        ar = client.delete(f"/api/activity-type-tags/{tid}", headers=headers)
        assert ar.status_code == 200
        # confirm not in active list
        lst = client.get("/api/activity-type-tags", headers=headers)
        assert not any(t["tag_id"] == tid for t in lst.json())
        # restore
        rr = client.post(f"/api/activity-type-tags/{tid}/restore", headers=headers)
        assert rr.status_code == 200
        # confirm back in active list
        lst2 = client.get("/api/activity-type-tags", headers=headers)
        assert any(t["tag_id"] == tid for t in lst2.json())

    def test_archive_already_archived_409(self, client):
        headers = login(client, ADM703)
        cr = client.post("/api/activity-type-tags", json={"display_name": "DoubleArchActType"}, headers=headers)
        tid = cr.json()["tag_id"]
        client.delete(f"/api/activity-type-tags/{tid}", headers=headers)
        r = client.delete(f"/api/activity-type-tags/{tid}", headers=headers)
        assert r.status_code == 409

    def test_restore_already_active_409(self, client):
        headers = login(client, ADM703)
        cr = client.post("/api/activity-type-tags", json={"display_name": "ActiveRestoreActType"}, headers=headers)
        tid = cr.json()["tag_id"]
        r = client.post(f"/api/activity-type-tags/{tid}/restore", headers=headers)
        assert r.status_code == 409

    def test_archive_not_found_404(self, client):
        headers = login(client, ADM703)
        r = client.delete("/api/activity-type-tags/nonexistent-id", headers=headers)
        assert r.status_code == 404

    def test_restore_not_found_404(self, client):
        headers = login(client, ADM703)
        r = client.post("/api/activity-type-tags/nonexistent-id/restore", headers=headers)
        assert r.status_code == 404

    def test_cross_squadron_archive_forbidden(self, client):
        headers703 = login(client, ADM703)
        headers704 = login(client, ADM704)
        cr = client.post("/api/activity-type-tags", json={"display_name": "Sqn703OnlyActType"}, headers=headers703)
        assert cr.status_code == 201
        tid = cr.json()["tag_id"]
        r = client.delete(f"/api/activity-type-tags/{tid}", headers=headers704)
        assert r.status_code == 403


# ── Training Area Capability Tags ─────────────────────────────────────────────

class TestTrainingAreaCapabilityTagList:
    def test_list_returns_seeded_global_tags(self, client):
        headers = login(client, ADM703)
        r = client.get("/api/training-area-capability-tags", headers=headers)
        assert r.status_code == 200
        names = [t["display_name"] for t in r.json()]
        assert "Projector" in names
        assert "Whiteboard" in names
        assert "WiFi" in names

    def test_list_excludes_archived_by_default(self, client):
        headers = login(client, SYSADMIN)
        cr = client.post("/api/training-area-capability-tags", json={"display_name": "ArchivedCap", "scope": "global"}, headers=headers)
        assert cr.status_code == 201
        tid = cr.json()["tag_id"]
        client.delete(f"/api/training-area-capability-tags/{tid}", headers=headers)
        r = client.get("/api/training-area-capability-tags", headers=headers)
        names = [t["display_name"] for t in r.json()]
        assert "ArchivedCap" not in names

    def test_list_unauthenticated(self, client):
        r = client.get("/api/training-area-capability-tags")
        assert r.status_code == 401


class TestTrainingAreaCapabilityTagCreate:
    def test_create_squadron_scoped(self, client):
        headers = login(client, ADM703)
        r = client.post("/api/training-area-capability-tags", json={"display_name": "Custom Room Cap"}, headers=headers)
        assert r.status_code == 201
        assert r.json()["scope"] == "squadron"

    def test_create_global_by_sysadmin(self, client):
        headers = login(client, SYSADMIN)
        r = client.post("/api/training-area-capability-tags", json={"display_name": "GlobalCap", "scope": "global"}, headers=headers)
        assert r.status_code == 201

    def test_create_duplicate_returns_409(self, client):
        headers = login(client, ADM703)
        client.post("/api/training-area-capability-tags", json={"display_name": "DupCap"}, headers=headers)
        r = client.post("/api/training-area-capability-tags", json={"display_name": "DupCap"}, headers=headers)
        assert r.status_code == 409

    def test_sqn_cannot_create_global(self, client):
        headers = login(client, ADM703)
        r = client.post("/api/training-area-capability-tags", json={"display_name": "GlobalFail", "scope": "global"}, headers=headers)
        assert r.status_code == 403

    def test_create_unauthenticated(self, client):
        r = client.post("/api/training-area-capability-tags", json={"display_name": "Unauth"})
        assert r.status_code == 401


class TestTrainingAreaCapabilityTagArchiveRestore:
    def test_archive_and_restore(self, client):
        headers = login(client, ADM703)
        cr = client.post("/api/training-area-capability-tags", json={"display_name": "ToArchiveCap"}, headers=headers)
        assert cr.status_code == 201
        tid = cr.json()["tag_id"]
        ar = client.delete(f"/api/training-area-capability-tags/{tid}", headers=headers)
        assert ar.status_code == 200
        rr = client.post(f"/api/training-area-capability-tags/{tid}/restore", headers=headers)
        assert rr.status_code == 200

    def test_archive_not_found_404(self, client):
        headers = login(client, ADM703)
        r = client.delete("/api/training-area-capability-tags/nonexistent", headers=headers)
        assert r.status_code == 404

    def test_restore_not_found_404(self, client):
        headers = login(client, ADM703)
        r = client.post("/api/training-area-capability-tags/nonexistent/restore", headers=headers)
        assert r.status_code == 404

    def test_cross_squadron_archive_forbidden(self, client):
        headers703 = login(client, ADM703)
        headers704 = login(client, ADM704)
        cr = client.post("/api/training-area-capability-tags", json={"display_name": "Sqn703OnlyCap"}, headers=headers703)
        assert cr.status_code == 201
        tid = cr.json()["tag_id"]
        r = client.delete(f"/api/training-area-capability-tags/{tid}", headers=headers704)
        assert r.status_code == 403


# ── Training Area capabilities field ─────────────────────────────────────────

class TestTrainingAreaCapabilities:
    def test_create_room_with_capabilities(self, client):
        headers = login(client, ADM703)
        r = client.post("/api/training-areas", json={
            "name": "Test Room Caps",
            "type": "Indoor",
            "capabilities": ["Projector", "WiFi"],
        }, headers=headers)
        assert r.status_code == 200
        rid = r.json()["training_area_id"]
        # capabilities should be returned in list
        lst = client.get("/api/training-areas", headers=headers)
        rooms = {room["training_area_id"]: room for room in lst.json()}
        assert rid in rooms
        assert set(rooms[rid]["capabilities"]) == {"Projector", "WiFi"}

    def test_update_room_capabilities(self, client):
        headers = login(client, ADM703)
        cr = client.post("/api/training-areas", json={"name": "PatchCapsRoom", "capabilities": ["Projector"]}, headers=headers)
        rid = cr.json()["training_area_id"]
        client.patch(f"/api/training-areas/{rid}", json={"capabilities": ["Whiteboard", "PA System"]}, headers=headers)
        lst = client.get("/api/training-areas", headers=headers)
        rooms = {r["training_area_id"]: r for r in lst.json()}
        assert set(rooms[rid]["capabilities"]) == {"Whiteboard", "PA System"}

    def test_room_without_capabilities_returns_empty_list(self, client):
        headers = login(client, ADM703)
        cr = client.post("/api/training-areas", json={"name": "NoCapsRoom"}, headers=headers)
        rid = cr.json()["training_area_id"]
        lst = client.get("/api/training-areas", headers=headers)
        rooms = {r["training_area_id"]: r for r in lst.json()}
        assert rooms[rid]["capabilities"] == []
