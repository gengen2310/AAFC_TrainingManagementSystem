"""Phase 3.5: GET /api/setup/status -- read-only aggregation feeding the
frontend "Getting Started" stepper. No writes, no new backend infrastructure
beyond this endpoint (per the plan).
"""
from tests.conftest import login, next_test_year


def _sysadmin(client):
    return login(client, "SYSADMIN2026")


def _nat_admin(client):
    return login(client, "ADMINNATIONAL")


def _sqn_admin_703(client):
    return login(client, "ADMIN703")


def _sqn_id_by_code(client, hdr, code):
    r = client.get("/api/squadrons", headers=hdr)
    for s in r.json():
        if s["code"] == code:
            return s["squadron_id"]
    raise AssertionError(f"squadron {code} not found")


def test_national_admin_sees_national_block(client):
    hdr = _nat_admin(client)
    r = client.get("/api/setup/status", headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["national"] is not None
    assert d["national"]["wings_created"] >= 1
    assert d["national"]["squadrons_created"] >= 1
    step_keys = {s["key"] for s in d["steps"]}
    assert "wings_created" in step_keys
    assert "squadrons_created" in step_keys


def test_sqn_admin_sees_squadron_block_not_national(client):
    hdr = _sqn_admin_703(client)
    r = client.get("/api/setup/status", headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["national"] is None
    assert d["squadron"] is not None
    assert d["squadron"]["squadron_code"] == "703"


def test_squadron_block_facilitator_count_matches_real_count(client):
    hdr = _sqn_admin_703(client)
    facs = client.get("/api/facilitators", headers=hdr).json()
    r = client.get("/api/setup/status", headers=hdr)
    d = r.json()
    assert d["squadron"]["facilitators_added"] == len(facs)


def test_squadron_block_timing_template_confirmed_true_for_seeded_703(client):
    hdr = _sqn_admin_703(client)
    r = client.get("/api/setup/status", headers=hdr)
    d = r.json()
    assert d["squadron"]["timing_template_confirmed"] is True


_SQUADRON_STEP_KEYS = {
    "planning_year_active", "training_classes_created", "facilitators_added", "training_areas_added",
    "equipment_added", "timing_template_confirmed", "crest_set", "cadets_added", "holidays_configured",
    "cea_imported", "activities_classified", "anchor_events_reviewed", "parade_nights_generated",
    "parade_night_published", "curriculum_coverage",
    "sessions_have_periods",   # added 2026-08-23
}


def test_steps_list_scoped_to_squadron_only_for_sqn_admin(client):
    hdr = _sqn_admin_703(client)
    r = client.get("/api/setup/status", headers=hdr)
    d = r.json()
    step_keys = {s["key"] for s in d["steps"]}
    assert step_keys == _SQUADRON_STEP_KEYS
    assert len(d["steps"]) == 16  # 15 original + training_classes_created + sessions_have_periods,
                                  # minus flights_created (removed 2026-08-25 at user request)


def test_flights_step_is_no_longer_in_the_checklist(client):
    """Removed 2026-08-25 at the user's request: "remove - Organise cadets into
    flights (0)".

    Flight is a local cadet-organisation grouping, not a tenancy level and not a
    setup prerequisite (Flight model docstring, architecture.md). Listing it as a
    step -- even an optional one -- implied it was part of getting set up.
    """
    d = client.get("/api/setup/status", headers=_sqn_admin_703(client)).json()
    keys = {st["key"] for st in d["steps"]}
    assert "flights_created" not in keys, "the flights step should no longer be a checklist item"


def test_removing_the_flights_step_did_not_remove_the_capability(client):
    """USER-AUTHORISED REMOVAL of a checklist step, not of a feature.

    703's seed has Alpha/Bravo flights. The count stays in the squadron block so
    anything reporting on flights still works, and the flights themselves are
    still managed in Unit Setup.
    """
    hdr = _sqn_admin_703(client)
    d = client.get("/api/setup/status", headers=hdr).json()
    assert "flights_created" in d["squadron"], "the flights count must still be reported"
    assert d["squadron"]["flights_created"] >= 2

    r = client.get("/api/flights", headers=hdr)
    assert r.status_code == 200, "the flights endpoint must still serve"
    assert len(r.json()) >= 2, "the seeded flights must still exist"


def test_squadron_id_query_param_lets_national_admin_view_a_squadron(client):
    hdr = _nat_admin(client)
    sqn_id = _sqn_id_by_code(client, hdr, "703")
    r = client.get(f"/api/setup/status?squadron_id={sqn_id}", headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["squadron"] is not None
    assert d["squadron"]["squadron_code"] == "703"
    assert d["national"] is not None  # national_admin still gets both blocks


def test_squadron_id_query_param_404_for_bogus_id(client):
    hdr = _nat_admin(client)
    r = client.get("/api/setup/status?squadron_id=does-not-exist", headers=hdr)
    assert r.status_code == 404


def test_new_squadron_with_nothing_set_up_is_not_complete(client):
    hdr = _sysadmin(client)
    wing_id = client.post("/api/wings", json={"code": "STWG1", "name": "Setup Test Wing"}, headers=hdr).json()["wing_id"]
    sqn_id = client.post("/api/squadrons", json={"wing_id": wing_id, "code": "ST01", "name": "Setup Test Unit"},
                         headers=hdr).json()["squadron_id"]

    r = client.get(f"/api/setup/status?squadron_id={sqn_id}", headers=hdr)
    d = r.json()
    assert d["complete"] is False
    assert d["squadron"]["facilitators_added"] == 0
    assert d["squadron"]["timing_template_confirmed"] is False
    assert d["squadron"]["parade_nights_generated"] == 0
    assert d["squadron"]["curriculum_coverage_pct"] == 0.0
    assert d["squadron"]["planning_year_active"] is False
    assert d["squadron"]["crest_set"] is False
    assert d["squadron"]["equipment_added"] == 0
    assert d["squadron"]["cadets_added"] == 0
    assert d["squadron"]["activities_classified"] is False
    assert d["squadron"]["anchor_events_reviewed"] is False
    assert d["squadron"]["parade_night_published"] is False
    assert d["squadron"]["flights_created"] == 0
    # hdr is system_admin, so d["steps"] also includes the national block's
    # steps (wings_created/squadrons_created) -- correctly done=True, since
    # wings/squadrons already exist globally from the seed data. Only this
    # brand-new squadron's OWN steps should all be pending.
    assert all(not s["done"] for s in d["steps"] if s["key"] in _SQUADRON_STEP_KEYS)


def test_holidays_configured_false_until_a_holiday_exists_for_the_active_year(client):
    # A fresh squadron, not the seeded "703" -- 703's seed data already
    # includes WA holidays for its planning year, so it can't demonstrate the
    # "not yet configured" starting state.
    hdr = _sysadmin(client)
    wing_id = client.post("/api/wings", json={"code": "HOLWG1", "name": "Holiday Setup Test Wing"}, headers=hdr).json()["wing_id"]
    sqn_id = client.post("/api/squadrons", json={"wing_id": wing_id, "code": "HOL01", "name": "Holiday Setup Test Unit"},
                         headers=hdr).json()["squadron_id"]

    d0 = client.get(f"/api/setup/status?squadron_id={sqn_id}", headers=hdr).json()
    assert d0["squadron"]["holidays_configured"] is False

    # Creating a squadron-scoped plan year is a delegated write on that
    # squadron's data (Stage 10 remediation) -- system_admin needs Delegated
    # Intervention for it, same as any other squadron-scoped write.
    enter = client.post(f"/api/proxy/enter/{sqn_id}", json={"reason": "Holiday setup test"}, headers=hdr)
    assert enter.status_code == 200, enter.text
    year_id = client.post("/api/planning/years", json={
        "year": next_test_year(), "name": "Holiday Setup Test Year", "unit_id": sqn_id,
    }, headers=hdr).json()["planning_year_id"]
    client.post(f"/api/planning/years/{year_id}/holidays", json={
        "name": "Test School Holidays", "start_date": "2099-04-01", "end_date": "2099-04-14",
    }, headers=hdr)
    client.post("/api/proxy/exit", headers=hdr)

    d1 = client.get(f"/api/setup/status?squadron_id={sqn_id}", headers=hdr).json()
    assert d1["squadron"]["holidays_configured"] is True
    step = next(s for s in d1["steps"] if s["key"] == "holidays_configured")
    assert step["done"] is True


def test_cadets_added_count_matches_real_count_for_seeded_703(client):
    hdr = _sqn_admin_703(client)
    cadets = client.get("/api/cadets", headers=hdr).json()
    d = client.get("/api/setup/status", headers=hdr).json()
    assert d["squadron"]["cadets_added"] == len(cadets)
    assert d["squadron"]["cadets_added"] > 0  # 703's seed data includes cadets


def test_planning_year_active_true_for_seeded_703(client):
    hdr = _sqn_admin_703(client)
    d = client.get("/api/setup/status", headers=hdr).json()
    assert d["squadron"]["planning_year_active"] is True
    step = next(s for s in d["steps"] if s["key"] == "planning_year_active")
    assert step["done"] is True


def _fresh_squadron_with_active_year(client, hdr, wing_code, sqn_code):
    wing_id = client.post("/api/wings", json={"code": wing_code, "name": f"{wing_code} Setup Test"},
                          headers=hdr).json()["wing_id"]
    sqn_id = client.post("/api/squadrons", json={"wing_id": wing_id, "code": sqn_code, "name": f"{sqn_code} Setup Test"},
                         headers=hdr).json()["squadron_id"]
    enter = client.post(f"/api/proxy/enter/{sqn_id}", json={"reason": "Setup status test"}, headers=hdr)
    assert enter.status_code == 200, enter.text
    year_id = client.post("/api/planning/years", json={
        "year": next_test_year(), "name": f"{sqn_code} Setup Test Year", "unit_id": sqn_id,
    }, headers=hdr).json()["planning_year_id"]
    return sqn_id, year_id


def test_crest_set_true_once_a_crest_url_is_saved(client):
    hdr = _sysadmin(client)
    sqn_id, _ = _fresh_squadron_with_active_year(client, hdr, "CRWG1", "CR01")
    d0 = client.get(f"/api/setup/status?squadron_id={sqn_id}", headers=hdr).json()
    assert d0["squadron"]["crest_set"] is False

    r = client.patch(f"/api/squadrons/{sqn_id}", json={"crest_url": "https://example.invalid/crest.png"}, headers=hdr)
    assert r.status_code == 200, r.text
    client.post("/api/proxy/exit", headers=hdr)

    d1 = client.get(f"/api/setup/status?squadron_id={sqn_id}", headers=hdr).json()
    assert d1["squadron"]["crest_set"] is True
    step = next(s for s in d1["steps"] if s["key"] == "crest_set")
    assert step["done"] is True


def test_equipment_added_count_matches_created_equipment(client):
    hdr = _sysadmin(client)
    sqn_id, _ = _fresh_squadron_with_active_year(client, hdr, "EQWG1", "EQ01")
    d0 = client.get(f"/api/setup/status?squadron_id={sqn_id}", headers=hdr).json()
    assert d0["squadron"]["equipment_added"] == 0

    r = client.post("/api/equipment", json={"name": "Test Radio", "type": "comms", "quantity": 2}, headers=hdr)
    assert r.status_code == 200, r.text
    client.post("/api/proxy/exit", headers=hdr)

    d1 = client.get(f"/api/setup/status?squadron_id={sqn_id}", headers=hdr).json()
    assert d1["squadron"]["equipment_added"] == 1
    step = next(s for s in d1["steps"] if s["key"] == "equipment_added")
    assert step["done"] is True


def test_activities_classified_true_once_an_activity_has_type_and_audience(client):
    hdr = _sysadmin(client)
    sqn_id, _ = _fresh_squadron_with_active_year(client, hdr, "ACWG1", "AC01")

    # An activity missing either activity_type or audience must NOT count --
    # matches the reported symptom's "priority/audience" framing, which is
    # about both being classified, not just an activity existing at all.
    r0 = client.post("/api/activities", json={
        "activity_name": "Unclassified Activity", "date_start": "2099-06-01",
    }, headers=hdr)
    assert r0.status_code == 200, r0.text
    d0 = client.get(f"/api/setup/status?squadron_id={sqn_id}", headers=hdr).json()
    assert d0["squadron"]["activities_classified"] is False

    r1 = client.post("/api/activities", json={
        "activity_name": "Classified Activity", "activity_type": "Key Event",
        "date_start": "2099-06-08", "audience": ["senior"],
    }, headers=hdr)
    assert r1.status_code == 200, r1.text
    client.post("/api/proxy/exit", headers=hdr)

    d1 = client.get(f"/api/setup/status?squadron_id={sqn_id}", headers=hdr).json()
    assert d1["squadron"]["activities_classified"] is True
    step = next(s for s in d1["steps"] if s["key"] == "activities_classified")
    assert step["done"] is True


def test_anchor_events_reviewed_true_once_an_anchor_event_exists_for_active_year(client):
    hdr = _sysadmin(client)
    sqn_id, year_id = _fresh_squadron_with_active_year(client, hdr, "ANWG1", "AN01")
    d0 = client.get(f"/api/setup/status?squadron_id={sqn_id}", headers=hdr).json()
    assert d0["squadron"]["anchor_events_reviewed"] is False

    r = client.post(f"/api/planning/years/{year_id}/anchors", json={
        "event_name": "Test Anchor Event", "start_date": "2099-07-01",
    }, headers=hdr)
    assert r.status_code == 200, r.text
    client.post("/api/proxy/exit", headers=hdr)

    d1 = client.get(f"/api/setup/status?squadron_id={sqn_id}", headers=hdr).json()
    assert d1["squadron"]["anchor_events_reviewed"] is True
    step = next(s for s in d1["steps"] if s["key"] == "anchor_events_reviewed")
    assert step["done"] is True


def test_parade_night_published_true_once_a_parade_night_is_published(client):
    hdr = _sysadmin(client)
    sqn_id, _ = _fresh_squadron_with_active_year(client, hdr, "PBWG1", "PB01")
    d0 = client.get(f"/api/setup/status?squadron_id={sqn_id}", headers=hdr).json()
    assert d0["squadron"]["parade_night_published"] is False
    assert d0["squadron"]["parade_nights_generated"] == 0

    pn_id = client.post("/api/parade-nights", json={
        "squadron_id": sqn_id, "date": "2099-08-01",
    }, headers=hdr).json()["parade_night_id"]

    d1 = client.get(f"/api/setup/status?squadron_id={sqn_id}", headers=hdr).json()
    assert d1["squadron"]["parade_nights_generated"] == 1
    assert d1["squadron"]["parade_night_published"] is False  # generated, not yet published

    # publish_blockers() requires every session to have a title, a
    # facilitator, and a room -- a bare parade night with no sessions (or an
    # incomplete one) is correctly refused, so this recipe builds a fully
    # detailed session before publishing.
    fac_id = client.post("/api/facilitators", json={"last_name": "Test Facilitator"}, headers=hdr).json()["facilitator_id"]
    room_id = client.post("/api/training-areas", json={"name": "Test Room"}, headers=hdr).json()["training_area_id"]
    sess_id = client.post("/api/sessions", json={
        "parade_night_id": pn_id, "period_number": 1, "custom_title": "Test Session",
        "facilitator_id": fac_id, "training_area_id": room_id,
    }, headers=hdr).json()["session_id"]
    assert sess_id

    pub = client.post(f"/api/parade-nights/{pn_id}/publish", headers=hdr)
    assert pub.status_code == 200, pub.text
    client.post("/api/proxy/exit", headers=hdr)

    d2 = client.get(f"/api/setup/status?squadron_id={sqn_id}", headers=hdr).json()
    assert d2["squadron"]["parade_night_published"] is True
    step = next(s for s in d2["steps"] if s["key"] == "parade_night_published")
    assert step["done"] is True


def test_setup_status_unauthenticated(client):
    r = client.get("/api/setup/status")
    assert r.status_code == 401


# ── 2026-08-23 audit of the Getting Started checklist ────────────────────────

def _steps(client, hdr):
    r = client.get("/api/setup/status", headers=hdr)
    assert r.status_code == 200, r.text
    return {st["key"]: st for st in r.json()["steps"]}


def test_curriculum_step_is_done_once_scheduling_has_started(client):
    # Coverage counts every curriculum item VISIBLE to the squadron, which is the
    # whole national curriculum across all Training Stages. A fully seeded 703 SQN
    # measures well under 100%, so requiring 100% made the step unreachable -- and
    # since `complete` is an AND over the non-optional steps, it made the whole
    # checklist unreachable for everyone.
    steps = _steps(client, _sqn_admin_703(client))
    cov = steps["curriculum_coverage"]
    assert 0 < cov["count"] < 100, f"expected partial coverage on seeded data, got {cov['count']}"
    assert cov["done"] is True, "scheduling has started, so the step should be done"


def test_a_squadron_that_has_scheduled_nothing_has_the_curriculum_step_pending(client):
    hdr = _sysadmin(client)
    wing_id = client.get("/api/wings", headers=hdr).json()[0]["wing_id"]
    r = client.post("/api/squadrons",
                    json={"code": "GS1", "name": "Getting Started Check 1", "wing_id": wing_id},
                    headers=hdr)
    assert r.status_code in (200, 201), r.text
    sq_id = r.json().get("squadron_id") or r.json().get("id")
    steps = {st["key"]: st
             for st in client.get(f"/api/setup/status?squadron_id={sq_id}", headers=hdr).json()["steps"]}
    assert steps["curriculum_coverage"]["done"] is False
    assert steps["curriculum_coverage"]["count"] == 0


def test_the_session_period_step_exists_and_links_to_parade_nights(client):
    # A session with no program period never reaches the Weekly Program grid, so
    # a squadron can look fully planned and print a blank page.
    steps = _steps(client, _sqn_admin_703(client))
    assert "sessions_have_periods" in steps, "the session-period step is missing"
    step = steps["sessions_have_periods"]
    assert step["link_page"] == "parade-nights"
    assert step["label"] == "Assign sessions to program periods"
    assert isinstance(step["count"], int)


def test_session_period_step_agrees_with_the_underlying_counts(client):
    # Not "all seeded sessions have a period": other tests in the suite create
    # sessions without one, and the database is seeded once per session, so that
    # assertion is order-dependent. Test the rule instead of a snapshot.
    hdr = _sqn_admin_703(client)
    d = client.get("/api/setup/status", headers=hdr).json()
    sq = d["squadron"]
    step = {st["key"]: st for st in d["steps"]}["sessions_have_periods"]

    assert sq["sessions_total"] > 0, "seeded 703 should have sessions"
    assert sq["sessions_with_period"] > 0, "the seed sets timing_block_id on its sessions"
    assert step["count"] == sq["sessions_with_period"]
    assert step["done"] is (sq["sessions_total"] > 0
                            and sq["sessions_with_period"] == sq["sessions_total"])


def test_every_step_links_to_a_page_that_exists(client):
    # A checklist row is clickable; a row pointing at a page that does not exist
    # is a dead end rather than a nudge.
    import pathlib, re
    html = pathlib.Path(__file__).resolve().parents[2] / "connected-frontend" / "index.html"
    if not html.exists():
        import pytest
        pytest.skip("connected-frontend/index.html not present in this checkout")
    pages = set(re.findall(r'id="page-([a-z0-9-]+)"', html.read_text()))
    for key, st in _steps(client, _sqn_admin_703(client)).items():
        assert st["link_page"] in pages, f"step {key} links to missing page {st['link_page']}"


def test_step_labels_use_sentence_case(client):
    # The rest of the interface is sentence case; the checklist was Title Case.
    allowed = {"CEA", "Wing", "Squadron", "Training", "Stage"}
    for key, st in _steps(client, _sqn_admin_703(client)).items():
        words = st["label"].split()
        for w in words[1:]:
            stripped = w.strip(".,/&")
            if stripped and stripped[0].isupper() and stripped not in allowed:
                raise AssertionError(f"step {key} label is not sentence case: {st['label']!r}")


def test_timing_template_step_ignores_a_template_outside_its_effective_window(client):
    # The check used to count any non-archived template, so a squadron whose only
    # template had expired reported "confirmed" while _effective_template()
    # returned None and new parade nights got no timing at all.
    from app.database import SessionLocal
    from app.models import TimingTemplate

    hdr = _sqn_admin_703(client)
    assert _steps(client, hdr)["timing_template_confirmed"]["done"] is True

    db = SessionLocal()
    saved = []
    try:
        # /api/auth/me nests everything under "session".
        sq_id = client.get("/api/auth/me", headers=hdr).json()["session"]["squadron_id"]
        rows = db.query(TimingTemplate).filter(TimingTemplate.squadron_id == sq_id).all()
        assert rows, "expected the seeded 703 timing template"
        saved = [(t.id, t.effective_to) for t in rows]
        for t in rows:
            t.effective_to = "2000-01-01"      # expired
        db.commit()

        assert _steps(client, hdr)["timing_template_confirmed"]["done"] is False, \
            "an expired template must not read as confirmed"
    finally:
        for tid, original in saved:
            db.get(TimingTemplate, tid).effective_to = original
        db.commit()
        db.close()
    assert _steps(client, hdr)["timing_template_confirmed"]["done"] is True
