"""Focused regression guards for the September 2026 remediation pass.

Test-only file. It deliberately exercises integration/data-integrity contracts
that are easy to miss when individual endpoint tests pass.
"""

import csv
import io
import uuid
from datetime import date

import pytest
from sqlalchemy import func

from tests.conftest import login


ADM703 = "ADMIN703"
ADM704 = "ADMIN704"


def _db():
    from app.database import SessionLocal
    return SessionLocal()


def _squadron(db, code: str):
    from app.models import Squadron
    return db.query(Squadron).filter(Squadron.code == code).first()


def _ensure_cadet(db, squadron_id: str, prefix: str):
    from app.models.training import Cadet

    service_number = f"{prefix}{uuid.uuid4().hex[:8]}"
    cadet = Cadet(
        squadron_id=squadron_id,
        service_number=service_number,
        first_name="Contract",
        last_name="Guard",
        created_by="test",
        updated_by="test",
    )
    db.add(cadet)
    db.commit()
    db.refresh(cadet)
    return cadet


def _ensure_training_class(db, squadron_id: str, label: str):
    from app.models.planning import PlanningYear
    from app.models.training import TrainingClass

    planning_year = db.query(PlanningYear).filter(
        PlanningYear.unit_id == squadron_id,
    ).first()
    if planning_year is None:
        planning_year = PlanningYear(
            unit_id=squadron_id,
            year=2099,
            name=f"Contract Guard {label}",
            created_by="test",
            updated_by="test",
        )
        db.add(planning_year)
        db.flush()

    # TrainingClass has a real unique constraint on
    # (squadron_id, training_year_id, class_number). The seeded DB already
    # contains class_number=1, so test data must allocate a collision-free
    # number instead of relying on the model default.
    max_class_number = db.query(func.max(TrainingClass.class_number)).filter(
        TrainingClass.squadron_id == squadron_id,
        TrainingClass.training_year_id == planning_year.id,
    ).scalar()

    training_class = TrainingClass(
        squadron_id=squadron_id,
        training_year_id=planning_year.id,
        display_name=f"Contract Guard {label} {uuid.uuid4().hex[:6]}",
        class_number=(max_class_number or 0) + 1,
        created_by="test",
        updated_by="test",
    )
    db.add(training_class)
    db.commit()
    db.refresh(training_class)
    return training_class


def _ensure_membership(db, cadet_id: str, class_id: str):
    from app.models import CadetClassMembership

    membership = CadetClassMembership(
        cadet_id=cadet_id,
        training_class_id=class_id,
        start_date=str(date.today()),
        active_status=True,
        source="manual",
        created_by="test",
        updated_by="test",
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


def _first_parade_night(db, squadron_id: str):
    from app.models import ParadeNight

    return db.query(ParadeNight).filter(
        ParadeNight.squadron_id == squadron_id,
        ParadeNight.is_archived == False,  # noqa: E712
    ).first()


def _make_session(db, squadron_id: str, parade_night_id: str, status: str = "planned"):
    from app.models.training import Session

    session = Session(
        squadron_id=squadron_id,
        parade_night_id=parade_night_id,
        period_number=90 + (uuid.uuid4().int % 9),
        status=status,
        delivery_notes="Seeded delivery" if status == "delivered" else None,
        cancelled_reason="Seeded cancellation" if status.startswith("cancelled") else None,
        created_by="test",
        updated_by="test",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def test_training_records_csv_always_exposes_cea_completion_headers(client):
    """Export headers are mandatory even when the selected class has no completions."""
    headers = login(client, ADM703)
    db = _db()
    try:
        sq = _squadron(db, "703")
        if sq is None:
            pytest.skip("703 squadron is not seeded")
        training_class = _ensure_training_class(db, sq.id, "CSV")
        class_id = training_class.id
    finally:
        db.close()

    response = client.get(
        f"/api/training-records/export?class_id={class_id}",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows, "CSV export must include a header row even with zero completions"
    assert "CEA Number" in rows[0]
    assert "Completion Date" in rows[0]


def test_bulk_move_rejects_real_cross_squadron_target_class(client):
    """A 703 membership cannot be moved into a real 704 Training Class."""
    headers = login(client, ADM703)
    db = _db()
    try:
        sq703 = _squadron(db, "703")
        sq704 = _squadron(db, "704")
        if sq703 is None or sq704 is None:
            pytest.skip("703/704 squadrons are not both seeded")

        source = _ensure_training_class(db, sq703.id, "Source 703")
        target = _ensure_training_class(db, sq704.id, "Target 704")
        cadet = _ensure_cadet(db, sq703.id, "X703")
        _ensure_membership(db, cadet.id, source.id)
        source_id, target_id, cadet_id = source.id, target.id, cadet.id
    finally:
        db.close()

    response = client.post(
        f"/api/training-classes/{source_id}/bulk-membership",
        json={
            "action": "move",
            "cadet_ids": [cadet_id],
            "target_class_id": target_id,
        },
        headers=headers,
    )
    assert response.status_code in (403, 404), (
        "Cross-squadron move must be rejected before any membership mutation; "
        f"got {response.status_code}: {response.text}"
    )

    # Re-open the DB and prove a rejected request did not close the source or
    # create a target membership.
    db = _db()
    try:
        from app.models import CadetClassMembership

        source_membership = db.query(CadetClassMembership).filter(
            CadetClassMembership.cadet_id == cadet_id,
            CadetClassMembership.training_class_id == source_id,
            CadetClassMembership.is_archived == False,  # noqa: E712
            CadetClassMembership.active_status == True,  # noqa: E712
        ).first()
        target_membership = db.query(CadetClassMembership).filter(
            CadetClassMembership.cadet_id == cadet_id,
            CadetClassMembership.training_class_id == target_id,
            CadetClassMembership.is_archived == False,  # noqa: E712
            CadetClassMembership.active_status == True,  # noqa: E712
        ).first()
        assert source_membership is not None, "Rejected move must leave source membership active"
        assert target_membership is None, "Rejected move must not create cross-squadron membership"
    finally:
        db.close()


def test_delivered_session_cannot_be_cancelled_via_normal_outcome_endpoint(client):
    """Normal workflow must never create Session=cancelled with completed cadet outcomes."""
    headers = login(client, ADM703)
    db = _db()
    try:
        sq = _squadron(db, "703")
        if sq is None:
            pytest.skip("703 squadron is not seeded")
        pn = _first_parade_night(db, sq.id)
        if pn is None:
            pytest.skip("703 has no parade night")
        session = _make_session(db, sq.id, pn.id, status="planned")
        session_id = session.id
    finally:
        db.close()

    delivered = client.post(
        f"/api/sessions/{session_id}/deliver",
        json={"delivery_note": "Delivered for transition guard."},
        headers=headers,
    )
    assert delivered.status_code == 200, delivered.text

    cancelled = client.post(
        f"/api/sessions/{session_id}/cancel",
        json={"cancellation_reason": "This must require an explicit correction workflow."},
        headers=headers,
    )
    assert cancelled.status_code == 409, (
        "Delivered -> Cancelled must be rejected by the normal outcome endpoint; "
        f"got {cancelled.status_code}: {cancelled.text}"
    )


def test_cancelled_session_cannot_be_delivered_via_normal_outcome_endpoint(client):
    """Cancelled history is immutable; rescheduling creates a replacement Session instead."""
    headers = login(client, ADM703)
    db = _db()
    try:
        sq = _squadron(db, "703")
        if sq is None:
            pytest.skip("703 squadron is not seeded")
        pn = _first_parade_night(db, sq.id)
        if pn is None:
            pytest.skip("703 has no parade night")
        session = _make_session(db, sq.id, pn.id, status="planned")
        session_id = session.id
    finally:
        db.close()

    cancelled = client.post(
        f"/api/sessions/{session_id}/cancel",
        json={"cancellation_reason": "Cancelled for transition guard."},
        headers=headers,
    )
    assert cancelled.status_code == 200, cancelled.text

    delivered = client.post(
        f"/api/sessions/{session_id}/deliver",
        json={"delivery_note": "Should not overwrite cancelled history."},
        headers=headers,
    )
    assert delivered.status_code == 409, (
        "Cancelled -> Delivered must be rejected; create/reschedule a replacement instead. "
        f"Got {delivered.status_code}: {delivered.text}"
    )


def test_real_cross_squadron_session_outcome_override_is_rejected(client):
    """Use a real foreign Session, not a random UUID, to prove relationship tenancy."""
    headers704 = login(client, ADM704)
    db = _db()
    try:
        sq703 = _squadron(db, "703")
        sq704 = _squadron(db, "704")
        if sq703 is None or sq704 is None:
            pytest.skip("703/704 squadrons are not both seeded")

        pn703 = _first_parade_night(db, sq703.id)
        if pn703 is None:
            pytest.skip("703 has no parade night")

        foreign_session = _make_session(db, sq703.id, pn703.id, status="delivered")
        local_cadet = _ensure_cadet(db, sq704.id, "X704")
        foreign_session_id, local_cadet_id = foreign_session.id, local_cadet.id
    finally:
        db.close()

    response = client.post(
        f"/api/cadets/{local_cadet_id}/session-outcomes/{foreign_session_id}",
        json={"status": "absent", "override_reason": "Cross-squadron guard"},
        headers=headers704,
    )
    assert response.status_code in (403, 404), (
        "A user authorised for the cadet's squadron must still be forbidden from "
        f"linking that cadet to a real foreign Session; got {response.status_code}: {response.text}"
    )
