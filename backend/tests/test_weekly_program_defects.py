"""Targeted regression tests for three Weekly Program backend defects:

1. Class-grouping (cadet_group) derivation silently returned None for a
   session created against training_class_ids when the TrainingClass has a
   training_stage_id (a governed CurriculumPhase) but no legacy stage_code --
   the standard shape for classes created directly against the Training
   Phase catalogue rather than the five auto-created stage_code classes.

2. GET /api/parade-nights/{id}/planner ("Weekly Program" canonical payload)
   ignored the squadron's date-effective timing template for parade nights
   created with timing_template_id left null (e.g. via
   POST /api/planning/years/{id}/parade-dates, which never sets it), instead
   synthesising placeholder periods with no timing_block_id.

3. PATCH/POST /api/timing-templates accepted a blocks list containing two
   training_period blocks with the same (explicit or auto-assigned) period_number,
   producing an ambiguous template that downstream period_number-keyed lookups
   (session placement, planner block resolution) could not resolve deterministically.
"""
from tests.conftest import login, next_test_year


def _sqn_admin_hdr(client):
    return login(client, "ADMIN703")


def _make_year(client, hdr, year=None):
    """Create a planning year, retrying with a fresh year on a 409 collision.

    next_test_year() is meant to hand out a value no other test in this
    session has used, but this suite's tests are split between two import
    spellings of the same conftest.py -- `from conftest import ...` and
    `from tests.conftest import ...` -- which Python loads as two distinct
    module objects, each with its own independent `itertools.count(5000, 3)`.
    Both sequences start at the same value and advance in lockstep, so
    whichever one is behind in call count can land on a year the other
    sequence already claimed for the same squadron. Retrying on the specific
    409 this collision produces makes this file's tests deterministic
    regardless of what else in the suite has already run, without touching
    the other 130+ files' import style.
    """
    for _ in range(20):
        y = year if year is not None else next_test_year()
        r = client.post("/api/planning/years", json={"year": y, "name": f"{y} WP Defect Test Year"}, headers=hdr)
        if r.status_code == 409 and r.json().get("detail", {}).get("error") == "planning_year_already_exists":
            year = None  # force a fresh next_test_year() draw on retry
            continue
        assert r.status_code == 200, r.text
        return r.json()
    raise AssertionError("could not allocate a free planning year after 20 attempts")


def _make_stage(client, hdr, squadron_id, name):
    r = client.post("/api/curriculum/phases", json={
        "name": name, "display_name": name, "scope_level": "squadron", "squadron_id": squadron_id,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["phase_id"]


def _make_class(client, hdr, year_id, stage_id, name):
    r = client.post("/api/training-classes", json={
        "training_year_id": year_id, "training_stage_id": stage_id, "display_name": name,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["training_class_id"]


# ── Defect 1: class grouping derivation when stage_code is null ────────────

def test_session_created_against_governed_phase_class_gets_cadet_group(client):
    """A TrainingClass created against a governed CurriculumPhase (training_stage_id)
    but with no legacy stage_code must still resolve a cadet_group for the session
    grid, by matching the phase's name (e.g. "A. Orientation") to the cadet-group
    keyword it names -- not silently drop to None."""
    hdr = _sqn_admin_hdr(client)
    py = _make_year(client, hdr)
    rp = client.post(f"/api/planning/years/{py['planning_year_id']}/parade-dates",
                      json={"parade_date": f"{py['year']}-05-01"}, headers=hdr)
    assert rp.status_code == 200, rp.text
    pd_id = rp.json()["parade_date_id"]

    # A phase named after the "Junior" cadet group, with no stage_code assigned
    # to the class -- the governed-phase path this task's defect covers.
    stage_id = _make_stage(client, hdr, py["unit_id"], f"C. Junior WP-{py['year']}")
    class_id = _make_class(client, hdr, py["planning_year_id"], stage_id, "Junior Governed Class")

    r = client.post(f"/api/planning/parade-dates/{pd_id}/sessions", json={
        "training_class_ids": [class_id], "session_number": 1, "activity_title": "Governed Phase Session",
    }, headers=hdr)
    assert r.status_code == 200, r.text
    sess = r.json()
    assert sess["cadet_group"] == "junior", (
        "a session created against a governed-phase class with no stage_code "
        f"must still derive cadet_group='junior'; got {sess['cadet_group']!r}"
    )


def test_class_with_neither_stage_code_nor_matching_phase_name_leaves_cadet_group_none(client):
    """When the phase name matches none of the five cadet-group keywords, the
    derivation must fall back to None rather than guessing -- this is a
    best-effort denormalisation, not a hard requirement."""
    hdr = _sqn_admin_hdr(client)
    py = _make_year(client, hdr)
    rp = client.post(f"/api/planning/years/{py['planning_year_id']}/parade-dates",
                      json={"parade_date": f"{py['year']}-05-02"}, headers=hdr)
    assert rp.status_code == 200, rp.text
    pd_id = rp.json()["parade_date_id"]

    stage_id = _make_stage(client, hdr, py["unit_id"], f"Z. Unrelated Phase WP-{py['year']}")
    class_id = _make_class(client, hdr, py["planning_year_id"], stage_id, "Unrelated Phase Class")

    r = client.post(f"/api/planning/parade-dates/{pd_id}/sessions", json={
        "training_class_ids": [class_id], "session_number": 1, "activity_title": "Unrelated Phase Session",
    }, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["cadet_group"] is None


def test_mission_assignment_also_derives_cadet_group_from_governed_phase(client):
    """assign_mission (Training Planner action) shares the same derivation
    helper as create_session -- confirm it is not left on the old behaviour."""
    hdr = _sqn_admin_hdr(client)
    py = _make_year(client, hdr)
    rp = client.post(f"/api/planning/years/{py['planning_year_id']}/parade-dates",
                      json={"parade_date": f"{py['year']}-05-03"}, headers=hdr)
    assert rp.status_code == 200, rp.text
    pd_id = rp.json()["parade_date_id"]

    stage_id = _make_stage(client, hdr, py["unit_id"], f"E. Senior WP-{py['year']}")
    class_id = _make_class(client, hdr, py["planning_year_id"], stage_id, "Senior Governed Class")

    ci = client.get("/api/curriculum", headers=hdr).json()["items"]
    assert ci, "seed must provide at least one curriculum item"
    curriculum_id = ci[0]["curriculum_id"]

    r = client.post(f"/api/planning/years/{py['planning_year_id']}/assign-mission", json={
        "training_class_ids": [class_id], "curriculum_id": curriculum_id,
        "parade_date_id": pd_id, "session_number": 1,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["cadet_group"] == "senior"


# ── Defect 2: legacy null timing_template_id resolves date-effective template ─

def test_planner_resolves_date_effective_template_when_night_has_none_set(client):
    """A parade night created via POST /api/planning/years/{id}/parade-dates
    never sets timing_template_id (planning.py add_parade_date) and has no
    ParadeNightTimingSnapshot. If the squadron has a timing template whose
    effective range covers the night's date, the canonical planner payload
    must resolve it -- both the block list AND each instructional block's
    real timing_block_id -- rather than synthesising placeholder periods."""
    hdr = _sqn_admin_hdr(client)
    py = _make_year(client, hdr)
    year = py["year"]
    date_str = f"{year}-06-01"

    tmpl = client.post("/api/timing-templates", json={
        "name": f"WP Defect Template {year}",
        "effective_from": f"{year}-01-01",
        "blocks": [
            {"display_order": 0, "block_name": "Period 1", "block_type": "training_period",
             "period_number": 1, "start_time": "19:00", "end_time": "19:45"},
            {"display_order": 1, "block_name": "Period 2", "block_type": "training_period",
             "period_number": 2, "start_time": "19:50", "end_time": "20:35"},
        ],
    }, headers=hdr)
    assert tmpl.status_code == 200, tmpl.text
    tmpl_body = tmpl.json()
    real_block_ids = {b["period_number"]: b["timing_block_id"]
                      for b in tmpl_body["blocks"] if b["is_instructional_period"]}

    rp = client.post(f"/api/planning/years/{py['planning_year_id']}/parade-dates",
                      json={"parade_date": date_str}, headers=hdr)
    assert rp.status_code == 200, rp.text
    pn_id = rp.json()["parade_date_id"]

    # Confirm the fixture actually reproduces the defect precondition.
    nights = client.get("/api/parade-nights", headers=hdr).json()
    night = next(n for n in nights if n["parade_night_id"] == pn_id)
    assert night["timing_template_id"] is None, \
        "add_parade_date must not auto-assign a timing template"

    planner = client.get(f"/api/parade-nights/{pn_id}/planner", headers=hdr)
    assert planner.status_code == 200, planner.text
    body = planner.json()

    periods = {b["period_number"]: b for b in body["timing"]["blocks"] if b["is_instructional"]}
    assert set(periods) == {1, 2}, f"expected the template's 2 periods, got {body['timing']['blocks']}"
    for pnum, block_id in real_block_ids.items():
        assert periods[pnum]["timing_block_id"] == block_id, (
            f"period {pnum} must resolve to the date-effective template's real "
            f"timing_block_id ({block_id}), got {periods[pnum]['timing_block_id']!r}"
        )


def test_planner_still_synthesises_when_no_template_is_effective_at_all(client):
    """No explicit template and none date-effective either: the "bare legacy"
    synthesis path must still apply (no regression from the fix above)."""
    hdr = _sqn_admin_hdr(client)
    py = _make_year(client, hdr)
    # 703's seeded default template is effective_from 2000-01-01 with no
    # effective_to (see seed_all.py), so anything after that is covered.
    # Before it is the one date range still genuinely template-free.
    date_str = "1999-01-15"

    rp = client.post(f"/api/planning/years/{py['planning_year_id']}/parade-dates",
                      json={"parade_date": date_str}, headers=hdr)
    assert rp.status_code == 200, rp.text
    pn_id = rp.json()["parade_date_id"]

    planner = client.get(f"/api/parade-nights/{pn_id}/planner", headers=hdr)
    assert planner.status_code == 200, planner.text
    body = planner.json()
    assert body["timing"]["timing_template_name"] is None
    for b in body["timing"]["blocks"]:
        assert b.get("timing_block_id") is None


# ── Defect 3: duplicate period_number validation on template replacement ───

def test_creating_a_template_with_duplicate_explicit_period_numbers_is_rejected(client):
    hdr = _sqn_admin_hdr(client)
    year = next_test_year()
    r = client.post("/api/timing-templates", json={
        "name": f"Duplicate Period Template {year}",
        "effective_from": f"{year}-01-01",
        "blocks": [
            {"display_order": 0, "block_name": "Period 1", "block_type": "training_period",
             "period_number": 1, "start_time": "19:00", "end_time": "19:45"},
            {"display_order": 1, "block_name": "Period 1 Again", "block_type": "training_period",
             "period_number": 1, "start_time": "19:50", "end_time": "20:35"},
        ],
    }, headers=hdr)
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["error"] == "duplicate_period_number"


def test_replacing_a_templates_blocks_with_duplicate_period_numbers_is_rejected_and_old_blocks_survive(client):
    hdr = _sqn_admin_hdr(client)
    year = next_test_year()
    created = client.post("/api/timing-templates", json={
        "name": f"Replace Duplicate Template {year}",
        "effective_from": f"{year}-01-01",
        "blocks": [
            {"display_order": 0, "block_name": "Period 1", "block_type": "training_period",
             "period_number": 1, "start_time": "19:00", "end_time": "19:45"},
        ],
    }, headers=hdr)
    assert created.status_code == 200, created.text
    tid = created.json()["timing_template_id"]

    r = client.patch(f"/api/timing-templates/{tid}", json={
        "blocks": [
            {"display_order": 0, "block_name": "Period A", "block_type": "training_period",
             "period_number": 1, "start_time": "19:00", "end_time": "19:45"},
            {"display_order": 1, "block_name": "Period B", "block_type": "training_period",
             "period_number": 1, "start_time": "19:50", "end_time": "20:35"},
        ],
    }, headers=hdr)
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["error"] == "duplicate_period_number"

    # The rejected replacement must not have torn down the template's existing blocks.
    after = client.get(f"/api/timing-templates/{tid}", headers=hdr)
    assert after.status_code == 200, after.text
    blocks = after.json()["blocks"]
    assert len(blocks) == 1 and blocks[0]["block_name"] == "Period 1"


def test_missing_period_numbers_continue_after_highest_explicit_number(client):
    """A new training-period block added beside existing explicit periods gets
    the next free number instead of colliding with an already-saved period."""
    hdr = _sqn_admin_hdr(client)
    year = next_test_year()
    r = client.post("/api/timing-templates", json={
        "name": f"Auto Allocation Template {year}",
        "effective_from": f"{year}-01-01",
        "blocks": [
            {"display_order": 0, "block_name": "Explicit Period 2", "block_type": "training_period",
             "period_number": 2, "start_time": "19:00", "end_time": "19:45"},
            {"display_order": 1, "block_name": "Auto Period 3", "block_type": "training_period",
             "start_time": "19:50", "end_time": "20:35"},
            {"display_order": 2, "block_name": "Auto Period 4", "block_type": "training_period",
             "start_time": "20:40", "end_time": "21:25"},
        ],
    }, headers=hdr)
    assert r.status_code == 200, r.text
    periods = [b["period_number"] for b in r.json()["blocks"] if b["is_instructional_period"]]
    assert periods == [2, 3, 4]


def test_distinct_period_numbers_still_save_normally(client):
    """Sanity check: the new validation must not reject a perfectly ordinary,
    non-ambiguous set of blocks."""
    hdr = _sqn_admin_hdr(client)
    year = next_test_year()
    r = client.post("/api/timing-templates", json={
        "name": f"Valid Template {year}",
        "effective_from": f"{year}-01-01",
        "blocks": [
            {"display_order": 0, "block_name": "Period 1", "block_type": "training_period",
             "period_number": 1, "start_time": "19:00", "end_time": "19:45"},
            {"display_order": 1, "block_name": "Period 2", "block_type": "training_period",
             "period_number": 2, "start_time": "19:50", "end_time": "20:35"},
        ],
    }, headers=hdr)
    assert r.status_code == 200, r.text
    periods = sorted(b["period_number"] for b in r.json()["blocks"] if b["is_instructional_period"])
    assert periods == [1, 2]
