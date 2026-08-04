"""Tests for Facilitator Type Tag endpoints (remediation program Section 6,
Stage 3). Mirrors test_subject_area_tags.py exactly -- same shape, same
permission model, same normalisation/dedup rules.

Covers: creation, normalisation, duplicate detection, permission control,
tag listing, archiving, and the global-scope seed values.
"""
from conftest import login


# ── helpers ───────────────────────────────────────────────────────────────────

def _sqn_admin(client):
    return login(client, "ADMIN703")


def _sqn_general(client):
    return login(client, "703SQN2026")


def _auditor(client):
    return login(client, "AUDITOR2026")


# ── list ──────────────────────────────────────────────────────────────────────

def test_list_tags_requires_auth(client):
    r = client.get("/api/facilitator-type-tags")
    assert r.status_code == 401


def test_sqn_general_can_list_tags(client):
    h = _sqn_general(client)
    r = client.get("/api/facilitator-type-tags", headers=h)
    assert r.status_code == 200


def test_seeded_global_types_appear_in_list(client):
    """The five seeded global types (Staff/Officer/NCO/Senior Cadet/Civilian
    -- the exact short codes #fac-type's <select> already stores as option
    values, plus "Staff", Facilitator.type's real default) must be visible
    to every squadron by default."""
    h = _sqn_admin(client)
    r = client.get("/api/facilitator-type-tags", headers=h)
    assert r.status_code == 200
    names = {t["display_name"] for t in r.json()}
    assert "Staff" in names
    assert "Officer" in names
    assert "Senior Cadet" in names
    assert "Civilian" in names
    globals_only = [t for t in r.json() if t["scope"] == "global"]
    assert len(globals_only) == 5


# ── create ────────────────────────────────────────────────────────────────────

def test_create_tag_requires_auth(client):
    r = client.post("/api/facilitator-type-tags", json={"display_name": "Reservist"})
    assert r.status_code == 401


def test_create_tag_forbidden_for_read_only(client):
    h = _sqn_general(client)
    r = client.post("/api/facilitator-type-tags", json={"display_name": "Reservist"}, headers=h)
    assert r.status_code == 403


def test_create_tag_forbidden_for_auditor(client):
    h = _auditor(client)
    r = client.post("/api/facilitator-type-tags", json={"display_name": "Reservist"}, headers=h)
    assert r.status_code == 403


def test_create_tag_success(client):
    h = _sqn_admin(client)
    r = client.post("/api/facilitator-type-tags", json={"display_name": "Reservist"}, headers=h)
    assert r.status_code == 201
    d = r.json()
    assert d["display_name"] == "Reservist"
    assert d["normalised_name"] == "reservist"
    assert d["is_active"] is True
    assert d["scope"] == "squadron"
    assert "tag_id" in d


def test_create_tag_normalises_whitespace(client):
    h = _sqn_admin(client)
    r = client.post("/api/facilitator-type-tags", json={"display_name": "  Guest  Presenter  "}, headers=h)
    assert r.status_code == 201
    d = r.json()
    assert d["display_name"] == "Guest  Presenter"
    assert d["normalised_name"] == "guest presenter"


def test_create_tag_rejects_blank(client):
    h = _sqn_admin(client)
    r = client.post("/api/facilitator-type-tags", json={"display_name": "   "}, headers=h)
    assert r.status_code == 400


def test_create_tag_rejects_duplicate_case_insensitive(client):
    h = _sqn_admin(client)
    client.post("/api/facilitator-type-tags", json={"display_name": "Volunteer"}, headers=h)
    r = client.post("/api/facilitator-type-tags", json={"display_name": "VOLUNTEER"}, headers=h)
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "tag_already_exists"


def test_create_tag_rejects_duplicate_of_seeded_global(client):
    """A squadron-scoped attempt to recreate a global-seeded type name must
    also be blocked -- global/wing/squadron scopes share one dedup namespace."""
    h = _sqn_admin(client)
    r = client.post("/api/facilitator-type-tags", json={"display_name": "senior cadet"}, headers=h)
    assert r.status_code == 409


def test_create_tag_appears_in_list(client):
    h = _sqn_admin(client)
    tag_name = "FACTYPE_UNIQUE_TAG"
    client.post("/api/facilitator-type-tags", json={"display_name": tag_name}, headers=h)
    r = client.get("/api/facilitator-type-tags", headers=h)
    names = [t["display_name"] for t in r.json()]
    assert tag_name in names


def test_create_tag_too_long(client):
    h = _sqn_admin(client)
    long_name = "X" * 81
    r = client.post("/api/facilitator-type-tags", json={"display_name": long_name}, headers=h)
    assert r.status_code == 400


# ── archive ────────────────────────────────────────────────────────────────────

def test_archive_tag(client):
    h = _sqn_admin(client)
    r = client.post("/api/facilitator-type-tags", json={"display_name": "ToBeArchivedFacType"}, headers=h)
    tag_id = r.json()["tag_id"]
    r2 = client.delete(f"/api/facilitator-type-tags/{tag_id}", headers=h)
    assert r2.status_code == 200
    assert r2.json()["ok"] is True


def test_archived_tag_not_in_list(client):
    h = _sqn_admin(client)
    r = client.post("/api/facilitator-type-tags", json={"display_name": "WillBeHiddenFacType"}, headers=h)
    tag_id = r.json()["tag_id"]
    client.delete(f"/api/facilitator-type-tags/{tag_id}", headers=h)
    r2 = client.get("/api/facilitator-type-tags", headers=h)
    ids = [t["tag_id"] for t in r2.json()]
    assert tag_id not in ids


def test_archive_nonexistent_tag(client):
    h = _sqn_admin(client)
    r = client.delete("/api/facilitator-type-tags/nonexistent-id", headers=h)
    assert r.status_code == 404


def test_archive_tag_forbidden_for_read_only(client):
    h_admin = _sqn_admin(client)
    h_gen = _sqn_general(client)
    r = client.post("/api/facilitator-type-tags", json={"display_name": "ArchiveTestFacType"}, headers=h_admin)
    tag_id = r.json()["tag_id"]
    r2 = client.delete(f"/api/facilitator-type-tags/{tag_id}", headers=h_gen)
    assert r2.status_code == 403
