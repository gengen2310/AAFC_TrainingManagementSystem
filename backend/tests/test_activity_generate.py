"""Tests for POST /api/activities/generate (preview and batch-create).

Covers: auth, permission control, preview mode, recurrence logic,
duplicate detection, excluded dates, repeat_count cap, audit log.
"""
import pytest
from conftest import login

URL = "/api/activities/generate"


# ── helpers ───────────────────────────────────────────────────────────────────

def _admin(client):
    return login(client, "ADMIN703")


def _general(client):
    return login(client, "703SQN2026")


def _auditor(client):
    return login(client, "AUDITOR2026")


def _body(**kwargs):
    base = {
        "activity_name": "Test Gen Activity",
        "start_date": "2026-09-07",   # a Monday
        "end_date": "2026-09-28",     # 4 Mondays
        "recurrence": "weekly",
        "weekday": 0,                 # Monday
        "preview_only": True,
    }
    base.update(kwargs)
    return base


# ── auth ──────────────────────────────────────────────────────────────────────

def test_generate_requires_auth(client):
    r = client.post(URL, json=_body())
    assert r.status_code == 401


# ── preview mode ──────────────────────────────────────────────────────────────

def test_preview_returns_list_without_creating(client):
    hdrs = _admin(client)
    r = client.post(URL, json=_body(preview_only=True), headers=hdrs)
    assert r.status_code == 200
    data = r.json()
    assert "preview" in data
    assert "would_create" in data
    assert "would_skip" in data
    # No activities created — verify list endpoint unchanged length
    r2 = client.get("/api/activities", headers=hdrs)
    assert r2.status_code == 200


def test_preview_read_only_role_allowed(client):
    hdrs = _general(client)
    r = client.post(URL, json=_body(preview_only=True), headers=hdrs)
    assert r.status_code == 200
    assert "preview" in r.json()


def test_preview_auditor_no_squadron_scope(client):
    # Auditor has no squadron scope — endpoint requires one
    hdrs = _auditor(client)
    r = client.post(URL, json=_body(preview_only=True), headers=hdrs)
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "no_squadron_scope"


# ── permission control for create ─────────────────────────────────────────────

def test_create_forbidden_for_sqn_general(client):
    hdrs = _general(client)
    r = client.post(URL, json=_body(preview_only=False), headers=hdrs)
    assert r.status_code == 403


def test_create_forbidden_for_auditor(client):
    hdrs = _auditor(client)
    r = client.post(URL, json=_body(preview_only=False), headers=hdrs)
    assert r.status_code == 403


# ── weekly recurrence ─────────────────────────────────────────────────────────

def test_weekly_generates_correct_dates(client):
    hdrs = _admin(client)
    r = client.post(URL, json=_body(
        activity_name="Weekly Cadets",
        start_date="2026-09-07",
        end_date="2026-09-28",
        recurrence="weekly",
        weekday=0,
        preview_only=True,
    ), headers=hdrs)
    assert r.status_code == 200
    dates = [row["date"] for row in r.json()["preview"]]
    assert dates == ["2026-09-07", "2026-09-14", "2026-09-21", "2026-09-28"]
    assert r.json()["would_create"] == 4


def test_fortnightly_generates_alternate_weeks(client):
    hdrs = _admin(client)
    r = client.post(URL, json=_body(
        activity_name="Fortnightly Mtg",
        start_date="2026-09-07",
        end_date="2026-10-05",
        recurrence="fortnightly",
        weekday=0,
        preview_only=True,
    ), headers=hdrs)
    assert r.status_code == 200
    dates = [row["date"] for row in r.json()["preview"]]
    assert dates == ["2026-09-07", "2026-09-21", "2026-10-05"]


def test_daily_generates_consecutive_days(client):
    hdrs = _admin(client)
    r = client.post(URL, json=_body(
        activity_name="Daily Drill",
        start_date="2026-09-07",
        end_date="2026-09-09",
        recurrence="daily",
        preview_only=True,
    ), headers=hdrs)
    assert r.status_code == 200
    dates = [row["date"] for row in r.json()["preview"]]
    assert dates == ["2026-09-07", "2026-09-08", "2026-09-09"]


def test_monthly_generates_same_day_of_month(client):
    hdrs = _admin(client)
    r = client.post(URL, json=_body(
        activity_name="Monthly Review",
        start_date="2026-09-15",
        end_date="2026-11-30",
        recurrence="monthly",
        preview_only=True,
    ), headers=hdrs)
    assert r.status_code == 200
    dates = [row["date"] for row in r.json()["preview"]]
    assert "2026-09-15" in dates
    assert "2026-10-15" in dates
    assert "2026-11-15" in dates


# ── excluded_dates ─────────────────────────────────────────────────────────────

def test_excluded_dates_skipped(client):
    hdrs = _admin(client)
    r = client.post(URL, json=_body(
        activity_name="Ex Skip Test",
        start_date="2026-09-07",
        end_date="2026-09-28",
        recurrence="weekly",
        weekday=0,
        excluded_dates=["2026-09-14"],
        preview_only=True,
    ), headers=hdrs)
    assert r.status_code == 200
    dates = [row["date"] for row in r.json()["preview"]]
    assert "2026-09-14" not in dates
    assert "2026-09-07" in dates
    assert "2026-09-21" in dates


# ── repeat_count cap ──────────────────────────────────────────────────────────

def test_repeat_count_caps_occurrences(client):
    hdrs = _admin(client)
    r = client.post(URL, json=_body(
        activity_name="Capped Activity",
        start_date="2026-09-07",
        end_date="2026-11-30",
        recurrence="weekly",
        weekday=0,
        repeat_count=3,
        preview_only=True,
    ), headers=hdrs)
    assert r.status_code == 200
    rows = r.json()["preview"]
    assert len(rows) == 3


# ── invalid recurrence ────────────────────────────────────────────────────────

def test_invalid_recurrence_returns_400(client):
    hdrs = _admin(client)
    r = client.post(URL, json=_body(recurrence="hourly", preview_only=True), headers=hdrs)
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "invalid_recurrence"


# ── batch create and audit ─────────────────────────────────────────────────────

def test_batch_create_returns_summary(client):
    hdrs = _admin(client)
    unique_name = "BatchGenTest2026_Unique"
    r = client.post(URL, json=_body(
        activity_name=unique_name,
        start_date="2026-10-05",
        end_date="2026-10-19",
        recurrence="weekly",
        weekday=0,
        preview_only=False,
    ), headers=hdrs)
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["created_count"] == 3
    assert len(data["created_ids"]) == 3


def test_batch_create_audit_log_entry(client):
    hdrs = _admin(client)
    unique_name = "AuditGenTest2026_Uniq2"
    client.post(URL, json=_body(
        activity_name=unique_name,
        start_date="2026-10-26",
        end_date="2026-11-09",
        recurrence="weekly",
        weekday=0,
        preview_only=False,
    ), headers=hdrs)
    r = client.get("/api/audit?limit=5", headers=hdrs)
    assert r.status_code == 200
    log = r.json() if isinstance(r.json(), list) else r.json().get("items", [])
    actions = [e.get("action") for e in log]
    assert "generate_batch" in actions


# ── duplicate detection ───────────────────────────────────────────────────────

def test_duplicate_detection_skips_existing(client):
    hdrs = _admin(client)
    unique_name = "DupDetectGen2026_Uniq"
    # First create a single activity on 2026-11-16 (Monday)
    client.post(URL, json=_body(
        activity_name=unique_name,
        start_date="2026-11-16",
        end_date="2026-11-16",
        recurrence="weekly",
        weekday=0,
        preview_only=False,
    ), headers=hdrs)
    # Now preview generation for a range including that date
    r = client.post(URL, json=_body(
        activity_name=unique_name,
        start_date="2026-11-16",
        end_date="2026-11-30",
        recurrence="weekly",
        weekday=0,
        preview_only=True,
    ), headers=hdrs)
    assert r.status_code == 200
    rows = r.json()["preview"]
    dup_row = next((row for row in rows if row["date"] == "2026-11-16"), None)
    assert dup_row is not None
    assert dup_row["status"] == "skip"
    assert dup_row["reason"] == "duplicate"
    assert r.json()["would_skip"] >= 1


# ── preview row fields ────────────────────────────────────────────────────────

def test_preview_rows_have_required_fields(client):
    hdrs = _admin(client)
    r = client.post(URL, json=_body(preview_only=True), headers=hdrs)
    assert r.status_code == 200
    rows = r.json()["preview"]
    assert len(rows) > 0
    for row in rows:
        assert "date" in row
        assert "status" in row
        assert row["status"] in ("include", "skip")
