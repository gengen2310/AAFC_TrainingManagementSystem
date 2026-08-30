"""T5 regression tests: training router cleanup — planning_year_id wired, bridge helpers removed."""
from conftest import login, next_test_year


def test_create_parade_sets_planning_year_id(client):
    """POST /api/parade-nights must return a night with planning_year_id set."""
    headers = login(client, "ADMIN703")
    year = next_test_year()
    date = f"{year}-07-15"
    body = {"date": date, "parade_type": "normal"}
    r = client.post("/api/parade-nights", headers=headers, json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert "parade_night_id" in data
    # Fetch the created night and confirm planning_year_id is set
    night_r = client.get(f"/api/parade-nights/{data['parade_night_id']}", headers=headers)
    assert night_r.status_code == 200, night_r.text
    pn = night_r.json()
    assert pn.get("planning_year_id") is not None


def test_create_parade_no_linked_to_planning_year(client):
    """linked_to_planning_year must be absent from create_parade response."""
    headers = login(client, "ADMIN703")
    year = next_test_year()
    date = f"{year}-07-16"
    body = {"date": date, "parade_type": "normal"}
    r = client.post("/api/parade-nights", headers=headers, json=body)
    assert r.status_code == 200, r.text
    assert "linked_to_planning_year" not in r.json()


def test_year_for_date_removed():
    """_year_for_date must not be importable from training router."""
    import importlib
    m = importlib.import_module("app.routers.training")
    assert not hasattr(m, "_year_for_date"), "_year_for_date should be deleted"
    assert not hasattr(m, "_find_or_create_parade_date_for_night"), \
        "_find_or_create_parade_date_for_night should be deleted"
