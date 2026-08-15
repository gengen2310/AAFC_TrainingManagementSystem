"""Tests for the term_comparison_ytd dashboard chart (Phase 6 / DASH-14).

Verifies that the chart returns correct YTD and term-comparison metrics,
handles missing term labels gracefully, and satisfies the required fields
contract enforced by test_all_charts_have_required_fields.
"""
import pytest
from tests.conftest import login


def _hdr(client):
    return login(client, "ADMIN703")


def _get_chart(client, hdr):
    r = client.get("/api/dashboard/charts", params={"window": "year"}, headers=hdr)
    assert r.status_code == 200, r.text
    charts = r.json().get("charts", r.json())
    assert "term_comparison_ytd" in charts, list(charts.keys())
    chart = charts["term_comparison_ytd"]
    assert chart.get("chart_type") != "error", chart
    return chart


def test_chart_has_required_fields(client):
    hdr = _hdr(client)
    chart = _get_chart(client, hdr)
    for key in ("chart_id", "chart_type", "title", "data", "insight", "empty_state", "permission_scope"):
        assert key in chart, f"missing field: {key}"
    assert chart["chart_id"] == "term_comparison_ytd"
    assert chart["permission_scope"] == "squadron"


def test_chart_type_is_correct(client):
    hdr = _hdr(client)
    chart = _get_chart(client, hdr)
    assert chart["chart_type"] == "term_comparison_ytd"


def test_data_has_expected_keys(client):
    hdr = _hdr(client)
    chart = _get_chart(client, hdr)
    data = chart["data"]
    for key in ("ytd_delivered", "ytd_total", "ytd_pct",
                "current_term", "current_term_pct",
                "prev_term", "prev_term_pct", "delta_pct"):
        assert key in data, f"data missing key: {key}"


def test_ytd_values_are_non_negative(client):
    hdr = _hdr(client)
    chart = _get_chart(client, hdr)
    data = chart["data"]
    assert data["ytd_delivered"] >= 0
    assert data["ytd_total"] >= 0
    if data["ytd_pct"] is not None:
        assert 0 <= data["ytd_pct"] <= 100


def test_delta_consistent_with_term_pcts(client):
    hdr = _hdr(client)
    chart = _get_chart(client, hdr)
    data = chart["data"]
    if data["current_term_pct"] is not None and data["prev_term_pct"] is not None:
        expected_delta = data["current_term_pct"] - data["prev_term_pct"]
        assert data["delta_pct"] == expected_delta
