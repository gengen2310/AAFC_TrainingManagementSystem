"""Tests for the class enrollment distribution dashboard chart (Phase 6).

Verifies chart.data matches the TrainingClass.expected_count source records,
and that the chart handles both populated and empty squadron states correctly.
"""
import uuid

import pytest
from tests.conftest import login, next_test_year


def _hdr(client):
    return login(client, "ADMIN703")


def _make_year(client, hdr, year):
    r = client.post("/api/planning/years", json={"year": year, "name": f"{year} Enrol Year"}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def _make_stage(client, hdr, squadron_id):
    name = f"ENROL-STAGE-{uuid.uuid4().hex[:8]}"
    r = client.post("/api/curriculum/phases", json={
        "name": name, "display_name": name, "scope_level": "squadron", "squadron_id": squadron_id,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["phase_id"], name


def _make_class(client, hdr, year_id, stage_id, name, expected_count=None):
    body = {"training_year_id": year_id, "training_stage_id": stage_id, "display_name": name}
    if expected_count is not None:
        body["expected_count"] = expected_count
    r = client.post("/api/training-classes", json=body, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["training_class_id"]


def _get_enrollment_chart(client, hdr):
    r = client.get("/api/dashboard/charts", params={"window": "year"}, headers=hdr)
    assert r.status_code == 200, r.text
    charts = r.json()["charts"] if "charts" in r.json() else r.json()
    assert "class_enrollment" in charts, list(charts.keys())
    chart = charts["class_enrollment"]
    assert chart.get("chart_type") != "error", chart
    return chart


def test_chart_has_required_fields(client):
    hdr = _hdr(client)
    chart = _get_enrollment_chart(client, hdr)
    for key in ("chart_id", "chart_type", "title", "data", "insight", "empty_state", "permission_scope"):
        assert key in chart, f"missing field: {key}"
    assert chart["chart_id"] == "class_enrollment"
    assert chart["permission_scope"] == "squadron"


def test_class_with_expected_count_appears_in_chart(client):
    hdr = _hdr(client)
    year = _make_year(client, hdr, next_test_year())
    stage_id, stage_name = _make_stage(client, hdr, year["unit_id"])

    c1 = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 1", expected_count=18)
    c2 = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 2", expected_count=12)

    chart = _get_enrollment_chart(client, hdr)
    entry = next((d for d in chart["data"] if d["stage_id"] == stage_id), None)
    assert entry is not None, "stage not found in chart data"
    assert entry["total_expected"] == 30

    by_name = {c["display_name"]: c for c in entry["classes"]}
    assert by_name["Senior 1"]["expected_count"] == 18
    assert by_name["Senior 2"]["expected_count"] == 12


def test_class_without_expected_count_shows_none(client):
    hdr = _hdr(client)
    year = _make_year(client, hdr, next_test_year())
    stage_id, _ = _make_stage(client, hdr, year["unit_id"])
    _make_class(client, hdr, year["planning_year_id"], stage_id, "Bronze 1")  # no expected_count

    chart = _get_enrollment_chart(client, hdr)
    entry = next((d for d in chart["data"] if d["stage_id"] == stage_id), None)
    assert entry is not None
    assert entry["classes"][0]["expected_count"] is None
    # Insight should flag the missing count
    assert chart["insight"] is not None
    assert "no expected size set" in chart["insight"]


def test_chart_not_error_type(client):
    hdr = _hdr(client)
    chart = _get_enrollment_chart(client, hdr)
    assert chart.get("chart_type") == "class_enrollment"
