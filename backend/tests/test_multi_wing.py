"""Multi-Wing scope isolation and national aggregation tests (DEF-07 / DOC-11).

Verifies:
- Wing admin for Wing A cannot read Wing B data (scope isolation)
- National admin sees all Wings in aggregated endpoints
- No cross-Wing data leak in wing-scoped report endpoints
- National-level endpoints aggregate correctly when 2+ Wings exist

These tests provision a synthetic second Wing (11WG) inside the test and
rely on seed_all() having already created 7WG as the first Wing.

Response shapes (verified against ops.py router):
  POST /api/system/provision-wing → {"wing": {id, code, name},
                                     "results": [{type, code, name, created}, ...],
                                     "accounts_created": [...]}
  GET  /api/reports/national-overview  → {"wings": [{wing_id, code, name, ...}]}
  GET  /api/reports/national-capability → {"subjects": [...], "wings": [{code, ...}]}
  GET  /api/reports/wing-overview      → {"squadrons": [{squadron_id, code, ...}]}
  GET  /api/reports/wing-phase-coverage → {"squadrons": [...], "phases": [...]}
  GET  /api/reports/wing-capability    → {"squadrons": [...], ...}
"""
import pytest
from tests.conftest import login

# ── Helpers ──────────────────────────────────────────────────────────────────

def _sysadmin_hdr(client):
    return login(client, "SYSADMIN2026")

def _national_hdr(client):
    return login(client, "ADMINNATIONAL")

def _wing7_hdr(client):
    return login(client, "ADMIN7WG")


def _provision_second_wing(client):
    """Create synthetic 11WG with one squadron. Idempotent. Returns response JSON."""
    hdr = _sysadmin_hdr(client)
    r = client.post("/api/system/provision-wing", json={
        "wing_code": "11WG",
        "wing_name": "11 Wing (Test)",
        "wing_short": "11WG",
        "squadrons": [{"code": "1101", "name": "1101 Squadron AAFC", "short_name": "1101SQN"}],
        "create_accounts": True,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


# ── Wing provisioning ─────────────────────────────────────────────────────────

def test_provision_second_wing_succeeds(client):
    result = _provision_second_wing(client)
    assert result["wing"]["code"] == "11WG"
    sqn_results = [r for r in result["results"] if r["type"] == "squadron"]
    assert len(sqn_results) >= 1
    assert sqn_results[0]["code"] == "1101"


def test_provision_second_wing_idempotent(client):
    _provision_second_wing(client)
    result = _provision_second_wing(client)
    assert result["wing"]["code"] == "11WG"
    wing_result = next(r for r in result["results"] if r["type"] == "wing")
    assert wing_result["created"] is False


# ── Scope isolation: wing admin cannot see other wing ─────────────────────────

def test_wing_admin_cannot_access_other_wings_squadrons(client):
    _provision_second_wing(client)
    hdr = _wing7_hdr(client)
    r = client.get("/api/squadrons", headers=hdr)
    assert r.status_code == 200
    body = r.json()
    # Support both list and {"squadrons": [...]} shapes
    sqns = body if isinstance(body, list) else body.get("squadrons", body.get("data", []))
    codes = [s.get("code", "") for s in sqns]
    assert any(c in codes for c in ["703", "704", "705"]), "7WG sqns not in response"
    assert "1101" not in codes, "201SQN from 11WG leaked to 7WG admin"


def test_wing_overview_scoped_to_requesting_wing(client):
    _provision_second_wing(client)
    hdr = _wing7_hdr(client)
    r = client.get("/api/reports/wing-overview", headers=hdr)
    assert r.status_code == 200
    sqns = r.json().get("squadrons", [])
    codes = [s.get("code", "") for s in sqns]
    assert "1101" not in codes, "11WG squadron leaked into 7WG wing-overview"


def test_wing_phase_coverage_scoped_to_requesting_wing(client):
    _provision_second_wing(client)
    hdr = _wing7_hdr(client)
    r = client.get("/api/reports/wing-phase-coverage", headers=hdr)
    assert r.status_code == 200
    sqns = r.json().get("squadrons", [])
    codes = [s.get("code", s.get("short_name", "")) for s in sqns]
    assert "1101" not in codes, "11WG squadron leaked into 7WG wing-phase-coverage"


def test_wing_capability_scoped_to_requesting_wing(client):
    _provision_second_wing(client)
    hdr = _wing7_hdr(client)
    r = client.get("/api/reports/wing-capability", headers=hdr)
    assert r.status_code == 200
    sqns = r.json().get("squadrons", [])
    codes = [s.get("code", s.get("short_name", "")) for s in sqns]
    assert "1101" not in codes, "11WG squadron leaked into 7WG wing-capability"


def test_wing_admin_cannot_query_other_wing_via_param(client):
    """wing_admin must not be able to pass another wing_id to read its data."""
    provisioned = _provision_second_wing(client)
    wing2_id = provisioned["wing"]["id"]
    hdr = _wing7_hdr(client)
    r = client.get(f"/api/reports/wing-overview?wing_id={wing2_id}", headers=hdr)
    # Endpoint pins wing_admin to their own wing regardless of param — must NOT return 11WG data
    if r.status_code == 200:
        sqns = r.json().get("squadrons", [])
        codes = [s.get("code", "") for s in sqns]
        assert "1101" not in codes, "wing_admin could read 11WG data via wing_id param"
    else:
        assert r.status_code in (403, 422, 404), f"Unexpected status {r.status_code}"


# ── National aggregation: sees all Wings ──────────────────────────────────────

def test_national_overview_includes_both_wings(client):
    _provision_second_wing(client)
    hdr = _national_hdr(client)
    r = client.get("/api/reports/national-overview", headers=hdr)
    assert r.status_code == 200
    wings = r.json().get("wings", [])
    codes = [w.get("code", "") for w in wings]
    assert "7WG" in codes, "7WG missing from national overview"
    assert "11WG" in codes, "11WG missing from national overview after provisioning"


def test_national_capability_includes_both_wings(client):
    _provision_second_wing(client)
    hdr = _national_hdr(client)
    r = client.get("/api/reports/national-capability", headers=hdr)
    assert r.status_code == 200
    wings = r.json().get("wings", [])
    codes = [w.get("code", "") for w in wings]
    assert "7WG" in codes, "7WG missing from national capability"
    assert "11WG" in codes, "11WG missing from national capability after provisioning"


def test_national_overview_wing_count_correct(client):
    _provision_second_wing(client)
    hdr = _national_hdr(client)
    r = client.get("/api/reports/national-overview", headers=hdr)
    assert r.status_code == 200
    wings = r.json().get("wings", [])
    assert len(wings) >= 2, f"Expected 2+ Wings in national overview, got {len(wings)}"


def test_national_capability_wing_count_correct(client):
    _provision_second_wing(client)
    hdr = _national_hdr(client)
    r = client.get("/api/reports/national-capability", headers=hdr)
    assert r.status_code == 200
    wings = r.json().get("wings", [])
    assert len(wings) >= 2, f"Expected 2+ Wings in national capability, got {len(wings)}"


# ── Wing admin cannot access national endpoints ──────────────────────────────

def test_wing_admin_denied_national_overview(client):
    hdr = _wing7_hdr(client)
    r = client.get("/api/reports/national-overview", headers=hdr)
    assert r.status_code == 403


def test_wing_admin_denied_national_capability(client):
    hdr = _wing7_hdr(client)
    r = client.get("/api/reports/national-capability", headers=hdr)
    assert r.status_code == 403


# ── Unauthenticated ──────────────────────────────────────────────────────────

def test_national_overview_unauthenticated(client):
    r = client.get("/api/reports/national-overview")
    assert r.status_code == 401


def test_national_capability_unauthenticated(client):
    r = client.get("/api/reports/national-capability")
    assert r.status_code == 401


def test_wing_overview_unauthenticated(client):
    r = client.get("/api/reports/wing-overview")
    assert r.status_code == 401
