"""Curriculum import tests — identifier uniqueness, upsert behaviour, 409 fix, RBAC.

Tests:
- Same Module_Code with different Part/Identifier → allowed, not a 409
- Duplicate Identifier → handled as upsert/skip, not a crash or 409
- system_admin can import via bulk import endpoint
- Re-running import is idempotent
- 409 now returns human-readable message, not a bare error code
- Audit log entry created on import
"""
import json
import pytest
from tests.conftest import login


def _sysadmin(client):
    return login(client, "SYSADMIN2026")


def _nat_admin(client):
    return login(client, "ADMINNATIONAL")


def _sqn_admin(client):
    return login(client, "ADMIN703")


# ── Helper: create a national curriculum item ────────────────────────────────

def _create_nat(client, hdr, code, title, identifier=None, part_number=1):
    payload = {
        "code": code,
        "title": title,
        "phase": "B. Initial",
        "duration_minutes": 60,
        "identifier": identifier,
        "part_number": part_number,
    }
    return client.post("/api/curriculum/national", json=payload, headers=hdr)


# ── 409 fix: same code, different identifier/part ──────────────────────────

def test_same_code_different_part_allowed(client):
    """Multiple parts of the same module (same code, different part_number) must NOT 409."""
    hdr = _sysadmin(client)
    r1 = _create_nat(client, hdr, "TEST-MULTI-01", "Multi-Part Module Part 1",
                     identifier="TEST-MULTI-01(1)", part_number=1)
    r2 = _create_nat(client, hdr, "TEST-MULTI-01", "Multi-Part Module Part 2",
                     identifier="TEST-MULTI-01(2)", part_number=2)
    assert r1.status_code == 200, f"Part 1 failed: {r1.text}"
    assert r2.status_code == 200, f"Part 2 with same Module_Code should succeed: {r2.text}"


def test_duplicate_identifier_returns_409_with_message(client):
    """Posting an item with the same identifier returns 409 with a human-readable message."""
    hdr = _sysadmin(client)
    _create_nat(client, hdr, "TEST-DUP-01", "Dup Item", identifier="TEST-DUP-01(1)", part_number=1)
    r = _create_nat(client, hdr, "TEST-DUP-01", "Dup Item Again", identifier="TEST-DUP-01(1)", part_number=1)
    assert r.status_code == 409
    detail = r.json().get("detail", {})
    # Must include human-readable message, not just a bare error code
    assert "message" in detail, f"409 should have 'message': {detail}"
    assert detail["error"] == "already_exists"


def test_duplicate_identifier_not_blank_error_code(client):
    """Regression: 409 detail must not be a bare 'code_exists' string without message."""
    hdr = _sysadmin(client)
    _create_nat(client, hdr, "TEST-BARE-01", "Bare Error Test", identifier="TEST-BARE-01(1)")
    r = _create_nat(client, hdr, "TEST-BARE-01", "Bare Error Test", identifier="TEST-BARE-01(1)")
    assert r.status_code == 409
    d = r.json()["detail"]
    # Old behaviour was {"error": "code_exists"} with no message. New behaviour must have message.
    assert d.get("error") != "code_exists" or "message" in d


# ── Bulk import ────────────────────────────────────────────────────────────

def _import(client, hdr, items, owning_level="national", squadron_id=None):
    payload = {"items": items, "owning_level": owning_level}
    if squadron_id:
        payload["squadron_id"] = squadron_id
    return client.post("/api/curriculum/import", json=payload, headers=hdr)


def test_bulk_import_create(client):
    """Bulk import creates new items and returns created count."""
    hdr = _sysadmin(client)
    items = [
        {"code": "IMP-TST-01", "title": "Import Test 1", "identifier": "IMP-TST-01(1)",
         "part_number": 1, "phase": "B. Initial", "duration_minutes": 60},
        {"code": "IMP-TST-01", "title": "Import Test 1 Part 2", "identifier": "IMP-TST-01(2)",
         "part_number": 2, "phase": "B. Initial", "duration_minutes": 60},
        {"code": "IMP-TST-02", "title": "Import Test 2", "identifier": "IMP-TST-02(1)",
         "part_number": 1, "phase": "C. Junior", "duration_minutes": 90},
    ]
    r = _import(client, hdr, items)
    assert r.status_code == 200
    d = r.json()
    assert d["created"] == 3
    assert d["updated"] == 0
    assert d["skipped"] == 0
    assert d["failed"] == 0


def test_bulk_import_idempotent(client):
    """Running the same import twice skips already-existing items."""
    hdr = _sysadmin(client)
    items = [
        {"code": "IMP-IDEM-01", "title": "Idempotent Test", "identifier": "IMP-IDEM-01(1)",
         "part_number": 1, "phase": "B. Initial", "duration_minutes": 60},
    ]
    r1 = _import(client, hdr, items)
    assert r1.json()["created"] == 1

    r2 = _import(client, hdr, items)
    d2 = r2.json()
    assert d2["created"] == 0
    assert d2["skipped"] == 1
    assert d2["failed"] == 0


def test_bulk_import_updates_changed_fields(client):
    """Re-importing with changed title updates the existing item."""
    hdr = _sysadmin(client)
    items = [
        {"code": "IMP-UPD-01", "title": "Original Title", "identifier": "IMP-UPD-01(1)",
         "part_number": 1, "phase": "B. Initial", "duration_minutes": 60},
    ]
    _import(client, hdr, items)

    items[0]["title"] = "Updated Title"
    r = _import(client, hdr, items)
    d = r.json()
    assert d["updated"] == 1
    assert d["created"] == 0


def test_bulk_import_requires_nat_admin(client):
    """sqn_admin must be denied access to bulk import."""
    hdr = _sqn_admin(client)
    r = _import(client, hdr, [{"code": "X", "title": "Y", "identifier": "X(1)", "part_number": 1}])
    assert r.status_code == 403


def test_bulk_import_nat_admin_allowed(client):
    """national_admin can also run the bulk import."""
    hdr = _nat_admin(client)
    items = [
        {"code": "IMP-NAT-01", "title": "Nat Admin Import", "identifier": "IMP-NAT-01(1)",
         "part_number": 1, "phase": "B. Initial", "duration_minutes": 60},
    ]
    r = _import(client, hdr, items)
    assert r.status_code == 200


def test_bulk_import_mixed_code_parts(client):
    """Module_Code with many parts should all be importable in one call without 409."""
    hdr = _sysadmin(client)
    # Simulates Skills-06 which has 11 parts in the real workbook
    items = [
        {"code": "SKILLS-06", "title": f"Skills Module Part {i}", "identifier": f"SKILLS-06({i})",
         "part_number": i, "phase": "M. CDT Skills", "duration_minutes": 60}
        for i in range(1, 12)
    ]
    r = _import(client, hdr, items)
    d = r.json()
    assert d["created"] == 11
    assert d["failed"] == 0, f"No failures expected; got: {[x for x in d['results'] if x['status']=='failed']}"


def test_bulk_import_audited(client):
    """Bulk import creates an audit log entry."""
    hdr = _sysadmin(client)
    items = [
        {"code": "IMP-AUD-01", "title": "Audit Test", "identifier": "IMP-AUD-01(1)",
         "part_number": 1, "phase": "B. Initial", "duration_minutes": 60},
    ]
    _import(client, hdr, items)
    r = client.get("/api/system/audit-summary?action=bulk_import&limit=10", headers=hdr)
    assert r.status_code == 200
    logs = r.json()["logs"]
    assert any(e["action"] == "bulk_import" for e in logs)


def test_curriculum_list_includes_identifier(client):
    """GET /api/curriculum response must include identifier and part_number fields."""
    hdr = _sqn_admin(client)
    r = client.get("/api/curriculum", headers=hdr)
    assert r.status_code == 200
    items = r.json().get("items", [])
    assert len(items) > 0, "Expected seeded curriculum items"
    # identifier field should be present (may be None for legacy items)
    for item in items[:3]:
        assert "identifier" in item, f"identifier missing from curriculum item: {item}"
        assert "part_number" in item, f"part_number missing from curriculum item: {item}"
