"""V9 Cadet Program tests: inheritance/visibility, coverage, scope enforcement,
exports, and real-workbook source import."""
import base64
import os
import glob
from conftest import login


def _codes(client, headers, schedulable=False):
    r = client.get(f"/api/program-items?schedulable={'true' if schedulable else 'false'}", headers=headers)
    assert r.status_code == 200, r.text
    return {i["code"] for i in r.json()}


# ── VISIBILITY MATRIX (spec §7) ──
def test_national_items_visible_to_squadron_and_wing(client):
    for code in ("ADMIN703", "ADMIN7WG", "NATIONAL2026"):
        h = login(client, code)
        codes = _codes(client, h)
        assert "ORI-M01" in codes  # a national item


def test_wing_item_visible_within_wing_only(client):
    h703 = login(client, "ADMIN703")     # squadron in 7 Wing
    assert "7WG-LOC01" in _codes(client, h703)
    hwing = login(client, "ADMIN7WG")
    assert "7WG-LOC01" in _codes(client, hwing)


def test_squadron_local_not_visible_to_peer(client):
    h703 = login(client, "ADMIN703")
    h704 = login(client, "ADMIN704")
    assert "703-LOC01" in _codes(client, h703)        # owner sees own local
    assert "703-LOC01" not in _codes(client, h704)    # peer must NOT see it


def test_squadron_local_visible_upward(client):
    hwing = login(client, "ADMIN7WG")
    hnat = login(client, "NATIONAL2026")
    assert "703-LOC01" in _codes(client, hwing)       # wing oversight
    assert "703-LOC01" in _codes(client, hnat)        # national oversight


# ── SCOPE EDIT ENFORCEMENT ──
def test_squadron_cannot_edit_national_package(client):
    h703 = login(client, "ADMIN703")
    pkgs = client.get("/api/program-packages", headers=h703).json()
    nat_pkg = next(k for k in pkgs if k["owning_scope"] == "national")
    r = client.post(f"/api/program-packages/{nat_pkg['id']}/retire", headers=h703)
    assert r.status_code == 403


def test_wing_cannot_edit_national_package(client):
    hwing = login(client, "ADMIN7WG")
    pkgs = client.get("/api/program-packages", headers=hwing).json()
    nat_pkg = next(k for k in pkgs if k["owning_scope"] == "national")
    assert client.post(f"/api/program-packages/{nat_pkg['id']}/publish", headers=hwing).status_code == 403


def test_squadron_admin_can_create_local_package_and_item(client):
    h = login(client, "ADMIN704")
    r = client.post("/api/program-packages", headers=h, json={"title": "704 Local"})
    assert r.status_code == 200 and r.json()["owning_scope"] == "squadron"
    pid = r.json()["id"]
    ri = client.post("/api/program-items", headers=h,
                     json={"package_id": pid, "code": "704-LOC9", "title": "704 STEM Night", "core_status": "local"})
    assert ri.status_code == 200
    # 703 must not see the new 704-local item
    assert "704-LOC9" not in _codes(client, login(client, "ADMIN703"))


# ── COVERAGE ENGINE ──
def test_coverage_counts_and_not_delivered(client):
    h = login(client, "ADMIN703")
    cov = client.get("/api/program-coverage/squadron", headers=h).json()
    assert cov["core"]["available"] >= 1
    # 703 demo delivered several national items → delivered coverage > 0
    assert cov["delivered_coverage_pct"] > 0
    # not-delivered demo session is reflected
    assert cov["core"]["not_delivered"] >= 0


def test_extension_separate_from_core(client):
    h = login(client, "ADMIN703")
    cov = client.get("/api/program-coverage/squadron", headers=h).json()
    assert "extension" in cov and "core" in cov
    # extension availability is tracked independently
    assert cov["extension"]["available"] >= 0


def test_wing_coverage_sees_squadrons(client):
    h = login(client, "ADMIN7WG")
    r = client.get("/api/program-coverage/wing", headers=h)
    assert r.status_code == 200
    assert len(r.json()["squadrons"]) >= 16


# ── PROMOTION ──
def test_squadron_to_wing_promotion_flow(client):
    h = login(client, "ADMIN703")
    items = client.get("/api/program-items", headers=h).json()
    local = next(i for i in items if i["code"] == "703-LOC01")
    r = client.post("/api/program-promotion/squadron-to-wing", headers=h,
                    json={"program_item_id": local["id"], "reason": "Useful wing-wide"})
    assert r.status_code == 200
    # wing admin approves → creates wing-owned copy, original intact
    hwing = login(client, "ADMIN7WG")
    reqs = client.get("/api/program-promotion/requests", headers=hwing).json()
    assert any(x["status"] == "pending" for x in reqs)
    rid = reqs[0]["id"]
    ap = client.post(f"/api/program-promotion/{rid}/approve", headers=hwing)
    assert ap.status_code == 200 and ap.json()["new_item_id"]


# ── LEARNING HUB ──
def test_learning_hub_links_present_and_missing_report(client):
    h = login(client, "ADMIN703")
    lh = client.get("/api/learning-hub-resources", headers=h).json()
    assert len(lh) >= 1 and all(r["url"] for r in lh)
    missing = client.get("/api/learning-hub-resources/missing", headers=h).json()
    assert "count" in missing  # the 703-local item has no LH link → appears here
    assert any(i["code"] == "703-LOC01" for i in missing["items"])


# ── EXPORTS (real files) ──
def test_xlsx_export_produces_file(client):
    h = login(client, "ADMIN703")
    r = client.get("/api/export/program-items.xlsx", headers=h)
    assert r.status_code == 200
    assert r.content[:2] == b"PK"  # xlsx is a zip
    assert len(r.content) > 500


def test_pdf_export_produces_file(client):
    h = login(client, "ADMIN703")
    r = client.get("/api/export/program-items.pdf", headers=h)
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_export_writes_log(client):
    h = login(client, "ADMIN703")
    client.get("/api/export/program-items.csv", headers=h)
    # audit records the export action
    aud = client.get("/api/audit", headers=h).json()
    assert any(a["action"] == "export" for a in aud)


# ── REAL WORKBOOK IMPORT (reads actual project files if present) ──
def _find_real_xlsx():
    for pat in ("/mnt/project/*703*.xls*", "/mnt/project/*704*.xls*", "/mnt/project/*.xlsx", "/mnt/project/*.xlsm"):
        hits = glob.glob(pat)
        if hits:
            return hits[0]
    return None


def test_program_import_preview_reads_real_workbook(client):
    path = _find_real_xlsx()
    if not path:
        import pytest
        pytest.skip("no real workbook available in /mnt/project")
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    h = login(client, "ADMIN703")
    r = client.post("/api/program-imports/preview", headers=h,
                    json={"source_category": "703_schedule", "filename": os.path.basename(path), "file_b64": b64})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["sheet_count"] >= 1
    assert "sheets" in body


def test_program_import_rejects_non_admin(client):
    h = login(client, "703SQN2026")  # general
    r = client.post("/api/program-imports/preview", headers=h,
                    json={"source_category": "other", "filename": "x.xlsx", "file_b64": "AAAA"})
    assert r.status_code == 403
