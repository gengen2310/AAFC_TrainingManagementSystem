"""Part 87 — the golden workflow: one squadron's training year, end to end.

Every other test in this suite checks one endpoint, or one pair of endpoints.
This one walks the whole journey in order, in a single test, with each step
feeding the next: set the squadron up, build a year, plan it across both
surfaces, run a parade night, and close it out. If any step's output stops
being usable as the next step's input, this fails -- which is the failure mode
that per-endpoint tests structurally cannot see.

WHAT THIS IS NOT. It exercises the API path both frontends share, not the
browsers. It cannot prove a React component renders a row or that a button is
reachable; frontend/e2e does that for the Planning Workspace, and nothing does
it across BOTH frontends yet, because the Playwright config serves only the PW
app. That gap is recorded in P87's traceability row rather than papered over.

It runs in squadron 707. The suite seeds once per session and never resets, so
anything written here is visible to every test that follows: 703 is used by
~309 assertions, 704 is the squadron test_dashboard_charts needs empty, and 705
belongs to the cross-surface round trips. 707 is untouched by anything else.
"""
import itertools

from conftest import login

# Private year range -- see test_cross_surface_round_trip for why this file does
# not draw from conftest's shared counter.
_year_counter = itertools.count(9000, 2)

SQN_CODE = "707"
SQN_ADMIN = "ADMIN707"


def _step(n, what):
    """Readable failure output: the step number is the first thing you see."""
    return f"step {n:02d} — {what}"


def test_golden_workflow_one_squadron_one_training_year(client):
    hdr = login(client, SQN_ADMIN)
    year = next(_year_counter)
    trail = []

    def ok(n, what, resp, *, expect=(200, 201)):
        assert resp.status_code in expect, f"{_step(n, what)}: {resp.status_code} {resp.text[:300]}"
        trail.append(_step(n, what))
        return resp.json() if resp.text else {}

    # ── SET UP THE SQUADRON ───────────────────────────────────────────────────
    me = ok(1, "sign in and resolve scope",
            client.get("/api/auth/me", headers=hdr))["session"]
    sqn_id = me["squadron_id"]
    assert sqn_id, _step(1, "squadron admin has no squadron scope")

    ok(2, "set parade day and times",
       client.patch(f"/api/squadrons/{sqn_id}", headers=hdr,
                    json={"default_parade_day": "Friday", "default_start_time": "18:00",
                          "default_end_time": "22:00", "default_session_count": 3}))

    tmpl = ok(3, "create a timing template with training periods",
              client.post("/api/timing-templates", headers=hdr,
                          json={"name": f"{year} Standard Night",
                                "effective_from": f"{year}-01-01",
                                "blocks": [
                                    {"block_name": "Arrival", "block_type": "arrival",
                                     "display_order": 1, "is_instructional_period": False},
                                    {"block_name": "Period 1", "block_type": "training_period",
                                     "display_order": 2, "is_instructional_period": True,
                                     "period_number": 1},
                                    {"block_name": "Period 2", "block_type": "training_period",
                                     "display_order": 3, "is_instructional_period": True,
                                     "period_number": 2},
                                ]}))
    tmpl_id = tmpl.get("timing_template_id") or tmpl.get("id")
    assert tmpl_id, _step(3, f"template create returned no id: {tmpl}")

    eff = ok(4, "the template resolves as effective for a date in the year",
             client.get(f"/api/timing-templates/effective?date={year}-05-01", headers=hdr))
    assert eff.get("instructional_period_count") == 2, (
        _step(4, f"expected 2 instructional periods, got {eff.get('instructional_period_count')}"))

    # ── BUILD THE YEAR ────────────────────────────────────────────────────────
    yr = ok(5, "create the training year",
            client.post("/api/planning/years", headers=hdr,
                        json={"year": year, "name": f"{year} Training Year"}))
    yr_id = yr["planning_year_id"]

    ok(6, "add a parade date",
       client.post(f"/api/planning/years/{yr_id}/parade-dates", headers=hdr,
                   json={"parade_date": f"{year}-05-01"}))
    ok(7, "add a second parade date",
       client.post(f"/api/planning/years/{yr_id}/parade-dates", headers=hdr,
                   json={"parade_date": f"{year}-05-08"}))

    dates = ok(8, "list the year's parade dates",
               client.get(f"/api/planning/years/{yr_id}/parade-dates", headers=hdr))
    assert len(dates) >= 2, _step(8, f"expected 2 dates, got {len(dates)}")
    date_a = next(d for d in dates if d["parade_date"] == f"{year}-05-01")
    date_b = next(d for d in dates if d["parade_date"] == f"{year}-05-08")

    ok(9, "add a holiday period covering the second date",
       client.post(f"/api/planning/years/{yr_id}/holidays", headers=hdr,
                   json={"name": "Term Break", "start_date": f"{year}-05-06",
                         "end_date": f"{year}-05-10", "affects_parade": True}))

    # ── PEOPLE AND PLACES ─────────────────────────────────────────────────────
    fac = ok(10, "add a facilitator",
             client.post("/api/facilitators", headers=hdr,
                         json={"first_name": "Jordan", "last_name": "Reyes",
                               "current_rank": "FSGT(AAFC)", "facilitator_type": "staff"}))
    fac_id = fac.get("facilitator_id") or fac.get("id")
    assert fac_id, _step(10, f"facilitator create returned no id: {fac}")

    room = ok(11, "add a training area",
              client.post("/api/training-areas", headers=hdr,
                          json={"name": "Lecture Room 1", "capacity": 30}))
    room_id = room.get("training_area_id") or room.get("id")
    assert room_id, _step(11, f"training area create returned no id: {room}")

    stages = ok(12, "read the training stages available to this squadron",
                client.get("/api/curriculum/phases", headers=hdr))
    stage_list = stages if isinstance(stages, list) else stages.get("phases", [])
    assert stage_list, _step(12, "no training stages available")
    stage_id = stage_list[0].get("phase_id") or stage_list[0].get("id")

    cls = ok(13, "create a training class for the year",
             client.post("/api/training-classes", headers=hdr,
                         json={"display_name": "Junior 1", "training_year_id": yr_id,
                               "training_stage_id": stage_id}))
    class_id = cls.get("training_class_id") or cls.get("id")
    assert class_id, _step(13, f"training class create returned no id: {cls}")

    # ── PLAN IT, THROUGH THE PLANNING WORKSPACE ───────────────────────────────
    s1 = ok(14, "schedule a session on the first parade date",
            client.post(f"/api/planning/parade-dates/{date_a['parade_date_id']}/sessions",
                        headers=hdr,
                        json={"cadet_group": "junior", "session_number": 1,
                              "activity_title": "Drill Fundamentals"}))
    sess1 = s1["session_id"]

    ok(15, "assign the facilitator and the room to that session",
       client.patch(f"/api/planning/sessions/{sess1}", headers=hdr,
                    json={"facilitator_id": fac_id, "location_id": room_id}))

    builder = ok(16, "the planning date now resolves to a real parade night",
                 client.get(f"/api/planning/parade-dates/{date_a['parade_date_id']}/builder",
                            headers=hdr))
    pn_id = builder.get("parade_night_id")
    assert pn_id, _step(16, "planning date did not link to a parade night")

    # ── THE PLAN DISAGREES WITH ITSELF ────────────────────────────────────────
    s2 = ok(17, "schedule a second session in the same period with the same facilitator",
            client.post(f"/api/planning/parade-dates/{date_a['parade_date_id']}/sessions",
                        headers=hdr,
                        json={"cadet_group": "senior", "session_number": 1,
                              "activity_title": "Navigation"}))
    sess2 = s2["session_id"]
    ok(18, "assign the same facilitator, creating a double-booking",
       client.patch(f"/api/planning/sessions/{sess2}", headers=hdr,
                    json={"facilitator_id": fac_id}))

    review = ok(19, "the derived plan review reports the clash without being asked",
                client.get(f"/api/planning/years/{yr_id}/plan-review", headers=hdr))
    clashes = [f for f in review["findings"]
               if f["conflict_type"] == "facilitator_double_booked"]
    assert clashes, _step(19, f"no facilitator clash detected; counts={review['counts']}")

    ok(20, "record the conflicts so one can be overridden",
       client.post(f"/api/planning/years/{yr_id}/run-checks", headers=hdr))
    conflicts = ok(21, "list the recorded conflicts",
                   client.get(f"/api/planning/years/{yr_id}/conflicts", headers=hdr))["conflicts"]
    target = next((c for c in conflicts
                   if c["conflict_type"] == "facilitator_double_booked"), None)
    assert target, _step(21, f"clash not recorded: {[c['conflict_type'] for c in conflicts]}")

    ok(22, "override the clash with a written reason",
       client.post(f"/api/planning/conflicts/{target['conflict_id']}/override", headers=hdr,
                   json={"override_reason": "Both groups combine for this period."}))

    review2 = ok(23, "the review now shows it overridden, with the reason, not hidden",
                 client.get(f"/api/planning/years/{yr_id}/plan-review", headers=hdr))
    kept = [f for f in review2["findings"]
            if f["conflict_type"] == "facilitator_double_booked" and f["is_overridden"]]
    assert kept, _step(23, "the overridden clash vanished from the review")
    assert kept[0]["override_reason"] == "Both groups combine for this period.", (
        _step(23, "the reason did not survive"))

    # ── THE OTHER SURFACE SEES THE SAME NIGHT ─────────────────────────────────
    tms_night = ok(24, "TMS shows the sessions the Planning Workspace scheduled",
                   client.get(f"/api/parade-nights/{pn_id}/builder", headers=hdr))
    tms_titles = [x.get("custom_title") or x.get("activity_title")
                  for x in tms_night["sessions"]]
    assert "Drill Fundamentals" in tms_titles, (
        _step(24, f"PW-scheduled session missing from TMS: {tms_titles}"))

    ok(25, "TMS renames a session; the Planning Workspace must agree",
       client.patch(f"/api/planning/sessions/{sess1}", headers=hdr,
                    json={"activity_title": "Drill Fundamentals (revised)"}))
    back = ok(25, "read it back through TMS",
              client.get(f"/api/parade-nights/{pn_id}/builder", headers=hdr))
    assert "Drill Fundamentals (revised)" in [
        x.get("custom_title") or x.get("activity_title") for x in back["sessions"]], (
        _step(25, "the rename did not cross surfaces"))

    # ── RUN THE NIGHT ─────────────────────────────────────────────────────────
    # The first publish attempt is blocked because the second session has no
    # room -- correct, and worth reaching deliberately rather than by accident.
    blocked = client.post(f"/api/parade-nights/{pn_id}/publish", headers=hdr)
    assert blocked.status_code == 409, (
        _step(26, f"expected publish to be blocked while a session has no room, "
                  f"got {blocked.status_code}"))
    first_blockers = blocked.json()["detail"].get("blockers")
    assert first_blockers, _step(26, "publish was blocked with no blockers listed")
    assert any(b.get("fix") == "assign_room" for b in first_blockers), (
        _step(26, f"blocked for the wrong reason: {first_blockers}"))

    ok(26, "give the second session a room, clearing the blocker",
       client.patch(f"/api/planning/sessions/{sess2}", headers=hdr,
                    json={"location_id": room_id}))

    pub = client.post(f"/api/parade-nights/{pn_id}/publish", headers=hdr)
    assert pub.status_code == 200, (
        _step(26, f"publish still refused once every blocker was cleared: "
                  f"{pub.status_code} {pub.text[:300]}"))
    trail.append(_step(26, "parade night published"))

    tms_sess_id = next(x["session_id"] for x in back["sessions"]
                       if (x.get("custom_title") or x.get("activity_title"))
                       == "Drill Fundamentals (revised)")
    ok(27, "record the session outcome",
       client.post(f"/api/sessions/{tms_sess_id}/status", headers=hdr,
                   json={"status": "delivered", "actual_attendance": 18}))

    hist = ok(27, "the status change is on the session's history",
              client.get(f"/api/sessions/{tms_sess_id}/status-history", headers=hdr))
    hist_list = hist if isinstance(hist, list) else hist.get("history", [])
    assert any(h.get("new_status") == "delivered" for h in hist_list), (
        _step(27, f"no delivered entry in status history: {hist_list}"))

    audit = ok(27, "the audit trail recorded it",
               client.get(f"/api/audit?object_type=session&object_id={tms_sess_id}",
                          headers=login(client, "AUDITOR2026")))
    entries = audit if isinstance(audit, list) else audit.get("entries", audit.get("logs", []))
    assert any(e.get("action") == "status_change" for e in entries), (
        _step(27, f"status change not audited: {[e.get('action') for e in entries]}"))

    # The trail is the point: if this test ever fails, the last line printed is
    # the last step that worked.
    # Count distinct step numbers, not trail lines: a few steps assert twice.
    reached = {t.split(" — ")[0] for t in trail}
    assert len(reached) >= 27, (
        f"only {len(reached)} of 27 steps completed:\n  " + "\n  ".join(trail))
