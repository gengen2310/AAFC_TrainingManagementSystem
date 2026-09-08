"""CEA rollback must unwind relationships that only exist because a NEW Cadet was imported."""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from tests.conftest import login
from tests.test_cea_member_identity_contract import HEADER, _db, _row, _sq


def test_rollback_new_cadet_does_not_leave_active_class_membership(client):
    """Archiving a newly imported Cadet while leaving an active membership is referentially stale."""
    headers = login(client, "ADMIN703")
    cea_id = f"CEARBREL{uuid.uuid4().hex[:8]}"
    commit = client.post(
        "/api/import/cea-members/commit",
        json={
            "csv_text": HEADER + _row(cea_id, "Cdt", "Rollback", "Relationship"),
            "file_name": "rollback-relationship.csv",
        },
        headers=headers,
    )
    assert commit.status_code == 200, commit.text
    batch_id = commit.json()["batch_id"]

    db = _db()
    try:
        from app.models import CadetClassMembership
        from app.models.training import Cadet, TrainingClass

        sq = _sq(db, "703")
        if sq is None:
            pytest.skip("703 squadron is not seeded")
        cadet = db.query(Cadet).filter(
            Cadet.service_number == cea_id,
            Cadet.is_archived == False,  # noqa: E712
        ).first()
        assert cadet is not None
        tc = db.query(TrainingClass).filter(
            TrainingClass.squadron_id == sq.id,
            TrainingClass.is_archived == False,  # noqa: E712
        ).first()
        if tc is None:
            pytest.skip("703 has no training class")
        membership = CadetClassMembership(
            cadet_id=cadet.id,
            training_class_id=tc.id,
            start_date=str(date.today()),
            active_status=True,
            source="manual",
            created_by="test",
            updated_by="test",
        )
        db.add(membership)
        db.commit()
        cadet_id, membership_id = cadet.id, membership.id
    finally:
        db.close()

    rollback = client.post(
        f"/api/import/cea-members/rollback?batch_id={batch_id}",
        headers=headers,
    )
    assert rollback.status_code == 200, rollback.text

    db = _db()
    try:
        from app.models import CadetClassMembership
        from app.models.training import Cadet

        cadet = db.get(Cadet, cadet_id)
        membership = db.get(CadetClassMembership, membership_id)
        assert cadet is not None and cadet.is_archived
        assert membership is not None
        assert membership.is_archived or not membership.active_status, (
            "Rollback of a NEW Cadet must not leave a live CadetClassMembership "
            "pointing at an archived Cadet"
        )
    finally:
        db.close()
