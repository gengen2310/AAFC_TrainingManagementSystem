"""Tests for Subject Area Tag endpoints.

Covers: creation, normalisation, duplicate detection, permission control,
tag listing, and archiving.
"""
import pytest
from conftest import login


# ── helpers ───────────────────────────────────────────────────────────────────

def _sqn_admin(client):
    return login(client, "ADMIN703")


def _sqn_general(client):
    return login(client, "703SQN2026")


def _auditor(client):
    return login(client, "AUDITOR2026")


def _wing_admin(client):
    return login(client, "ADMIN7WG")


def _nat_admin(client):
    return login(client, "ADMINNATIONAL")


def _sysadmin(client):
    return login(client, "SYSADMIN2026")


def _own_squadron_id(client, hdr):
    return client.get("/api/auth/me", headers=hdr).json()["session"]["squadron_id"]


# ── list ──────────────────────────────────────────────────────────────────────

def test_list_tags_requires_auth(client):
    r = client.get("/api/subject-area-tags")
    assert r.status_code == 401


def test_list_tags_empty_initially(client):
    h = _sqn_admin(client)
    r = client.get("/api/subject-area-tags", headers=h)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_sqn_general_can_list_tags(client):
    h = _sqn_general(client)
    r = client.get("/api/subject-area-tags", headers=h)
    assert r.status_code == 200


# ── create ────────────────────────────────────────────────────────────────────

def test_create_tag_requires_auth(client):
    r = client.post("/api/subject-area-tags", json={"display_name": "Drill"})
    assert r.status_code == 401


def test_create_tag_forbidden_for_read_only(client):
    h = _sqn_general(client)
    r = client.post("/api/subject-area-tags", json={"display_name": "Drill"}, headers=h)
    assert r.status_code == 403


def test_create_tag_forbidden_for_auditor(client):
    h = _auditor(client)
    r = client.post("/api/subject-area-tags", json={"display_name": "Drill"}, headers=h)
    assert r.status_code == 403


def test_create_tag_success(client):
    h = _sqn_admin(client)
    r = client.post("/api/subject-area-tags", json={"display_name": "Leadership"}, headers=h)
    assert r.status_code == 201
    d = r.json()
    assert d["display_name"] == "Leadership"
    assert d["normalised_name"] == "leadership"
    assert d["is_active"] is True
    assert "tag_id" in d


def test_create_tag_normalises_whitespace(client):
    h = _sqn_admin(client)
    r = client.post("/api/subject-area-tags", json={"display_name": "  First  Aid  "}, headers=h)
    assert r.status_code == 201
    d = r.json()
    assert d["display_name"] == "First  Aid"
    assert d["normalised_name"] == "first aid"


def test_create_tag_rejects_blank(client):
    h = _sqn_admin(client)
    r = client.post("/api/subject-area-tags", json={"display_name": "   "}, headers=h)
    assert r.status_code == 400


def test_create_tag_rejects_duplicate_case_insensitive(client):
    h = _sqn_admin(client)
    client.post("/api/subject-area-tags", json={"display_name": "Fieldcraft"}, headers=h)
    r = client.post("/api/subject-area-tags", json={"display_name": "FIELDCRAFT"}, headers=h)
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "tag_already_exists"


def test_create_tag_rejects_near_identical_spacing(client):
    h = _sqn_admin(client)
    client.post("/api/subject-area-tags", json={"display_name": "Service Knowledge"}, headers=h)
    r = client.post("/api/subject-area-tags", json={"display_name": "  Service  Knowledge  "}, headers=h)
    assert r.status_code == 409


def test_create_tag_appears_in_list(client):
    h = _sqn_admin(client)
    tag_name = "STEM_UNIQUE_TAG"
    client.post("/api/subject-area-tags", json={"display_name": tag_name}, headers=h)
    r = client.get("/api/subject-area-tags", headers=h)
    names = [t["display_name"] for t in r.json()]
    assert tag_name in names


def test_create_tag_too_long(client):
    h = _sqn_admin(client)
    long_name = "X" * 81
    r = client.post("/api/subject-area-tags", json={"display_name": long_name}, headers=h)
    assert r.status_code == 400


# ── archive ────────────────────────────────────────────────────────────────────

def test_archive_tag(client):
    h = _sqn_admin(client)
    r = client.post("/api/subject-area-tags", json={"display_name": "ToBeArchived"}, headers=h)
    tag_id = r.json()["tag_id"]
    r2 = client.delete(f"/api/subject-area-tags/{tag_id}", headers=h)
    assert r2.status_code == 200
    assert r2.json()["ok"] is True


def test_archived_tag_not_in_list(client):
    h = _sqn_admin(client)
    r = client.post("/api/subject-area-tags", json={"display_name": "WillBeHidden"}, headers=h)
    tag_id = r.json()["tag_id"]
    client.delete(f"/api/subject-area-tags/{tag_id}", headers=h)
    r2 = client.get("/api/subject-area-tags", headers=h)
    ids = [t["tag_id"] for t in r2.json()]
    assert tag_id not in ids


def test_archive_nonexistent_tag(client):
    h = _sqn_admin(client)
    r = client.delete("/api/subject-area-tags/nonexistent-id", headers=h)
    assert r.status_code == 404


def test_archive_tag_forbidden_for_read_only(client):
    h_admin = _sqn_admin(client)
    h_gen = _sqn_general(client)
    r = client.post("/api/subject-area-tags", json={"display_name": "ArchiveTest"}, headers=h_admin)
    tag_id = r.json()["tag_id"]
    r2 = client.delete(f"/api/subject-area-tags/{tag_id}", headers=h_gen)
    assert r2.status_code == 403


# ── wing/national/system_admin scope creation ──────────────────────────────────
# DEFECT: create_subject_area_tag used to unconditionally require p.squadron_id
# (db.get(Squadron, p.squadron_id)) -- wing_admin/national_admin/system_admin
# never have that set (only p.acting_squadron_id changes during Proxy/
# Delegated Intervention), so those roles could never create a tag at ANY
# scope. Fixed to mirror _can_create_phase's proven role/proxy pattern.

def test_wing_admin_can_create_wing_scope_tag(client):
    h = _wing_admin(client)
    r = client.post("/api/subject-area-tags", json={"display_name": "Wing Custom Tag", "scope": "wing"}, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["scope"] == "wing"
    listed = client.get("/api/subject-area-tags", headers=h).json()
    assert "Wing Custom Tag" in [t["display_name"] for t in listed]


def test_nat_admin_can_create_global_scope_tag(client):
    h = _nat_admin(client)
    r = client.post("/api/subject-area-tags", json={"display_name": "Global Custom Tag", "scope": "global"}, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["scope"] == "global"


def test_sysadmin_can_create_global_scope_tag(client):
    h = _sysadmin(client)
    r = client.post("/api/subject-area-tags", json={"display_name": "SysAdmin Global Tag", "scope": "global"}, headers=h)
    assert r.status_code == 201, r.text


def test_wing_admin_cannot_create_global_scope_tag(client):
    h = _wing_admin(client)
    r = client.post("/api/subject-area-tags", json={"display_name": "Wing Attempt Global", "scope": "global"}, headers=h)
    assert r.status_code == 403


def test_wing_admin_without_proxy_cannot_create_squadron_scope_tag(client):
    h = _wing_admin(client)
    r = client.post("/api/subject-area-tags", json={"display_name": "Wing Attempt Squadron", "scope": "squadron"}, headers=h)
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "proxy_required"


def test_wing_admin_with_active_proxy_can_create_squadron_scope_tag(client):
    h_sqn = _sqn_admin(client)
    sqn_id = _own_squadron_id(client, h_sqn)
    h = _wing_admin(client)
    enter = client.post(f"/api/proxy/enter/{sqn_id}", json={"reason": "tag setup"}, headers=h)
    assert enter.status_code == 200, enter.text
    try:
        r = client.post("/api/subject-area-tags", json={"display_name": "Proxied Squadron Tag", "scope": "squadron"}, headers=h)
        assert r.status_code == 201, r.text
    finally:
        client.post("/api/proxy/exit", headers=h)


def test_nat_admin_without_intervention_cannot_create_squadron_scope_tag(client):
    h = _nat_admin(client)
    r = client.post("/api/subject-area-tags", json={"display_name": "Nat Attempt Squadron", "scope": "squadron"}, headers=h)
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "intervention_required"


def test_nat_admin_can_view_tags_at_every_scope(client):
    """A national_admin/system_admin's own list view must reflect exactly what
    they're allowed to create -- otherwise a create succeeds but the tag
    appears to vanish from their own view."""
    h_wing = _wing_admin(client)
    client.post("/api/subject-area-tags", json={"display_name": "NatView Wing Tag", "scope": "wing"}, headers=h_wing)
    h = _nat_admin(client)
    listed = client.get("/api/subject-area-tags", headers=h).json()
    names = [t["display_name"] for t in listed]
    assert "NatView Wing Tag" in names


def test_wing_admin_can_archive_own_wing_scope_tag(client):
    h = _wing_admin(client)
    r = client.post("/api/subject-area-tags", json={"display_name": "Wing Tag To Archive", "scope": "wing"}, headers=h)
    tag_id = r.json()["tag_id"]
    r2 = client.delete(f"/api/subject-area-tags/{tag_id}", headers=h)
    assert r2.status_code == 200, r2.text


def test_sqn_admin_cannot_archive_a_wing_scope_tag(client):
    """Archive is now scope-checked the same as creation -- previously any
    sqn_admin could archive ANY tag regardless of owning scope."""
    h_wing = _wing_admin(client)
    r = client.post("/api/subject-area-tags", json={"display_name": "Wing Tag Protected", "scope": "wing"}, headers=h_wing)
    tag_id = r.json()["tag_id"]
    h_sqn = _sqn_admin(client)
    r2 = client.delete(f"/api/subject-area-tags/{tag_id}", headers=h_sqn)
    assert r2.status_code == 403


# ── ui-config health endpoint ──────────────────────────────────────────────────

def test_ui_config_no_auth_required(client):
    r = client.get("/api/health/ui-config")
    assert r.status_code == 200
    d = r.json()
    assert "training_year" in d
    assert "environment" in d
    assert "planning_workspace_url" in d
