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


def _import_preview(client, hdr, items, owning_level="national", squadron_id=None):
    payload = {"items": items, "owning_level": owning_level, "preview": True}
    if squadron_id:
        payload["squadron_id"] = squadron_id
    return client.post("/api/curriculum/import", json=payload, headers=hdr)


def test_preview_reports_create_but_writes_nothing(client):
    """Phase 3.4: preview=true must classify rows exactly like a real import
    (so the caller can trust the count before committing) but must not
    persist anything -- confirmed by re-running the same preview and getting
    an identical 'created' count, not 'updated'/'skipped' from a leftover row."""
    hdr = _sysadmin(client)
    items = [
        {"code": "IMP-PREV-01", "title": "Preview Test", "identifier": "IMP-PREV-01(1)",
         "part_number": 1, "phase": "B. Initial", "duration_minutes": 60},
    ]
    r1 = _import_preview(client, hdr, items)
    assert r1.status_code == 200, r1.text
    d1 = r1.json()
    assert d1["preview"] is True
    assert d1["created"] == 1

    r2 = _import_preview(client, hdr, items)
    d2 = r2.json()
    assert d2["created"] == 1  # still "would create" -- nothing was actually written by r1

    # A real, un-previewed GET confirms the item genuinely doesn't exist yet.
    listed = client.get("/api/curriculum", headers=hdr).json()["items"]
    assert not any(i.get("identifier") == "IMP-PREV-01(1)" for i in listed)


def test_preview_then_commit_creates_the_item(client):
    hdr = _sysadmin(client)
    items = [
        {"code": "IMP-PREV-02", "title": "Preview Then Commit", "identifier": "IMP-PREV-02(1)",
         "part_number": 1, "phase": "B. Initial", "duration_minutes": 60},
    ]
    preview = _import_preview(client, hdr, items)
    assert preview.json()["created"] == 1

    commit = _import(client, hdr, items)  # preview defaults to False
    d = commit.json()
    assert d["preview"] is False
    assert d["created"] == 1

    listed = client.get("/api/curriculum", headers=hdr).json()["items"]
    assert any(i.get("identifier") == "IMP-PREV-02(1)" for i in listed)


def test_preview_classifies_update_without_changing_the_stored_title(client):
    hdr = _sysadmin(client)
    items = [
        {"code": "IMP-PREV-03", "title": "Original Title", "identifier": "IMP-PREV-03(1)",
         "part_number": 1, "phase": "B. Initial", "duration_minutes": 60},
    ]
    _import(client, hdr, items)  # real create

    items[0]["title"] = "Changed Title"
    preview = _import_preview(client, hdr, items)
    d = preview.json()
    assert d["preview"] is True
    assert d["updated"] == 1

    listed = client.get("/api/curriculum", headers=hdr).json()["items"]
    match = next(i for i in listed if i.get("identifier") == "IMP-PREV-03(1)")
    assert match["title"] == "Original Title"  # preview must not have written the change


def test_import_csv_preview_writes_nothing_then_commit_creates(client):
    """Phase 3.4: the CSV upload endpoint threads preview through to the same
    JSON import path -- same non-destructive preview-then-commit guarantee,
    reachable via a real file upload rather than a JSON body."""
    hdr = _sysadmin(client)
    csv_content = (
        "Module Code,Title,Training Phase,Instructor Suitability\r\n"
        "IMP-CSV-01,CSV Preview Test,B. Initial,Any\r\n"
    )
    files = {"file": ("curriculum.csv", csv_content, "text/csv")}

    preview = client.post("/api/curriculum/import-csv?preview=true", headers=hdr, files=files)
    assert preview.status_code == 200, preview.text
    dp = preview.json()
    assert dp["preview"] is True
    assert dp["created"] == 1

    listed_before = client.get("/api/curriculum", headers=hdr).json()["items"]
    assert not any(i.get("code") == "IMP-CSV-01" for i in listed_before)

    commit = client.post("/api/curriculum/import-csv", headers=hdr, files=files)
    dc = commit.json()
    assert dc["preview"] is False
    assert dc["created"] == 1

    listed_after = client.get("/api/curriculum", headers=hdr).json()["items"]
    assert any(i.get("code") == "IMP-CSV-01" for i in listed_after)


def test_import_csv_core_status_column_is_respected(client):
    """Final-assurance Stage 2 finding: the CSV import path computed a per-row
    core_status ("Foundation"->core, "Extension"->additional) from the
    "Foundation or Extension"/"Type" column but silently discarded it --
    CurriculumImportItem had no core_status field to carry it, so every
    imported item silently got the same core_status derived only from
    owning_level, regardless of what the CSV actually said. Fixed by adding
    the field and threading it through create + update."""
    hdr = _sysadmin(client)
    csv_content = (
        "Module Code,Title,Training Phase,Foundation or Extension\r\n"
        "IMP-CORE-01,Core Module,B. Initial,Foundation\r\n"
        "IMP-CORE-02,Extension Module,B. Initial,Extension\r\n"
    )
    files = {"file": ("curriculum.csv", csv_content, "text/csv")}

    commit = client.post("/api/curriculum/import-csv", headers=hdr, files=files)
    assert commit.status_code == 200, commit.text
    assert commit.json()["created"] == 2

    listed = client.get("/api/curriculum", headers=hdr).json()["items"]
    core = next(i for i in listed if i["code"] == "IMP-CORE-01")
    extension = next(i for i in listed if i["code"] == "IMP-CORE-02")
    assert core["core_status"] == "core"
    assert extension["core_status"] == "additional"

    # Re-import with the Foundation/Extension values swapped -- the update
    # path must also respect the CSV, not just the create path.
    csv_swapped = (
        "Module Code,Title,Training Phase,Foundation or Extension\r\n"
        "IMP-CORE-01,Core Module,B. Initial,Extension\r\n"
        "IMP-CORE-02,Extension Module,B. Initial,Foundation\r\n"
    )
    files2 = {"file": ("curriculum.csv", csv_swapped, "text/csv")}
    commit2 = client.post("/api/curriculum/import-csv", headers=hdr, files=files2)
    assert commit2.status_code == 200, commit2.text
    assert commit2.json()["updated"] == 2

    listed2 = client.get("/api/curriculum", headers=hdr).json()["items"]
    core2 = next(i for i in listed2 if i["code"] == "IMP-CORE-01")
    extension2 = next(i for i in listed2 if i["code"] == "IMP-CORE-02")
    assert core2["core_status"] == "additional"
    assert extension2["core_status"] == "core"


def test_import_csv_oversized_file_rejected_before_parsing(client):
    """Security review candidate 5 (docs/qualification/06_security_review.md Finding 4.4):
    the whole uploaded body is read into memory before parsing -- confirm a size limit is
    enforced, matching every other upload endpoint in this codebase, rather than reading
    an arbitrarily large file into memory unbounded (a DoS/memory candidate)."""
    from app.config import settings as _settings
    hdr = _sysadmin(client)
    oversized = "A" * (_settings.UPLOAD_MAX_MB * 1024 * 1024 + 1)
    files = {"file": ("huge.csv", oversized, "text/csv")}
    r = client.post("/api/curriculum/import-csv", headers=hdr, files=files)
    assert r.status_code == 413, r.text
    assert r.json()["detail"]["error"] == "file_too_large"


def test_import_xlsm_oversized_file_rejected_before_parsing(client):
    """Same size-limit protection for the .xlsm import endpoint -- this one hands the raw
    bytes straight to openpyxl.load_workbook(), which has significant memory overhead of
    its own on top of the raw read, making an unbounded upload here worse than the CSV
    case, not just equivalent."""
    from app.config import settings as _settings
    hdr = _sysadmin(client)
    oversized = b"P" * (_settings.UPLOAD_MAX_MB * 1024 * 1024 + 1)
    files = {"file": ("huge.xlsm", oversized,
                      "application/vnd.ms-excel.sheet.macroEnabled.12")}
    r = client.post("/api/curriculum/import-xlsm", headers=hdr, files=files)
    assert r.status_code == 413, r.text
    assert r.json()["detail"]["error"] == "file_too_large"


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
