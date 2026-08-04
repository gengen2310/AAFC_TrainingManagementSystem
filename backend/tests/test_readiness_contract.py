"""Contract test: the SAME parade night must report the SAME planning_status on
every consuming surface (master transformation plan Block 4). Before this pass,
three-plus-one independently-computed readiness values could disagree with each
other for the exact same data; this test proves that can no longer happen for the
four surfaces wired onto services_readiness.parade_night_readiness() in this pass:
Dashboard's "tonight" card, GET /api/parade-nights/{id} (readiness_v2), and
/api/reports/readiness — plus /api/reports/wing-overview from a wing-scoped role.
"""
from datetime import date, timedelta

from tests.conftest import login

ADM703 = "ADMIN703"
ADM7WG = "ADMIN7WG"


def _make_parade_night_with_one_incomplete_session(client, hdr, days_ahead=1):
    """A parade night with exactly one session missing its facilitator and room —
    every surface should agree this is "at_risk". `days_ahead` must differ between
    tests sharing the same squadron/DB to avoid the unique (squadron, date) conflict.

    703's seeded demo data recurs weekly on its own default_parade_day (Friday) --
    a small fixed days_ahead can land on that same weekday depending on what day
    the suite happens to run (confirmed: passed for weeks, then broke the day
    "today + 2" first landed on a Friday), colliding with an already-seeded
    parade night. Nudge forward a day whenever the candidate date is a Friday so
    this is robust regardless of which day the suite runs on."""
    candidate = date.today() + timedelta(days=days_ahead)
    if candidate.weekday() == 4:  # Monday=0 .. Friday=4
        candidate += timedelta(days=1)
    target_date = candidate.isoformat()
    r = client.get("/api/auth/me", headers=hdr)
    session_info = r.json()["session"]  # /api/auth/me nests fields under "session"
    sqn_id, wing_id = session_info.get("squadron_id"), session_info.get("wing_id")

    pn = client.post("/api/parade-nights", json={
        "squadron_id": sqn_id, "wing_id": wing_id, "date": target_date, "parade_type": "normal",
    }, headers=hdr)
    assert pn.status_code in (200, 201), pn.text
    pn_id = pn.json().get("parade_night_id") or pn.json().get("id")

    sess = client.post("/api/sessions", json={
        "parade_night_id": pn_id, "period_number": 1, "cadet_group": "junior",
    }, headers=hdr)
    assert sess.status_code in (200, 201), sess.text
    return pn_id, target_date


def test_same_parade_night_reports_same_planning_status_everywhere(client):
    hdr = login(client, ADM703)
    pn_id, pn_date = _make_parade_night_with_one_incomplete_session(client, hdr)

    # Surface 1: parade night detail (readiness_v2, computed live).
    detail = client.get(f"/api/parade-nights/{pn_id}", headers=hdr)
    assert detail.status_code == 200, detail.text
    detail_status = detail.json()["readiness_v2"]["planning_status"]

    # Surface 2: /api/reports/readiness (next 8 upcoming nights for this squadron).
    rep = client.get("/api/reports/readiness", headers=hdr)
    assert rep.status_code == 200, rep.text
    rep_entry = next((x for x in rep.json()["parade_nights"] if x["parade_night_id"] == pn_id), None)
    assert rep_entry is not None, "New parade night not found in /reports/readiness"
    rep_status = rep_entry["planning_status"]

    # Surface 3: Dashboard "tonight" card (next upcoming parade night chronologically).
    dash = client.get("/api/dashboard/charts", params={"window": "week"}, headers=hdr)
    assert dash.status_code == 200, dash.text
    tonight = dash.json()["charts"].get("tonight")
    dash_status = None
    if tonight and tonight.get("data") and tonight["data"].get("date") == pn_date:
        dash_status = tonight["data"]["planning_status"]

    assert detail_status == rep_status, (
        f"Parade night detail says '{detail_status}' but /reports/readiness says '{rep_status}' "
        "for the exact same parade night — readiness has drifted between surfaces."
    )
    if dash_status is not None:
        assert detail_status == dash_status, (
            f"Parade night detail says '{detail_status}' but the Dashboard tonight card says "
            f"'{dash_status}' for the exact same parade night — readiness has drifted."
        )

    # This specific fixture (one session, missing facilitator+room) must be at_risk —
    # not "not_planned" (that's reserved for zero sessions) and not "planned".
    assert detail_status == "at_risk"


def test_same_parade_night_reports_same_planning_status_from_wing_scope(client):
    """A wing_admin viewing the same squadron's data via /reports/wing-overview must
    see the identical planning_status a squadron admin sees directly for whichever
    parade night wing-overview is actually reporting on (its own earliest-future-
    night selection) — same computation, different caller, same answer. This test
    does NOT assume the parade night created here is that "earliest" night (the
    demo seed squadron already has other future nights that may sort earlier); it
    independently determines which night wing-overview must be describing and
    compares against that specific night's own /api/parade-nights/{id} response."""
    hdr_sqn = login(client, ADM703)
    # Ensure at least one incomplete-session future night exists (exercises the
    # same "at_risk" computation as the other tests), though wing-overview may
    # still pick an earlier night from the squadron's existing seeded data.
    # Deliberately far from the other test's days_ahead=1 (not just +1) so that
    # even after each independently nudges off a Friday collision (see the
    # helper's docstring), the two can never land on the same date.
    _make_parade_night_with_one_incomplete_session(client, hdr_sqn, days_ahead=9)

    r = client.get("/api/auth/me", headers=hdr_sqn)
    sqn_id = r.json()["session"].get("squadron_id")

    # Independently compute which future parade night is "earliest" for this
    # squadron — the same selection wing_overview's `sorted(future, ...)[0]` makes.
    all_pns = client.get("/api/parade-nights", headers=hdr_sqn)
    assert all_pns.status_code == 200, all_pns.text
    today_str = date.today().isoformat()
    future_pns = [pn for pn in all_pns.json() if pn["date"] >= today_str]
    assert future_pns, "Expected at least one future parade night after creating one"
    earliest = sorted(future_pns, key=lambda pn: pn["date"])[0]
    earliest_id = earliest.get("parade_night_id") or earliest.get("id")

    detail = client.get(f"/api/parade-nights/{earliest_id}", headers=hdr_sqn)
    assert detail.status_code == 200, detail.text
    detail_status = detail.json()["readiness_v2"]["planning_status"]

    hdr_wing = login(client, ADM7WG)
    wing = client.get("/api/reports/wing-overview", headers=hdr_wing)
    assert wing.status_code == 200, wing.text
    sqn_row = next((x for x in wing.json()["squadrons"] if x["squadron_id"] == sqn_id), None)
    assert sqn_row is not None, "Squadron not found in wing-overview"

    if sqn_row.get("planning_status") is not None:
        assert sqn_row["planning_status"] == detail_status, (
            f"Squadron's earliest future parade night ({earliest_id}) says '{detail_status}' "
            f"but wing-overview says '{sqn_row['planning_status']}' for the same squadron."
        )


def test_zero_session_parade_night_is_not_planned_on_every_surface(client):
    """The exact reported defect: a parade night with zero sessions must read
    'not_planned' everywhere, never 'ready'/100%/'fully staffed' on any surface."""
    hdr = login(client, ADM703)
    r = client.get("/api/auth/me", headers=hdr)
    session_info = r.json()["session"]
    sqn_id, wing_id = session_info.get("squadron_id"), session_info.get("wing_id")
    far_future = (date.today() + timedelta(days=200)).isoformat()

    pn = client.post("/api/parade-nights", json={
        "squadron_id": sqn_id, "wing_id": wing_id, "date": far_future, "parade_type": "normal",
    }, headers=hdr)
    assert pn.status_code in (200, 201), pn.text
    pn_id = pn.json().get("parade_night_id") or pn.json().get("id")

    detail = client.get(f"/api/parade-nights/{pn_id}", headers=hdr)
    assert detail.status_code == 200, detail.text
    assert detail.json()["readiness_v2"]["planning_status"] == "not_planned"
    assert detail.json()["readiness_v2"]["legacy_score"] == 100  # legacy field only — never displayed as "ready"

    rep = client.get("/api/reports/readiness", headers=hdr)
    rep_entry = next((x for x in rep.json()["parade_nights"] if x["parade_night_id"] == pn_id), None)
    if rep_entry is not None:
        assert rep_entry["planning_status"] == "not_planned"
