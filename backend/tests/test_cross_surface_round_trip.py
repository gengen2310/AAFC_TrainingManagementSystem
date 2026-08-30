"""Part 55 — TMS -> PW -> TMS round trips for the entities both surfaces write.

test_cross_frontend_visibility.py already proves one direction for six entities:
something created in TMS is READABLE from the Planning Workspace's endpoints.
That catches "it never arrived". It does not catch the harder case, which is
what this file adds: something WRITTEN through one surface and then written or
read back through the other, where the two can disagree about the same row.

Both frontends share one backend, so a round trip is the strongest statement
available at the API layer: create through the endpoint TMS uses, modify through
the endpoint Planning Workspace uses, and read back through TMS. If the two
surfaces have drifted apart on a shared entity, the value comes back wrong or
does not come back at all.

These cannot prove a React component renders the row. They prove the data is the
same data -- which is the distinction that matters when a user reports "I
changed it there and it didn't change here".
"""
import itertools

from conftest import login

# A private year range, deliberately NOT conftest's next_test_year().
#
# That counter steps by 3 and is shared session-wide, and some tests derive a
# second year from their allocation (base and base + 1). Consuming values from
# it therefore shifts which numbers every later file receives -- adding this
# file's six tests moved the alignment enough to make
# test_parade_night_year_linkage collide with years it had not created. Taking
# a private range means these tests cannot perturb anyone else's.
#
# 8000+ is clear: conftest allocates from 5000 and the highest hand-written
# literal in the suite is 2999.
_year_counter = itertools.count(8000, 2)


def _admin(client):
    # 705, and the choice matters. The suite seeds once and never resets, so
    # anything created here is visible to every test that runs afterwards.
    #   703 is used by ~309 assertions, several of which resolve "the active
    #       planning year" -- adding years there failed eight tests in files
    #       this one never touches.
    #   704 is the squadron test_dashboard_charts relies on having NO data, to
    #       check empty-state safety.
    # 705 is referenced by no other test, so writing here perturbs nothing.
    hdr = login(client, "ADMIN705")
    me = client.get("/api/auth/me", headers=hdr).json()["session"]
    return hdr, me["squadron_id"]


def _year_with_date(client, hdr):
    """A planning year with one parade date, from this file's private range."""
    year = next(_year_counter)
    r = client.post("/api/planning/years",
                    json={"year": year, "name": f"{year} cross-surface"}, headers=hdr)
    yr_id = (r.json()["planning_year_id"] if r.status_code == 200
             else r.json()["detail"]["existing_id"])
    dates = client.get(f"/api/planning/years/{yr_id}/parade-dates", headers=hdr)
    assert dates.status_code == 200, dates.text
    if dates.json():
        d = dates.json()[0]
        return yr_id, d["parade_date_id"], d["parade_date"]
    iso = f"{year}-05-01"
    rp = client.post(f"/api/planning/years/{yr_id}/parade-dates",
                     json={"parade_date": iso}, headers=hdr)
    assert rp.status_code == 200, rp.text
    return yr_id, rp.json()["parade_date_id"], iso


def _pw_sessions(client, hdr, date_id):
    r = client.get(f"/api/planning/parade-dates/{date_id}/builder", headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["sessions"]


def _tms_night_sessions(client, hdr, pn_id):
    r = client.get(f"/api/parade-nights/{pn_id}/builder", headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["sessions"]


# ── PW writes, TMS reads ──────────────────────────────────────────────────────

def test_a_session_scheduled_in_pw_appears_on_the_tms_parade_night(client):
    hdr, _ = _admin(client)
    _, date_id, _ = _year_with_date(client, hdr)

    made = client.post(f"/api/planning/parade-dates/{date_id}/sessions",
                       json={"cadet_group": "junior", "session_number": 1,
                             "activity_title": "PW Scheduled Drill"}, headers=hdr)
    assert made.status_code == 200, made.text

    # PW auto-links the date to a real parade night; TMS reads that night.
    builder = client.get(f"/api/planning/parade-dates/{date_id}/builder", headers=hdr)
    pn_id = builder.json().get("parade_night_id")
    assert pn_id, "PW did not link the parade date to a parade night"

    titles = [s.get("custom_title") or s.get("activity_title")
              for s in _tms_night_sessions(client, hdr, pn_id)]
    assert "PW Scheduled Drill" in titles, (
        f"a session scheduled in the Planning Workspace is not on the TMS parade "
        f"night: {titles}"
    )


# ── TMS writes, PW reads ──────────────────────────────────────────────────────

def test_a_session_created_in_tms_appears_in_the_pw_builder(client):
    hdr, _ = _admin(client)
    _, date_id, _ = _year_with_date(client, hdr)

    # Establish the link by scheduling once through PW, then create in TMS.
    seed = client.post(f"/api/planning/parade-dates/{date_id}/sessions",
                       json={"cadet_group": "senior", "session_number": 1}, headers=hdr)
    assert seed.status_code == 200, seed.text
    pn_id = client.get(f"/api/planning/parade-dates/{date_id}/builder",
                       headers=hdr).json()["parade_night_id"]

    made = client.post("/api/sessions", headers=hdr,
                       json={"parade_night_id": pn_id, "period_number": 2,
                             "cadet_group": "junior", "custom_title": "TMS Created Lesson"})
    assert made.status_code == 200, made.text

    titles = [s.get("activity_title") or s.get("custom_title")
              for s in _pw_sessions(client, hdr, date_id)]
    assert "TMS Created Lesson" in titles, (
        f"a session created in TMS is not in the Planning Workspace builder: {titles}"
    )


# ── the full round trip ───────────────────────────────────────────────────────

def test_a_tms_session_edited_in_pw_reads_back_changed_in_tms(client):
    """TMS -> PW -> TMS. The one that catches two surfaces disagreeing."""
    hdr, _ = _admin(client)
    _, date_id, _ = _year_with_date(client, hdr)

    seed = client.post(f"/api/planning/parade-dates/{date_id}/sessions",
                       json={"cadet_group": "orientation", "session_number": 1}, headers=hdr)
    assert seed.status_code == 200, seed.text
    pn_id = client.get(f"/api/planning/parade-dates/{date_id}/builder",
                       headers=hdr).json()["parade_night_id"]

    made = client.post("/api/sessions", headers=hdr,
                       json={"parade_night_id": pn_id, "period_number": 3,
                             "cadet_group": "junior", "custom_title": "Round Trip Original"})
    assert made.status_code == 200, made.text
    assert made.json().get("session_id") or made.json().get("id"), made.text

    # Find the same row through PW and edit it there.
    pw_row = [s for s in _pw_sessions(client, hdr, date_id)
              if (s.get("activity_title") or s.get("custom_title")) == "Round Trip Original"]
    assert pw_row, "TMS session not visible in PW, so the round trip cannot start"
    pw_id = pw_row[0].get("session_id") or pw_row[0].get("id")

    # No fallback to a TMS edit here on purpose. If PW's PATCH ever stops
    # working, this test must FAIL -- quietly editing through TMS instead would
    # leave it passing while testing TMS -> TMS, which proves nothing about two
    # surfaces agreeing.
    edited = client.patch(f"/api/planning/sessions/{pw_id}",
                          json={"activity_title": "Round Trip Edited"}, headers=hdr)
    assert edited.status_code == 200, (
        f"the Planning Workspace could not edit a TMS-created session: "
        f"{edited.status_code} {edited.text[:200]}"
    )

    titles = [s.get("custom_title") or s.get("activity_title")
              for s in _tms_night_sessions(client, hdr, pn_id)]
    assert "Round Trip Edited" in titles, (
        f"an edit made in the Planning Workspace did not read back in TMS: {titles}"
    )
    assert "Round Trip Original" not in titles, (
        "TMS still shows the pre-edit title -- the two surfaces disagree about "
        "the same session"
    )


def test_archiving_in_pw_removes_the_session_from_the_tms_night(client):
    """A soft delete on one surface must not leave the row live on the other."""
    hdr, _ = _admin(client)
    _, date_id, _ = _year_with_date(client, hdr)

    made = client.post(f"/api/planning/parade-dates/{date_id}/sessions",
                       json={"cadet_group": "intermediate", "session_number": 1,
                             "activity_title": "To Be Archived"}, headers=hdr)
    assert made.status_code == 200, made.text
    sess_id = made.json()["session_id"]
    pn_id = client.get(f"/api/planning/parade-dates/{date_id}/builder",
                       headers=hdr).json()["parade_night_id"]

    assert "To Be Archived" in [s.get("custom_title") or s.get("activity_title")
                                for s in _tms_night_sessions(client, hdr, pn_id)]

    gone = client.delete(f"/api/planning/sessions/{sess_id}", headers=hdr)
    assert gone.status_code == 200, gone.text

    titles = [s.get("custom_title") or s.get("activity_title")
              for s in _tms_night_sessions(client, hdr, pn_id)]
    assert "To Be Archived" not in titles, (
        f"a session archived in the Planning Workspace is still live on the TMS "
        f"parade night: {titles}"
    )


# ── notices: one entity, two surfaces ────────────────────────────────────────
# TMS posts a notice against a PARADE NIGHT, the Planning Workspace against a
# PARADE DATE, and both resolve to the same PlanningNotice row. That is the
# correct shared-entity shape, and worth pinning: if either side ever grew its
# own notice table the two pages would silently stop showing each other's.

def test_a_notice_added_in_tms_appears_on_the_pw_parade_date(client):
    hdr, _ = _admin(client)
    _, date_id, _ = _year_with_date(client, hdr)
    seed = client.post(f"/api/planning/parade-dates/{date_id}/sessions",
                       json={"cadet_group": "junior", "session_number": 1}, headers=hdr)
    assert seed.status_code == 200, seed.text
    pn_id = client.get(f"/api/planning/parade-dates/{date_id}/builder",
                       headers=hdr).json()["parade_night_id"]

    made = client.post(f"/api/parade-nights/{pn_id}/notices", headers=hdr,
                       json={"notice_text": "Notice written in TMS"})
    assert made.status_code in (200, 201), made.text

    pw = client.get(f"/api/planning/parade-dates/{date_id}/notices", headers=hdr)
    assert pw.status_code == 200, pw.text
    body = pw.json()
    items = body if isinstance(body, list) else body.get("notices", [])
    texts = [n.get("notice_text") or n.get("text") for n in items]
    assert "Notice written in TMS" in texts, (
        f"a notice added in TMS is not on the Planning Workspace parade date: {texts}"
    )


def test_a_notice_added_in_pw_appears_on_the_tms_parade_night(client):
    hdr, _ = _admin(client)
    _, date_id, _ = _year_with_date(client, hdr)
    seed = client.post(f"/api/planning/parade-dates/{date_id}/sessions",
                       json={"cadet_group": "junior", "session_number": 1}, headers=hdr)
    assert seed.status_code == 200, seed.text
    pn_id = client.get(f"/api/planning/parade-dates/{date_id}/builder",
                       headers=hdr).json()["parade_night_id"]

    made = client.post(f"/api/planning/parade-dates/{date_id}/notices", headers=hdr,
                       json={"notice_text": "Notice written in PW"})
    assert made.status_code in (200, 201), made.text

    tms = client.get(f"/api/parade-nights/{pn_id}/notices", headers=hdr)
    assert tms.status_code == 200, tms.text
    body = tms.json()
    items = body if isinstance(body, list) else body.get("notices", [])
    texts = [n.get("notice_text") or n.get("text") for n in items]
    assert "Notice written in PW" in texts, (
        f"a notice added in the Planning Workspace is not on the TMS parade "
        f"night: {texts}"
    )
