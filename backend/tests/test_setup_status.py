"""Phase 3.5: GET /api/setup/status -- read-only aggregation feeding the
frontend "Getting Started" stepper. No writes, no new backend infrastructure
beyond this endpoint (per the plan).
"""
from tests.conftest import login


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


def test_steps_list_scoped_to_squadron_only_for_sqn_admin(client):
    hdr = _sqn_admin_703(client)
    r = client.get("/api/setup/status", headers=hdr)
    d = r.json()
    step_keys = {s["key"] for s in d["steps"]}
    assert step_keys == {
        "facilitators_added", "training_areas_added", "timing_template_confirmed",
        "holidays_configured", "cea_imported", "parade_nights_generated", "curriculum_coverage",
    }


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
    # hdr is system_admin, so d["steps"] also includes the national block's
    # steps (wings_created/squadrons_created) -- correctly done=True, since
    # wings/squadrons already exist globally from the seed data. Only this
    # brand-new squadron's OWN steps should all be pending.
    squadron_step_keys = {"facilitators_added", "training_areas_added", "timing_template_confirmed",
                          "holidays_configured", "cea_imported", "parade_nights_generated", "curriculum_coverage"}
    assert all(not s["done"] for s in d["steps"] if s["key"] in squadron_step_keys)


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

    year_id = client.post("/api/planning/years", json={
        "year": 2099, "name": "Holiday Setup Test Year", "unit_id": sqn_id,
    }, headers=hdr).json()["planning_year_id"]
    client.post(f"/api/planning/years/{year_id}/holidays", json={
        "name": "Test School Holidays", "start_date": "2099-04-01", "end_date": "2099-04-14",
    }, headers=hdr)

    d1 = client.get(f"/api/setup/status?squadron_id={sqn_id}", headers=hdr).json()
    assert d1["squadron"]["holidays_configured"] is True
    step = next(s for s in d1["steps"] if s["key"] == "holidays_configured")
    assert step["done"] is True


def test_setup_status_unauthenticated(client):
    r = client.get("/api/setup/status")
    assert r.status_code == 401
