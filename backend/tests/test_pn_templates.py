"""Tests for Parade Night Template endpoints (WORK-17).

Covers:
  POST /api/parade-nights/{pnid}/save-as-template
  GET  /api/parade-night-templates
  GET  /api/parade-night-templates/{tid}
  POST /api/parade-night-templates/{tid}/apply/{pnid}
  DELETE /api/parade-night-templates/{tid}
"""
import pytest
from tests.conftest import login


def _sqn_admin_hdr(client):
    return login(client, "ADMIN703")


def _general_hdr(client):
    return login(client, "703SQN2026")


def _create_pn(client, hdr, date, term="T1"):
    r = client.post("/api/parade-nights", json={"date": date, "term": term}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["parade_night_id"]


def _add_session(client, hdr, pnid, period):
    r = client.post(
        "/api/sessions",
        json={"parade_night_id": pnid, "period_number": period, "cadet_group": "junior"},
        headers=hdr,
    )
    assert r.status_code == 200, r.text
    return r.json()


def _save_url(pnid):
    return f"/api/parade-nights/{pnid}/save-as-template"


def _apply_url(tid, pnid):
    return f"/api/parade-night-templates/{tid}/apply/{pnid}"


# ── Save as template ──────────────────────────────────────────────────────────

def test_save_parade_night_as_template_happy_path(client):
    hdr = _sqn_admin_hdr(client)
    pnid = _create_pn(client, hdr, "2035-01-08")
    _add_session(client, hdr, pnid, 1)
    _add_session(client, hdr, pnid, 2)

    r = client.post(_save_url(pnid), json={"name": "Standard Wed", "description": "Two-period standard night"}, headers=hdr)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["name"] == "Standard Wed"
    assert data["session_count"] == 2
    assert len(data["sessions"]) == 2
    assert data["sessions"][0]["period_number"] == 1
    return data["id"]


def test_save_template_no_sessions_returns_400(client):
    hdr = _sqn_admin_hdr(client)
    pnid = _create_pn(client, hdr, "2035-01-15")
    r = client.post(_save_url(pnid), json={"name": "Empty"}, headers=hdr)
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "no_sessions"


def test_save_template_unknown_pn_returns_404(client):
    hdr = _sqn_admin_hdr(client)
    r = client.post(_save_url("00000000-0000-0000-0000-000000000000"), json={"name": "Ghost"}, headers=hdr)
    assert r.status_code == 404


def test_save_template_unauthorized(client):
    hdr = _sqn_admin_hdr(client)
    pnid = _create_pn(client, hdr, "2035-01-22")
    _add_session(client, hdr, pnid, 1)

    gen_hdr = _general_hdr(client)
    r = client.post(_save_url(pnid), json={"name": "No write"}, headers=gen_hdr)
    assert r.status_code == 403


def test_save_template_unauthenticated(client):
    r = client.post("/api/parade-nights/fake/save-as-template", json={"name": "x"})
    assert r.status_code == 401


# ── List templates ────────────────────────────────────────────────────────────

def test_list_templates_returns_created_template(client):
    hdr = _sqn_admin_hdr(client)
    pnid = _create_pn(client, hdr, "2035-02-05")
    _add_session(client, hdr, pnid, 1)
    client.post(_save_url(pnid), json={"name": "List Test Tpl"}, headers=hdr)

    r = client.get("/api/parade-night-templates", headers=hdr)
    assert r.status_code == 200
    names = [t["name"] for t in r.json()]
    assert "List Test Tpl" in names


def test_list_templates_unauthenticated(client):
    r = client.get("/api/parade-night-templates")
    assert r.status_code == 401


# ── Get single template ───────────────────────────────────────────────────────

def test_get_template_includes_sessions(client):
    hdr = _sqn_admin_hdr(client)
    pnid = _create_pn(client, hdr, "2035-02-12")
    _add_session(client, hdr, pnid, 1)
    _add_session(client, hdr, pnid, 2)
    create_r = client.post(_save_url(pnid), json={"name": "Get Test Tpl"}, headers=hdr)
    tid = create_r.json()["id"]

    r = client.get(f"/api/parade-night-templates/{tid}", headers=hdr)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == tid
    assert len(data["sessions"]) == 2


def test_get_template_not_found(client):
    hdr = _sqn_admin_hdr(client)
    r = client.get("/api/parade-night-templates/00000000-0000-0000-0000-000000000000", headers=hdr)
    assert r.status_code == 404


# ── Apply template ────────────────────────────────────────────────────────────

def test_apply_template_creates_sessions(client):
    hdr = _sqn_admin_hdr(client)
    src_pnid = _create_pn(client, hdr, "2035-03-05")
    _add_session(client, hdr, src_pnid, 1)
    _add_session(client, hdr, src_pnid, 2)
    create_r = client.post(_save_url(src_pnid), json={"name": "Apply Test Tpl"}, headers=hdr)
    tid = create_r.json()["id"]

    target_pnid = _create_pn(client, hdr, "2035-03-12")
    r = client.post(_apply_url(tid, target_pnid), headers=hdr)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert data["applied"] == 2
    assert data["skipped"] == 0

    # Verify sessions were actually created
    pn_r = client.get(f"/api/parade-nights/{target_pnid}", headers=hdr)
    assert pn_r.status_code == 200
    sessions = pn_r.json().get("sessions", [])
    assert len(sessions) == 2


def test_apply_template_skips_occupied_periods(client):
    hdr = _sqn_admin_hdr(client)
    src_pnid = _create_pn(client, hdr, "2035-03-19")
    _add_session(client, hdr, src_pnid, 1)
    _add_session(client, hdr, src_pnid, 2)
    create_r = client.post(_save_url(src_pnid), json={"name": "Skip Test Tpl"}, headers=hdr)
    tid = create_r.json()["id"]

    target_pnid = _create_pn(client, hdr, "2035-03-26")
    _add_session(client, hdr, target_pnid, 1)  # period 1 already occupied

    r = client.post(_apply_url(tid, target_pnid), headers=hdr)
    assert r.status_code == 200
    data = r.json()
    assert data["applied"] == 1
    assert data["skipped"] == 1


def test_apply_template_unknown_template_returns_404(client):
    hdr = _sqn_admin_hdr(client)
    pnid = _create_pn(client, hdr, "2035-04-02")
    r = client.post(_apply_url("00000000-0000-0000-0000-000000000000", pnid), headers=hdr)
    assert r.status_code == 404


def test_apply_template_unknown_pn_returns_404(client):
    hdr = _sqn_admin_hdr(client)
    src_pnid = _create_pn(client, hdr, "2035-04-09")
    _add_session(client, hdr, src_pnid, 1)
    create_r = client.post(_save_url(src_pnid), json={"name": "404 Tpl"}, headers=hdr)
    tid = create_r.json()["id"]
    r = client.post(_apply_url(tid, "00000000-0000-0000-0000-000000000000"), headers=hdr)
    assert r.status_code == 404


def test_apply_template_unauthorized(client):
    hdr = _sqn_admin_hdr(client)
    src_pnid = _create_pn(client, hdr, "2035-04-16")
    _add_session(client, hdr, src_pnid, 1)
    create_r = client.post(_save_url(src_pnid), json={"name": "Auth Tpl"}, headers=hdr)
    tid = create_r.json()["id"]
    target_pnid = _create_pn(client, hdr, "2035-04-23")

    gen_hdr = _general_hdr(client)
    r = client.post(_apply_url(tid, target_pnid), headers=gen_hdr)
    assert r.status_code == 403


# ── Archive (delete) template ─────────────────────────────────────────────────

def test_archive_template(client):
    hdr = _sqn_admin_hdr(client)
    src_pnid = _create_pn(client, hdr, "2035-05-07")
    _add_session(client, hdr, src_pnid, 1)
    create_r = client.post(_save_url(src_pnid), json={"name": "Archive Tpl"}, headers=hdr)
    tid = create_r.json()["id"]

    r = client.delete(f"/api/parade-night-templates/{tid}", headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True

    # Should not appear in list
    list_r = client.get("/api/parade-night-templates", headers=hdr)
    ids = [t["id"] for t in list_r.json()]
    assert tid not in ids


def test_archive_template_already_archived(client):
    hdr = _sqn_admin_hdr(client)
    src_pnid = _create_pn(client, hdr, "2035-05-14")
    _add_session(client, hdr, src_pnid, 1)
    create_r = client.post(_save_url(src_pnid), json={"name": "Dbl Archive Tpl"}, headers=hdr)
    tid = create_r.json()["id"]
    client.delete(f"/api/parade-night-templates/{tid}", headers=hdr)
    r = client.delete(f"/api/parade-night-templates/{tid}", headers=hdr)
    assert r.status_code == 409


def test_archive_template_not_found(client):
    hdr = _sqn_admin_hdr(client)
    r = client.delete("/api/parade-night-templates/00000000-0000-0000-0000-000000000000", headers=hdr)
    assert r.status_code == 404


def test_archive_template_unauthorized(client):
    hdr = _sqn_admin_hdr(client)
    src_pnid = _create_pn(client, hdr, "2035-05-21")
    _add_session(client, hdr, src_pnid, 1)
    create_r = client.post(_save_url(src_pnid), json={"name": "Auth Archive Tpl"}, headers=hdr)
    tid = create_r.json()["id"]
    gen_hdr = _general_hdr(client)
    r = client.delete(f"/api/parade-night-templates/{tid}", headers=gen_hdr)
    assert r.status_code == 403


# ── Bulk Apply Template (BULK-01) ──────────────────────────────────────────────

_BULK_URL = "/api/parade-nights/bulk-apply-template"


def _make_tpl(client, hdr, date, name, periods=(1, 2)):
    src = _create_pn(client, hdr, date)
    for p in periods:
        _add_session(client, hdr, src, p)
    r = client.post(_save_url(src), json={"name": name}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_bulk_apply_dry_run_returns_counts(client):
    hdr = _sqn_admin_hdr(client)
    tid = _make_tpl(client, hdr, "2036-01-07", "Bulk Dry Run Tpl", periods=(1, 2))
    pn1 = _create_pn(client, hdr, "2036-01-14")
    pn2 = _create_pn(client, hdr, "2036-01-21")
    r = client.post(_BULK_URL, json={
        "template_id": tid,
        "parade_night_ids": [pn1, pn2],
        "conflict_resolution": "skip_night",
        "dry_run": True,
    }, headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert d["dry_run"] is True
    assert d["nights_processed"] == 2
    assert d["sessions_added"] == 4  # 2 sessions × 2 nights
    assert d["nights_skipped"] == 0
    # Verify dry_run wrote nothing
    pn_r = client.get(f"/api/parade-nights/{pn1}", headers=hdr)
    assert len(pn_r.json().get("sessions", [])) == 0


def test_bulk_apply_skip_night_leaves_occupied_nights(client):
    hdr = _sqn_admin_hdr(client)
    tid = _make_tpl(client, hdr, "2036-02-04", "Skip Tpl", periods=(1,))
    pn_empty = _create_pn(client, hdr, "2036-02-11")
    pn_occupied = _create_pn(client, hdr, "2036-02-18")
    _add_session(client, hdr, pn_occupied, 1)  # pre-populate period 1
    r = client.post(_BULK_URL, json={
        "template_id": tid,
        "parade_night_ids": [pn_empty, pn_occupied],
        "conflict_resolution": "skip_night",
        "dry_run": False,
    }, headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert d["nights_processed"] == 1  # pn_empty processed
    assert d["nights_skipped"] == 1    # pn_occupied skipped
    assert d["conflict_nights"] == 1


def test_bulk_apply_alongside_adds_to_occupied(client):
    hdr = _sqn_admin_hdr(client)
    tid = _make_tpl(client, hdr, "2036-03-04", "Alongside Tpl", periods=(1,))
    pn = _create_pn(client, hdr, "2036-03-11")
    _add_session(client, hdr, pn, 1)  # period 1 already occupied
    r = client.post(_BULK_URL, json={
        "template_id": tid,
        "parade_night_ids": [pn],
        "conflict_resolution": "alongside",
        "dry_run": False,
    }, headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert d["sessions_added"] == 1  # template period 1 added alongside existing


def test_bulk_apply_replace_draft_removes_planned_sessions(client):
    hdr = _sqn_admin_hdr(client)
    tid = _make_tpl(client, hdr, "2036-04-01", "Replace Draft Tpl", periods=(1, 2))
    pn = _create_pn(client, hdr, "2036-04-08")
    _add_session(client, hdr, pn, 1)  # planned session in period 1
    r = client.post(_BULK_URL, json={
        "template_id": tid,
        "parade_night_ids": [pn],
        "conflict_resolution": "replace_draft",
        "dry_run": False,
    }, headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert d["nights_processed"] == 1
    assert d["sessions_added"] == 2  # both template periods applied


def test_bulk_apply_does_not_copy_delivered_outcomes(client):
    hdr = _sqn_admin_hdr(client)
    src = _create_pn(client, hdr, "2036-05-06")
    sess = _add_session(client, hdr, src, 1)
    # Mark as delivered so template captures a session (but with planned status in template)
    tpl_r = client.post(_save_url(src), json={"name": "Delivered Tpl"}, headers=hdr)
    tid = tpl_r.json()["id"]
    dest = _create_pn(client, hdr, "2036-05-13")
    r = client.post(_BULK_URL, json={
        "template_id": tid,
        "parade_night_ids": [dest],
        "conflict_resolution": "skip_night",
        "dry_run": False,
    }, headers=hdr)
    assert r.status_code == 200
    # Applied session must have status=planned (never delivered/historical)
    pn_r = client.get(f"/api/parade-nights/{dest}", headers=hdr)
    sessions = pn_r.json().get("sessions", [])
    assert all(s.get("status") == "planned" for s in sessions)


def test_bulk_apply_unknown_template_returns_404(client):
    hdr = _sqn_admin_hdr(client)
    pn = _create_pn(client, hdr, "2036-06-03")
    r = client.post(_BULK_URL, json={
        "template_id": "00000000-0000-0000-0000-000000000000",
        "parade_night_ids": [pn],
        "conflict_resolution": "skip_night",
        "dry_run": True,
    }, headers=hdr)
    assert r.status_code == 404


def test_bulk_apply_unauthenticated(client):
    r = client.post(_BULK_URL, json={
        "template_id": "x", "parade_night_ids": [], "dry_run": True,
    })
    assert r.status_code == 401
