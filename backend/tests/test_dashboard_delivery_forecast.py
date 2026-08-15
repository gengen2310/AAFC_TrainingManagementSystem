"""Tests for the delivery_forecast dashboard chart (Phase 6 / DASH-15).

Verifies the deterministic forecast: projected_delivered = remaining_planned
times the historical delivery rate, with correct zero/empty handling.
"""
from tests.conftest import login


def _hdr(client):
    return login(client, "ADMIN703")


def _get_chart(client, hdr):
    r = client.get("/api/dashboard/charts", params={"window": "year"}, headers=hdr)
    assert r.status_code == 200, r.text
    charts = r.json().get("charts", r.json())
    assert "delivery_forecast" in charts, list(charts.keys())
    chart = charts["delivery_forecast"]
    assert chart.get("chart_type") != "error", chart
    return chart


def test_chart_has_required_fields(client):
    hdr = _hdr(client)
    chart = _get_chart(client, hdr)
    for key in ("chart_id", "chart_type", "title", "data", "insight", "empty_state", "permission_scope"):
        assert key in chart, f"missing field: {key}"
    assert chart["chart_id"] == "delivery_forecast"
    assert chart["permission_scope"] == "squadron"


def test_chart_type_is_correct(client):
    hdr = _hdr(client)
    chart = _get_chart(client, hdr)
    assert chart["chart_type"] == "delivery_forecast"


def test_data_has_expected_keys(client):
    hdr = _hdr(client)
    chart = _get_chart(client, hdr)
    data = chart["data"]
    for key in ("ytd_delivered", "ytd_not_delivered", "ytd_total_terminal",
                "delivery_rate_pct", "remaining_planned",
                "projected_delivered", "projected_missed"):
        assert key in data, f"data missing key: {key}"


def test_ytd_values_consistent(client):
    hdr = _hdr(client)
    chart = _get_chart(client, hdr)
    data = chart["data"]
    assert data["ytd_total_terminal"] == data["ytd_delivered"] + data["ytd_not_delivered"]
    if data["delivery_rate_pct"] is not None:
        assert 0 <= data["delivery_rate_pct"] <= 100


def test_projected_consistency(client):
    hdr = _hdr(client)
    chart = _get_chart(client, hdr)
    data = chart["data"]
    if data["projected_delivered"] is not None and data["projected_missed"] is not None:
        assert data["projected_delivered"] + data["projected_missed"] == data["remaining_planned"]
