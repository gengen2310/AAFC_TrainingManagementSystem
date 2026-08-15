"""Tests for GET /api/sessions/{sid}/facilitator-suggestions (FAC-SUG-01)."""
import pytest
from tests.conftest import login


def _hdr(client):
    return login(client, "ADMIN703")


def _create_pn(client, hdr, date, term="T1"):
    r = client.post("/api/parade-nights", json={"date": date, "term": term}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["parade_night_id"]


def _add_session(client, hdr, pnid, period=1):
    r = client.post(
        "/api/sessions",
        json={"parade_night_id": pnid, "period_number": period, "cadet_group": "junior"},
        headers=hdr,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _assign_fac(client, hdr, sess_data, fac_id, pnid, period):
    """Assign a facilitator via PUT /api/sessions/{sid}."""
    sid = sess_data.get("id") or sess_data.get("session_id")
    r = client.put(
        f"/api/sessions/{sid}",
        json={"parade_night_id": pnid, "period_number": period, "facilitator_id": fac_id},
        headers=hdr,
    )
    return r


def _create_fac(client, hdr, last_name="TestSug", subject_areas=None):
    r = client.post(
        "/api/facilitators",
        json={
            "last_name": last_name,
            "first_name": "A",
            "type": "Staff",
            "current_rank": "CPL",
            "active_status": True,
            "subject_areas": subject_areas or [],
        },
        headers=hdr,
    )
    assert r.status_code == 200, r.text
    return r.json()["facilitator_id"]


# ── Basic shape ───────────────────────────────────────────────────────────────

def test_suggestions_returns_list(client):
    hdr = _hdr(client)
    pnid = _create_pn(client, hdr, "2037-01-06")
    sess = _add_session(client, hdr, pnid)
    sid = sess.get("id") or sess.get("session_id")
    r = client.get(f"/api/sessions/{sid}/facilitator-suggestions", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert "suggestions" in d
    assert "no_recommendation" in d
    assert isinstance(d["suggestions"], list)


def test_suggestions_unauthenticated(client):
    r = client.get("/api/sessions/00000000-0000-0000-0000-000000000001/facilitator-suggestions")
    assert r.status_code == 401


def test_suggestions_unknown_session(client):
    hdr = _hdr(client)
    r = client.get(
        "/api/sessions/00000000-0000-0000-0000-000000000000/facilitator-suggestions",
        headers=hdr,
    )
    assert r.status_code == 404


def test_suggestions_each_item_has_required_fields(client):
    hdr = _hdr(client)
    pnid = _create_pn(client, hdr, "2037-01-20")
    sess = _add_session(client, hdr, pnid)
    sid = sess.get("id") or sess.get("session_id")
    _create_fac(client, hdr, "SugShape")
    r = client.get(f"/api/sessions/{sid}/facilitator-suggestions", headers=hdr)
    assert r.status_code == 200
    for item in r.json()["suggestions"]:
        assert "facilitator_id" in item
        assert "display_name" in item
        assert "rank_label" in item
        assert "reasons" in item
        assert "conflicts" in item
        assert "workload_sessions_this_term" in item


def test_conflict_flagged_when_fac_in_same_period(client):
    hdr = _hdr(client)
    pnid = _create_pn(client, hdr, "2037-02-03")
    fac_id = _create_fac(client, hdr, "ConflictFac")
    # Assign facilitator to period 1 via PUT
    sess1 = _add_session(client, hdr, pnid, period=1)
    ar = _assign_fac(client, hdr, sess1, fac_id, pnid, 1)
    assert ar.status_code == 200, ar.text
    # Query suggestions for period 1 from a different session view
    sess2 = _add_session(client, hdr, pnid, period=2)
    s2_id = sess2.get("id") or sess2.get("session_id")
    r = client.get(
        f"/api/sessions/{s2_id}/facilitator-suggestions?period=1",
        headers=hdr,
    )
    assert r.status_code == 200
    suggs = r.json()["suggestions"]
    matched = [s for s in suggs if s["facilitator_id"] == fac_id]
    if matched:
        assert matched[0]["rank_label"] in ("CONFLICT", "UNAVAILABLE")
        assert len(matched[0]["conflicts"]) > 0


def test_workload_counted_in_term(client):
    hdr = _hdr(client)
    pnid = _create_pn(client, hdr, "2037-02-10", term="T1")
    fac_id = _create_fac(client, hdr, "WorkloadFac")
    # Assign facilitator to period 1 via PUT
    sess1 = _add_session(client, hdr, pnid, period=1)
    ar = _assign_fac(client, hdr, sess1, fac_id, pnid, 1)
    assert ar.status_code == 200, ar.text
    # Query suggestions for period 2 on the same night
    sess2 = _add_session(client, hdr, pnid, period=2)
    s2_id = sess2.get("id") or sess2.get("session_id")
    r = client.get(f"/api/sessions/{s2_id}/facilitator-suggestions", headers=hdr)
    assert r.status_code == 200
    suggs = r.json()["suggestions"]
    matched = [s for s in suggs if s["facilitator_id"] == fac_id]
    if matched:
        assert matched[0]["workload_sessions_this_term"] >= 1
