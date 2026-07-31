"""Tests for the Wing/National Training Dashboard Sections A+B —
GET /api/dashboard/command.

Covers: role/scope enforcement, IDOR prevention, archive filtering,
count-first aggregation (never per-unit percentage averaging), zero-vs-no-data
distinction, readiness matrix, risk forecast detection, immediate issues
rollup, delivery performance charts, data confidence, drill-down shape.
"""
from datetime import date, timedelta

from tests.conftest import login

COMMAND_URL = "/api/dashboard/command"


def _sysadmin(client):     return login(client, "SYSADMIN2026")
def _nat_admin(client):    return login(client, "ADMINNATIONAL")
def _wing_admin(client):   return login(client, "ADMIN7WG")
def _wing_viewer(client):  return login(client, "7WG2026")
def _sqn_admin(client):    return login(client, "ADMIN703")


def _wing_id_by_code(client, hdr, code):
    r = client.get("/api/wings", headers=hdr)
    for w in r.json():
        if w["code"] == code:
            return w["wing_id"]
    raise AssertionError(f"wing {code} not found")


def _make_test_wing_and_squadron(client, hdr, wing_code, sqn_code):
    wing_id = client.post("/api/wings", json={"code": wing_code, "name": f"{wing_code} Test Wing"}, headers=hdr).json()["wing_id"]
    sqn_id = client.post("/api/squadrons", json={"wing_id": wing_id, "code": sqn_code, "name": f"{sqn_code} Test Unit"}, headers=hdr).json()["squadron_id"]
    return wing_id, sqn_id


def _enter_di(client, hdr, sqn_id, reason="command dashboard test"):
    r = client.post(f"/api/proxy/enter/{sqn_id}", json={"reason": reason}, headers=hdr)
    assert r.status_code == 200, r.text


def _exit_di(client, hdr):
    client.post("/api/proxy/exit", headers=hdr)


def _session_id(resp_json):
    return resp_json.get("session_id") or resp_json.get("id")


# ── auth / scope enforcement ────────────────────────────────────────────────

def test_command_requires_auth(client):
    assert client.get(COMMAND_URL).status_code == 401


def test_squadron_scope_returns_400_not_applicable(client):
    hdr = _sqn_admin(client)
    r = client.get(COMMAND_URL, headers=hdr)
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "not_applicable"


def test_wing_admin_gets_own_wing_scope(client):
    hdr = _wing_admin(client)
    r = client.get(COMMAND_URL, headers=hdr)
    assert r.status_code == 200
    assert r.json()["scope"] == "wing"


def test_wing_viewer_gets_own_wing_read_only(client):
    hdr = _wing_viewer(client)
    r = client.get(COMMAND_URL, headers=hdr)
    assert r.status_code == 200
    assert r.json()["scope"] == "wing"


def test_national_admin_gets_national_scope(client):
    hdr = _nat_admin(client)
    r = client.get(COMMAND_URL, headers=hdr)
    assert r.status_code == 200
    assert r.json()["scope"] == "national"


def test_sysadmin_gets_national_scope_by_default(client):
    hdr = _sysadmin(client)
    r = client.get(COMMAND_URL, headers=hdr)
    assert r.status_code == 200
    assert r.json()["scope"] == "national"


def test_sysadmin_can_drill_into_wing_via_param(client):
    hdr = _sysadmin(client)
    wing_id = _wing_id_by_code(client, hdr, "7WG")
    r = client.get(COMMAND_URL, params={"wing_id": wing_id}, headers=hdr)
    assert r.status_code == 200
    assert r.json()["scope"] == "wing"
    assert r.json()["wing_id"] == wing_id


def test_view_access_requires_no_intervention_mode(client):
    """Viewing the command dashboard must not require Proxy/Intervention Mode —
    no /api/proxy/enter call is made anywhere in this test."""
    hdr = _nat_admin(client)
    r = client.get(COMMAND_URL, headers=hdr)
    assert r.status_code == 200


def test_unknown_wing_id_404s(client):
    hdr = _sysadmin(client)
    r = client.get(COMMAND_URL, params={"wing_id": "does-not-exist"}, headers=hdr)
    assert r.status_code == 404


# ── IDOR prevention ──────────────────────────────────────────────────────────

def test_wing_admin_wing_id_param_is_ignored_uses_own_wing_only(client):
    """A wing_admin's own p.wing_id path must win regardless of any wing_id
    query param — the param is national-scope-only, matching the existing
    pattern already established for /charts and /reports/*."""
    hdr = _wing_admin(client)
    sysadm = _sysadmin(client)
    other_wing_id, _ = _make_test_wing_and_squadron(client, sysadm, "CMDW1", "CMD01")
    r = client.get(COMMAND_URL, params={"wing_id": other_wing_id}, headers=hdr)
    assert r.status_code == 200
    assert r.json()["wing_id"] != other_wing_id


# ── archive filtering ────────────────────────────────────────────────────────

def test_archived_squadron_excluded_from_readiness_matrix(client):
    hdr = _sysadmin(client)
    wing_id, sqn_id = _make_test_wing_and_squadron(client, hdr, "ARCW1", "ARC01")
    r = client.get(COMMAND_URL, params={"wing_id": wing_id}, headers=hdr)
    labels = [row["label"] for row in r.json()["sections"]["A"]["readiness_matrix"]["data"]]
    assert "ARC01" in labels

    client.post(f"/api/squadrons/{sqn_id}/archive", headers=hdr)
    r2 = client.get(COMMAND_URL, params={"wing_id": wing_id}, headers=hdr)
    labels2 = [row["label"] for row in r2.json()["sections"]["A"]["readiness_matrix"]["data"]]
    assert "ARC01" not in labels2


# ── zero vs no-data distinction ──────────────────────────────────────────────

def test_unit_with_no_upcoming_parade_night_reports_no_data_not_zero(client):
    hdr = _sysadmin(client)
    wing_id, _ = _make_test_wing_and_squadron(client, hdr, "NDW1", "ND01")
    r = client.get(COMMAND_URL, params={"wing_id": wing_id}, headers=hdr)
    row = next(row for row in r.json()["sections"]["A"]["readiness_matrix"]["data"] if row["label"] == "ND01")
    assert row["status"] == "no_data"
    assert row["overall_readiness"]["pct"] is None
    assert row["curriculum_allocated"]["data_available"] is False


def test_zero_session_next_pn_does_not_report_fabricated_100_pct(client):
    """The exact bug caught during live verification: a next-parade-night
    record with zero sessions attached must not report pct=100
    (legacy_score's documented fabricated value for the empty case) — it
    must be honestly None/no_data."""
    hdr = _sysadmin(client)
    wing_id, sqn_id = _make_test_wing_and_squadron(client, hdr, "ZSW1", "ZS01")
    _enter_di(client, hdr, sqn_id)
    future_date = (date.today() + timedelta(days=3)).isoformat()
    r = client.post("/api/parade-nights", json={"date": future_date, "term": "T3", "session_count": 0}, headers=hdr)
    assert r.status_code == 200, r.text
    _exit_di(client, hdr)

    r = client.get(COMMAND_URL, params={"wing_id": wing_id}, headers=hdr)
    row = next(row for row in r.json()["sections"]["A"]["readiness_matrix"]["data"] if row["label"] == "ZS01")
    assert row["overall_readiness"]["pct"] is None
    assert row["overall_readiness"]["status"] == "no_data"
    assert row["trend"] == "no_data"


# ── risk forecast detection ─────────────────────────────────────────────────

def test_risk_forecast_detects_understaffed_session(client):
    hdr = _sysadmin(client)
    wing_id, sqn_id = _make_test_wing_and_squadron(client, hdr, "RFW1", "RF01")
    _enter_di(client, hdr, sqn_id)
    future_date = (date.today() + timedelta(weeks=3)).isoformat()
    pn = client.post("/api/parade-nights", json={"date": future_date, "term": "T3", "session_count": 1}, headers=hdr)
    assert pn.status_code == 200, pn.text
    pn_id = pn.json()["parade_night_id"]
    s = client.post("/api/sessions", json={"parade_night_id": pn_id}, headers=hdr)
    assert s.status_code == 200, s.text
    _exit_di(client, hdr)

    r = client.get(COMMAND_URL, params={"wing_id": wing_id}, headers=hdr)
    items = r.json()["sections"]["A"]["risk_forecast"]["data"]
    categories = {it["category"] for it in items if it["unit_label"] == "RF01"}
    assert "no_facilitator" in categories
    assert "no_facility" in categories
    assert "curriculum_not_allocated" in categories


def test_risk_forecast_marks_equipment_as_unavailable_not_fabricated(client):
    hdr = _sysadmin(client)
    r = client.get(COMMAND_URL, headers=hdr)
    conf = r.json()["sections"]["A"]["risk_forecast"]["data_confidence"]
    assert "equipment_unavailable" in conf["categories_not_available"]


def test_risk_forecast_out_of_horizon_session_not_included(client):
    """A session 10 weeks out (beyond the 8-week forecast horizon) must not
    appear in the risk forecast."""
    hdr = _sysadmin(client)
    wing_id, sqn_id = _make_test_wing_and_squadron(client, hdr, "OHW1", "OH01")
    _enter_di(client, hdr, sqn_id)
    far_date = (date.today() + timedelta(weeks=10)).isoformat()
    pn = client.post("/api/parade-nights", json={"date": far_date, "term": "T4", "session_count": 1}, headers=hdr)
    pn_id = pn.json()["parade_night_id"]
    client.post("/api/sessions", json={"parade_night_id": pn_id}, headers=hdr)
    _exit_di(client, hdr)

    r = client.get(COMMAND_URL, params={"wing_id": wing_id}, headers=hdr)
    items = r.json()["sections"]["A"]["risk_forecast"]["data"]
    assert not any(it["unit_label"] == "OH01" for it in items)


def test_immediate_issues_ranks_units_with_near_term_risk(client):
    hdr = _sysadmin(client)
    wing_id, sqn_id = _make_test_wing_and_squadron(client, hdr, "IIW1", "II01")
    _enter_di(client, hdr, sqn_id)
    near_date = (date.today() + timedelta(days=5)).isoformat()
    pn = client.post("/api/parade-nights", json={"date": near_date, "term": "T3", "session_count": 1}, headers=hdr)
    pn_id = pn.json()["parade_night_id"]
    client.post("/api/sessions", json={"parade_night_id": pn_id}, headers=hdr)
    _exit_di(client, hdr)

    r = client.get(COMMAND_URL, params={"wing_id": wing_id}, headers=hdr)
    data = r.json()["sections"]["A"]["immediate_issues"]["data"]
    assert any(row["label"] == "II01" and row["total"] > 0 for row in data)


# ── delivery performance (Section B) — aggregation, not averaging ──────────

def test_outcomes_by_unit_counts_sum_to_total(client):
    hdr = _sysadmin(client)
    wing_id, _ = _make_test_wing_and_squadron(client, hdr, "AGW1", "AG01")
    r = client.get(COMMAND_URL, params={"wing_id": wing_id}, headers=hdr)
    assert r.status_code == 200
    b3 = r.json()["sections"]["B"]["outcomes_by_unit"]
    assert b3["chart_type"] == "stacked_bar_horizontal_100"
    for row in b3["data"]:
        assert row["total"] == sum(row["counts"].values())


def test_delivered_session_reflected_in_outcomes_by_unit(client):
    hdr = _sysadmin(client)
    wing_id, sqn_id = _make_test_wing_and_squadron(client, hdr, "DLW1", "DL01")
    _enter_di(client, hdr, sqn_id)
    past_date = (date.today() - timedelta(days=3)).isoformat()
    pn = client.post("/api/parade-nights", json={"date": past_date, "term": "T3", "session_count": 1}, headers=hdr)
    pn_id = pn.json()["parade_night_id"]
    s = client.post("/api/sessions", json={"parade_night_id": pn_id}, headers=hdr)
    sid = _session_id(s.json())
    st = client.post(f"/api/sessions/{sid}/status", json={"status": "delivered"}, headers=hdr)
    assert st.status_code == 200, st.text
    _exit_di(client, hdr)

    r = client.get(COMMAND_URL, params={"wing_id": wing_id, "window": "term"}, headers=hdr)
    b3 = r.json()["sections"]["B"]["outcomes_by_unit"]
    row = next(x for x in b3["data"] if x["label"] == "DL01")
    assert row["counts"]["delivered"] == 1


def test_cancellation_pareto_has_cumulative_percentage(client):
    hdr = _sysadmin(client)
    wing_id, sqn_id = _make_test_wing_and_squadron(client, hdr, "CPW1", "CP01")
    _enter_di(client, hdr, sqn_id)
    past_date = (date.today() - timedelta(days=3)).isoformat()
    pn = client.post("/api/parade-nights", json={"date": past_date, "term": "T3", "session_count": 1}, headers=hdr)
    pn_id = pn.json()["parade_night_id"]
    s = client.post("/api/sessions", json={"parade_night_id": pn_id}, headers=hdr)
    sid = _session_id(s.json())
    st = client.post(f"/api/sessions/{sid}/status", json={"status": "cancelled", "reason": "Weather"}, headers=hdr)
    assert st.status_code == 200, st.text
    _exit_di(client, hdr)

    r = client.get(COMMAND_URL, params={"wing_id": wing_id, "window": "term"}, headers=hdr)
    pareto = r.json()["sections"]["B"]["cancellation_pareto"]
    assert pareto["data"]
    assert "cumulative_pct" in pareto["data"][0]
    assert all(0 <= d["cumulative_pct"] <= 100 for d in pareto["data"])


def test_reliability_trend_has_labelled_thresholds(client):
    hdr = _sysadmin(client)
    r = client.get(COMMAND_URL, headers=hdr)
    trend = r.json()["sections"]["B"]["reliability_trend"]
    assert "threshold_labels" in trend
    assert "80" in trend["threshold_labels"]
    assert "60" in trend["threshold_labels"]


# ── data confidence, envelope fields, drill-down ────────────────────────────

def test_every_chart_has_required_envelope_fields(client):
    hdr = _sysadmin(client)
    r = client.get(COMMAND_URL, headers=hdr)
    d = r.json()
    for section in ("A", "B"):
        for chart in d["sections"][section].values():
            for field in ("purpose", "measure", "action"):
                assert field in chart, f"{chart.get('chart_id')} missing {field}"


def test_readiness_matrix_has_drill_down(client):
    hdr = _sysadmin(client)
    r = client.get(COMMAND_URL, headers=hdr)
    assert "drill_down" in r.json()["sections"]["A"]["readiness_matrix"]


def test_top_level_data_confidence_reports_units_reporting_vs_expected(client):
    hdr = _sysadmin(client)
    r = client.get(COMMAND_URL, headers=hdr)
    conf = r.json()["data_confidence"]
    assert "units_reporting" in conf and "units_expected" in conf


def test_readiness_matrix_data_confidence(client):
    hdr = _sysadmin(client)
    r = client.get(COMMAND_URL, headers=hdr)
    conf = r.json()["sections"]["A"]["readiness_matrix"]["data_confidence"]
    assert conf["units_expected"] >= conf["units_reporting"]


# ── window handling ──────────────────────────────────────────────────────────

def test_invalid_window_rejected(client):
    hdr = _sysadmin(client)
    r = client.get(COMMAND_URL, params={"window": "hourly"}, headers=hdr)
    assert r.status_code == 422


def test_semester_window_accepted(client):
    hdr = _sysadmin(client)
    r = client.get(COMMAND_URL, params={"window": "semester"}, headers=hdr)
    assert r.status_code == 200
    assert r.json()["period"]["label"] == "Semester"
