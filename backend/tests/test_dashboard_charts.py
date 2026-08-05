"""Tests for GET /api/dashboard/charts and /api/dashboard/charts/strategic.

Covers: auth, scope detection, chart shape, key presence, empty state,
squadron/wing/national scope, window parameter validation.
"""
from unittest.mock import patch

import pytest
from conftest import login

CHARTS_URL = "/api/dashboard/charts"
STRATEGIC_URL = "/api/dashboard/charts/strategic"

# ── helpers ───────────────────────────────────────────────────────────────────

def _sqn_admin(client):    return login(client, "ADMIN703")
def _sqn_general(client):  return login(client, "703SQN2026")
def _wing_admin(client):   return login(client, "ADMIN7WG")
def _wing_viewer(client):  return login(client, "7WG2026")
def _national(client):     return login(client, "ADMINNATIONAL")
def _auditor(client):      return login(client, "AUDITOR2026")

_CHART_KEYS = ["chart_id", "chart_type", "empty_state"]
_CHART_WITH_DATA = ["chart_id", "chart_type", "data", "empty_state"]


def _charts(r):
    return r.json().get("charts", {})


# ── auth ──────────────────────────────────────────────────────────────────────

def test_charts_requires_auth(client):
    assert client.get(CHARTS_URL).status_code == 401

def test_strategic_requires_auth(client):
    assert client.get(STRATEGIC_URL).status_code == 401


# ── window validation ─────────────────────────────────────────────────────────

def test_invalid_window_rejected(client):
    hdrs = _sqn_admin(client)
    r = client.get(CHARTS_URL + "?window=hourly", headers=hdrs)
    assert r.status_code == 422

def test_week_window_accepted(client):
    hdrs = _sqn_admin(client)
    r = client.get(CHARTS_URL + "?window=week", headers=hdrs)
    assert r.status_code == 200

def test_year_window_accepted(client):
    hdrs = _sqn_admin(client)
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    assert r.status_code == 200


# ── squadron scope ────────────────────────────────────────────────────────────

def test_squadron_scope_returns_200(client):
    hdrs = _sqn_admin(client)
    r = client.get(CHARTS_URL, headers=hdrs)
    assert r.status_code == 200
    data = r.json()
    assert data["scope"] == "squadron"
    assert "charts" in data

def test_sqn_general_can_view_charts(client):
    hdrs = _sqn_general(client)
    r = client.get(CHARTS_URL, headers=hdrs)
    assert r.status_code == 200
    assert r.json()["scope"] == "squadron"

def test_squadron_returns_tonight_chart(client):
    hdrs = _sqn_admin(client)
    r = client.get(CHARTS_URL, headers=hdrs)
    charts = _charts(r)
    assert "tonight" in charts
    t = charts["tonight"]
    assert t["chart_id"] == "tonight"
    assert t["chart_type"] == "readiness_card"

def test_squadron_returns_weekly_outcomes(client):
    hdrs = _sqn_admin(client)
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    charts = _charts(r)
    assert "weekly_outcomes" in charts
    wo = charts["weekly_outcomes"]
    assert wo["chart_type"] == "stacked_bar"
    assert "series" in wo
    assert "data" in wo
    series_keys = {s["key"] for s in wo["series"]}
    assert "delivered" in series_keys
    assert "cancelled" in series_keys
    assert "not_delivered" in series_keys

def test_weekly_outcomes_data_rows_have_correct_keys(client):
    hdrs = _sqn_admin(client)
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    rows = _charts(r).get("weekly_outcomes", {}).get("data", [])
    for row in rows:
        assert "label" in row
        assert "delivered" in row
        assert "cancelled" in row
        assert "not_delivered" in row
        assert "planned" in row

def test_squadron_returns_delivery_trend(client):
    hdrs = _sqn_admin(client)
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    charts = _charts(r)
    assert "delivery_trend" in charts
    dt = charts["delivery_trend"]
    assert dt["chart_type"] == "line"
    assert "thresholds" in dt
    assert dt["thresholds"]["green"] == 80

def test_delivery_trend_data_has_reliability_pct(client):
    hdrs = _sqn_admin(client)
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    rows = _charts(r).get("delivery_trend", {}).get("data", [])
    for row in rows:
        assert "label" in row
        # reliability_pct may be None if no terminal sessions that week
        assert "reliability_pct" in row

def test_squadron_returns_curriculum_progress(client):
    hdrs = _sqn_admin(client)
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    charts = _charts(r)
    assert "curriculum_progress" in charts
    cp = charts["curriculum_progress"]
    assert cp["chart_type"] == "stacked_bar_horizontal"
    # All seeded national phases present even with zero data. Not an exact-count
    # assertion: the chart now sources phases from the live, governed
    # CurriculumPhase catalogue (not a hardcoded constant), so other tests in
    # the full suite legitimately add more national/wing-scope phases that are
    # visible here too -- that's the correct, intended behaviour, not pollution.
    phases = [d["phase"] for d in cp["data"]]
    assert "A. Orientation" in phases
    assert "I. Bronze" in phases
    assert len(phases) >= 8

def test_curriculum_progress_includes_custom_squadron_phase(client):
    """A squadron-scoped custom CurriculumPhase must appear in the chart, not be
    silently dropped -- previously curriculum_progress iterated a hardcoded
    8-phase constant instead of the governed CurriculumPhase catalogue, so a
    custom phase like this never showed up (not even at 0%). Uses 704 (not
    703) so this doesn't change 703's phase count for other tests in this file."""
    hdrs = login(client, "ADMIN704")
    r = client.post("/api/curriculum/phases", json={
        "name": "Z. Custom Squadron Phase", "display_name": "Custom Squadron Phase",
        "scope_level": "squadron",
    }, headers=hdrs)
    assert r.status_code == 200, r.text

    charts = _charts(client.get(CHARTS_URL + "?window=year", headers=hdrs))
    cp = charts["curriculum_progress"]
    phases = [d["phase"] for d in cp["data"]]
    assert "Z. Custom Squadron Phase" in phases
    # Still includes the national catalogue too
    assert "A. Orientation" in phases

def test_one_broken_chart_builder_does_not_take_down_the_others(client):
    """Previously _full_squadron_charts had zero fault isolation -- one
    builder throwing 500'd the ENTIRE /api/dashboard/charts response, taking
    every other chart down with it. Simulates a single builder failing and
    confirms the endpoint still returns 200 with every other chart intact,
    and the broken one marked distinctly rather than missing or crashing
    the whole response."""
    hdrs = _sqn_admin(client)
    with patch("app.routers.dashboard._weekly_outcomes", side_effect=RuntimeError("boom")):
        r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    assert r.status_code == 200, r.text
    charts = _charts(r)
    # The broken chart is present but marked as failed, not silently missing
    assert charts["weekly_outcomes"]["error"] is True
    assert charts["weekly_outcomes"]["chart_type"] == "error"
    # Every other chart in the same bundle survived untouched
    assert charts["curriculum_progress"]["chart_type"] == "stacked_bar_horizontal"
    assert "error" not in charts["curriculum_progress"]
    assert charts["tonight"]["chart_id"] == "tonight"
    assert "error" not in charts["tonight"]


def test_squadron_returns_facilitator_workload(client):
    hdrs = _sqn_admin(client)
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    charts = _charts(r)
    assert "facilitator_workload" in charts
    fw = charts["facilitator_workload"]
    assert fw["chart_type"] == "bar_horizontal"
    for row in fw.get("data", []):
        assert "name" in row
        assert "delivered" in row
        assert "total" in row

def test_squadron_returns_facilitator_status_distribution(client):
    hdrs = _sqn_admin(client)
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    charts = _charts(r)
    assert "facilitator_status_distribution" in charts
    fsd = charts["facilitator_status_distribution"]
    assert fsd["chart_type"] == "donut"
    statuses = {row["status"] for row in fsd["data"]}
    assert statuses == {"available", "on_leave", "unavailable"}
    # 703 squadron demo data seeds 5 active facilitators, none on leave.
    counts = {row["status"]: row["count"] for row in fsd["data"]}
    assert sum(counts.values()) == 5
    assert counts["on_leave"] == 0

def test_squadron_returns_subject_area_resilience(client):
    hdrs = _sqn_admin(client)
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    charts = _charts(r)
    assert "subject_area_resilience" in charts
    sar = charts["subject_area_resilience"]
    assert sar["chart_type"] == "bar_horizontal" or "data" in sar
    for row in sar.get("data", []):
        assert row["risk"] in ("critical", "warn", "ok")

def test_squadron_returns_facilitator_repeated_gaps(client):
    hdrs = _sqn_admin(client)
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    charts = _charts(r)
    assert "facilitator_repeated_gaps" in charts
    gaps = charts["facilitator_repeated_gaps"]
    assert gaps["chart_type"] == "bar_horizontal"
    for row in gaps.get("data", []):
        assert "label" in row
        assert "count" in row
        assert row["count"] >= 1

def test_squadron_returns_capability_dependency(client):
    hdrs = _sqn_admin(client)
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    charts = _charts(r)
    assert "capability_dependency" in charts
    assert charts["capability_dependency"]["chart_type"] == "bar_horizontal"

def test_facilitator_charts_zero_data_for_new_squadron(client):
    # 704 squadron has no facilitators/sessions seeded — verifies empty-state safety.
    hdrs = login(client, "ADMIN704")
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    assert r.status_code == 200
    charts = _charts(r)
    fsd = charts["facilitator_status_distribution"]
    assert sum(row["count"] for row in fsd["data"]) == 0
    assert charts["facilitator_repeated_gaps"]["data"] == []

def test_squadron_general_can_view_facilitator_charts(client):
    hdrs = _sqn_general(client)
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    charts = _charts(r)
    assert "facilitator_status_distribution" in charts
    assert "facilitator_repeated_gaps" in charts

def test_squadron_returns_cancellation_reasons(client):
    hdrs = _sqn_admin(client)
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    charts = _charts(r)
    assert "cancellation_reasons" in charts
    cr = charts["cancellation_reasons"]
    assert cr["chart_type"] == "bar_horizontal"

def test_squadron_returns_session_outcomes(client):
    hdrs = _sqn_admin(client)
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    charts = _charts(r)
    assert "session_outcomes" in charts
    so = charts["session_outcomes"]
    assert so["chart_type"] == "donut"
    statuses = {d["status"] for d in so["data"]}
    assert "delivered" in statuses
    assert "cancelled" in statuses

def test_squadron_returns_upcoming_readiness(client):
    hdrs = _sqn_admin(client)
    r = client.get(CHARTS_URL, headers=hdrs)
    charts = _charts(r)
    assert "upcoming_readiness" in charts
    ur = charts["upcoming_readiness"]
    assert ur["chart_type"] == "readiness_grid"
    for row in ur.get("data", []):
        assert "date" in row
        assert "readiness_pct" in row
        assert "unstaffed" in row

def test_squadron_returns_curriculum_backlog(client):
    hdrs = _sqn_admin(client)
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    charts = _charts(r)
    assert "curriculum_backlog" in charts

def test_all_charts_have_required_fields(client):
    hdrs = _sqn_admin(client)
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    for chart_id, chart in _charts(r).items():
        assert "chart_id" in chart, f"chart {chart_id} missing chart_id"
        assert "chart_type" in chart, f"chart {chart_id} missing chart_type"
        assert "empty_state" in chart, f"chart {chart_id} missing empty_state"


# ── strategic charts ──────────────────────────────────────────────────────────

def test_strategic_returns_200_for_sqn(client):
    hdrs = _sqn_admin(client)
    r = client.get(STRATEGIC_URL, headers=hdrs)
    assert r.status_code == 200
    assert r.json()["scope"] == "squadron"

def test_strategic_returns_capability_dependency(client):
    hdrs = _sqn_admin(client)
    r = client.get(STRATEGIC_URL + "?window=year", headers=hdrs)
    charts = _charts(r)
    assert "capability_dependency" in charts
    cd = charts["capability_dependency"]
    assert cd["chart_type"] == "bar_horizontal"

def test_strategic_returns_subject_area_resilience(client):
    hdrs = _sqn_admin(client)
    r = client.get(STRATEGIC_URL, headers=hdrs)
    charts = _charts(r)
    assert "subject_area_resilience" in charts
    sar = charts["subject_area_resilience"]
    assert sar["chart_type"] == "bar_horizontal"
    for row in sar.get("data", []):
        assert "risk" in row
        assert row["risk"] in ("ok", "warn", "critical")

def test_strategic_returns_facilitator_status_distribution(client):
    hdrs = _sqn_admin(client)
    r = client.get(STRATEGIC_URL, headers=hdrs)
    charts = _charts(r)
    assert "facilitator_status_distribution" in charts
    assert charts["facilitator_status_distribution"]["chart_type"] == "donut"

def test_strategic_returns_facilitator_repeated_gaps(client):
    hdrs = _sqn_admin(client)
    r = client.get(STRATEGIC_URL, headers=hdrs)
    charts = _charts(r)
    assert "facilitator_repeated_gaps" in charts
    assert charts["facilitator_repeated_gaps"]["chart_type"] == "bar_horizontal"

def test_strategic_returns_long_term_trend(client):
    hdrs = _sqn_admin(client)
    r = client.get(STRATEGIC_URL, headers=hdrs)
    charts = _charts(r)
    assert "long_term_delivery_trend" in charts
    lt = charts["long_term_delivery_trend"]
    assert lt["chart_type"] == "line"
    assert "thresholds" in lt


# ── wing scope ────────────────────────────────────────────────────────────────

def test_wing_scope_returns_wing_charts(client):
    hdrs = _wing_admin(client)
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    assert r.status_code == 200
    data = r.json()
    assert data["scope"] == "wing"
    charts = data.get("charts", {})
    assert "squadron_readiness" in charts

def test_wing_viewer_can_view_charts(client):
    hdrs = _wing_viewer(client)
    r = client.get(CHARTS_URL, headers=hdrs)
    assert r.status_code == 200
    assert r.json()["scope"] == "wing"

def test_wing_squadron_readiness_shape(client):
    hdrs = _wing_admin(client)
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    chart = _charts(r).get("squadron_readiness", {})
    assert chart["chart_type"] == "bar_horizontal"
    for row in chart.get("data", []):
        assert "label" in row
        assert "readiness_pct" in row
        assert 0 <= row["readiness_pct"] <= 100

def test_wing_returns_subject_area_gaps(client):
    hdrs = _wing_admin(client)
    r = client.get(CHARTS_URL, headers=hdrs)
    charts = _charts(r)
    assert "wing_subject_area_gaps" in charts
    gaps = charts["wing_subject_area_gaps"]
    assert gaps["chart_type"] == "heatmap"
    for row in gaps.get("data", []):
        assert "label" in row
        assert "cells" in row

def test_wing_delivery_rates_not_averaged(client):
    """Wing delivery rate must be recalculated from raw counts, not averaged."""
    hdrs = _wing_admin(client)
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    chart = _charts(r).get("squadron_readiness", {})
    # Each squadron row must have delivered and total, not just a pre-averaged pct
    for row in chart.get("data", []):
        if row.get("total", 0) > 0:
            expected_pct = round(row["delivered"] / row["total"] * 100)
            assert abs(row["readiness_pct"] - expected_pct) <= 1


# ── national scope ────────────────────────────────────────────────────────────

def test_national_scope_returns_wing_readiness(client):
    hdrs = _national(client)
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    assert r.status_code == 200
    data = r.json()
    assert data["scope"] == "national"
    charts = data.get("charts", {})
    assert "wing_readiness" in charts

def test_national_wing_readiness_shape(client):
    hdrs = _national(client)
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    chart = _charts(r).get("wing_readiness", {})
    assert chart["chart_type"] == "bar_horizontal"
    for row in chart.get("data", []):
        assert "label" in row
        assert "readiness_pct" in row
        assert 0 <= row["readiness_pct"] <= 100

def test_national_wing_delivery_comparison(client):
    hdrs = _national(client)
    r = client.get(CHARTS_URL + "?window=year", headers=hdrs)
    chart = _charts(r).get("wing_delivery_comparison", {})
    assert chart["chart_type"] == "grouped_bar"
    assert "series" in chart

def test_auditor_can_view_national_charts(client):
    hdrs = _auditor(client)
    r = client.get(CHARTS_URL, headers=hdrs)
    assert r.status_code == 200
    assert r.json()["scope"] == "national"


# ── response metadata ─────────────────────────────────────────────────────────

def test_response_includes_window_bounds(client):
    hdrs = _sqn_admin(client)
    r = client.get(CHARTS_URL + "?window=term", headers=hdrs)
    data = r.json()
    assert "window_start" in data
    assert "window_end" in data
    assert data["window"] == "term"

def test_response_scope_matches_role(client):
    for fn, expected in [(_sqn_admin, "squadron"), (_wing_admin, "wing"), (_national, "national")]:
        r = client.get(CHARTS_URL, headers=fn(client))
        assert r.json()["scope"] == expected, f"Expected {expected} for {fn.__name__}"
