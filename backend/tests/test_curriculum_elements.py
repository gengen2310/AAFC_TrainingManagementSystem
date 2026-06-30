"""Curriculum element tests — RBAC, scope, idempotency, import integration, term rules.

Tests:
- squadron_admin can create squadron-scope elements
- squadron_admin cannot create wing/national elements
- wing_admin can create wing elements
- national_admin can create national elements
- system_admin can create elements at any scope
- viewer/auditor cannot create elements
- duplicate element create is idempotent (returns existing, not 409)
- curriculum can be created with a custom element
- workbook import creates missing elements idempotently
- national curriculum can be created without term
- wing curriculum can be created without term
- frontend error message hint (element list returns managed elements)
"""
import pytest
from tests.conftest import login


def _sysadmin(client):
    return login(client, "SYSADMIN2026")

def _nat_admin(client):
    return login(client, "ADMINNATIONAL")

def _sqn_admin(client):
    return login(client, "ADMIN703")

def _wing_viewer(client):
    return login(client, "AUDITOR2026")  # auditor is read-only


# ── Element list ──────────────────────────────────────────────────────────

def test_elements_list_returns_defaults(client):
    """GET /api/curriculum/elements returns at least the seeded national elements."""
    hdr = _sqn_admin(client)
    r = client.get("/api/curriculum/elements", headers=hdr)
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    names = [e["name"] for e in data]
    assert "Air_Space" in names or "Drill" in names  # at least one default exists


def test_elements_list_unauthenticated(client):
    r = client.get("/api/curriculum/elements")
    assert r.status_code == 401


# ── RBAC: who can create elements ────────────────────────────────────────

def test_sqn_admin_can_create_sqn_element(client):
    """squadron_admin can create elements scoped to their own squadron."""
    hdr = _sqn_admin(client)
    r = client.post("/api/curriculum/elements", json={
        "name": "SQN_Leadership", "display_name": "Squadron Leadership",
        "scope_level": "squadron",
    }, headers=hdr)
    assert r.status_code == 200
    assert r.json()["name"] == "SQN_Leadership"


def test_sqn_admin_cannot_create_national_element(client):
    """squadron_admin must be denied when creating at national scope."""
    hdr = _sqn_admin(client)
    r = client.post("/api/curriculum/elements", json={
        "name": "NAT_TEST", "display_name": "National Test",
        "scope_level": "national",
    }, headers=hdr)
    assert r.status_code == 403


def test_sqn_admin_cannot_create_wing_element(client):
    """squadron_admin must be denied when creating at wing scope."""
    hdr = _sqn_admin(client)
    r = client.post("/api/curriculum/elements", json={
        "name": "WING_TEST", "display_name": "Wing Test",
        "scope_level": "wing",
    }, headers=hdr)
    assert r.status_code == 403


def test_nat_admin_can_create_national_element(client):
    """national_admin can create national-scope elements."""
    hdr = _nat_admin(client)
    r = client.post("/api/curriculum/elements", json={
        "name": "NAT_CUSTOM_EL", "display_name": "National Custom Element",
        "scope_level": "national",
    }, headers=hdr)
    assert r.status_code == 200
    assert r.json()["scope_level"] == "national"


def test_sysadmin_can_create_any_scope_element(client):
    """system_admin can create elements at any scope."""
    hdr = _sysadmin(client)
    for scope in ("national", "wing", "squadron"):
        r = client.post("/api/curriculum/elements", json={
            "name": f"SYSADM_EL_{scope.upper()[:3]}", "display_name": f"SysAdmin {scope}",
            "scope_level": scope,
        }, headers=hdr)
        assert r.status_code == 200, f"scope={scope} failed: {r.text}"


def test_auditor_cannot_create_element(client):
    """Auditors (viewers) must be denied element creation."""
    hdr = _wing_viewer(client)
    r = client.post("/api/curriculum/elements", json={
        "name": "AUD_EL", "display_name": "Auditor Attempt",
        "scope_level": "national",
    }, headers=hdr)
    assert r.status_code == 403


def test_invalid_scope_level_rejected(client):
    """Invalid scope_level returns 400."""
    hdr = _sysadmin(client)
    r = client.post("/api/curriculum/elements", json={
        "name": "BAD_SCOPE", "display_name": "Bad Scope",
        "scope_level": "galactic",  # invalid
    }, headers=hdr)
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "invalid_scope"


# ── Idempotency ───────────────────────────────────────────────────────────

def test_duplicate_element_is_idempotent(client):
    """Creating the same element twice returns the existing one with existed=True."""
    hdr = _nat_admin(client)
    payload = {"name": "IDEM_ELEMENT", "display_name": "Idempotent Element",
               "scope_level": "national"}
    r1 = client.post("/api/curriculum/elements", json=payload, headers=hdr)
    r2 = client.post("/api/curriculum/elements", json=payload, headers=hdr)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json()["existed"] is True
    assert r1.json()["element_id"] == r2.json()["element_id"]


# ── Curriculum create with custom element ─────────────────────────────────

def test_curriculum_created_with_custom_element(client):
    """A curriculum item can be created using a custom element string."""
    hdr = _sysadmin(client)
    # First ensure element exists
    client.post("/api/curriculum/elements", json={
        "name": "Robotics", "display_name": "Robotics", "scope_level": "national",
    }, headers=hdr)
    r = client.post("/api/curriculum/national", json={
        "code": "ROBO-01", "title": "Intro to Robotics",
        "identifier": "ROBO-01(1)", "part_number": 1,
        "phase": "C. Junior", "element": "Robotics", "duration_minutes": 60,
    }, headers=hdr)
    assert r.status_code == 200
    # Verify element shows in curriculum list
    items = client.get("/api/curriculum", headers=hdr).json().get("items", [])
    robo = next((i for i in items if i["code"] == "ROBO-01"), None)
    assert robo is not None
    assert robo["element"] == "Robotics"


# ── Term rules ────────────────────────────────────────────────────────────

def test_national_curriculum_no_term_allowed(client):
    """National curriculum can be created without specifying a term (None is valid)."""
    hdr = _sysadmin(client)
    r = client.post("/api/curriculum/national", json={
        "code": "NO-TERM-NAT", "title": "No Term National",
        "identifier": "NO-TERM-NAT(1)", "part_number": 1,
        "phase": "B. Initial", "duration_minutes": 60,
        # no recommended_term field → defaults to None
    }, headers=hdr)
    assert r.status_code == 200
    items = client.get("/api/curriculum", headers=hdr).json().get("items", [])
    item = next((i for i in items if i["code"] == "NO-TERM-NAT"), None)
    assert item is not None
    assert item["recommended_term"] is None


def test_wing_curriculum_no_term_allowed(client):
    """Wing curriculum can be created without a term; nat_admin must provide wing_id."""
    hdr = _nat_admin(client)
    # Get a valid wing_id from the seeded wings
    wings = client.get("/api/wings", headers=hdr).json()
    assert wings, "Expected at least one wing to be seeded"
    wing_id = wings[0]["wing_id"]
    r = client.post("/api/curriculum/wing", json={
        "code": "NO-TERM-WING", "title": "No Term Wing",
        "identifier": "NO-TERM-WING(1)", "part_number": 1,
        "phase": "B. Initial", "duration_minutes": 60,
        "wing_id": wing_id,
    }, headers=hdr)
    assert r.status_code == 200


# ── Import creates elements idempotently ──────────────────────────────────

def test_import_creates_missing_elements_idempotently(client):
    """Importing curriculum with a novel element name creates that element without error."""
    hdr = _sysadmin(client)
    items = [
        {"code": "EL-IMP-01", "title": "Element Import Test", "identifier": "EL-IMP-01(1)",
         "part_number": 1, "phase": "B. Initial", "duration_minutes": 60,
         "element": "BRAND_NEW_ELEMENT"},
    ]
    r = client.post("/api/curriculum/import", json={
        "items": items, "owning_level": "national"
    }, headers=hdr)
    assert r.status_code == 200
    assert r.json()["failed"] == 0
    # Run again — element now exists, must not fail
    r2 = client.post("/api/curriculum/import", json={
        "items": items, "owning_level": "national"
    }, headers=hdr)
    assert r2.status_code == 200
    assert r2.json()["failed"] == 0
    # Verify the element was created
    els = client.get("/api/curriculum/elements", headers=hdr).json()
    assert any(e["name"] == "BRAND_NEW_ELEMENT" for e in els)


def test_elements_visible_in_curriculum_list_response(client):
    """GET /api/curriculum/elements returns correct shape for frontend rendering."""
    hdr = _sqn_admin(client)
    els = client.get("/api/curriculum/elements", headers=hdr).json()
    assert isinstance(els, list)
    for el in els:
        assert "element_id" in el
        assert "name" in el
        assert "display_name" in el
        assert "scope_level" in el
