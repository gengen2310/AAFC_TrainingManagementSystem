"""Training-record visibility/order contracts discovered during remediation review.

Training Records must use the same visible curriculum catalogue as normal squadron
planning: national + own-wing + own-squadron phases. They must not silently drop
inherited national curriculum merely because CurriculumPhase.squadron_id is null.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import func

from tests.conftest import login


ADM703 = "ADMIN703"
NAT_ADMIN = "ADMINNATIONAL"


def _db():
    from app.database import SessionLocal

    return SessionLocal()


def _squadron(db):
    from app.models import Squadron

    return db.query(Squadron).filter(Squadron.code == "703").first()


def _planning_year(db, squadron_id: str):
    from app.models.planning import PlanningYear

    py = db.query(PlanningYear).filter(PlanningYear.unit_id == squadron_id).first()
    if py is None:
        py = PlanningYear(
            unit_id=squadron_id,
            year=2097,
            name="Training Record Visibility Guard",
            created_by="test",
            updated_by="test",
        )
        db.add(py)
        db.flush()
    return py


def _training_class(db, squadron_id: str, phase_id: str):
    from app.models.training import TrainingClass

    py = _planning_year(db, squadron_id)
    max_number = db.query(func.max(TrainingClass.class_number)).filter(
        TrainingClass.squadron_id == squadron_id,
        TrainingClass.training_year_id == py.id,
    ).scalar()
    tc = TrainingClass(
        squadron_id=squadron_id,
        training_year_id=py.id,
        training_stage_id=phase_id,
        display_name=f"National Curriculum Guard {uuid.uuid4().hex[:6]}",
        class_number=(max_number or 0) + 1,
        created_by="test",
        updated_by="test",
    )
    db.add(tc)
    db.commit()
    db.refresh(tc)
    return tc


def _cadet_member(db, squadron_id: str, class_id: str):
    from app.models import CadetClassMembership
    from app.models.training import Cadet

    cadet = Cadet(
        squadron_id=squadron_id,
        service_number=f"TRVIS{uuid.uuid4().hex[:8]}",
        first_name="Training",
        last_name="RecordGuard",
        created_by="test",
        updated_by="test",
    )
    db.add(cadet)
    db.flush()
    membership = CadetClassMembership(
        cadet_id=cadet.id,
        training_class_id=class_id,
        start_date=str(date.today()),
        active_status=True,
        source="manual",
        created_by="test",
        updated_by="test",
    )
    db.add(membership)
    db.commit()
    db.refresh(cadet)
    return cadet


def _national_phase(client):
    headers = login(client, NAT_ADMIN)
    name = f"TR-NATIONAL-{uuid.uuid4().hex[:10]}"
    response = client.post(
        "/api/curriculum/phases",
        json={
            "name": name,
            "display_name": f"Training Record National {name[-6:]}",
            "scope_level": "national",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["phase_id"], name


def _curriculum_item(db, phase_name: str, *, code: str | None = None, title: str | None = None,
                     part_number: int = 1, sequence: int = 1):
    from app.models import CurriculumItem

    suffix = uuid.uuid4().hex[:8]
    ci = CurriculumItem(
        identifier=f"TRVIS-{suffix}-{part_number}",
        code=code or f"TRVIS-{suffix}",
        part_number=part_number,
        title=title or f"Training Record Visibility {suffix}",
        phase=phase_name,
        recommended_sequence=sequence,
        active_status=True,
    )
    db.add(ci)
    db.commit()
    db.refresh(ci)
    return ci


def test_training_records_matrix_includes_visible_national_curriculum(client):
    """A squadron class linked to a national phase must show that phase's lessons."""
    phase_id, phase_name = _national_phase(client)
    headers = login(client, ADM703)

    db = _db()
    try:
        sq = _squadron(db)
        if sq is None:
            pytest.skip("703 squadron is not seeded")
        item = _curriculum_item(db, phase_name)
        tc = _training_class(db, sq.id, phase_id)
        _cadet_member(db, sq.id, tc.id)
        item_id, class_id = item.id, tc.id
    finally:
        db.close()

    response = client.get(f"/api/training-records?class_id={class_id}", headers=headers)
    assert response.status_code == 200, response.text
    item_ids = {row["curriculum_item_id"] for row in response.json()["curriculum_items"]}
    assert item_id in item_ids, (
        "Training Records must use the visible inherited curriculum catalogue; "
        "national lessons cannot disappear because phase.squadron_id is null"
    )


def test_individual_training_record_includes_visible_national_curriculum(client):
    """Individual Cadet history must use the same national/wing/squadron phase visibility rules."""
    phase_id, phase_name = _national_phase(client)
    headers = login(client, ADM703)

    db = _db()
    try:
        sq = _squadron(db)
        if sq is None:
            pytest.skip("703 squadron is not seeded")
        item = _curriculum_item(db, phase_name)
        tc = _training_class(db, sq.id, phase_id)
        cadet = _cadet_member(db, sq.id, tc.id)
        item_id, cadet_id = item.id, cadet.id
    finally:
        db.close()

    response = client.get(f"/api/cadets/{cadet_id}/training-record", headers=headers)
    assert response.status_code == 200, response.text
    returned_item_ids = {
        item_row["curriculum_item_id"]
        for phase in response.json()["phases"]
        for item_row in phase.get("items", [])
    }
    assert item_id in returned_item_ids, (
        "Individual Training Record must not omit national curriculum visible to the Cadet's squadron"
    )


def test_training_records_orders_equal_sequence_parts_by_part_number(client):
    """Curriculum order tie-break is part_number after phase/sequence/code."""
    headers = login(client, ADM703)
    phase_name = f"TR-ORDER-{uuid.uuid4().hex[:10]}"
    create_phase = client.post(
        "/api/curriculum/phases",
        json={"name": phase_name, "display_name": phase_name, "scope_level": "squadron"},
        headers=headers,
    )
    assert create_phase.status_code == 200, create_phase.text
    phase_id = create_phase.json()["phase_id"]

    db = _db()
    try:
        sq = _squadron(db)
        if sq is None:
            pytest.skip("703 squadron is not seeded")
        shared_code = f"TR-PART-{uuid.uuid4().hex[:8]}"
        # Insert part 2 first intentionally so an unspecified SQL tie order cannot
        # accidentally satisfy the contract through insertion order.
        part2 = _curriculum_item(
            db, phase_name, code=shared_code, title="Part 2 guard", part_number=2, sequence=5
        )
        part1 = _curriculum_item(
            db, phase_name, code=shared_code, title="Part 1 guard", part_number=1, sequence=5
        )
        tc = _training_class(db, sq.id, phase_id)
        _cadet_member(db, sq.id, tc.id)
        class_id = tc.id
        ids = {part1.id, part2.id}
    finally:
        db.close()

    response = client.get(f"/api/training-records?class_id={class_id}", headers=headers)
    assert response.status_code == 200, response.text
    relevant = [
        row for row in response.json()["curriculum_items"]
        if row["curriculum_item_id"] in ids
    ]
    assert [row["title"] for row in relevant] == ["Part 1 guard", "Part 2 guard"], (
        "Training Records curriculum ordering must use part_number as the final tie-breaker"
    )
