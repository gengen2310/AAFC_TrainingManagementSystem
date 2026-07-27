"""Tests for Dashboard chart data-quality fixes (master transformation plan Block 5):
- "Unknown" phase and "Reason not recorded" must never drive a chart's headline
  insight as if they were real operational findings.
- curriculum_progress must reflect a squadron's full delivery history, not silently
  render all-zero because the requested window happens to exclude older data.
"""
from datetime import date, timedelta

from tests.conftest import login

ADM703 = "ADMIN703"


def test_curriculum_backlog_unknown_phase_is_flagged_not_ranked_as_insight(client):
    """A session missing phase_at_time must appear as a distinctly-flagged
    data-quality gap, never as the chart's "largest backlog" headline finding."""
    hdr = login(client, ADM703)
    r = client.get("/api/dashboard/charts", params={"window": "year"}, headers=hdr)
    assert r.status_code == 200, r.text
    backlog = r.json()["charts"].get("curriculum_backlog")
    if not backlog or not backlog.get("data"):
        return  # nothing to assert if there's no backlog data in this environment
    gap_rows = [d for d in backlog["data"] if d.get("data_quality_gap")]
    real_rows = [d for d in backlog["data"] if not d.get("data_quality_gap")]
    for g in gap_rows:
        assert "Unknown" not in g["label"] or "needs information" in g["label"].lower(), (
            "Missing-phase rows must be labelled as a data-quality gap, not a bare 'Unknown' phase name"
        )
    if gap_rows and backlog.get("insight"):
        # The insight must never claim the gap label is "the largest backlog" —
        # it should only ever headline a REAL phase, or explicitly call out the gap.
        if not real_rows:
            assert "phase" in backlog["insight"].lower()
        else:
            assert real_rows[0]["label"] in backlog["insight"], (
                f"Insight '{backlog['insight']}' should headline a real phase, not the data-quality gap"
            )


def test_cancellation_reasons_missing_reason_is_flagged_not_ranked_as_insight(client):
    """A cancelled/not-delivered session with no reason recorded must be flagged
    as a data-quality gap, never presented as "the most common cause"."""
    hdr = login(client, ADM703)
    r = client.get("/api/dashboard/charts", params={"window": "year"}, headers=hdr)
    assert r.status_code == 200, r.text
    reasons = r.json()["charts"].get("cancellation_reasons")
    if not reasons or not reasons.get("data"):
        return
    gap_rows = [d for d in reasons["data"] if d.get("data_quality_gap")]
    real_rows = [d for d in reasons["data"] if not d.get("data_quality_gap")]
    if gap_rows and reasons.get("insight") and real_rows:
        assert real_rows[0]["label"] in reasons["insight"], (
            f"Insight '{reasons['insight']}' must headline a real reason, not 'reason not recorded'"
        )
    elif gap_rows and reasons.get("insight") and not real_rows:
        assert "no reason recorded" in reasons["insight"].lower()


def test_curriculum_progress_reflects_full_history_not_only_current_window(client):
    """curriculum_progress must use the squadron's full session history (like its
    sibling curriculum_backlog), not silently show all-zero because a delivered
    session happens to predate the requested window — this was a real,
    reproduced defect: 'term' window (~90 days back) excluded historical
    delivered sessions entirely, so every phase row showed 0 across the board
    despite real delivered data existing for the squadron."""
    hdr = login(client, ADM703)

    # Create a session dated well before any reasonable window, with a real phase
    # and a delivered status, to prove curriculum_progress picks it up regardless
    # of the requested window.
    old_date = (date.today() - timedelta(days=400)).isoformat()
    r = client.get("/api/auth/me", headers=hdr)
    sqn_id = r.json()["session"]["squadron_id"]
    wing_id = r.json()["session"]["wing_id"]
    pn = client.post("/api/parade-nights", json={
        "squadron_id": sqn_id, "wing_id": wing_id, "date": old_date, "parade_type": "normal",
    }, headers=hdr)
    assert pn.status_code in (200, 201), pn.text
    pn_id = pn.json().get("parade_night_id") or pn.json().get("id")

    sess = client.post("/api/sessions", json={
        "parade_night_id": pn_id, "period_number": 1, "phase_at_time": "A. Orientation",
    }, headers=hdr)
    assert sess.status_code in (200, 201), sess.text
    sid = sess.json().get("session_id") or sess.json().get("id")

    status_r = client.post(f"/api/sessions/{sid}/status", json={"status": "delivered"}, headers=hdr)
    assert status_r.status_code == 200, status_r.text

    # window=week (a narrow, recent-only window) must still surface this old
    # delivered session in curriculum_progress's "A. Orientation" row.
    dash = client.get("/api/dashboard/charts", params={"window": "week"}, headers=hdr)
    assert dash.status_code == 200, dash.text
    cp = dash.json()["charts"]["curriculum_progress"]
    orientation_row = next(row for row in cp["data"] if row["phase"] == "A. Orientation")
    assert orientation_row["delivered"] >= 1, (
        "curriculum_progress must reflect delivered sessions regardless of the "
        "requested window's date range — it is a cumulative measure, not a windowed one"
    )
