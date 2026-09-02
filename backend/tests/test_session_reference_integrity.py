"""Session foreign-reference integrity — Task 2 gap coverage.

This file adds regression coverage for cases NOT already in
test_session_reference_tenancy.py and test_session_audience.py:

1. Archived training class is rejected (same error as foreign-squadron class).
2. assign-mission rejects a cross-squadron training_class_id.
3. PATCH (planning sessions/{sid}) rejects a cross-squadron training_area_id.
4. PATCH (planning sessions/{sid}) rejects a cross-squadron curriculum_item_id.

Pre-existing coverage (do not duplicate here):
  facilitator_id  cross-squadron create/edit  → test_session_reference_tenancy.py
  training_area_id cross-squadron CREATE       → test_session_reference_tenancy.py
  curriculum_item_id cross-squadron CREATE     → test_session_reference_tenancy.py
  assistant_facilitator persistence + scoping  → test_session_reference_tenancy.py
  training_class_ids cross-squadron via PUT audience → test_session_audience.py
  invalid/nonexistent UUID in audience PUT     → test_session_audience.py
"""
import pytest
from datetime import date, timedelta

from tests.conftest import login, next_test_year


# ─── helpers ───────────────────────────────────────────────────────────────


def _make_year(client, hdr):
    year = next_test_year()
    r = client.post("/api/planning/years",
                    json={"year": year, "name": f"{year} Integrity Test"},
                    headers=hdr)
    assert r.status_code in (200, 201), r.text
    return r.json()


def _senior_stage_id(client, hdr):
    r = client.get("/api/curriculum/phases", headers=hdr)
    assert r.status_code == 200, r.text
    senior = next((p for p in r.json() if p["name"] == "E. Senior"), None)
    if senior is None:
        pytest.skip("No 'E. Senior' phase in seeded data")
    return senior["phase_id"]


def _make_class(client, hdr, year_id, stage_id, name):
    r = client.post("/api/training-classes", json={
        "training_year_id": year_id,
        "training_stage_id": stage_id,
        "display_name": name,
    }, headers=hdr)
    assert r.status_code in (200, 201), r.text
    return r.json()["training_class_id"]


def _make_pn(client, hdr, iso_date):
    me = client.get("/api/auth/me", headers=hdr).json()["session"]
    r = client.post("/api/parade-nights", json={
        "squadron_id": me["squadron_id"],
        "wing_id": me["wing_id"],
        "date": iso_date,
        "parade_type": "normal",
    }, headers=hdr)
    assert r.status_code in (200, 201), r.text
    return r.json().get("parade_night_id") or r.json().get("id")


def _create_planning_session(client, hdr, pn_id, **extra):
    body = {"session_number": 1, "cadet_group": "senior"}
    body.update(extra)
    return client.post(f"/api/planning/parade-dates/{pn_id}/sessions",
                       json=body, headers=hdr)


def _stored(client, hdr, sid):
    r = client.get(f"/api/planning/sessions/{sid}", headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def _national_curriculum_id(client, hdr):
    r = client.get("/api/curriculum", headers=hdr)
    assert r.status_code == 200, r.text
    items = r.json()
    items = items["items"] if isinstance(items, dict) else items
    nat = next((i for i in items
                if (i.get("owning_level") or "national") == "national"), None)
    if nat is None:
        pytest.skip("No national curriculum item in seeded data")
    return nat.get("curriculum_id") or nat.get("curriculum_item_id")


def _pn_for_year(client, hdr, year_id):
    """Get or create the first parade date within a planning year."""
    r = client.get(f"/api/planning/years/{year_id}/parade-dates", headers=hdr)
    if r.status_code == 200 and r.json():
        return r.json()[0]["id"]
    # Create one
    target = (date(2044, 9, 1)).isoformat()  # far-future, unlikely to collide
    r2 = client.post(f"/api/planning/years/{year_id}/parade-dates",
                     json={"date": target, "parade_type": "normal"}, headers=hdr)
    if r2.status_code not in (200, 201):
        pytest.skip(f"Could not create parade date for year: {r2.text}")
    return r2.json().get("id") or r2.json().get("parade_night_id")


# ─── 1. Archived training class rejected ────────────────────────────────────


def test_archived_training_class_rejected_on_session_create(client):
    """An archived training class must not be linkable to a new session.

    _resolve_scoped_classes (planning.py) checks tc.is_archived — this test
    verifies the check reaches the endpoint rather than being a dead branch.
    A 200 that silently ignores the archived id is also a test failure.
    """
    hdr = login(client, "ADMIN703")
    stage_id = _senior_stage_id(client, hdr)
    year = _make_year(client, hdr)
    year_id = year["planning_year_id"]
    tc_id = _make_class(client, hdr, year_id, stage_id, "ArchiveTest Senior")

    # Archive the class
    r_del = client.delete(f"/api/training-classes/{tc_id}", headers=hdr)
    assert r_del.status_code in (200, 204), (
        f"Could not archive training class: {r_del.text}"
    )

    pn_id = _make_pn(client, hdr, "2043-10-07")
    r = _create_planning_session(client, hdr, pn_id,
                                 training_class_ids=[tc_id])
    assert r.status_code in (400, 422), (
        f"Archived training class must be rejected; got {r.status_code}: {r.text}"
    )


# ─── 2. assign-mission cross-squadron class ─────────────────────────────────


def test_assign_mission_rejects_cross_squadron_training_class(client):
    """assign-mission calls _resolve_scoped_classes — it must reject a class
    that belongs to another squadron.

    planning.py lines 126-128 note this path was previously unguarded.
    """
    a703 = login(client, "ADMIN703")
    a705 = login(client, "ADMIN705")

    stage_703 = _senior_stage_id(client, a703)
    stage_705 = _senior_stage_id(client, a705)

    year_703 = _make_year(client, a703)
    year_705 = _make_year(client, a705)

    foreign_tc = _make_class(client, a705, year_705["planning_year_id"],
                             stage_705, "705 Foreign Class")

    # A parade night owned by squadron 703
    pn_id_703 = _make_pn(client, a703, "2043-10-14")
    ci_id = _national_curriculum_id(client, a703)

    r = client.post(
        f"/api/planning/years/{year_703['planning_year_id']}/assign-mission",
        json={
            "curriculum_id": ci_id,
            "parade_date_id": pn_id_703,
            "session_number": 1,
            "training_class_ids": [foreign_tc],
        },
        headers=a703,
    )
    assert r.status_code in (400, 403, 422), (
        f"Cross-squadron class on assign-mission must be rejected; "
        f"got {r.status_code}: {r.text}"
    )


# ─── 3. PATCH: cross-squadron training_area_id ──────────────────────────────


def test_edit_cannot_swap_in_another_squadrons_training_area(client):
    """PATCH /api/planning/sessions/{sid} must reject a foreign training_area_id.

    test_session_reference_tenancy.py only covers this for PATCH on facilitator_id.
    Both create and edit use scoped_training_area() — the edit path needs its
    own test because having the check on CREATE is not proof it's on PATCH.
    """
    a703 = login(client, "ADMIN703")
    a705 = login(client, "ADMIN705")

    foreign_area = client.post("/api/training-areas",
                               json={"name": "Integrity705 Room"}, headers=a705)
    assert foreign_area.status_code in (200, 201), foreign_area.text
    taid = foreign_area.json()["training_area_id"]

    pn = _make_pn(client, a703, "2043-10-21")
    created = _create_planning_session(client, a703, pn)
    assert created.status_code in (200, 201), created.text
    sid = created.json().get("session_id") or created.json().get("id")
    version = _stored(client, a703, sid).get("version")

    r = client.patch(f"/api/planning/sessions/{sid}",
                     json={"location_id": taid, "version": version},
                     headers=a703)
    assert r.status_code in (200, 201, 400, 403, 409, 422), r.text

    row = _stored(client, a703, sid)
    assert row.get("location_id") != taid, (
        "PATCH swapped 705's training area onto 703's session"
    )
    assert "Integrity705" not in (row.get("location_name") or ""), (
        "705's room name was denormalised onto 703's session via PATCH"
    )


# ─── 4. PATCH: cross-squadron curriculum_item_id ────────────────────────────


def test_edit_cannot_swap_in_another_squadrons_curriculum_item(client):
    """PATCH /api/planning/sessions/{sid} must reject a squadron-owned curriculum
    item from another squadron.

    test_session_reference_tenancy.py covers this only for CREATE. The edit
    path also uses visible_curriculum_item() — this test proves it does.
    """
    a703 = login(client, "ADMIN703")
    a705 = login(client, "ADMIN705")

    made = client.post("/api/curriculum", json={
        "code": "SQN705-INTEGRITY2",
        "title": "705 Integrity PATCH Local",
        "phase": "E. Senior",
        "element": "Service",
        "owning_level": "squadron",
        "duration_minutes": 60,
    }, headers=a705)
    if made.status_code not in (200, 201):
        pytest.skip(f"Could not create squadron-owned curriculum item: {made.text}")
    cid = made.json().get("curriculum_id") or made.json().get("curriculum_item_id")

    pn = _make_pn(client, a703, "2043-10-28")
    created = _create_planning_session(client, a703, pn)
    assert created.status_code in (200, 201), created.text
    sid = created.json().get("session_id") or created.json().get("id")
    version = _stored(client, a703, sid).get("version")

    r = client.patch(f"/api/planning/sessions/{sid}",
                     json={"curriculum_id": cid, "version": version},
                     headers=a703)
    assert r.status_code in (200, 201, 400, 403, 409, 422), r.text

    row = _stored(client, a703, sid)
    assert row.get("curriculum_id") != cid, (
        "PATCH swapped 705's local curriculum onto 703's session"
    )
    assert "705 Integrity PATCH Local" not in (row.get("curriculum_title") or ""), (
        "705's curriculum title was denormalised onto 703's session via PATCH"
    )
