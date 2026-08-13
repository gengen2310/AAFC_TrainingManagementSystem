"""Regression tests for input length and enum validation fixes.

Ensures that: (1) overlong strings return 422 rather than a DB 500;
(2) invalid enum values for parade_type and session status are rejected;
(3) update_notice now writes an audit log entry.
"""
import pytest
from conftest import login


def _sqn(client):
    return login(client, "ADMIN703")


def _setup_planning_session(client, h):
    """Create a planning year, parade date, and session; return the session_id."""
    years = client.get("/api/planning/years", headers=h).json()
    if not years:
        pytest.skip("No planning year in test DB")
    year_id = years[0]["planning_year_id"]
    pd_r = client.post(f"/api/planning/years/{year_id}/parade-dates", json={
        "parade_date": "2091-03-10",
    }, headers=h)
    assert pd_r.status_code in (200, 409), pd_r.text
    pds = client.get(f"/api/planning/years/{year_id}/parade-dates", headers=h).json()
    if not pds:
        pytest.skip("No parade dates available")
    date_id = pds[0]["parade_date_id"]
    sess_r = client.post(f"/api/planning/parade-dates/{date_id}/sessions", json={
        "cadet_group": "senior", "session_number": 9,
    }, headers=h)
    assert sess_r.status_code == 200, sess_r.text
    return sess_r.json()["session_id"], date_id, year_id


# ── Facilitator field length ────────────────────────────────────────────────

def test_facilitator_last_name_too_long_rejected(client):
    h = _sqn(client)
    r = client.post("/api/facilitators", json={
        "last_name": "X" * 81, "first_name": "Test"
    }, headers=h)
    assert r.status_code == 422, r.text


def test_facilitator_first_name_too_long_rejected(client):
    h = _sqn(client)
    r = client.post("/api/facilitators", json={
        "last_name": "ValidName", "first_name": "X" * 81
    }, headers=h)
    assert r.status_code == 422, r.text


def test_facilitator_type_too_long_rejected(client):
    h = _sqn(client)
    r = client.post("/api/facilitators", json={
        "last_name": "ValidName", "type": "X" * 31
    }, headers=h)
    assert r.status_code == 422, r.text


def test_facilitator_valid_fields_accepted(client):
    h = _sqn(client)
    r = client.post("/api/facilitators", json={
        "last_name": "ValidSurname", "first_name": "ValidFirst", "type": "Staff"
    }, headers=h)
    assert r.status_code == 200, r.text


# ── Parade night term length ───────────────────────────────────────────────

def test_parade_night_term_too_long_rejected(client):
    h = _sqn(client)
    me = client.get("/api/auth/me", headers=h).json()
    r = client.post("/api/parade-nights", json={
        "date": "2087-01-01",
        "term": "T" + "1" * 10,  # 11 chars — exceeds String(10)
        "parade_type": "normal",
    }, headers=h)
    assert r.status_code == 422, r.text


def test_parade_night_term_at_limit_accepted(client):
    h = _sqn(client)
    r = client.post("/api/parade-nights", json={
        "date": "2087-01-02",
        "term": "T" + "1" * 9,  # exactly 10 chars — must pass
        "parade_type": "normal",
    }, headers=h)
    assert r.status_code == 200, r.text


# ── Parade type enum ──────────────────────────────────────────────────────

def test_parade_night_invalid_parade_type_rejected(client):
    h = _sqn(client)
    r = client.post("/api/parade-nights", json={
        "date": "2087-01-03",
        "parade_type": "invalid_type",
    }, headers=h)
    assert r.status_code == 422, r.text


def test_parade_night_valid_parade_types_accepted(client):
    h = _sqn(client)
    for pt, day in [("activity", "04"), ("admin", "05"), ("stand_down", "06")]:
        r = client.post("/api/parade-nights", json={
            "date": f"2087-01-{day}", "parade_type": pt,
        }, headers=h)
        assert r.status_code == 200, f"{pt}: {r.text}"


# ── Curriculum recommended_term length ────────────────────────────────────

def test_curriculum_recommended_term_too_long_rejected(client):
    h = _sqn(client)
    me = client.get("/api/auth/me", headers=h).json()
    sqn_id = me["session"]["squadron_id"]
    r = client.post("/api/curriculum", json={
        "code": "VAL-TEST-01", "title": "Validation test",
        "squadron_id": sqn_id, "recommended_term": "T1-extended",  # 11 chars
    }, headers=h)
    assert r.status_code == 422, r.text


# ── Curriculum code/title length ─────────────────────────────────────────

def test_curriculum_code_too_long_rejected(client):
    h = _sqn(client)
    me = client.get("/api/auth/me", headers=h).json()
    sqn_id = me["session"]["squadron_id"]
    r = client.post("/api/curriculum", json={
        "code": "C" * 41, "title": "Valid title", "squadron_id": sqn_id,
    }, headers=h)
    assert r.status_code == 422, r.text


def test_curriculum_title_too_long_rejected(client):
    h = _sqn(client)
    me = client.get("/api/auth/me", headers=h).json()
    sqn_id = me["session"]["squadron_id"]
    r = client.post("/api/curriculum", json={
        "code": "VAL-01", "title": "T" * 201, "squadron_id": sqn_id,
    }, headers=h)
    assert r.status_code == 422, r.text


def test_curriculum_javascript_url_rejected(client):
    h = _sqn(client)
    me = client.get("/api/auth/me", headers=h).json()
    sqn_id = me["session"]["squadron_id"]
    r = client.post("/api/curriculum", json={
        "code": "VAL-02", "title": "XSS test", "squadron_id": sqn_id,
        "learning_hub_url": "javascript:alert(1)",
    }, headers=h)
    assert r.status_code == 422, r.text


def test_curriculum_https_url_accepted(client):
    h = _sqn(client)
    me = client.get("/api/auth/me", headers=h).json()
    sqn_id = me["session"]["squadron_id"]
    r = client.post("/api/curriculum", json={
        "code": "VAL-HTTPS", "title": "HTTPS test", "squadron_id": sqn_id,
        "learning_hub_url": "https://example.com/resource",
    }, headers=h)
    assert r.status_code == 200, r.text


# ── Notice priority/audience length ───────────────────────────────────────

def test_notice_priority_too_long_rejected(client):
    h = _sqn(client)
    years = client.get("/api/planning/years", headers=h).json()
    if not years:
        pytest.skip("No planning year in test DB")
    year_id = years[0]["planning_year_id"]
    pds = client.get(f"/api/planning/years/{year_id}/parade-dates", headers=h).json()
    if not pds:
        pytest.skip("No parade dates")
    date_id = pds[0]["parade_date_id"]
    r = client.post(f"/api/planning/parade-dates/{date_id}/notices", json={
        "notice_text": "Test notice", "priority": "P" * 21,
    }, headers=h)
    assert r.status_code == 422, r.text


def test_notice_audience_too_long_rejected(client):
    h = _sqn(client)
    years = client.get("/api/planning/years", headers=h).json()
    if not years:
        pytest.skip("No planning year in test DB")
    year_id = years[0]["planning_year_id"]
    pds = client.get(f"/api/planning/years/{year_id}/parade-dates", headers=h).json()
    if not pds:
        pytest.skip("No parade dates")
    date_id = pds[0]["parade_date_id"]
    r = client.post(f"/api/planning/parade-dates/{date_id}/notices", json={
        "notice_text": "Test notice", "priority": "normal", "audience": "A" * 61,
    }, headers=h)
    assert r.status_code == 422, r.text


# ── TrainingClass display_name length ─────────────────────────────────────

def test_training_class_display_name_too_long_rejected(client):
    h = _sqn(client)
    me = client.get("/api/auth/me", headers=h).json()
    sqn_id = me["session"]["squadron_id"]
    years_r = client.get("/api/training/years", headers=h)
    if years_r.status_code != 200 or not years_r.json():
        pytest.skip("No training years available")
    year_id = years_r.json()[0]["training_year_id"]
    stages_r = client.get("/api/training/stages", headers=h)
    if stages_r.status_code != 200 or not stages_r.json():
        pytest.skip("No training stages available")
    stage_id = stages_r.json()[0]["training_stage_id"]
    r = client.post("/api/training/classes", json={
        "training_year_id": year_id,
        "training_stage_id": stage_id,
        "display_name": "N" * 81,
    }, headers=h)
    assert r.status_code == 422, r.text


# ── Planning session status enum ──────────────────────────────────────────

def test_planning_session_invalid_status_rejected(client):
    """PATCH /api/planning/sessions/{id} must reject unrecognised status values."""
    h = _sqn(client)
    sess_id, _, _ = _setup_planning_session(client, h)
    r = client.patch(f"/api/planning/sessions/{sess_id}", json={
        "status": "invalid_made_up_status",
    }, headers=h)
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["error"] == "invalid_status"


def test_planning_session_valid_status_accepted(client):
    """PATCH /api/planning/sessions/{id} must accept known status values."""
    h = _sqn(client)
    sess_id, _, _ = _setup_planning_session(client, h)
    r = client.patch(f"/api/planning/sessions/{sess_id}", json={
        "status": "delivered",
    }, headers=h)
    assert r.status_code == 200, r.text


# ── update_notice audit ───────────────────────────────────────────────────

def test_update_notice_is_audited(client):
    """PATCH /api/planning/notices/{id} must write an audit log entry."""
    from app.database import SessionLocal
    from app.models import AuditLog
    h = _sqn(client)
    years = client.get("/api/planning/years", headers=h).json()
    if not years:
        pytest.skip("No planning year in test DB")
    year_id = years[0]["planning_year_id"]
    pds = client.get(f"/api/planning/years/{year_id}/parade-dates", headers=h).json()
    if not pds:
        pytest.skip("No parade dates")
    date_id = pds[0]["parade_date_id"]
    n_r = client.post(f"/api/planning/parade-dates/{date_id}/notices", json={
        "notice_text": "Original notice", "priority": "info", "audience": "all",
    }, headers=h)
    assert n_r.status_code == 200, n_r.text
    notice_id = n_r.json()["notice_id"]
    upd = client.patch(f"/api/planning/notices/{notice_id}", json={
        "notice_text": "Updated notice",
    }, headers=h)
    assert upd.status_code == 200, upd.text
    db = SessionLocal()
    try:
        entry = db.query(AuditLog).filter(
            AuditLog.object_type == "PlanningNotice",
            AuditLog.object_id == notice_id,
            AuditLog.action == "update",
        ).first()
        assert entry is not None, "audit entry missing after notice update"
    finally:
        db.close()
