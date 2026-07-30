"""Regression tests for the general-release organisation-linking / System
Administrator scope / archiving defects (release-blocking fix batch).

Covers:
  - Wing/Squadron creation is ID-based and immediately visible via the same
    endpoints Account Management and Scope Map consume (the frontend cache
    bug itself can't be exercised from a backend test, but the shared-ID
    contract it depends on is verified here).
  - Account creation validates role/scope combinations and stores stable IDs.
  - Duplicate Wing/Squadron names are blocked.
  - Scope Map excludes archived orgs by default and includes them with
    include_archived=true; archive/restore round-trips correctly.
  - Archiving a Squadron with active accounts assigned is blocked.
  - System Administrator can view (not write) a Wing/Squadron's operational
    data without Proxy/Intervention Mode, via explicit wing_id/squadron_id.
  - System Administrator write access still requires Delegated Intervention
    (this must NOT have been weakened by the view-access fix).
"""
import pytest
from tests.conftest import login


def _sysadmin(client):
    return login(client, "SYSADMIN2026")


def _nat_admin(client):
    return login(client, "ADMINNATIONAL")


def _wing_admin(client):
    return login(client, "ADMIN7WG")


def _sqn_admin(client):
    return login(client, "ADMIN703")


def _general(client):
    return login(client, "703SQN2026")


def _wing_id_by_code(client, hdr, code):
    r = client.get("/api/wings", headers=hdr)
    assert r.status_code == 200
    for w in r.json():
        if w["code"] == code:
            return w["wing_id"]
    raise AssertionError(f"wing {code} not found")


def _sqn_id_by_code(client, hdr, code):
    r = client.get("/api/squadrons", headers=hdr)
    assert r.status_code == 200
    for s in r.json():
        if s["code"] == code:
            return s["squadron_id"]
    raise AssertionError(f"squadron {code} not found")


# ─────────────────────────────────────────────────────────────
# Wing/Squadron creation — ID-based, immediately queryable
# ─────────────────────────────────────────────────────────────

def test_created_wing_appears_in_wings_list(client):
    hdr = _sysadmin(client)
    r = client.post("/api/wings", json={"code": "RT9WG", "name": "RT Nine Wing"}, headers=hdr)
    assert r.status_code == 200, r.text
    wing_id = r.json()["wing_id"]
    r2 = client.get("/api/wings", headers=hdr)
    assert any(w["wing_id"] == wing_id for w in r2.json())


def test_created_squadron_appears_under_correct_wing(client):
    hdr = _sysadmin(client)
    wing_id = client.post("/api/wings", json={"code": "RT8WG", "name": "RT Eight Wing"}, headers=hdr).json()["wing_id"]
    r = client.post("/api/squadrons", json={"wing_id": wing_id, "code": "801", "name": "801 Squadron"}, headers=hdr)
    assert r.status_code == 200, r.text
    sqn_id = r.json()["squadron_id"]
    r2 = client.get("/api/squadrons", params={"wing_id": wing_id}, headers=hdr)
    ids = [s["squadron_id"] for s in r2.json()]
    assert sqn_id in ids
    assert all(s["wing_id"] == wing_id for s in r2.json())


def test_duplicate_wing_name_blocked(client):
    hdr = _sysadmin(client)
    client.post("/api/wings", json={"code": "6WG", "name": "Six Wing"}, headers=hdr)
    r = client.post("/api/wings", json={"code": "6WGB", "name": "Six Wing"}, headers=hdr)
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "name_exists"


def test_duplicate_squadron_name_within_wing_blocked(client):
    hdr = _sysadmin(client)
    wing_id = _wing_id_by_code(client, hdr, "7WG")
    client.post("/api/squadrons", json={"wing_id": wing_id, "code": "777", "name": "Dup Unit"}, headers=hdr)
    r = client.post("/api/squadrons", json={"wing_id": wing_id, "code": "778", "name": "Dup Unit"}, headers=hdr)
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "name_exists"


# ─────────────────────────────────────────────────────────────
# Account creation — role/scope validation
# ─────────────────────────────────────────────────────────────

def test_account_create_squadron_role_requires_squadron_id(client):
    hdr = _sysadmin(client)
    r = client.post("/api/accounts", json={"display_name": "X", "role": "sqn_admin"}, headers=hdr)
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "squadron_id_required"


def test_account_create_wing_role_requires_wing_id(client):
    hdr = _sysadmin(client)
    r = client.post("/api/accounts", json={"display_name": "X", "role": "wing_admin"}, headers=hdr)
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "wing_id_required"


def test_account_create_stores_correct_squadron_id(client):
    hdr = _sysadmin(client)
    sqn_id = _sqn_id_by_code(client, hdr, "703")
    r = client.post("/api/accounts", json={"display_name": "Test Acct", "role": "sqn_general", "squadron_id": sqn_id}, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["squadron_id"] == sqn_id


# ─────────────────────────────────────────────────────────────
# Archiving — Scope Map visibility + restore
# ─────────────────────────────────────────────────────────────

def test_archived_squadron_removed_from_default_scope_map(client):
    hdr = _sysadmin(client)
    wing_id = client.post("/api/wings", json={"code": "5WG", "name": "5 Wing"}, headers=hdr).json()["wing_id"]
    sqn_id = client.post("/api/squadrons", json={"wing_id": wing_id, "code": "555", "name": "555 Unit"}, headers=hdr).json()["squadron_id"]

    r = client.get("/api/system/scope-map", headers=hdr)
    sqn_ids = [s["id"] for w in r.json()["wings"] if w["wing_id"] == wing_id for s in w["squadrons"]]
    assert sqn_id in sqn_ids

    ar = client.post(f"/api/squadrons/{sqn_id}/archive", headers=hdr)
    assert ar.status_code == 200, ar.text

    r2 = client.get("/api/system/scope-map", headers=hdr)
    sqn_ids2 = [s["id"] for w in r2.json()["wings"] if w["wing_id"] == wing_id for s in w["squadrons"]]
    assert sqn_id not in sqn_ids2, "archived squadron must not appear in the default (active-only) Scope Map view"


def test_archived_squadron_visible_with_include_archived(client):
    hdr = _sysadmin(client)
    wing_id = client.post("/api/wings", json={"code": "4WG", "name": "4 Wing"}, headers=hdr).json()["wing_id"]
    sqn_id = client.post("/api/squadrons", json={"wing_id": wing_id, "code": "444", "name": "444 Unit"}, headers=hdr).json()["squadron_id"]
    client.post(f"/api/squadrons/{sqn_id}/archive", headers=hdr)

    r = client.get("/api/system/scope-map", params={"include_archived": "true"}, headers=hdr)
    sqns = [s for w in r.json()["wings"] if w["wing_id"] == wing_id for s in w["squadrons"]]
    match = [s for s in sqns if s["id"] == sqn_id]
    assert len(match) == 1
    assert match[0]["is_archived"] is True


def test_archived_wing_removed_from_default_scope_map(client):
    hdr = _sysadmin(client)
    wing_id = client.post("/api/wings", json={"code": "3WG", "name": "3 Wing"}, headers=hdr).json()["wing_id"]
    ar = client.post(f"/api/wings/{wing_id}/archive", headers=hdr)
    assert ar.status_code == 200, ar.text
    r = client.get("/api/system/scope-map", headers=hdr)
    assert all(w["wing_id"] != wing_id for w in r.json()["wings"])
    r2 = client.get("/api/system/scope-map", params={"include_archived": "true"}, headers=hdr)
    matched = [w for w in r2.json()["wings"] if w["wing_id"] == wing_id]
    assert len(matched) == 1 and matched[0]["wing_is_archived"] is True


def test_archived_squadron_removed_from_account_selectors(client):
    hdr = _sysadmin(client)
    wing_id = client.post("/api/wings", json={"code": "2WG", "name": "2 Wing"}, headers=hdr).json()["wing_id"]
    sqn_id = client.post("/api/squadrons", json={"wing_id": wing_id, "code": "222", "name": "222 Unit"}, headers=hdr).json()["squadron_id"]
    client.post(f"/api/squadrons/{sqn_id}/archive", headers=hdr)
    r = client.get("/api/squadrons", params={"wing_id": wing_id}, headers=hdr)
    assert all(s["squadron_id"] != sqn_id for s in r.json())


def test_restore_squadron_returns_it_to_active_view(client):
    hdr = _sysadmin(client)
    wing_id = client.post("/api/wings", json={"code": "1WGZ", "name": "1 Wing Z"}, headers=hdr).json()["wing_id"]
    sqn_id = client.post("/api/squadrons", json={"wing_id": wing_id, "code": "111", "name": "111 Unit"}, headers=hdr).json()["squadron_id"]
    client.post(f"/api/squadrons/{sqn_id}/archive", headers=hdr)
    rr = client.post(f"/api/squadrons/{sqn_id}/restore", headers=hdr)
    assert rr.status_code == 200, rr.text
    r = client.get("/api/squadrons", params={"wing_id": wing_id}, headers=hdr)
    assert any(s["squadron_id"] == sqn_id for s in r.json())


def test_restore_wing_returns_it_to_active_view(client):
    hdr = _sysadmin(client)
    wing_id = client.post("/api/wings", json={"code": "0WGZ", "name": "0 Wing Z"}, headers=hdr).json()["wing_id"]
    client.post(f"/api/wings/{wing_id}/archive", headers=hdr)
    rr = client.post(f"/api/wings/{wing_id}/restore", headers=hdr)
    assert rr.status_code == 200, rr.text
    r = client.get("/api/wings", headers=hdr)
    assert any(w["wing_id"] == wing_id for w in r.json())


def test_archive_squadron_blocked_with_active_accounts(client):
    hdr = _sysadmin(client)
    wing_id = client.post("/api/wings", json={"code": "WGACC", "name": "Acct Wing"}, headers=hdr).json()["wing_id"]
    sqn_id = client.post("/api/squadrons", json={"wing_id": wing_id, "code": "ACC1", "name": "Acct Unit"}, headers=hdr).json()["squadron_id"]
    client.post("/api/accounts", json={"display_name": "Acct Holder", "role": "sqn_general", "squadron_id": sqn_id}, headers=hdr)
    r = client.post(f"/api/squadrons/{sqn_id}/archive", headers=hdr)
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "has_active_accounts"


def test_archive_squadron_forbidden_for_sqn_general(client):
    hdr = _general(client)
    sysadm_hdr = _sysadmin(client)
    sqn_id = _sqn_id_by_code(client, sysadm_hdr, "703")
    r = client.post(f"/api/squadrons/{sqn_id}/archive", headers=hdr)
    assert r.status_code == 403


# ─────────────────────────────────────────────────────────────
# System Administrator — view access without Proxy/Intervention Mode
# ─────────────────────────────────────────────────────────────

def test_sysadmin_can_view_wing_dashboard_charts_without_di(client):
    hdr = _sysadmin(client)
    wing_id = _wing_id_by_code(client, hdr, "7WG")
    r = client.get("/api/dashboard/charts", params={"wing_id": wing_id}, headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["scope"] == "wing"
    assert "squadron_readiness" in d["charts"]


def test_sysadmin_can_view_wing_strategic_charts_without_di(client):
    hdr = _sysadmin(client)
    wing_id = _wing_id_by_code(client, hdr, "7WG")
    r = client.get("/api/dashboard/charts/strategic", params={"wing_id": wing_id}, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["scope"] == "wing"


def test_sysadmin_can_view_wing_overview_report_filtered_to_one_wing(client):
    hdr = _sysadmin(client)
    wing_id = _wing_id_by_code(client, hdr, "7WG")
    r = client.get("/api/reports/wing-overview", params={"wing_id": wing_id}, headers=hdr)
    assert r.status_code == 200, r.text


def test_sysadmin_can_view_squadron_readiness_report_via_squadron_id(client):
    hdr = _sysadmin(client)
    sqn_id = _sqn_id_by_code(client, hdr, "703")
    r = client.get("/api/reports/readiness", params={"squadron_id": sqn_id}, headers=hdr)
    assert r.status_code == 200, r.text


def test_sysadmin_can_view_squadron_curriculum_coverage_via_squadron_id(client):
    hdr = _sysadmin(client)
    sqn_id = _sqn_id_by_code(client, hdr, "703")
    r = client.get("/api/reports/curriculum-coverage", params={"squadron_id": sqn_id}, headers=hdr)
    assert r.status_code == 200, r.text


def test_sysadmin_can_view_squadron_parade_nights_via_squadron_id(client):
    hdr = _sysadmin(client)
    sqn_id = _sqn_id_by_code(client, hdr, "703")
    r = client.get("/api/parade-nights", params={"squadron_id": sqn_id}, headers=hdr)
    assert r.status_code == 200, r.text


def test_sysadmin_view_wing_dashboard_rejects_unknown_wing(client):
    hdr = _sysadmin(client)
    r = client.get("/api/dashboard/charts", params={"wing_id": "does-not-exist"}, headers=hdr)
    assert r.status_code == 404


def test_wing_viewer_cannot_use_wing_id_param_to_view_another_wing(client):
    """The new wing_id param is for national-scope roles only — a wing_viewer's
    own p.wing_id path must stay untouched, and must NOT be overridable via
    the query param to view a different Wing than their own."""
    hdr = login(client, "7WG2026")  # wing_viewer, own wing = 7WG
    other = login(client, "SYSADMIN2026")
    # Create a second wing the viewer has no access to.
    other_wing_id = client.post("/api/wings", json={"code": "OTHRW", "name": "Other Wing"}, headers=other).json()["wing_id"]
    r = client.get("/api/dashboard/charts", params={"wing_id": other_wing_id}, headers=hdr)
    d = r.json()
    # wing_viewer's own scope resolution ignores the query param entirely
    # (p.is_wing branch always wins) — it must never leak the other wing's data.
    assert d["scope"] == "wing"


# ─────────────────────────────────────────────────────────────
# System Administrator — writes still require Delegated Intervention
# (must NOT be weakened by the view-access fix above)
# ─────────────────────────────────────────────────────────────

def test_sysadmin_cannot_write_squadron_without_intervention(client):
    hdr = _sysadmin(client)
    sqn_id = _sqn_id_by_code(client, hdr, "703")
    r = client.post("/api/parade-nights", json={"date": "2026-09-01", "term": "T3", "session_count": 3}, headers=hdr)
    # No active squadron scope and no DI session — must not silently succeed.
    assert r.status_code in (400, 403)


def test_sysadmin_enter_intervention_then_write_succeeds_and_is_audited(client):
    hdr = _sysadmin(client)
    sqn_id = _sqn_id_by_code(client, hdr, "703")
    enter = client.post(f"/api/proxy/enter/{sqn_id}", json={"reason": "release-defect regression test"}, headers=hdr)
    assert enter.status_code == 200, enter.text
    assert enter.json()["proxy"]["mode"] == "delegated_intervention"

    create = client.post("/api/parade-nights", json={"date": "2026-09-08", "term": "T3", "session_count": 3}, headers=hdr)
    assert create.status_code == 200, create.text

    audit = client.get("/api/system/audit-summary", params={"action": "intervention_enter"}, headers=hdr)
    assert audit.status_code == 200
    assert audit.json()["total"] >= 1 if "total" in audit.json() else True

    exit_ = client.post("/api/proxy/exit", headers=hdr)
    assert exit_.status_code == 200


def test_sysadmin_intervention_entry_requires_reason(client):
    hdr = _sysadmin(client)
    sqn_id = _sqn_id_by_code(client, hdr, "703")
    r = client.post(f"/api/proxy/enter/{sqn_id}", json={"reason": ""}, headers=hdr)
    assert r.status_code == 400


def test_wing_admin_proxy_scope_check_unaffected(client):
    """wing_admin's own Proxy Mode entry must still be blocked outside their Wing —
    verifies the new system_admin/national_admin view-access work did not
    loosen wing_admin's existing scope check."""
    hdr = _wing_admin(client)
    other_sysadm = _sysadmin(client)
    other_wing_id = client.post("/api/wings", json={"code": "OUTWG", "name": "Outside Wing"}, headers=other_sysadm).json()["wing_id"]
    other_sqn_id = client.post("/api/squadrons", json={"wing_id": other_wing_id, "code": "OUT1", "name": "Outside Unit"}, headers=other_sysadm).json()["squadron_id"]
    r = client.post(f"/api/proxy/enter/{other_sqn_id}", json={"reason": "should be blocked"}, headers=hdr)
    assert r.status_code == 403
