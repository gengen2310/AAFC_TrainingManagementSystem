"""Tests for Session Status Reason Tag endpoints (REM-23 continuation).
Mirrors test_facilitator_type_tags.py exactly -- same shape, same
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
    r = client.get("/api/session-status-reason-tags")
    assert r.status_code == 401


def test_sqn_general_can_list_tags(client):
    h = _sqn_general(client)
    r = client.get("/api/session-status-reason-tags", headers=h)
    assert r.status_code == 200


def test_seeded_global_reasons_appear_in_list(client):
    """The 10 seeded global reasons -- REM-14 (original_instruction.md
    Section 12): "Insufficient numbers" and "Administrative requirement"
    were added, and "Insufficient time" renamed to "Time lost", to match
    the instruction's exact preset-reason list -- must be visible to every
    squadron by default. "Other" is deliberately not seeded (a non-governed
    catch-all, not reference data)."""
    h = _sqn_admin(client)
    r = client.get("/api/session-status-reason-tags", headers=h)
    assert r.status_code == 200
    names = {t["display_name"] for t in r.json()}
    assert "Facilitator unavailable" in names
    assert "Venue unavailable" in names
    assert "Weather" in names
    assert "Safety concern" in names
    assert "Insufficient numbers" in names
    assert "Administrative requirement" in names
    assert "Time lost" in names
    assert "Insufficient time" not in names, "must be renamed, not left as a duplicate"
    assert "Other" not in names
    globals_only = [t for t in r.json() if t["scope"] == "global"]
    assert len(globals_only) == 10


# ── create ────────────────────────────────────────────────────────────────────

def test_create_tag_requires_auth(client):
    r = client.post("/api/session-status-reason-tags", json={"display_name": "Cadet illness"})
    assert r.status_code == 401


def test_create_tag_forbidden_for_read_only(client):
    h = _sqn_general(client)
    r = client.post("/api/session-status-reason-tags", json={"display_name": "Cadet illness"}, headers=h)
    assert r.status_code == 403


def test_create_tag_forbidden_for_auditor(client):
    h = _auditor(client)
    r = client.post("/api/session-status-reason-tags", json={"display_name": "Cadet illness"}, headers=h)
    assert r.status_code == 403


def test_create_tag_success(client):
    h = _sqn_admin(client)
    r = client.post("/api/session-status-reason-tags", json={"display_name": "Cadet illness"}, headers=h)
    assert r.status_code == 201
    d = r.json()
    assert d["display_name"] == "Cadet illness"
    assert d["normalised_name"] == "cadet illness"
    assert d["is_active"] is True
    assert d["scope"] == "squadron"
    assert "tag_id" in d


def test_create_tag_normalises_whitespace(client):
    h = _sqn_admin(client)
    r = client.post("/api/session-status-reason-tags", json={"display_name": "  Transport  delay  "}, headers=h)
    assert r.status_code == 201
    d = r.json()
    assert d["display_name"] == "Transport  delay"
    assert d["normalised_name"] == "transport delay"


def test_create_tag_rejects_blank(client):
    h = _sqn_admin(client)
    r = client.post("/api/session-status-reason-tags", json={"display_name": "   "}, headers=h)
    assert r.status_code == 400


def test_create_tag_rejects_duplicate_case_insensitive(client):
    h = _sqn_admin(client)
    client.post("/api/session-status-reason-tags", json={"display_name": "Power outage"}, headers=h)
    r = client.post("/api/session-status-reason-tags", json={"display_name": "POWER OUTAGE"}, headers=h)
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "tag_already_exists"


def test_create_tag_rejects_duplicate_of_seeded_global(client):
    """A squadron-scoped attempt to recreate a global-seeded reason name must
    also be blocked -- global/wing/squadron scopes share one dedup namespace."""
    h = _sqn_admin(client)
    r = client.post("/api/session-status-reason-tags", json={"display_name": "weather"}, headers=h)
    assert r.status_code == 409


def test_create_tag_appears_in_list(client):
    h = _sqn_admin(client)
    tag_name = "REASON_UNIQUE_TAG"
    client.post("/api/session-status-reason-tags", json={"display_name": tag_name}, headers=h)
    r = client.get("/api/session-status-reason-tags", headers=h)
    names = [t["display_name"] for t in r.json()]
    assert tag_name in names


def test_create_tag_too_long(client):
    h = _sqn_admin(client)
    long_name = "X" * 81
    r = client.post("/api/session-status-reason-tags", json={"display_name": long_name}, headers=h)
    assert r.status_code == 400


# ── archive ────────────────────────────────────────────────────────────────────

def test_archive_tag(client):
    h = _sqn_admin(client)
    r = client.post("/api/session-status-reason-tags", json={"display_name": "ToBeArchivedReason"}, headers=h)
    tag_id = r.json()["tag_id"]
    r2 = client.delete(f"/api/session-status-reason-tags/{tag_id}", headers=h)
    assert r2.status_code == 200
    assert r2.json()["ok"] is True


def test_archived_tag_not_in_list(client):
    h = _sqn_admin(client)
    r = client.post("/api/session-status-reason-tags", json={"display_name": "WillBeHiddenReason"}, headers=h)
    tag_id = r.json()["tag_id"]
    client.delete(f"/api/session-status-reason-tags/{tag_id}", headers=h)
    r2 = client.get("/api/session-status-reason-tags", headers=h)
    ids = [t["tag_id"] for t in r2.json()]
    assert tag_id not in ids


def test_archive_nonexistent_tag(client):
    h = _sqn_admin(client)
    r = client.delete("/api/session-status-reason-tags/nonexistent-id", headers=h)
    assert r.status_code == 404


def test_archive_tag_forbidden_for_read_only(client):
    h_admin = _sqn_admin(client)
    h_gen = _sqn_general(client)
    r = client.post("/api/session-status-reason-tags", json={"display_name": "ArchiveTestReason"}, headers=h_admin)
    tag_id = r.json()["tag_id"]
    r2 = client.delete(f"/api/session-status-reason-tags/{tag_id}", headers=h_gen)
    assert r2.status_code == 403


# ── wing/national/system_admin scope creation ──────────────────────────────────
# Same defect and fix as test_facilitator_type_tags.py -- create_session_status_
# reason_tag used the shared _can_create_tag helper, which used to unconditionally
# require p.squadron_id, so wing_admin/national_admin/system_admin could never
# create a tag at any scope.

def test_wing_admin_can_create_wing_scope_tag(client):
    h = _wing_admin(client)
    r = client.post("/api/session-status-reason-tags", json={"display_name": "Wing Custom Reason", "scope": "wing"}, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["scope"] == "wing"


def test_nat_admin_can_create_global_scope_tag(client):
    h = _nat_admin(client)
    r = client.post("/api/session-status-reason-tags", json={"display_name": "Global Custom Reason", "scope": "global"}, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["scope"] == "global"


def test_sysadmin_can_create_global_scope_tag(client):
    h = _sysadmin(client)
    r = client.post("/api/session-status-reason-tags", json={"display_name": "SysAdmin Global Reason", "scope": "global"}, headers=h)
    assert r.status_code == 201, r.text


def test_wing_admin_without_proxy_cannot_create_squadron_scope_tag(client):
    h = _wing_admin(client)
    r = client.post("/api/session-status-reason-tags", json={"display_name": "Wing Attempt Squadron Reason", "scope": "squadron"}, headers=h)
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "proxy_required"


def test_wing_admin_with_active_proxy_can_create_squadron_scope_tag(client):
    h_sqn = _sqn_admin(client)
    sqn_id = _own_squadron_id(client, h_sqn)
    h = _wing_admin(client)
    enter = client.post(f"/api/proxy/enter/{sqn_id}", json={"reason": "reason tag setup"}, headers=h)
    assert enter.status_code == 200, enter.text
    try:
        r = client.post("/api/session-status-reason-tags", json={"display_name": "Proxied Squadron Reason", "scope": "squadron"}, headers=h)
        assert r.status_code == 201, r.text
    finally:
        client.post("/api/proxy/exit", headers=h)


def test_nat_admin_without_intervention_cannot_create_squadron_scope_tag(client):
    h = _nat_admin(client)
    r = client.post("/api/session-status-reason-tags", json={"display_name": "Nat Attempt Squadron Reason", "scope": "squadron"}, headers=h)
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "intervention_required"


def test_sqn_admin_cannot_archive_a_wing_scope_tag(client):
    h_wing = _wing_admin(client)
    r = client.post("/api/session-status-reason-tags", json={"display_name": "Wing Reason Protected", "scope": "wing"}, headers=h_wing)
    tag_id = r.json()["tag_id"]
    h_sqn = _sqn_admin(client)
    r2 = client.delete(f"/api/session-status-reason-tags/{tag_id}", headers=h_sqn)
    assert r2.status_code == 403
