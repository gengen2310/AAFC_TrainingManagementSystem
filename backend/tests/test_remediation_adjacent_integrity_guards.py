"""Adjacent integration guards discovered while tracing September 2026 remediation failures.

Test-only. These checks tighten relationship-tenancy and immutable-history contracts
around the same user workflows already covered by test_remediation_contract_guards.py.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import func

from tests.conftest import login


ADM703 = "ADMIN703"


def _db():
    from app.database import SessionLocal

    return SessionLocal()


def _squadron(db, code: str):
    from app.models import Squadron

    return db.query(Squadron).filter(Squadron.code == code).first()


def _first_parade_night(db, squadron_id: str):
    from app.models import ParadeNight

    return db.query(ParadeNight).filter(
        ParadeNight.squadron_id == squadron_id,
        ParadeNight.is_archived == False,  # noqa: E712
    ).first()


def _planning_year(db, squadron_id: str):
    from app.models.planning import PlanningYear

    py = db.query(PlanningYear).filter(PlanningYear.unit_id == squadron_id).first()
    if py is None:
        py = PlanningYear(
            unit_id=squadron_id,
            year=2098,
            name=f"Adjacent Guard {squadron_id[:6]}",
            created_by="test",
            updated_by="test",
        )
        db.add(py)
        db.flush()
    return py


def _training_class(db, squadron_id: str, label: str, *, stage_id: str | None = None):
    from app.models.training import TrainingClass

    py = _planning_year(db, squadron_id)
    max_number = db.query(func.max(TrainingClass.class_number)).filter(
        TrainingClass.squadron_id == squadron_id,
        TrainingClass.training_year_id == py.id,
    ).scalar()
    tc = TrainingClass(
        squadron_id=squadron_id,
        training_year_id=py.id,
        training_stage_id=stage_id,
        display_name=f"{label} {uuid.uuid4().hex[:6]}",
        class_number=(max_number or 0) + 1,
        created_by="test",
        updated_by="test",
    )
    db.add(tc)
    db.commit()
    db.refresh(tc)
    return tc


def _cadet(db, squadron_id: str, prefix: str):
    from app.models.training import Cadet

    c = Cadet(
        squadron_id=squadron_id,
        service_number=f"{prefix}{uuid.uuid4().hex[:8]}",
        first_name="Adjacent",
        last_name="Guard",
        created_by="test",
        updated_by="test",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _membership(db, cadet_id: str, class_id: str):
    from app.models import CadetClassMembership

    m = CadetClassMembership(
        cadet_id=cadet_id,
        training_class_id=class_id,
        start_date=str(date.today()),
        active_status=True,
        source="manual",
        created_by="test",
        updated_by="test",
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _cancelled_session(db, squadron_id: str, parade_night_id: str):
    from app.models.training import Session

    s = Session(
        squadron_id=squadron_id,
        parade_night_id=parade_night_id,
        period_number=1,
        status="cancelled",
        cancelled_reason="Adjacent integrity guard",
        custom_title="Adjacent integrity guard",
        created_by="test",
        updated_by="test",
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def test_bulk_add_rejects_foreign_cadet_relationship(client):
    """A 703 class must never accept a real 704 Cadet via bulk Add to Class."""
    headers = login(client, ADM703)
    db = _db()
    try:
        sq703 = _squadron(db, "703")
        sq704 = _squadron(db, "704")
        if sq703 is None or sq704 is None:
            pytest.skip("703/704 squadrons are not both seeded")
        tc = _training_class(db, sq703.id, "703 roster")
        foreign_cadet = _cadet(db, sq704.id, "F704")
        class_id, cadet_id = tc.id, foreign_cadet.id
    finally:
        db.close()

    response = client.post(
        f"/api/training-classes/{class_id}/bulk-membership",
        json={"action": "add", "cadet_ids": [cadet_id]},
        headers=headers,
    )
    assert response.status_code in (403, 404), (
        "Bulk Add to Class must reject a foreign-squadron Cadet before creating "
        f"a relationship; got {response.status_code}: {response.text}"
    )

    db = _db()
    try:
        from app.models import CadetClassMembership

        linked = db.query(CadetClassMembership).filter(
            CadetClassMembership.cadet_id == cadet_id,
            CadetClassMembership.training_class_id == class_id,
            CadetClassMembership.is_archived == False,  # noqa: E712
        ).first()
        assert linked is None, "Rejected foreign Cadet add must leave no membership row"
    finally:
        db.close()


def test_bulk_move_rejects_cross_stage_and_preserves_source_membership(client):
    """Move is a same-phase/class reassignment; cross-stage participation uses Add to Class."""
    headers = login(client, ADM703)
    db = _db()
    try:
        from app.models.training import CurriculumPhase

        sq = _squadron(db, "703")
        if sq is None:
            pytest.skip("703 squadron is not seeded")
        phases = db.query(CurriculumPhase).filter(
            CurriculumPhase.is_archived == False,  # noqa: E712
            CurriculumPhase.active_status == True,  # noqa: E712
        ).order_by(CurriculumPhase.sort_order, CurriculumPhase.name).all()
        distinct = []
        for ph in phases:
            if ph.id not in [p.id for p in distinct]:
                distinct.append(ph)
            if len(distinct) == 2:
                break
        if len(distinct) < 2:
            pytest.skip("Need two training stages to exercise cross-stage move")

        source = _training_class(db, sq.id, "Source stage", stage_id=distinct[0].id)
        target = _training_class(db, sq.id, "Target stage", stage_id=distinct[1].id)
        cadet = _cadet(db, sq.id, "S703")
        _membership(db, cadet.id, source.id)
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
    assert response.status_code in (400, 409), (
        "Move to Class must not silently turn a same-stage reassignment into a "
        f"cross-stage transfer; got {response.status_code}: {response.text}"
    )

    db = _db()
    try:
        from app.models import CadetClassMembership

        src = db.query(CadetClassMembership).filter(
            CadetClassMembership.cadet_id == cadet_id,
            CadetClassMembership.training_class_id == source_id,
            CadetClassMembership.is_archived == False,  # noqa: E712
            CadetClassMembership.active_status == True,  # noqa: E712
        ).first()
        dst = db.query(CadetClassMembership).filter(
            CadetClassMembership.cadet_id == cadet_id,
            CadetClassMembership.training_class_id == target_id,
            CadetClassMembership.is_archived == False,  # noqa: E712
            CadetClassMembership.active_status == True,  # noqa: E712
        ).first()
        assert src is not None, "Rejected cross-stage move must keep source membership active"
        assert dst is None, "Rejected cross-stage move must not create target membership"
    finally:
        db.close()


def test_reschedule_rejects_foreign_parade_night_relationship(client):
    """A 703 cancelled Session cannot be replaced onto a real 704 Parade Night."""
    headers = login(client, ADM703)
    db = _db()
    try:
        sq703 = _squadron(db, "703")
        sq704 = _squadron(db, "704")
        if sq703 is None or sq704 is None:
            pytest.skip("703/704 squadrons are not both seeded")
        pn703 = _first_parade_night(db, sq703.id)
        pn704 = _first_parade_night(db, sq704.id)
        if pn703 is None or pn704 is None:
            pytest.skip("703/704 both need a parade night")
        original = _cancelled_session(db, sq703.id, pn703.id)
        original_id, foreign_pn_id = original.id, pn704.id
    finally:
        db.close()

    response = client.post(
        f"/api/sessions/{original_id}/reschedule",
        json={"parade_night_id": foreign_pn_id, "period_number": 1},
        headers=headers,
    )
    assert response.status_code in (400, 403, 404, 409), (
        "Reschedule must reject a Parade Night from another squadron before "
        f"creating a replacement; got {response.status_code}: {response.text}"
    )

    db = _db()
    try:
        from app.models.training import Session

        original = db.get(Session, original_id)
        assert original is not None
        assert original.rescheduled_to_session_id is None
        corrupt = db.query(Session).filter(
            Session.parade_night_id == foreign_pn_id,
            Session.squadron_id == original.squadron_id,
            Session.is_archived == False,  # noqa: E712
        ).all()
        assert corrupt == [], "Rejected reschedule must not create cross-squadron Session/ParadeNight linkage"
    finally:
        db.close()


def test_reschedule_is_single_replacement_not_duplicate_append(client):
    """Retrying/double-clicking reschedule must not create multiple replacement Sessions."""
    headers = login(client, ADM703)
    db = _db()
    try:
        from app.models.training import Session

        sq = _squadron(db, "703")
        if sq is None:
            pytest.skip("703 squadron is not seeded")
        pn = _first_parade_night(db, sq.id)
        if pn is None:
            pytest.skip("703 has no parade night")
        original = _cancelled_session(db, sq.id, pn.id)
        original_id, pn_id = original.id, pn.id
        before_ids = {r.id for r in db.query(Session).filter(Session.squadron_id == sq.id).all()}
    finally:
        db.close()

    first = client.post(
        f"/api/sessions/{original_id}/reschedule",
        json={"parade_night_id": pn_id, "period_number": 2},
        headers=headers,
    )
    assert first.status_code == 200, first.text
    first_replacement = first.json()["new_session_id"]

    second = client.post(
        f"/api/sessions/{original_id}/reschedule",
        json={"parade_night_id": pn_id, "period_number": 2},
        headers=headers,
    )
    assert second.status_code in (200, 409), second.text
    if second.status_code == 200:
        assert second.json()["new_session_id"] == first_replacement, (
            "An idempotent 200 retry must return the existing replacement, not append another"
        )

    db = _db()
    try:
        from app.models.training import Session

        original = db.get(Session, original_id)
        assert original is not None
        assert original.rescheduled_to_session_id == first_replacement
        after_ids = {r.id for r in db.query(Session).filter(Session.squadron_id == original.squadron_id).all()}
        created_ids = after_ids - before_ids
        assert created_ids == {first_replacement}, (
            f"Exactly one replacement may be created; got new session ids {sorted(created_ids)}"
        )
    finally:
        db.close()


def test_manual_cadet_outcome_requires_session_audience_membership(client):
    """Per-cadet exceptions belong to the delivered Session's audience, not arbitrary local Cadets."""
    headers = login(client, ADM703)
    db = _db()
    try:
        from app.models.training import Session

        sq = _squadron(db, "703")
        if sq is None:
            pytest.skip("703 squadron is not seeded")
        pn = _first_parade_night(db, sq.id)
        if pn is None:
            pytest.skip("703 has no parade night")
        cadet = _cadet(db, sq.id, "NA703")
        delivered = Session(
            squadron_id=sq.id,
            parade_night_id=pn.id,
            period_number=1,
            status="delivered",
            delivery_notes="Delivered to a different audience",
            created_by="test",
            updated_by="test",
        )
        db.add(delivered)
        db.commit()
        db.refresh(delivered)
        cadet_id, session_id = cadet.id, delivered.id
    finally:
        db.close()

    response = client.post(
        f"/api/cadets/{cadet_id}/session-outcomes/{session_id}",
        json={"status": "absent", "override_reason": "Must belong to session audience"},
        headers=headers,
    )
    assert response.status_code in (400, 404, 409), (
        "Manual per-cadet outcome override must reject a Cadet who was not in any "
        f"target class for the Session; got {response.status_code}: {response.text}"
    )
