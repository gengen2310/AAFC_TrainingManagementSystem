"""Tests for the class-aware curriculum-progress dashboard chart (CLASS-07).

Per the governing whole-system hardening program §51 (dashboard data
verification): every chart needs a test verifying its displayed value
against source records, not just "chart rendered". Each test here traces
SOURCE DATA -> EXPECTED CALCULATION -> API RESPONSE, and cross-checks the
dashboard chart's numbers against CLASS-04's own per-class API (a second,
independent source) rather than trusting the chart's internal arithmetic
alone.

Every test uses its own dedicated squadron-scoped Training Stage -- see
test_class_curriculum_progress.py's module docstring for why the shared
national catalogue and relative dates both caused real cross-test pollution
in the sibling test file; the same isolation discipline is used here.
"""
import uuid
from datetime import date, timedelta

import pytest
from tests.conftest import login, next_test_year


def _sqn_admin_hdr(client):
    return login(client, "ADMIN703")


def _make_year(client, hdr, year):
    r = client.post("/api/planning/years", json={"year": year, "name": f"{year} Training Year"}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def _make_stage(client, hdr, squadron_id):
    name = f"CLASS-07-TEST-{uuid.uuid4().hex[:10]}"
    r = client.post("/api/curriculum/phases", json={
        "name": name, "display_name": name, "scope_level": "squadron", "squadron_id": squadron_id,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["phase_id"], name


def _make_class(client, hdr, year_id, stage_id, name):
    r = client.post("/api/training-classes", json={
        "training_year_id": year_id, "training_stage_id": stage_id, "display_name": name,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["training_class_id"]


def _make_curriculum_item(client, hdr, code, phase):
    r = client.post("/api/curriculum", json={
        "code": code, "title": f"{code} title", "phase": phase,
        "learning_hub_url": "https://example.invalid/learning-hub/test-fixture",
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["curriculum_id"]


_next_day_offset = [200]  # a range this file owns exclusively, clear of every other file's literals


def _make_delivered_session(client, hdr, curriculum_item_id, training_class_id):
    offset = _next_day_offset[0]
    _next_day_offset[0] += 3
    candidate = date(2050, 1, 1) + timedelta(days=offset)
    if candidate.weekday() == 4:
        candidate += timedelta(days=1)
    target_date = candidate.isoformat()
    r = client.get("/api/auth/me", headers=hdr)
    session_info = r.json()["session"]
    sqn_id, wing_id = session_info.get("squadron_id"), session_info.get("wing_id")

    pn = client.post("/api/parade-nights", json={
        "squadron_id": sqn_id, "wing_id": wing_id, "date": target_date, "parade_type": "normal",
    }, headers=hdr)
    assert pn.status_code in (200, 201), pn.text
    pn_id = pn.json().get("parade_night_id") or pn.json().get("id")

    sess = client.post("/api/sessions", json={
        "parade_night_id": pn_id, "period_number": 1, "cadet_group": "senior",
        "curriculum_item_id": curriculum_item_id,
    }, headers=hdr)
    assert sess.status_code in (200, 201), sess.text
    sid = sess.json()["session_id"]

    edit = client.put(f"/api/sessions/{sid}", json={
        "parade_night_id": pn_id, "period_number": 1, "cadet_group": "senior",
        "curriculum_item_id": curriculum_item_id, "status": "delivered",
    }, headers=hdr)
    assert edit.status_code == 200, edit.text

    aud = client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [training_class_id]}, headers=hdr)
    assert aud.status_code == 200, aud.text
    return sid


def _get_chart(client, hdr):
    r = client.get("/api/dashboard/charts", params={"window": "year"}, headers=hdr)
    assert r.status_code == 200, r.text
    charts = r.json()["charts"] if "charts" in r.json() else r.json()
    assert "class_curriculum_progress" in charts, list(charts.keys())
    chart = charts["class_curriculum_progress"]
    assert chart.get("chart_type") != "error", chart
    return chart


# ─────────────────────────────────────────────────────────────
# Source data -> chart value
# ─────────────────────────────────────────────────────────────

def test_chart_matches_class_progress_api_for_two_even_classes(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, next_test_year())
    stage_id, stage_name = _make_stage(client, hdr, year["unit_id"])
    c1 = _make_class(client, hdr, year["planning_year_id"], stage_id, "Bronze 1")
    c2 = _make_class(client, hdr, year["planning_year_id"], stage_id, "Bronze 2")

    item1 = _make_curriculum_item(client, hdr, "B1", stage_name)
    item2 = _make_curriculum_item(client, hdr, "B2", stage_name)
    _make_delivered_session(client, hdr, item1, c1)
    _make_delivered_session(client, hdr, item2, c2)

    # Independent source: CLASS-04's own per-class API.
    p1 = client.get(f"/api/training-classes/{c1}/curriculum-progress", headers=hdr).json()
    p2 = client.get(f"/api/training-classes/{c2}/curriculum-progress", headers=hdr).json()
    expected_delivered = p1["summary"]["delivered"] + p2["summary"]["delivered"]
    expected_total = p1["summary"]["total"] + p2["summary"]["total"]

    chart = _get_chart(client, hdr)
    entry = next(d for d in chart["data"] if d["stage_id"] == stage_id)
    assert entry["class_count"] == 2
    assert entry["delivered"] == expected_delivered == 2
    assert entry["total"] == expected_total == 4
    assert entry["coverage_pct"] == round(100 * expected_delivered / expected_total)

    by_name = {c["display_name"]: c for c in entry["classes"]}
    assert by_name["Bronze 1"]["delivered"] == p1["summary"]["delivered"]
    assert by_name["Bronze 1"]["total"] == p1["summary"]["total"]
    assert by_name["Bronze 2"]["delivered"] == p2["summary"]["delivered"]
    assert by_name["Bronze 2"]["total"] == p2["summary"]["total"]

    # Even classes, neither more than the threshold behind -> no exception.
    assert entry["stage"] == stage_name
    stage_behind = [b for b in chart["classes_behind"] if b["stage_name"] == stage_name]
    assert stage_behind == []


def test_significantly_behind_class_is_flagged(client):
    """addendum §75: a stage aggregate must not hide one struggling class
    behind a healthy blended number."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, next_test_year())
    stage_id, stage_name = _make_stage(client, hdr, year["unit_id"])
    c_ahead = _make_class(client, hdr, year["planning_year_id"], stage_id, "Silver 1")
    c_behind = _make_class(client, hdr, year["planning_year_id"], stage_id, "Silver 2")

    # 4 shared items; Silver 1 gets all 4 delivered to it, Silver 2 gets none
    # -- Silver 1 is 100%, Silver 2 is 0%, both far past the 15pp threshold
    # on either side of whatever the blended aggregate turns out to be.
    for i in range(4):
        item_id = _make_curriculum_item(client, hdr, f"S-{i}", stage_name)
        _make_delivered_session(client, hdr, item_id, c_ahead)

    chart = _get_chart(client, hdr)
    entry = next(d for d in chart["data"] if d["stage_id"] == stage_id)
    by_name = {c["display_name"]: c for c in entry["classes"]}
    assert by_name["Silver 1"]["coverage_pct"] == 100
    assert by_name["Silver 2"]["coverage_pct"] == 0

    stage_behind = [b for b in chart["classes_behind"] if b["stage_name"] == stage_name]
    assert len(stage_behind) == 1
    assert stage_behind[0]["display_name"] == "Silver 2"

    # The chart-wide insight names only the first 3 behind-classes across
    # the WHOLE squadron (every stage's classes, not just this test's) --
    # other test files sharing squadron 703's DB may have created their own
    # behind classes too, so assert this stage's own entry is present in
    # classes_behind (already proven above) rather than assuming Silver 2
    # is always among the global top-3 named in free text.
    assert chart["insight"] is not None and "significantly behind" in chart["insight"]


# ─────────────────────────────────────────────────────────────
# Empty state and chart shape
# ─────────────────────────────────────────────────────────────

def test_chart_has_no_error_and_documented_shape(client):
    hdr = _sqn_admin_hdr(client)
    chart = _get_chart(client, hdr)
    for key in ("chart_id", "title", "explanation", "question", "chart_type",
               "data", "classes_behind", "empty_state", "drill_down", "permission_scope"):
        assert key in chart, f"missing documented field: {key}"
    assert chart["chart_id"] == "class_curriculum_progress"
    assert chart["permission_scope"] == "squadron"


def test_full_dashboard_charts_endpoint_still_returns_every_other_chart(client):
    """A new chart builder must not break the rest of the response -- the
    existing _safe_chart fault isolation is what protects this, but the
    integration point itself is worth a direct check."""
    hdr = _sqn_admin_hdr(client)
    r = client.get("/api/dashboard/charts", params={"window": "term"}, headers=hdr)
    assert r.status_code == 200, r.text
    charts = r.json()["charts"] if "charts" in r.json() else r.json()
    assert charts["curriculum_progress"].get("chart_type") != "error"
    assert charts["class_curriculum_progress"].get("chart_type") != "error"
    assert charts["session_outcomes"].get("chart_type") != "error"
