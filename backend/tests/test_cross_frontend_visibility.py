"""What one frontend creates, the other must be able to read.

Reported 2026-08-25: holidays, activities, facilitators, training areas, parade
nights and custom phases created in TMS "did not show up in planning workspace",
with the closing request to "test that created one variable in one group will be
show up in the other and vice versa".

Both frontends talk to one backend, so this fixes the contract at the API layer:
create through the endpoint TMS uses, read back through the endpoint Planning
Workspace uses. It cannot prove a React component renders the row, but it does
prove the data is reachable — and it is what distinguishes a real sync defect
from a client-side one, which is exactly the distinction that was missing when
these were reported together.
"""
from conftest import login, next_test_year


def _sqn(client):
    hdr = login(client, "ADMIN703")
    me = client.get("/api/auth/me", headers=hdr).json()["session"]
    return hdr, me["squadron_id"]


def _year(client, hdr):
    return client.post("/api/planning/years",
                       json={"year": next_test_year(), "name": "cross-frontend"},
                       headers=hdr).json()


def test_a_facilitator_created_in_tms_is_listed_for_planning_workspace(client):
    hdr, _ = _sqn(client)
    r = client.post("/api/facilitators",
                    json={"first_name": "Cross", "last_name": "Frontend", "current_rank": "FSGT"},
                    headers=hdr)
    assert r.status_code == 200, r.text
    fid = r.json().get("facilitator_id") or r.json().get("id")
    try:
        rows = client.get("/api/facilitators", headers=hdr).json()
        assert any((x.get("facilitator_id") or x.get("id")) == fid for x in rows), \
            "a facilitator created in TMS must appear in the list Planning Workspace reads"
    finally:
        # The suite seeds once and never resets, and test_dashboard_charts.py
        # asserts exact facilitator status/type distributions for 703. Leaving
        # this one behind broke both of those. Archive it again.
        client.delete(f"/api/facilitators/{fid}", headers=hdr)


def test_a_training_area_created_in_tms_is_listed_for_planning_workspace(client):
    hdr, _ = _sqn(client)
    r = client.post("/api/training-areas",
                    json={"name": "Cross-Frontend Room", "area_type": "classroom", "capacity": 20},
                    headers=hdr)
    assert r.status_code == 200, r.text
    rows = client.get("/api/training-areas", headers=hdr).json()
    assert any(x.get("name") == "Cross-Frontend Room" for x in rows)


def test_a_holiday_created_in_tms_is_listed_under_its_year(client):
    hdr, _ = _sqn(client)
    y = _year(client, hdr)
    r = client.post(f"/api/planning/years/{y['planning_year_id']}/holidays",
                    json={"name": "Cross-Frontend Holiday",
                          "start_date": f"{y['year']}-04-01", "end_date": f"{y['year']}-04-02",
                          "holiday_type": "public", "affects_parade": True},
                    headers=hdr)
    assert r.status_code == 200, r.text
    rows = client.get(f"/api/planning/years/{y['planning_year_id']}/holidays", headers=hdr).json()
    assert any(x.get("name") == "Cross-Frontend Holiday" for x in rows)


def test_an_activity_created_in_tms_is_listed_for_planning_workspace(client):
    hdr, _ = _sqn(client)
    y = _year(client, hdr)
    r = client.post("/api/activities",
                    json={"activity_name": "Cross-Frontend Activity", "activity_type": "field_day",
                          "date_start": f"{y['year']}-05-02", "date_end": f"{y['year']}-05-02"},
                    headers=hdr)
    assert r.status_code == 200, r.text
    body = client.get("/api/activities", headers=hdr).json()
    rows = body if isinstance(body, list) else body.get("activities", [])
    assert any((x.get("activity_name") or x.get("name")) == "Cross-Frontend Activity" for x in rows)


def test_a_parade_night_created_in_tms_reaches_its_planning_year(client):
    """The defect that produced most of the report. A night was linked to the
    highest-numbered active year rather than the one its date falls in, so
    Planning Workspace — which builds its canvas from ParadeDate rows joined on
    planning_year_id — showed nothing for the year the user scheduled in."""
    hdr, _ = _sqn(client)
    y = _year(client, hdr)
    date = f"{y['year']}-06-11"
    r = client.post("/api/parade-nights", json={"date": date, "term": "T2"}, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["linked_to_planning_year"] is True

    rows = client.get(f"/api/planning/years/{y['planning_year_id']}/parade-dates", headers=hdr).json()
    dates = rows if isinstance(rows, list) else rows.get("parade_dates", [])
    assert any(d.get("parade_date") == date for d in dates), \
        "the night must appear under the planning year its date falls in"


def test_a_custom_phase_is_not_offered_where_a_stage_foreign_key_is_expected(client):
    """Custom phases are ad-hoc scheduling groups, not curriculum stages.

    They are now offered in the SESSION phase picker, where the value is a name
    string stored as Session.phase_at_time. They must stay out of
    /api/curriculum/phases, which also backs the Training Class stage picker
    where training_stage_id is a foreign key to curriculum_phases.id — offering
    one there would let a user pick a value that cannot be stored.
    """
    hdr, sq = _sqn(client)
    r = client.post("/api/custom-training-phases",
                    json={"name": "Cross-Frontend Band", "scope_type": "squadron",
                          "scope_id": sq, "applies_from": "2026-01-01"},
                    headers=hdr)
    assert r.status_code == 200, r.text

    own = client.get("/api/custom-training-phases", headers=hdr).json()
    assert any(x.get("name") == "Cross-Frontend Band" for x in own), \
        "a custom phase must be readable from its own endpoint"

    stages = client.get("/api/curriculum/phases", headers=hdr).json()
    assert not any(x.get("name") == "Cross-Frontend Band" for x in stages), \
        "a custom phase must NOT appear where a curriculum_phases FK is expected"
