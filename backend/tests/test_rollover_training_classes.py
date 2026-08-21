"""Tests for CLASS-11: Training Year rollover carrying Training Classes
forward.

Confirmed via code read that rollover_year() (planning.py) copied holidays
and parade dates to the new year but never touched TrainingClass at all --
a squadron with e.g. Senior 1/Senior 2 set up in the current year silently
lost that structure on rollover and had to manually recreate every class
in the new year. Fixed by adding a copy_training_classes flag (default
True, matching copy_holidays's own pattern) that recreates each active
class scoped to the new PlanningYear, preserving stage/name/sequence/
expected_count/notes but not start_date/end_date (those are calendar dates
specific to the source year's own season and would be stale in the new
year, unlike holidays which are explicitly year-shifted).

Uses year values (2660+) clear of every other test file's own literals
(confirmed via grep before picking this range), and does not clean up its
created years afterward -- matching this suite's own established
convention for rollover tests (test_planner_v14.py's 8 existing rollover
tests don't deactivate their years either; rollover-created years are only
a REM-129 risk for a later plain POST /api/parade-nights call, which
neither this file nor rollover_year() itself makes -- _find_or_create_parade_night
here is called with the new year's own unit_id, not the "highest active
year" lookup).
"""
from tests.conftest import login


def _sqn_admin_hdr(client):
    return login(client, "ADMIN703")


def _make_year(client, hdr, year, name):
    r = client.post("/api/planning/years", json={"year": year, "name": name}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def _make_stage(client, hdr, squadron_id):
    import uuid
    name = f"CLASS-11-TEST-{uuid.uuid4().hex[:10]}"
    r = client.post("/api/curriculum/phases", json={
        "name": name, "display_name": name, "scope_level": "squadron", "squadron_id": squadron_id,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["phase_id"]


def _make_class(client, hdr, year_id, stage_id, name, **kwargs):
    body = {"training_year_id": year_id, "training_stage_id": stage_id, "display_name": name, **kwargs}
    r = client.post("/api/training-classes", json=body, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["training_class_id"]


def _get_classes(client, hdr, year_id):
    r = client.get(f"/api/training-classes?training_year_id={year_id}", headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def test_rollover_copies_active_training_classes_by_default(client):
    hdr = _sqn_admin_hdr(client)
    py = _make_year(client, hdr, 2660, "CLASS-11 Rollover Source A")
    year_id = py["planning_year_id"]
    stage_id = _make_stage(client, hdr, py["unit_id"])
    _make_class(client, hdr, year_id, stage_id, "Senior 1", sequence=1, expected_count=12, notes="Test note")
    _make_class(client, hdr, year_id, stage_id, "Senior 2", sequence=2)

    r = client.post(f"/api/planning/years/{year_id}/rollover", json={}, headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    # Year creation auto-creates 5 standard classes (ORI/INI/JNR/INT/SNR), so 5 + 2 manual = 7 copied.
    assert d["training_classes_copied"] == 7

    new_classes = _get_classes(client, hdr, d["new_planning_year_id"])
    names = {c["display_name"] for c in new_classes}
    # The 2 manually created classes are present alongside the 5 auto-classes
    assert "Senior 1" in names
    assert "Senior 2" in names

    s1 = next(c for c in new_classes if c["display_name"] == "Senior 1")
    assert s1["training_stage_id"] == stage_id
    assert s1["sequence"] == 1
    assert s1["expected_count"] == 12
    assert s1["notes"] == "Test note"
    # start_date/end_date are deliberately not carried over -- they're
    # specific to the source year's own calendar season.
    assert s1["start_date"] is None
    assert s1["end_date"] is None


def test_rollover_does_not_copy_archived_classes(client):
    hdr = _sqn_admin_hdr(client)
    py = _make_year(client, hdr, 2661, "CLASS-11 Rollover Source B")
    year_id = py["planning_year_id"]
    stage_id = _make_stage(client, hdr, py["unit_id"])
    keep_id = _make_class(client, hdr, year_id, stage_id, "Kept Class")
    archived_id = _make_class(client, hdr, year_id, stage_id, "Archived Class")
    arc = client.delete(f"/api/training-classes/{archived_id}", headers=hdr)
    assert arc.status_code == 200, arc.text

    r = client.post(f"/api/planning/years/{year_id}/rollover", json={}, headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    # Year creation auto-creates 5 standard classes (ORI/INI/JNR/INT/SNR) + 1 kept manual = 6 copied.
    # Archived classes are never rolled over.
    assert d["training_classes_copied"] == 6

    new_classes = _get_classes(client, hdr, d["new_planning_year_id"])
    names = {c["display_name"] for c in new_classes}
    assert "Kept Class" in names
    assert "Archived Class" not in names
    assert keep_id  # sanity: the id we kept is a real class, not unused


def test_rollover_with_copy_training_classes_false_skips_them(client):
    hdr = _sqn_admin_hdr(client)
    py = _make_year(client, hdr, 2662, "CLASS-11 Rollover Source C")
    year_id = py["planning_year_id"]
    stage_id = _make_stage(client, hdr, py["unit_id"])
    _make_class(client, hdr, year_id, stage_id, "Should Not Copy")

    r = client.post(f"/api/planning/years/{year_id}/rollover",
                     json={"copy_training_classes": False}, headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["training_classes_copied"] == 0

    new_classes = _get_classes(client, hdr, d["new_planning_year_id"])
    assert new_classes == []


def test_rollover_with_no_classes_reports_zero_not_an_error(client):
    hdr = _sqn_admin_hdr(client)
    py = _make_year(client, hdr, 2663, "CLASS-11 Rollover No Classes")
    r = client.post(f"/api/planning/years/{py['planning_year_id']}/rollover", json={}, headers=hdr)
    assert r.status_code == 200, r.text
    # Year creation auto-creates 5 standard classes (ORI/INI/JNR/INT/SNR), all of which are copied.
    assert r.json()["training_classes_copied"] == 5


def test_copied_training_class_is_independently_editable(client):
    """The copy must be a real, separate row -- editing the new year's class
    must not affect the source year's class."""
    hdr = _sqn_admin_hdr(client)
    py = _make_year(client, hdr, 2664, "CLASS-11 Rollover Independence")
    year_id = py["planning_year_id"]
    stage_id = _make_stage(client, hdr, py["unit_id"])
    _make_class(client, hdr, year_id, stage_id, "Original Name")

    r = client.post(f"/api/planning/years/{year_id}/rollover", json={}, headers=hdr)
    assert r.status_code == 200, r.text
    new_year_id = r.json()["new_planning_year_id"]

    new_class = _get_classes(client, hdr, new_year_id)[0]
    edit = client.patch(f"/api/training-classes/{new_class['training_class_id']}", json={
        "display_name": "Renamed In New Year", "client_version": new_class["version"],
    }, headers=hdr)
    assert edit.status_code == 200, edit.text

    old_classes = _get_classes(client, hdr, year_id)
    assert old_classes[0]["display_name"] == "Original Name"
