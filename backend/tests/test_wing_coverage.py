"""Tests for the Wing/National coverage enrichments and the phase-coverage heatmap matrix."""
from conftest import login


def test_wing_overview_includes_coverage_and_not_delivered(client):
    h = login(client, "ADMIN7WG")
    r = client.get("/api/reports/wing-overview", headers=h)
    assert r.status_code == 200, r.text
    sqns = r.json()["squadrons"]
    assert sqns, "expected at least one squadron in the wing"
    for s in sqns:
        assert "coverage_pct" in s and 0 <= s["coverage_pct"] <= 100
        assert "not_delivered" in s and s["not_delivered"] >= 0


def test_wing_phase_coverage_matrix(client):
    h = login(client, "ADMIN7WG")
    r = client.get("/api/reports/wing-phase-coverage", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body["phases"], list)
    assert isinstance(body["squadrons"], list)
    for row in body["squadrons"]:
        assert "short_name" in row and "phase_pct" in row
        for pct in row["phase_pct"].values():
            assert 0 <= pct <= 100


def test_national_overview_includes_coverage(client):
    h = login(client, "NATIONAL2026")
    r = client.get("/api/reports/national-overview", headers=h)
    assert r.status_code == 200, r.text
    for w in r.json()["wings"]:
        assert "coverage_pct" in w and 0 <= w["coverage_pct"] <= 100


def test_phase_coverage_blocked_for_squadron_general(client):
    h = login(client, "703SQN2026")
    r = client.get("/api/reports/wing-phase-coverage", headers=h)
    assert r.status_code in (401, 403)
