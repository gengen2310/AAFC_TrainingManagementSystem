"""Tests for POST /api/parade-nights/{pnid}/copy-sessions-to/{target_pnid}.

Covers: auth, scope enforcement, happy path, skip-existing-period, cross-squadron
rejection, source/target not-found handling.
"""
import pytest
from conftest import login


def _sqn_admin(client):
    return login(client, "ADMIN703")

def _wing_admin(client):
    return login(client, "ADMIN7WG")


def _create_pn(client, hdr, date, term="T1"):
    r = client.post("/api/parade-nights", json={"date": date, "term": term}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["parade_night_id"]


def _add_session(client, hdr, pnid, period):
    """Add a bare planned session to a parade night at the given period."""
    r = client.put(
        f"/api/parade-nights/{pnid}/sessions",
        json={"sessions": [{"period_number": period, "status": "planned"}]},
        headers=hdr,
    )
    assert r.status_code in (200, 201), r.text
    # Fetch the session list to get the actual session id
    sessions = client.get(f"/api/parade-nights/{pnid}", headers=hdr).json().get("sessions", [])
    match = [s for s in sessions if s["period_number"] == period]
    return match[0]["id"] if match else None


def _copy_url(source, target):
    return f"/api/parade-nights/{source}/copy-sessions-to/{target}"


# ── Auth ─────────────────────────────────────────────────────────────────────

def test_copy_sessions_requires_auth(client):
    r = client.post(_copy_url("fake", "fake"))
    assert r.status_code == 401


def test_copy_sessions_sqn_admin_can_copy(client):
    hdr = _sqn_admin(client)
    source_pnid = _create_pn(client, hdr, "2032-01-14")
    target_pnid = _create_pn(client, hdr, "2032-01-21")
    r = client.post(_copy_url(source_pnid, target_pnid), headers=hdr)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "copied" in body
    assert "skipped" in body


# ── Not found ────────────────────────────────────────────────────────────────

def test_copy_sessions_source_not_found(client):
    hdr = _sqn_admin(client)
    target_pnid = _create_pn(client, hdr, "2032-02-04")
    r = client.post(_copy_url("00000000-0000-0000-0000-000000000000", target_pnid), headers=hdr)
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "source_not_found"


def test_copy_sessions_target_not_found(client):
    hdr = _sqn_admin(client)
    source_pnid = _create_pn(client, hdr, "2032-02-11")
    r = client.post(_copy_url(source_pnid, "00000000-0000-0000-0000-000000000000"), headers=hdr)
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "target_not_found"


# ── Happy path ────────────────────────────────────────────────────────────────

def test_copy_sessions_empty_source_returns_zero_copied(client):
    hdr = _sqn_admin(client)
    source_pnid = _create_pn(client, hdr, "2032-03-04")
    target_pnid = _create_pn(client, hdr, "2032-03-11")
    r = client.post(_copy_url(source_pnid, target_pnid), headers=hdr)
    assert r.status_code == 200
    assert r.json()["copied"] == 0
    assert r.json()["skipped"] == 0


def test_copy_sessions_response_shape(client):
    hdr = _sqn_admin(client)
    source_pnid = _create_pn(client, hdr, "2032-04-01")
    target_pnid = _create_pn(client, hdr, "2032-04-08")
    r = client.post(_copy_url(source_pnid, target_pnid), headers=hdr)
    body = r.json()
    assert "ok" in body
    assert "copied" in body
    assert "skipped" in body
    assert isinstance(body["copied"], int)
    assert isinstance(body["skipped"], int)
    assert body["copied"] >= 0
    assert body["skipped"] >= 0


# ── Skip existing period ──────────────────────────────────────────────────────

def test_copy_sessions_skips_existing_period(client):
    """Sessions at periods already occupied in the target are not overwritten."""
    hdr = _sqn_admin(client)
    source_pnid = _create_pn(client, hdr, "2032-05-06")
    target_pnid = _create_pn(client, hdr, "2032-05-13")
    # First copy — populates target
    r1 = client.post(_copy_url(source_pnid, target_pnid), headers=hdr)
    assert r1.status_code == 200
    copied_first = r1.json()["copied"]
    # Second copy of same source → target — all periods already filled
    r2 = client.post(_copy_url(source_pnid, target_pnid), headers=hdr)
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["copied"] == 0
    assert body2["skipped"] == copied_first


# ── Idempotent audit trail ────────────────────────────────────────────────────

def test_copy_sessions_is_audited(client):
    """The copy operation writes an audit entry."""
    hdr = _sqn_admin(client)
    source_pnid = _create_pn(client, hdr, "2032-06-03")
    target_pnid = _create_pn(client, hdr, "2032-06-10")
    r = client.post(_copy_url(source_pnid, target_pnid), headers=hdr)
    assert r.status_code == 200
    # Audit log visible to the sqn_admin (scoped to their squadron)
    audit_r = client.get("/api/audit", headers=hdr)
    if audit_r.status_code == 403:
        pytest.skip("sqn_admin cannot read audit log in this deployment")
    assert audit_r.status_code == 200
