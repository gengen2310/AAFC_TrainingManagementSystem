"""Tests for TRGO Workflow v30 features:
- Training Command Centre endpoint
- Activity Calendar with audience/priority filtering
- Activity classification (PATCH)
- Local lessons CRUD and seed-defaults
"""
import pytest
from tests.conftest import login


def _sqn_admin(client):
    return login(client, "ADMIN703")


def _wing_admin(client):
    return login(client, "ADMIN7WG")


def _sys_admin(client):
    return login(client, "SYSADMIN2026")


def _nat_admin(client):
    return login(client, "ADMINNATIONAL")


def _viewer(client):
    return login(client, "703SQN2026")


# ─────────────────────────────────────────────────────────────
# Training Command Centre
# ─────────────────────────────────────────────────────────────

def test_command_centre_returns_200_for_sqn_admin(client):
    hdr = _sqn_admin(client)
    r = client.get("/api/planning/command-centre", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert "summary" in d
    assert "upcoming_anchors" in d
    assert "prep_gaps" in d
    assert "unreviewed_wing_events" in d
    assert "active_conflicts" in d
    assert "unfacilitated_sessions" in d


def test_command_centre_summary_has_required_keys(client):
    hdr = _sqn_admin(client)
    r = client.get("/api/planning/command-centre", headers=hdr)
    assert r.status_code == 200
    s = r.json()["summary"]
    for key in ("upcoming_anchors", "prep_gaps", "unreviewed_wing_events",
                "active_conflicts", "parade_nights_missing_facilitators"):
        assert key in s, f"missing summary key: {key}"


def test_command_centre_returns_200_for_wing_admin(client):
    hdr = _wing_admin(client)
    r = client.get("/api/planning/command-centre", headers=hdr)
    assert r.status_code == 200


def test_command_centre_viewer_can_access(client):
    hdr = _viewer(client)
    r = client.get("/api/planning/command-centre", headers=hdr)
    assert r.status_code == 200


def test_command_centre_unauthenticated_blocked(client):
    r = client.get("/api/planning/command-centre")
    assert r.status_code == 401


def test_command_centre_with_year_id(client):
    hdr = _sqn_admin(client)
    # Create a planning year first
    r_year = client.post("/api/planning/years", json={"year": 2031, "term_count": 4},
                         headers=hdr)
    if r_year.status_code in (200, 201):
        year_id = r_year.json().get("planning_year_id") or r_year.json().get("id")
        if year_id:
            r = client.get(f"/api/planning/command-centre?year_id={year_id}", headers=hdr)
            assert r.status_code == 200


# ─────────────────────────────────────────────────────────────
# Activity Calendar — list and filter
# ─────────────────────────────────────────────────────────────

def test_list_activities_returns_200(client):
    hdr = _sqn_admin(client)
    r = client.get("/api/planning/activities", headers=hdr)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_list_activities_wing_admin(client):
    hdr = _wing_admin(client)
    r = client.get("/api/planning/activities", headers=hdr)
    assert r.status_code == 200


def test_list_activities_unauthenticated_blocked(client):
    r = client.get("/api/planning/activities")
    assert r.status_code == 401


def test_list_activities_filter_by_importance(client):
    hdr = _sqn_admin(client)
    r = client.get("/api/planning/activities?planning_importance=must_attend", headers=hdr)
    assert r.status_code == 200
    items = r.json()
    for item in items:
        assert item["planning_importance"] == "must_attend"


def test_list_activities_filter_by_date_range(client):
    hdr = _sqn_admin(client)
    r = client.get("/api/planning/activities?start_date=2030-01-01&end_date=2030-12-31", headers=hdr)
    assert r.status_code == 200
    items = r.json()
    for item in items:
        assert item["date_start"] >= "2030-01-01"
        assert item["date_start"] <= "2030-12-31"


def test_activity_classify_sets_importance(client):
    hdr = _sqn_admin(client)
    # Create an activity to classify
    import uuid
    from app.database import SessionLocal, utcnow
    from app.models.training import Activity
    from app.models.organisations import Squadron
    db = SessionLocal()
    try:
        sqn = db.query(Squadron).filter(Squadron.code == "703").first()
        if not sqn:
            pytest.skip("703 squadron not seeded")
        act = Activity(
            id=str(uuid.uuid4()), squadron_id=sqn.id, wing_id=sqn.wing_id,
            owning_level="squadron", activity_name="Test CEA Activity",
            activity_type="cea_import", date_start="2029-09-01",
            created_at=utcnow(), updated_at=utcnow(),
        )
        db.add(act); db.commit()
        act_id = act.id
    finally:
        db.close()

    r = client.patch(f"/api/planning/activities/{act_id}/classify", headers=hdr,
                     json={"planning_importance": "must_attend", "importance_level": 1,
                           "audience": ["first_years", "seniors"]})
    assert r.status_code == 200
    d = r.json()
    assert d["planning_importance"] == "must_attend"
    assert d["importance_level"] == 1
    assert "first_years" in d["audience"]


def test_activity_classify_rejects_invalid_importance(client):
    hdr = _sqn_admin(client)
    import uuid
    from app.database import SessionLocal, utcnow
    from app.models.training import Activity
    from app.models.organisations import Squadron
    db = SessionLocal()
    try:
        sqn = db.query(Squadron).filter(Squadron.code == "703").first()
        if not sqn:
            pytest.skip("703 squadron not seeded")
        act = Activity(
            id=str(uuid.uuid4()), squadron_id=sqn.id, wing_id=sqn.wing_id,
            owning_level="squadron", activity_name="Classify Validation Test",
            activity_type="cea_import", date_start="2029-10-01",
            created_at=utcnow(), updated_at=utcnow(),
        )
        db.add(act); db.commit()
        act_id = act.id
    finally:
        db.close()

    r = client.patch(f"/api/planning/activities/{act_id}/classify", headers=hdr,
                     json={"planning_importance": "super_important"})
    assert r.status_code == 422


def test_activity_classify_other_sqn_blocked(client):
    hdr = _sqn_admin(client)
    import uuid
    from app.database import SessionLocal, utcnow
    from app.models.training import Activity
    from app.models.organisations import Squadron
    db = SessionLocal()
    try:
        # Find a different squadron
        other_sqn = db.query(Squadron).filter(Squadron.code != "703").first()
        if not other_sqn:
            pytest.skip("No other squadron seeded")
        act = Activity(
            id=str(uuid.uuid4()), squadron_id=other_sqn.id, wing_id=other_sqn.wing_id,
            owning_level="squadron", activity_name="Other Sqn Activity",
            activity_type="cea_import", date_start="2029-11-01",
            created_at=utcnow(), updated_at=utcnow(),
        )
        db.add(act); db.commit()
        act_id = act.id
    finally:
        db.close()

    r = client.patch(f"/api/planning/activities/{act_id}/classify", headers=hdr,
                     json={"planning_importance": "must_attend"})
    assert r.status_code == 403


# ─────────────────────────────────────────────────────────────
# Local Lessons
# ─────────────────────────────────────────────────────────────

def test_list_local_lessons_returns_200(client):
    hdr = _sqn_admin(client)
    r = client.get("/api/planning/local-lessons", headers=hdr)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_list_local_lessons_unauthenticated_blocked(client):
    r = client.get("/api/planning/local-lessons")
    assert r.status_code == 401


def test_seed_defaults_requires_nat_or_system(client):
    hdr = _sqn_admin(client)
    r = client.post("/api/planning/local-lessons/seed-defaults", headers=hdr)
    assert r.status_code == 403


def test_seed_defaults_as_system_admin(client):
    hdr = _sys_admin(client)
    r = client.post("/api/planning/local-lessons/seed-defaults", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    assert isinstance(d["created"], list)


def test_seed_defaults_idempotent(client):
    hdr = _sys_admin(client)
    r1 = client.post("/api/planning/local-lessons/seed-defaults", headers=hdr)
    assert r1.status_code == 200
    r2 = client.post("/api/planning/local-lessons/seed-defaults", headers=hdr)
    assert r2.status_code == 200
    # Second call: nothing new created
    assert r2.json()["created"] == []


def test_list_local_lessons_shows_templates_after_seed(client):
    hdr_sys = _sys_admin(client)
    client.post("/api/planning/local-lessons/seed-defaults", headers=hdr_sys)

    hdr = _sqn_admin(client)
    r = client.get("/api/planning/local-lessons", headers=hdr)
    assert r.status_code == 200
    codes = [ll["lesson_code"] for ll in r.json()]
    for code in ("Skills-01", "Skills-02", "Skills-03", "Skills-13", "Skills-14"):
        assert code in codes, f"{code} missing after seed"


def test_sqn_admin_can_create_custom_local_lesson(client):
    hdr = _sqn_admin(client)
    r = client.post("/api/planning/local-lessons", headers=hdr, json={
        "lesson_code": "Skills-Custom-1",
        "lesson_name": "Pre-Fieldcraft Safety Briefing",
        "subject_area": "Field",
        "default_duration_mins": 30,
    })
    assert r.status_code == 200
    d = r.json()
    assert d["lesson_code"] == "Skills-Custom-1"
    assert d["lesson_name"] == "Pre-Fieldcraft Safety Briefing"
    assert d["is_template"] is False


def test_sqn_admin_can_update_custom_local_lesson(client):
    hdr = _sqn_admin(client)
    r_create = client.post("/api/planning/local-lessons", headers=hdr, json={
        "lesson_code": "Skills-Custom-2",
        "lesson_name": "Original Name",
    })
    assert r_create.status_code == 200
    ll_id = r_create.json()["local_lesson_id"]

    r_patch = client.patch(f"/api/planning/local-lessons/{ll_id}", headers=hdr,
                           json={"lesson_name": "Updated Name", "default_duration_mins": 45})
    assert r_patch.status_code == 200
    assert r_patch.json()["lesson_name"] == "Updated Name"
    assert r_patch.json()["default_duration_mins"] == 45


def test_sqn_admin_can_delete_own_custom_lesson(client):
    hdr = _sqn_admin(client)
    r_create = client.post("/api/planning/local-lessons", headers=hdr, json={
        "lesson_code": "Skills-Custom-3",
        "lesson_name": "To Delete",
    })
    assert r_create.status_code == 200
    ll_id = r_create.json()["local_lesson_id"]

    r_del = client.delete(f"/api/planning/local-lessons/{ll_id}", headers=hdr)
    assert r_del.status_code == 200
    assert r_del.json()["ok"] is True

    # Should no longer appear in list
    r_list = client.get("/api/planning/local-lessons", headers=hdr)
    assert not any(ll["local_lesson_id"] == ll_id for ll in r_list.json())


def test_viewer_cannot_create_local_lesson(client):
    hdr = _viewer(client)
    r = client.post("/api/planning/local-lessons", headers=hdr, json={
        "lesson_code": "Skills-Viewer",
        "lesson_name": "Should Fail",
    })
    assert r.status_code == 403


def test_wing_admin_can_list_local_lessons(client):
    hdr = _wing_admin(client)
    r = client.get("/api/planning/local-lessons", headers=hdr)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
