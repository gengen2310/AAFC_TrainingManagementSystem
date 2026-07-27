"""Tests for the Facilitator Schedule Explorer endpoint (master transformation
plan Block 9): GET /api/dashboard/facilitator-schedule returns one row per
facilitator plus their assigned sessions and recorded leave, scoped the same
way every other squadron page is under Block 8 (own squadron directly, or a
Wing/National viewer via squadron_id with no proxy needed). Also covers the
facilitator_leave_impact strategic chart, which surfaces the same
leave/session collision as a ranked "who needs a substitute" chart.
"""
from datetime import date, timedelta

from tests.conftest import login

ADM703 = "ADMIN703"
ADM7WG = "ADMIN7WG"
ADMNAT = "ADMINNATIONAL"


def _own_squadron_id(client, hdr):
    return client.get("/api/auth/me", headers=hdr).json()["session"]["squadron_id"]


def _seed_facilitator(client, hdr):
    r = client.get("/api/facilitators", headers=hdr)
    assert r.status_code == 200, r.text
    facs = r.json()
    assert facs, "expected at least one seeded 703 facilitator"
    return facs[0]["facilitator_id"]


def _create_session_with_facilitator(client, hdr, sqn_id, wing_id, fac_id, on_date, status=None):
    pn = client.post("/api/parade-nights", json={
        "squadron_id": sqn_id, "wing_id": wing_id, "date": on_date, "parade_type": "normal",
    }, headers=hdr)
    assert pn.status_code in (200, 201), pn.text
    pn_id = pn.json().get("parade_night_id") or pn.json().get("id")

    sess = client.post("/api/sessions", json={
        "parade_night_id": pn_id, "period_number": 1, "facilitator_id": fac_id,
    }, headers=hdr)
    assert sess.status_code in (200, 201), sess.text
    sid = sess.json().get("session_id") or sess.json().get("id")

    if status:
        st = client.post(f"/api/sessions/{sid}/status", json={"status": status}, headers=hdr)
        assert st.status_code == 200, st.text

    return pn_id, sid


def test_squadron_admin_sees_own_facilitators_and_session_items(client):
    hdr = login(client, ADM703)
    sqn_id = _own_squadron_id(client, hdr)
    wing_id = client.get("/api/auth/me", headers=hdr).json()["session"]["wing_id"]
    fac_id = _seed_facilitator(client, hdr)

    # Offset must stay within the current calendar year (the "year" window is
    # calendar-year-bounded, see _date_window) while landing on a date that
    # collides with neither seed_all()'s baseline data nor another test's
    # parade night. seed_all() seeds a real ParadeNight for squadron 703 on
    # EVERY Friday from 2026-01-30 through 2026-12-11 -- any today+N offset
    # that lands on a Friday inside that range hits a 409 duplicate_date (this
    # is what broke a prior +130 offset once the suite ran on 2026-07-27,
    # since today's weekday made +130 land on a seeded Friday). +144 lands on
    # 2026-12-18, a Friday just past the seeded range's end (and inside the
    # Term 4/Summer Holidays period, which seed_all() explicitly skips when
    # seeding Fridays) -- safe regardless of which weekday "today" falls on
    # this year, as long as today+144 stays in-year.
    future = (date.today() + timedelta(days=144)).isoformat()
    _create_session_with_facilitator(client, hdr, sqn_id, wing_id, fac_id, future)

    r = client.get("/api/dashboard/facilitator-schedule", params={"window": "year"}, headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["squadron_id"] == sqn_id
    assert any(f["facilitator_id"] == fac_id for f in body["facilitators"])
    session_items = [i for i in body["items"] if i["kind"] == "session" and i["facilitator_id"] == fac_id]
    assert any(i["date"] == future for i in session_items)


def test_wing_admin_can_view_via_squadron_id_without_proxy(client):
    hdr703 = login(client, ADM703)
    sqn_id = _own_squadron_id(client, hdr703)

    hdr_wing = login(client, ADM7WG)
    r = client.get("/api/dashboard/facilitator-schedule", params={"squadron_id": sqn_id}, headers=hdr_wing)
    assert r.status_code == 200, r.text
    assert r.json()["squadron_id"] == sqn_id


def test_wing_admin_without_squadron_id_gets_empty_result_not_error(client):
    hdr_wing = login(client, ADM7WG)
    r = client.get("/api/dashboard/facilitator-schedule", headers=hdr_wing)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["squadron_id"] is None
    assert body["facilitators"] == []
    assert body["items"] == []


def test_wing_admin_cannot_view_squadron_outside_their_wing(client):
    hdr_wing = login(client, ADM7WG)
    r = client.get("/api/dashboard/facilitator-schedule",
                    params={"squadron_id": "00000000-0000-0000-0000-000000000000"}, headers=hdr_wing)
    assert r.status_code == 404, r.text


def test_national_admin_can_view_via_squadron_id(client):
    hdr703 = login(client, ADM703)
    sqn_id = _own_squadron_id(client, hdr703)

    hdr_nat = login(client, ADMNAT)
    r = client.get("/api/dashboard/facilitator-schedule", params={"squadron_id": sqn_id}, headers=hdr_nat)
    assert r.status_code == 200, r.text
    assert r.json()["squadron_id"] == sqn_id


def test_leave_item_appears_with_correct_kind(client):
    hdr = login(client, ADM703)
    fac_id = _seed_facilitator(client, hdr)

    start = (date.today() + timedelta(days=5)).isoformat()
    end = (date.today() + timedelta(days=12)).isoformat()
    lv = client.post(f"/api/planning/facilitators/{fac_id}/leave",
                      json={"start_date": start, "end_date": end, "reason": "annual leave"}, headers=hdr)
    assert lv.status_code == 200, lv.text

    r = client.get("/api/dashboard/facilitator-schedule", params={"window": "year"}, headers=hdr)
    assert r.status_code == 200, r.text
    leave_items = [i for i in r.json()["items"] if i["kind"] == "leave" and i["facilitator_id"] == fac_id]
    assert any(i["start_date"] == start and i["end_date"] == end for i in leave_items)


def test_facilitator_leave_impact_flags_session_scheduled_during_leave(client):
    """A session assigned to a facilitator that falls inside their own recorded
    leave must surface in the facilitator_leave_impact strategic chart — the
    'who needs a substitute' signal (master transformation plan Block 9)."""
    hdr = login(client, ADM703)
    sqn_id = _own_squadron_id(client, hdr)
    wing_id = client.get("/api/auth/me", headers=hdr).json()["session"]["wing_id"]
    fac_id = _seed_facilitator(client, hdr)

    clash_date = (date.today() + timedelta(days=145)).isoformat()
    _create_session_with_facilitator(client, hdr, sqn_id, wing_id, fac_id, clash_date, status="planned")

    lv = client.post(f"/api/planning/facilitators/{fac_id}/leave", json={
        "start_date": (date.today() + timedelta(days=140)).isoformat(),
        "end_date": (date.today() + timedelta(days=150)).isoformat(),
        "reason": "leave over the clash date",
    }, headers=hdr)
    assert lv.status_code == 200, lv.text

    r = client.get("/api/dashboard/charts/strategic", params={"window": "year"}, headers=hdr)
    assert r.status_code == 200, r.text
    chart = r.json()["charts"].get("facilitator_leave_impact")
    assert chart is not None
    assert chart["chart_id"] == "facilitator_leave_impact"
    assert sum(row["count"] for row in chart["data"]) >= 1, (
        "expected the clashing session to be counted in facilitator_leave_impact's data"
    )
