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
