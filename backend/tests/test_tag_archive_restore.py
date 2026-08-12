"""REM-23: Subject Area, Facilitator Type, and Session Status Reason tags use
is_active=False for archiving (not is_archived — a different field from the
SoftDeleteMixin used by TrainingArea/Equipment).

The archive endpoints already existed; this file tests:
- include_archived=true list param (archived items now visible)
- restore endpoint (POST /{tag_id}/restore)
- 409 if tag is already active
- 403 cross-scope guard (squadron-scoped tag not restorable by another squadron)
- 401 unauthenticated
- 404 non-existent tag
- Default list regression guard (archived items excluded by default)

Uses ADMIN703 / ADMIN704 for cross-scope boundary test (two different squadrons).
"""
from tests.conftest import login

ADM703 = "ADMIN703"
ADM704 = "ADMIN704"


# ─── Subject Area Tags ────────────────────────────────────────────────────────

def _create_subjarea(client, hdr, name="Restore Test SubjectArea"):
    r = client.post("/api/subject-area-tags", json={"display_name": name, "scope": "squadron"}, headers=hdr)
    assert r.status_code == 201, r.text
    return r.json()["tag_id"]


def test_subjarea_restore_reverses_archive_visible_via_include_archived(client):
    h = login(client, ADM703)
    tid = _create_subjarea(client, h)

    assert client.delete(f"/api/subject-area-tags/{tid}", headers=h).status_code == 200

    default_list = client.get("/api/subject-area-tags", headers=h).json()
    assert not any(t["tag_id"] == tid for t in default_list)

    archived_list = client.get("/api/subject-area-tags?include_archived=true", headers=h).json()
    entry = next((t for t in archived_list if t["tag_id"] == tid), None)
    assert entry is not None
    assert entry["is_active"] is False

    assert client.post(f"/api/subject-area-tags/{tid}/restore", headers=h).status_code == 200

    restored_list = client.get("/api/subject-area-tags", headers=h).json()
    restored = next((t for t in restored_list if t["tag_id"] == tid), None)
    assert restored is not None
    assert restored["is_active"] is True


def test_subjarea_restore_rejects_already_active(client):
    h = login(client, ADM703)
    tid = _create_subjarea(client, h, "Not Archived SubjectArea")
    r = client.post(f"/api/subject-area-tags/{tid}/restore", headers=h)
    assert r.status_code == 409, r.text


def test_subjarea_restore_scoped_out_for_other_squadron(client):
    h703 = login(client, ADM703)
    tid = _create_subjarea(client, h703, "Scope Test SubjectArea")
    assert client.delete(f"/api/subject-area-tags/{tid}", headers=h703).status_code == 200

    h704 = login(client, ADM704)
    r = client.post(f"/api/subject-area-tags/{tid}/restore", headers=h704)
    assert r.status_code == 403, r.text


def test_subjarea_restore_requires_authentication(client):
    h = login(client, ADM703)
    tid = _create_subjarea(client, h, "Auth Test SubjectArea")
    assert client.delete(f"/api/subject-area-tags/{tid}", headers=h).status_code == 200
    client.cookies.clear()
    r = client.post(f"/api/subject-area-tags/{tid}/restore")
    assert r.status_code == 401, r.text


def test_subjarea_restore_nonexistent_returns_404(client):
    h = login(client, ADM703)
    r = client.post("/api/subject-area-tags/does-not-exist/restore", headers=h)
    assert r.status_code == 404, r.text


def test_archived_subjarea_excluded_from_default_list(client):
    h = login(client, ADM703)
    tid = _create_subjarea(client, h, "Default Filter SubjectArea")
    assert client.delete(f"/api/subject-area-tags/{tid}", headers=h).status_code == 200
    default_list = client.get("/api/subject-area-tags", headers=h).json()
    assert not any(t["tag_id"] == tid for t in default_list)
    explicit_false = client.get("/api/subject-area-tags?include_archived=false", headers=h).json()
    assert not any(t["tag_id"] == tid for t in explicit_false)


# ─── Facilitator Type Tags ────────────────────────────────────────────────────

def _create_factype(client, hdr, name="Restore Test FacType"):
    r = client.post("/api/facilitator-type-tags", json={"display_name": name, "scope": "squadron"}, headers=hdr)
    assert r.status_code == 201, r.text
    return r.json()["tag_id"]


def test_factype_restore_reverses_archive_visible_via_include_archived(client):
    h = login(client, ADM703)
    tid = _create_factype(client, h)

    assert client.delete(f"/api/facilitator-type-tags/{tid}", headers=h).status_code == 200

    default_list = client.get("/api/facilitator-type-tags", headers=h).json()
    assert not any(t["tag_id"] == tid for t in default_list)

    archived_list = client.get("/api/facilitator-type-tags?include_archived=true", headers=h).json()
    entry = next((t for t in archived_list if t["tag_id"] == tid), None)
    assert entry is not None
    assert entry["is_active"] is False

    assert client.post(f"/api/facilitator-type-tags/{tid}/restore", headers=h).status_code == 200

    restored_list = client.get("/api/facilitator-type-tags", headers=h).json()
    restored = next((t for t in restored_list if t["tag_id"] == tid), None)
    assert restored is not None
    assert restored["is_active"] is True


def test_factype_restore_rejects_already_active(client):
    h = login(client, ADM703)
    tid = _create_factype(client, h, "Not Archived FacType")
    r = client.post(f"/api/facilitator-type-tags/{tid}/restore", headers=h)
    assert r.status_code == 409, r.text


def test_factype_restore_scoped_out_for_other_squadron(client):
    h703 = login(client, ADM703)
    tid = _create_factype(client, h703, "Scope Test FacType")
    assert client.delete(f"/api/facilitator-type-tags/{tid}", headers=h703).status_code == 200

    h704 = login(client, ADM704)
    r = client.post(f"/api/facilitator-type-tags/{tid}/restore", headers=h704)
    assert r.status_code == 403, r.text


def test_factype_restore_requires_authentication(client):
    h = login(client, ADM703)
    tid = _create_factype(client, h, "Auth Test FacType")
    assert client.delete(f"/api/facilitator-type-tags/{tid}", headers=h).status_code == 200
    client.cookies.clear()
    r = client.post(f"/api/facilitator-type-tags/{tid}/restore")
    assert r.status_code == 401, r.text


def test_factype_restore_nonexistent_returns_404(client):
    h = login(client, ADM703)
    r = client.post("/api/facilitator-type-tags/does-not-exist/restore", headers=h)
    assert r.status_code == 404, r.text


def test_archived_factype_excluded_from_default_list(client):
    h = login(client, ADM703)
    tid = _create_factype(client, h, "Default Filter FacType")
    assert client.delete(f"/api/facilitator-type-tags/{tid}", headers=h).status_code == 200
    default_list = client.get("/api/facilitator-type-tags", headers=h).json()
    assert not any(t["tag_id"] == tid for t in default_list)
    explicit_false = client.get("/api/facilitator-type-tags?include_archived=false", headers=h).json()
    assert not any(t["tag_id"] == tid for t in explicit_false)


# ─── Session Status Reason Tags ───────────────────────────────────────────────

def _create_reason(client, hdr, name="Restore Test Reason"):
    r = client.post("/api/session-status-reason-tags", json={"display_name": name, "scope": "squadron"}, headers=hdr)
    assert r.status_code == 201, r.text
    return r.json()["tag_id"]


def test_reason_restore_reverses_archive_visible_via_include_archived(client):
    h = login(client, ADM703)
    tid = _create_reason(client, h)

    assert client.delete(f"/api/session-status-reason-tags/{tid}", headers=h).status_code == 200

    default_list = client.get("/api/session-status-reason-tags", headers=h).json()
    assert not any(t["tag_id"] == tid for t in default_list)

    archived_list = client.get("/api/session-status-reason-tags?include_archived=true", headers=h).json()
    entry = next((t for t in archived_list if t["tag_id"] == tid), None)
    assert entry is not None
    assert entry["is_active"] is False

    assert client.post(f"/api/session-status-reason-tags/{tid}/restore", headers=h).status_code == 200

    restored_list = client.get("/api/session-status-reason-tags", headers=h).json()
    restored = next((t for t in restored_list if t["tag_id"] == tid), None)
    assert restored is not None
    assert restored["is_active"] is True


def test_reason_restore_rejects_already_active(client):
    h = login(client, ADM703)
    tid = _create_reason(client, h, "Not Archived Reason")
    r = client.post(f"/api/session-status-reason-tags/{tid}/restore", headers=h)
    assert r.status_code == 409, r.text


def test_reason_restore_scoped_out_for_other_squadron(client):
    h703 = login(client, ADM703)
    tid = _create_reason(client, h703, "Scope Test Reason")
    assert client.delete(f"/api/session-status-reason-tags/{tid}", headers=h703).status_code == 200

    h704 = login(client, ADM704)
    r = client.post(f"/api/session-status-reason-tags/{tid}/restore", headers=h704)
    assert r.status_code == 403, r.text


def test_reason_restore_requires_authentication(client):
    h = login(client, ADM703)
    tid = _create_reason(client, h, "Auth Test Reason")
    assert client.delete(f"/api/session-status-reason-tags/{tid}", headers=h).status_code == 200
    client.cookies.clear()
    r = client.post(f"/api/session-status-reason-tags/{tid}/restore")
    assert r.status_code == 401, r.text


def test_reason_restore_nonexistent_returns_404(client):
    h = login(client, ADM703)
    r = client.post("/api/session-status-reason-tags/does-not-exist/restore", headers=h)
    assert r.status_code == 404, r.text


def test_archived_reason_excluded_from_default_list(client):
    h = login(client, ADM703)
    tid = _create_reason(client, h, "Default Filter Reason")
    assert client.delete(f"/api/session-status-reason-tags/{tid}", headers=h).status_code == 200
    default_list = client.get("/api/session-status-reason-tags", headers=h).json()
    assert not any(t["tag_id"] == tid for t in default_list)
    explicit_false = client.get("/api/session-status-reason-tags?include_archived=false", headers=h).json()
    assert not any(t["tag_id"] == tid for t in explicit_false)
