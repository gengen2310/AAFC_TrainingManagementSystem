"""
Gap #16 — Background Jobs: tests for the job submission and polling API.

In the test environment (no Redis broker), the dispatcher falls back to
synchronous execution. Jobs complete immediately and are already in a terminal
state by the time the POST /api/jobs/export response arrives.
"""
import pytest
from conftest import login

SQN_ADMIN   = "ADMIN703"
SQN_GENERAL = "703SQN2026"
WING_ADMIN  = "ADMIN7WG"
NAT_ADMIN   = "ADMINNATIONAL"
SYSADMIN    = "SYSADMIN2026"
AUDITOR     = "AUDITOR2026"


# ── Submit export job ─────────────────────────────────────────────────────────

def test_submit_export_returns_job_id(client):
    h = login(client, SQN_ADMIN)
    r = client.post("/api/jobs/export", json={"export_type": "program-items", "format": "csv"},
                    headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "job_id" in body and body["job_id"]
    assert body["status"] in ("queued", "running", "succeeded", "failed")


def test_submit_export_sync_fallback_completes(client):
    """Without a Redis broker the dispatcher runs synchronously; job should reach a terminal state."""
    h = login(client, SQN_ADMIN)
    r = client.post("/api/jobs/export", json={"export_type": "program-items", "format": "xlsx"},
                    headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] in ("succeeded", "failed"), (
        f"Expected terminal state after sync fallback, got {body['status']!r}")


def test_submit_export_sqn_general_forbidden(client):
    h = login(client, SQN_GENERAL)
    r = client.post("/api/jobs/export", json={"export_type": "program-items", "format": "csv"},
                    headers=h)
    assert r.status_code == 403, r.text


def test_submit_export_unauthenticated(client):
    r = client.post("/api/jobs/export", json={"export_type": "program-items", "format": "csv"})
    assert r.status_code == 401


def test_submit_export_invalid_type(client):
    h = login(client, SQN_ADMIN)
    r = client.post("/api/jobs/export", json={"export_type": "secrets", "format": "csv"}, headers=h)
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["error"] == "unsupported_export_type"


def test_submit_export_invalid_format(client):
    h = login(client, SQN_ADMIN)
    r = client.post("/api/jobs/export", json={"export_type": "program-items", "format": "exe"},
                    headers=h)
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["error"] == "unsupported_format"


# ── Poll job status ───────────────────────────────────────────────────────────

def test_poll_own_job(client):
    h = login(client, SQN_ADMIN)
    r = client.post("/api/jobs/export", json={"export_type": "program-items", "format": "pdf"},
                    headers=h)
    assert r.status_code == 200, r.text
    job_id = r.json()["job_id"]

    r2 = client.get(f"/api/jobs/{job_id}", headers=h)
    assert r2.status_code == 200, r2.text
    body = r2.json()
    assert body["job_id"] == job_id
    assert body["status"] in ("queued", "running", "succeeded", "failed")
    assert "progress_percentage" in body
    assert "job_type" in body


def test_poll_job_not_found(client):
    h = login(client, SQN_ADMIN)
    r = client.get("/api/jobs/00000000-0000-0000-0000-000000000000", headers=h)
    assert r.status_code == 404, r.text


def test_poll_other_users_job_forbidden(client):
    """sqn_admin from one session submits; sqn_general from a different session cannot poll it."""
    h_admin = login(client, SQN_ADMIN)
    r = client.post("/api/jobs/export", json={"export_type": "program-items", "format": "csv"},
                    headers=h_admin)
    job_id = r.json()["job_id"]

    h_gen = login(client, SQN_GENERAL)
    r2 = client.get(f"/api/jobs/{job_id}", headers=h_gen)
    assert r2.status_code == 403, r2.text


def test_oversight_roles_can_poll_any_job(client):
    """wing_admin should be able to see any job regardless of requester."""
    h_admin = login(client, SQN_ADMIN)
    r = client.post("/api/jobs/export", json={"export_type": "program-items", "format": "csv"},
                    headers=h_admin)
    job_id = r.json()["job_id"]

    for code in (WING_ADMIN, NAT_ADMIN, SYSADMIN, AUDITOR):
        h = login(client, code)
        r2 = client.get(f"/api/jobs/{job_id}", headers=h)
        assert r2.status_code == 200, f"{code} got {r2.status_code}: {r2.text}"


def test_poll_job_unauthenticated(client):
    r = client.get("/api/jobs/00000000-0000-0000-0000-000000000001")
    assert r.status_code == 401


def test_wing_admin_can_submit_export(client):
    h = login(client, WING_ADMIN)
    r = client.post("/api/jobs/export", json={"export_type": "program-items", "format": "csv"},
                    headers=h)
    assert r.status_code == 200, r.text


def test_national_admin_can_submit_export(client):
    h = login(client, NAT_ADMIN)
    r = client.post("/api/jobs/export", json={"export_type": "program-items", "format": "csv"},
                    headers=h)
    assert r.status_code == 200, r.text
