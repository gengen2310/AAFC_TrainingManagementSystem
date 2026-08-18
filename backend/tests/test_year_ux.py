"""Tests for Year UX feature — Task 1: CSV export endpoint.

GET /api/planning/years/{year_id}/export → text/csv
"""
import pytest
from tests.conftest import login


# ── helpers ────────────────────────────────────────────────────────────────────

def _sqn_admin_hdr(client):
    return login(client, "ADMIN703")


def _wing_admin_hdr(client):
    return login(client, "ADMIN7WG")


# ── tests ──────────────────────────────────────────────────────────────────────

def test_export_year_csv_returns_200(client):
    headers = _sqn_admin_hdr(client)
    r = client.get("/api/planning/years", headers=headers)
    assert r.status_code == 200
    years = r.json()
    if not years:
        pytest.skip("No planning years available")
    year_id = years[0]["planning_year_id"]

    r = client.get(f"/api/planning/years/{year_id}/export", headers=headers)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "attachment" in r.headers.get("content-disposition", "")
    body = r.text
    assert "TRAINING PROGRAM" in body
    assert "ACTIVITIES" in body
    assert "PARADE SCHEDULE" in body
    assert "SESSIONS" in body


def test_export_year_csv_unauthenticated(client):
    r = client.get("/api/planning/years/nonexistent-id/export")
    assert r.status_code == 401


def test_export_year_csv_wrong_scope(client):
    # Wing admin for a different wing cannot export a year they don't own.
    # Using a fabricated UUID verifies 403 or 404 path.
    headers = _wing_admin_hdr(client)
    r = client.get(
        "/api/planning/years/00000000-0000-0000-0000-000000000000/export",
        headers=headers,
    )
    assert r.status_code in (403, 404)


# ── Task 2: keep_existing override flag ────────────────────────────────────────

def test_cea_import_keep_existing_skips_update(client):
    """An activity whose cea_activity_id is in keep_existing is not overwritten."""
    headers = _wing_admin_hdr(client)
    # Get a year in wing scope
    r = client.get("/api/planning/years", headers=headers)
    assert r.status_code == 200
    years = [y for y in r.json() if y.get("active_status")]
    if not years:
        pytest.skip("No active wing year available")
    year_id = years[0]["planning_year_id"]

    # First import: create a CEA activity
    csv1 = b"ActivityID,ActivityName,ActivityType,ActivityStartDate\nCEA-KEEP-001,Original Name,Mandatory,2026-10-01\n"
    r = client.post(
        f"/api/planning/years/{year_id}/cea/import",
        headers=headers,
        files={"file": ("import1.csv", csv1, "text/csv")},
        data={"keep_existing": ""},
    )
    assert r.status_code == 200

    # Second import: updated name, but keep_existing includes the cea_activity_id
    csv2 = b"ActivityID,ActivityName,ActivityType,ActivityStartDate\nCEA-KEEP-001,Updated Name,Mandatory,2026-10-01\n"
    r = client.post(
        f"/api/planning/years/{year_id}/cea/import",
        headers=headers,
        files={"file": ("import2.csv", csv2, "text/csv")},
        data={"keep_existing": "CEA-KEEP-001"},
    )
    assert r.status_code == 200
    result = r.json()
    # The activity should be reported as skipped, not updated
    assert result.get("skipped", 0) >= 1 or result.get("kept", 0) >= 1


def test_cea_import_without_keep_existing_still_works(client):
    """Existing behaviour: import without keep_existing field works unchanged."""
    headers = _wing_admin_hdr(client)
    r = client.get("/api/planning/years", headers=headers)
    assert r.status_code == 200
    years = [y for y in r.json() if y.get("active_status")]
    if not years:
        pytest.skip("No active wing year available")
    year_id = years[0]["planning_year_id"]
    csv_data = b"ActivityID,ActivityName,ActivityType,ActivityStartDate\nCEA-BACK-001,Back Compat Test,Mandatory,2026-11-01\n"
    r = client.post(
        f"/api/planning/years/{year_id}/cea/import",
        headers=headers,
        files={"file": ("compat.csv", csv_data, "text/csv")},
    )
    assert r.status_code == 200
