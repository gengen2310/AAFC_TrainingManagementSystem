"""Tests for the atomic session edit + status transition endpoint (PUT /api/sessions/{sid}).

Covers the master-transformation-plan Block 2 requirement: session field edits and an
outcome/status transition must succeed or fail together, in one transaction, never
producing a partial update. Each rollback scenario below asserts both the HTTP error
and that the session's persisted state (fields AND status) is completely unchanged.
"""
import pytest
from fastapi.testclient import TestClient
from app.main import app
from tests.conftest import login

ADM703 = "ADMIN703"
GEN703 = "703SQN2026"
ADM704 = "ADMIN704"


def _get_planned_session(client, hdr):
    r = client.get("/api/parade-nights", headers=hdr)
    assert r.status_code == 200
    pns = r.json()
    t3 = next((p for p in pns if p.get("term") == "T3"), None)
    assert t3, f"T3 parade night not found in {pns}"
    pnid = t3["parade_night_id"]
    r2 = client.get(f"/api/parade-nights/{pnid}/builder", headers=hdr)
    assert r2.status_code == 200
    sessions = r2.json().get("sessions", [])
    assert sessions, "No sessions in T3 parade night builder"
    return sessions[0]["id"], pnid


def _snapshot(client, hdr, pnid, sid):
    """Read back the session's persisted state via the builder endpoint."""
    r = client.get(f"/api/parade-nights/{pnid}/builder", headers=hdr)
    assert r.status_code == 200
    return next(s for s in r.json()["sessions"] if s["id"] == sid)


# ── Atomic success path ──────────────────────────────────────────────────────

def test_atomic_edit_with_status_transition_succeeds(client):
    """Field edits and a status transition in one PUT both persist together."""
    hdr = login(client, ADM703)
    sid, pnid = _get_planned_session(client, hdr)
    before = _snapshot(client, hdr, pnid, sid)

    r = client.put(f"/api/sessions/{sid}", json={
        "parade_night_id": pnid,
        "period_number": before["period_number"],
        "phase_at_time": before.get("phase_at_time") or "B. Initial",
        "expected_attendance": 12,
        "status": "delivered",
        "version": before["version"],
    }, headers=hdr)
    assert r.status_code == 200, r.text

    after = _snapshot(client, hdr, pnid, sid)
    assert after["status"] == "delivered"
    assert after["expected_attendance"] == 12
    assert after["version"] == before["version"] + 1


# ── Rollback: missing required reason ────────────────────────────────────────

def test_rollback_on_missing_required_reason(client):
    """cancelled/not_delivered/delivered_with_issue require a reason; if absent,
    the 400 must leave both the field edit and the status completely unapplied."""
    hdr = login(client, ADM703)
    sid, pnid = _get_planned_session(client, hdr)
    before = _snapshot(client, hdr, pnid, sid)

    r = client.put(f"/api/sessions/{sid}", json={
        "parade_night_id": pnid,
        "period_number": before["period_number"],
        "expected_attendance": 99,       # a field edit that must NOT persist either
        "status": "not_delivered",       # no reason provided
        "version": before["version"],
    }, headers=hdr)
    assert r.status_code == 400, r.text
    assert "reason_required" in r.text

    after = _snapshot(client, hdr, pnid, sid)
    assert after["status"] == before["status"]
    assert after["expected_attendance"] != 99
    assert after["version"] == before["version"], "version must not increment on a rejected transition"


def test_rollback_on_missing_reason_for_cancelled(client):
    hdr = login(client, ADM703)
    sid, pnid = _get_planned_session(client, hdr)
    before = _snapshot(client, hdr, pnid, sid)

    r = client.put(f"/api/sessions/{sid}", json={
        "parade_night_id": pnid,
        "period_number": before["period_number"],
        "status": "cancelled",
        "version": before["version"],
    }, headers=hdr)
    assert r.status_code == 400, r.text
    assert "reason_required_cancelled" in r.text

    after = _snapshot(client, hdr, pnid, sid)
    assert after["status"] == before["status"]
    assert after["version"] == before["version"]


def test_rollback_on_missing_reason_for_delivered_with_issue(client):
    hdr = login(client, ADM703)
    sid, pnid = _get_planned_session(client, hdr)
    before = _snapshot(client, hdr, pnid, sid)

    r = client.put(f"/api/sessions/{sid}", json={
        "parade_night_id": pnid,
        "period_number": before["period_number"],
        "status": "delivered_with_issue",
        "version": before["version"],
    }, headers=hdr)
    assert r.status_code == 400, r.text
    assert "reason_required_delivered_with_issue" in r.text

    after = _snapshot(client, hdr, pnid, sid)
    assert after["status"] == before["status"]


# ── Rollback: invalid status transition ──────────────────────────────────────

def test_rollback_on_invalid_status_value(client):
    hdr = login(client, ADM703)
    sid, pnid = _get_planned_session(client, hdr)
    before = _snapshot(client, hdr, pnid, sid)

    r = client.put(f"/api/sessions/{sid}", json={
        "parade_night_id": pnid,
        "period_number": before["period_number"],
        "expected_attendance": 42,
        "status": "not_a_real_status",
        "version": before["version"],
    }, headers=hdr)
    assert r.status_code == 400, r.text
    assert "invalid_status" in r.text

    after = _snapshot(client, hdr, pnid, sid)
    assert after["status"] == before["status"]
    assert after["expected_attendance"] != 42
    assert after["version"] == before["version"]


# ── Rollback: invalid related record ──────────────────────────────────────────

def test_rollback_on_invalid_curriculum_item(client):
    hdr = login(client, ADM703)
    sid, pnid = _get_planned_session(client, hdr)
    before = _snapshot(client, hdr, pnid, sid)

    r = client.put(f"/api/sessions/{sid}", json={
        "parade_night_id": pnid,
        "period_number": before["period_number"],
        "curriculum_item_id": "00000000-0000-0000-0000-000000000000",
        "status": "delivered",
        "version": before["version"],
    }, headers=hdr)
    assert r.status_code == 400, r.text
    assert "invalid_curriculum_item" in r.text

    after = _snapshot(client, hdr, pnid, sid)
    assert after["status"] == before["status"], "status must not change when a related record is invalid"
    assert after["version"] == before["version"]


def test_rollback_on_invalid_facilitator(client):
    hdr = login(client, ADM703)
    sid, pnid = _get_planned_session(client, hdr)
    before = _snapshot(client, hdr, pnid, sid)

    r = client.put(f"/api/sessions/{sid}", json={
        "parade_night_id": pnid,
        "period_number": before["period_number"],
        "facilitator_id": "00000000-0000-0000-0000-000000000000",
        "version": before["version"],
    }, headers=hdr)
    assert r.status_code == 400, r.text
    assert "invalid_facilitator" in r.text

    after = _snapshot(client, hdr, pnid, sid)
    assert after["version"] == before["version"]


def test_rollback_on_invalid_training_area(client):
    hdr = login(client, ADM703)
    sid, pnid = _get_planned_session(client, hdr)
    before = _snapshot(client, hdr, pnid, sid)

    r = client.put(f"/api/sessions/{sid}", json={
        "parade_night_id": pnid,
        "period_number": before["period_number"],
        "training_area_id": "00000000-0000-0000-0000-000000000000",
        "version": before["version"],
    }, headers=hdr)
    assert r.status_code == 400, r.text
    assert "invalid_training_area" in r.text

    after = _snapshot(client, hdr, pnid, sid)
    assert after["version"] == before["version"]


# ── Rollback: permission denial ──────────────────────────────────────────────

def test_rollback_on_permission_denial(client):
    """sqn_general has no write access; the edit+status must be fully rejected."""
    hdr_gen = login(client, GEN703)
    hdr_adm = login(client, ADM703)
    sid, pnid = _get_planned_session(client, hdr_adm)
    before = _snapshot(client, hdr_adm, pnid, sid)

    r = client.put(f"/api/sessions/{sid}", json={
        "parade_night_id": pnid,
        "period_number": before["period_number"],
        "expected_attendance": 55,
        "status": "delivered",
        "version": before["version"],
    }, headers=hdr_gen)
    assert r.status_code == 403, r.text

    after = _snapshot(client, hdr_adm, pnid, sid)
    assert after["status"] == before["status"]
    assert after["expected_attendance"] != 55
    assert after["version"] == before["version"]


def test_rollback_on_cross_squadron_permission_denial(client):
    hdr_adm = login(client, ADM703)
    sid, pnid = _get_planned_session(client, hdr_adm)
    before = _snapshot(client, hdr_adm, pnid, sid)

    hdr_704 = login(client, ADM704)
    r = client.put(f"/api/sessions/{sid}", json={
        "parade_night_id": pnid,
        "period_number": before["period_number"],
        "status": "cancelled",
        "reason": "Should never apply",
        "version": before["version"],
    }, headers=hdr_704)
    assert r.status_code == 403, r.text

    after = _snapshot(client, hdr_adm, pnid, sid)
    assert after["status"] == before["status"]
    assert after["version"] == before["version"]


# ── Rollback: stale optimistic-lock version ──────────────────────────────────

def test_rollback_on_stale_version_with_status_transition(client):
    """A stale version must reject the WHOLE combined edit+status request, not
    just the field edit — confirming the version check runs before any mutation,
    including the status transition."""
    hdr = login(client, ADM703)
    sid, pnid = _get_planned_session(client, hdr)
    before = _snapshot(client, hdr, pnid, sid)

    # First write succeeds and bumps the version.
    r1 = client.put(f"/api/sessions/{sid}", json={
        "parade_night_id": pnid,
        "period_number": before["period_number"],
        "expected_attendance": 5,
        "version": before["version"],
    }, headers=hdr)
    assert r1.status_code == 200, r1.text

    # Second write reuses the now-stale version AND attempts a status transition —
    # must 409 and leave status untouched (not silently apply the status while
    # rejecting only the version-checked fields).
    r2 = client.put(f"/api/sessions/{sid}", json={
        "parade_night_id": pnid,
        "period_number": before["period_number"],
        "status": "cancelled",
        "reason": "Should never apply",
        "version": before["version"],  # stale — server is now at before["version"] + 1
    }, headers=hdr)
    assert r2.status_code == 409, r2.text
    assert r2.json()["detail"]["error"] == "version_conflict"

    after = _snapshot(client, hdr, pnid, sid)
    assert after["status"] == before["status"], "stale-version request must not apply its status transition"


# ── Audit-record atomicity (structural, not a forced-failure test) ───────────

def test_status_change_and_field_edit_share_one_audit_pass(client):
    """Both the field-edit and status-change audit entries appear after one PUT,
    confirming they were written in the same request/transaction rather than one
    silently failing while the other succeeds. (A genuine forced-commit-failure
    rollback test would require mocking the DB session's commit() — this
    codebase's testing rules disfavour mocking the database, so this test instead
    confirms the structural guarantee: audit() is called with commit=False for
    both entries and a single db.commit() follows, per training.py's edit_session
    — verified by code inspection alongside this behavioural check.)"""
    hdr = login(client, ADM703)
    sid, pnid = _get_planned_session(client, hdr)
    before = _snapshot(client, hdr, pnid, sid)

    r = client.put(f"/api/sessions/{sid}", json={
        "parade_night_id": pnid,
        "period_number": before["period_number"],
        "status": "delivered",
        "version": before["version"],
    }, headers=hdr)
    assert r.status_code == 200, r.text

    audit_r = client.get("/api/audit", headers=hdr)
    assert audit_r.status_code == 200
    entries = [e for e in audit_r.json() if e.get("object_id") == sid]
    actions = [e["action"] for e in entries]
    assert "edit" in actions
    assert "status_change" in actions
