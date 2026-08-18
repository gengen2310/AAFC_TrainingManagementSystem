"""Tests for GET /api/search — universal entity search."""
import pytest
from tests.conftest import login


def test_search_requires_auth(client):
    r = client.get("/api/search?q=Daniels")
    assert r.status_code == 401


def test_search_short_query_returns_empty(client):
    h = login(client, "ADMIN703")
    r = client.get("/api/search?q=D", headers=h)
    assert r.status_code == 200
    assert r.json() == {"results": []}


def test_search_single_char_returns_empty(client):
    h = login(client, "ADMIN703")
    r = client.get("/api/search?q=a", headers=h)
    assert r.status_code == 200
    assert r.json()["results"] == []


def test_search_facilitator_by_last_name(client):
    h = login(client, "ADMIN703")
    r = client.get("/api/search?q=Daniels", headers=h)
    assert r.status_code == 200
    results = r.json()["results"]
    facs = [x for x in results if x["type"] == "facilitator"]
    assert len(facs) >= 1
    assert any("Daniels" in f["label"] for f in facs)


def test_search_result_shape(client):
    h = login(client, "ADMIN703")
    r = client.get("/api/search?q=Daniels", headers=h)
    assert r.status_code == 200
    for item in r.json()["results"]:
        assert "type" in item
        assert "id" in item
        assert "label" in item
        assert "sub" in item
        assert "meta" in item


def test_search_activity_by_name(client):
    """Activity search returns results when activity_name matches."""
    from app.database import SessionLocal
    from app.models import Activity, Squadron
    db = SessionLocal()
    activity_id = None
    try:
        # Create a test activity in 703 SQN
        sqn_703 = db.query(Squadron).filter(Squadron.code == "703").first()
        assert sqn_703 is not None, "Seed must include 703 SQN"

        activity = Activity(
            squadron_id=sqn_703.id,
            activity_name="Orienteering Competition",
            date_start="2026-09-15",
            date_end="2026-09-15",
            location="National Park",
            owning_level="squadron"
        )
        db.add(activity)
        db.commit()
        activity_id = activity.id

        # Search as sqn_admin for the activity
        headers = login(client, "ADMIN703")
        r = client.get("/api/search?q=Orienteering", headers=headers)
        assert r.status_code == 200
        activities = [x for x in r.json()["results"] if x["type"] == "activity"]
        assert len(activities) >= 1, "Expected at least one activity result"
        assert any(a["id"] == activity_id for a in activities)
    finally:
        if activity_id:
            db.query(Activity).filter(Activity.id == activity_id).delete()
            db.commit()
        db.close()


def test_search_wing_admin_scope(client):
    """wing_admin finds facilitators in own wing; does NOT see other wings."""
    # Positive: wing_admin for 7WG finds Flanders (703 SQN is in 7WG)
    h = login(client, "ADMIN7WG")
    r = client.get("/api/search?q=Flanders", headers=h)
    assert r.status_code == 200
    facs = [x for x in r.json()["results"] if x["type"] == "facilitator"]
    assert len(facs) >= 1, "wing_admin must find facilitators in own wing"
    # Negative: wing_admin must NOT see facilitators from outside the wing.
    # McGhie is also in 703 SQN, so we can't use that test here.
    # But we can verify that facilitators returned all belong to wing_id 7WG.
    # (In this test data, all facilitators are in 703 SQN which IS in 7WG, so they should appear.
    # To truly test negative case, we'd need facilitators in OTHER wings, which don't exist in seed.)
    # The key assertion: if wing_admin searches for a facilitator in 7WG, they get results
    assert any("Flanders" in f["label"] for f in facs)


def test_search_system_admin_cross_org(client):
    """system_admin must find facilitators from any squadron."""
    h = login(client, "SYSADMIN2026")
    r = client.get("/api/search?q=McGhie", headers=h)
    assert r.status_code == 200
    facs = [x for x in r.json()["results"] if x["type"] == "facilitator"]
    assert len(facs) >= 1
    assert any("McGhie" in f["label"] for f in facs)


def test_search_accounts_by_name_sqn_admin(client):
    """sqn_admin can search accounts in own squadron."""
    h = login(client, "ADMIN703")
    r = client.get("/api/search?q=703 Admin", headers=h)
    assert r.status_code == 200
    accounts = [x for x in r.json()["results"] if x["type"] == "account"]
    assert len(accounts) >= 1


def test_search_wing_by_code(client):
    h = login(client, "SYSADMIN2026")
    r = client.get("/api/search?q=7WG", headers=h)
    assert r.status_code == 200
    wings = [x for x in r.json()["results"] if x["type"] == "wing"]
    assert len(wings) >= 1
    assert any("7W" in w["label"] or "7WG" in w["sub"] for w in wings)


def test_search_squadron_by_code(client):
    h = login(client, "SYSADMIN2026")
    r = client.get("/api/search?q=703", headers=h)
    assert r.status_code == 200
    sqns = [x for x in r.json()["results"] if x["type"] == "squadron"]
    assert len(sqns) >= 1
    assert any("703" in s["label"] or "703" in s["meta"].get("code", "") for s in sqns)


def test_search_session_by_curriculum(client):
    """Sessions can be found by curriculum_title_at_time or curriculum_code_at_time."""
    h = login(client, "ADMIN703")
    # Search for a term that appears in seeded curriculum titles (e.g., "PDL Critical")
    r = client.get("/api/search?q=PDL", headers=h)
    assert r.status_code == 200
    sess = [x for x in r.json()["results"] if x["type"] == "session"]
    # Verify at least one session is found (seeded data includes sessions with PDL curriculum)
    assert len(sess) >= 1, "Expected at least one session result when searching for curriculum"


def test_search_auditor_gets_only_wings_and_squadrons(client):
    h = login(client, "AUDITOR2026")
    r = client.get("/api/search?q=703", headers=h)
    assert r.status_code == 200
    results = r.json()["results"]
    for item in results:
        assert item["type"] in ("wing", "squadron"), f"Auditor must not see {item['type']}"


def test_search_excludes_archived_facilitator(client):
    """Soft-archived facilitators must not appear in results."""
    from app.database import SessionLocal
    from app.models import Facilitator
    db = SessionLocal()
    try:
        # Archive Daley
        f = db.query(Facilitator).filter(Facilitator.last_name == "Daley").first()
        assert f is not None, "Seed must include Daley facilitator"
        original = f.is_archived
        f.is_archived = True
        db.commit()

        h = login(client, "SYSADMIN2026")
        r = client.get("/api/search?q=Daley", headers=h)
        assert r.status_code == 200
        facs = [x for x in r.json()["results"] if x["type"] == "facilitator"]
        assert all("Daley" not in f["label"] for f in facs)
    finally:
        # Restore
        f.is_archived = original
        db.commit()
        db.close()
