"""Tests for POST /api/parade-nights/{pnid}/cancel-all.

Covers: auth, 403 for read-only, 404 for missing pn, 422 for empty reason,
happy path with session updates, skips already-finalised sessions, response
shape, and audit trail.
"""
import pytest
from starlette.testclient import TestClient
from tests.conftest import login
from app.main import app

ADM703 = "ADMIN703"
GEN703 = "703SQN2026"

REASON = "Training cancelled — facility unavailable"


def _create_pn(client, hdr, date, term="T1"):
    r = client.post("/api/parade-nights", json={"date": date, "term": term}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["parade_night_id"]


def _add_session(client, hdr, pnid, period):
    r = client.post("/api/sessions", json={"parade_night_id": pnid, "period_number": period}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def _cancel_all(client, hdr, pnid, reason=REASON, notes=None):
    return client.post(
        f"/api/parade-nights/{pnid}/cancel-all",
        json={"reason": reason, "notes": notes},
        headers=hdr,
    )


# ── Auth ─────────────────────────────────────────────────────────────────────

def test_cancel_all_requires_auth(client):
    hdr = login(client, ADM703)
    pnid = _create_pn(client, hdr, "2033-01-05")
    fresh = TestClient(app)
    r = fresh.post(f"/api/parade-nights/{pnid}/cancel-all", json={"reason": REASON})
    assert r.status_code == 401


def test_cancel_all_forbidden_for_read_only(client):
    hdr_adm = login(client, ADM703)
    hdr_gen = login(client, GEN703)
    pnid = _create_pn(client, hdr_adm, "2033-01-12")
    _add_session(client, hdr_adm, pnid, 1)
    r = _cancel_all(client, hdr_gen, pnid)
    assert r.status_code == 403


# ── Not found ────────────────────────────────────────────────────────────────

def test_cancel_all_404_for_missing_pn(client):
    hdr = login(client, ADM703)
    r = _cancel_all(client, hdr, "00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "not_found"


# ── Validation ───────────────────────────────────────────────────────────────

def test_cancel_all_requires_non_empty_reason(client):
    hdr = login(client, ADM703)
    pnid = _create_pn(client, hdr, "2033-01-19")
    r = _cancel_all(client, hdr, pnid, reason="   ")
    assert r.status_code == 422
    assert r.json()["detail"]["error"] == "reason_required"


# ── Empty source ─────────────────────────────────────────────────────────────

def test_cancel_all_empty_pn_returns_zero(client):
    hdr = login(client, ADM703)
    pnid = _create_pn(client, hdr, "2033-02-02")
    r = _cancel_all(client, hdr, pnid)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["sessions_updated"] == 0
    assert body["session_ids"] == []


# ── Happy path ────────────────────────────────────────────────────────────────

def test_cancel_all_cancels_planned_sessions(client):
    hdr = login(client, ADM703)
    pnid = _create_pn(client, hdr, "2033-02-09")
    sid1 = _add_session(client, hdr, pnid, 1)
    sid2 = _add_session(client, hdr, pnid, 2)

    r = _cancel_all(client, hdr, pnid)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["sessions_updated"] == 2
    assert set(body["session_ids"]) == {sid1, sid2}

    builder = client.get(f"/api/parade-nights/{pnid}/builder", headers=hdr).json()
    by_id = {s["id"]: s for s in builder["sessions"]}
    assert by_id[sid1]["status"] == "cancelled"
    assert by_id[sid2]["status"] == "cancelled"


def test_cancel_all_response_shape(client):
    hdr = login(client, ADM703)
    pnid = _create_pn(client, hdr, "2033-02-16")
    r = _cancel_all(client, hdr, pnid)
    body = r.json()
    for field in ("ok", "batch_id", "sessions_updated", "session_ids"):
        assert field in body, f"Missing field: {field}"
    assert isinstance(body["sessions_updated"], int)
    assert isinstance(body["session_ids"], list)


# ── Skips finalised sessions ──────────────────────────────────────────────────

def test_cancel_all_skips_already_cancelled(client):
    hdr = login(client, ADM703)
    pnid = _create_pn(client, hdr, "2033-03-02")
    sid_a = _add_session(client, hdr, pnid, 1)
    sid_b = _add_session(client, hdr, pnid, 2)

    # Manually cancel sid_a first
    c = client.post(f"/api/sessions/{sid_a}/status",
                    json={"status": "cancelled", "reason": "Pre-cancelled"}, headers=hdr)
    assert c.status_code == 200, c.text

    r = _cancel_all(client, hdr, pnid)
    assert r.status_code == 200
    # sid_a was already cancelled — only sid_b should appear in the update
    assert sid_a not in r.json()["session_ids"]
    assert sid_b in r.json()["session_ids"]


def test_cancel_all_skips_delivered(client):
    hdr = login(client, ADM703)
    pnid = _create_pn(client, hdr, "2033-03-09")
    sid_a = _add_session(client, hdr, pnid, 1)
    sid_b = _add_session(client, hdr, pnid, 2)

    d = client.post(f"/api/sessions/{sid_a}/status",
                    json={"status": "delivered", "reason": None}, headers=hdr)
    assert d.status_code == 200, d.text

    r = _cancel_all(client, hdr, pnid)
    assert r.status_code == 200
    assert sid_a not in r.json()["session_ids"]
    assert sid_b in r.json()["session_ids"]


# ── Idempotency (second call finds nothing) ───────────────────────────────────

def test_cancel_all_idempotent(client):
    hdr = login(client, ADM703)
    pnid = _create_pn(client, hdr, "2033-03-16")
    _add_session(client, hdr, pnid, 1)

    r1 = _cancel_all(client, hdr, pnid)
    assert r1.status_code == 200
    assert r1.json()["sessions_updated"] == 1

    r2 = _cancel_all(client, hdr, pnid)
    assert r2.status_code == 200
    assert r2.json()["sessions_updated"] == 0


# ── Status history ────────────────────────────────────────────────────────────

def test_cancel_all_creates_status_history(client):
    hdr = login(client, ADM703)
    pnid = _create_pn(client, hdr, "2033-04-06")
    sid = _add_session(client, hdr, pnid, 1)

    r = _cancel_all(client, hdr, pnid)
    assert r.status_code == 200

    hist = client.get(f"/api/sessions/{sid}/status-history", headers=hdr).json()
    assert any(h["new_status"] == "cancelled" for h in hist)


# ── Audit trail ───────────────────────────────────────────────────────────────

def test_cancel_all_is_audited(client):
    hdr = login(client, ADM703)
    pnid = _create_pn(client, hdr, "2033-04-13")
    _add_session(client, hdr, pnid, 1)

    r = _cancel_all(client, hdr, pnid)
    assert r.status_code == 200
    batch_id = r.json()["batch_id"]
    assert batch_id

    audit_r = client.get("/api/audit?object_type=parade_night_bulk", headers=hdr)
    if audit_r.status_code == 403:
        pytest.skip("sqn_admin cannot read audit log in this deployment")
    assert audit_r.status_code == 200
    matches = [a for a in audit_r.json() if a["action"] == "bulk_cancel_all"]
    assert len(matches) >= 1
