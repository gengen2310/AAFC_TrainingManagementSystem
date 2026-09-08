"""Regression guard: rescheduling must not silently strip Session assignments."""

import uuid

import pytest

from tests.conftest import login


def test_reschedule_preserves_operational_assignments_and_assistants(client):
    """A replacement Session keeps the original lesson's operational assignment data.

    The date/period/status change; curriculum/audience/facilitator/room/assistant
    context must not disappear merely because the lesson was rescheduled.
    """
    headers = login(client, "ADMIN703")

    from app.database import SessionLocal
    from app.models import ParadeNight, Squadron
    from app.models.training import Session, SessionAssistantFacilitator

    db = SessionLocal()
    try:
        sq = db.query(Squadron).filter(Squadron.code == "703").first()
        if sq is None:
            pytest.skip("703 squadron is not seeded")
        pn = db.query(ParadeNight).filter(
            ParadeNight.squadron_id == sq.id,
            ParadeNight.is_archived == False,  # noqa: E712
        ).first()
        if pn is None:
            pytest.skip("703 has no parade night")

        assistant_user_id = str(uuid.uuid4())
        original = Session(
            squadron_id=sq.id,
            parade_night_id=pn.id,
            period_number=1,
            status="cancelled",
            cancelled_reason="Instructor unavailable",
            custom_title="Reschedule preservation lesson",
            facilitator_id="facilitator-contract-guard",
            assistant_facilitator_id="legacy-assistant-contract-guard",
            training_area_id="room-contract-guard",
            equipment_required="Projector",
            expected_attendance=18,
            cadet_group="junior",
            part_number=2,
            created_by="test",
            updated_by="test",
        )
        db.add(original)
        db.flush()
        db.add(SessionAssistantFacilitator(
            session_id=original.id,
            user_id=assistant_user_id,
        ))
        db.commit()
        original_id = original.id
        parade_night_id = pn.id
    finally:
        db.close()

    response = client.post(
        f"/api/sessions/{original_id}/reschedule",
        json={"parade_night_id": parade_night_id, "period_number": 2},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    replacement_id = response.json()["new_session_id"]

    db = SessionLocal()
    try:
        replacement = db.get(Session, replacement_id)
        assert replacement is not None
        assert replacement.status == "planned"
        assert replacement.custom_title == "Reschedule preservation lesson"
        assert replacement.facilitator_id == "facilitator-contract-guard"
        assert replacement.assistant_facilitator_id == "legacy-assistant-contract-guard"
        assert replacement.training_area_id == "room-contract-guard"
        assert replacement.equipment_required == "Projector"
        assert replacement.expected_attendance == 18
        assert replacement.cadet_group == "junior"
        assert replacement.part_number == 2

        assistants = db.query(SessionAssistantFacilitator).filter(
            SessionAssistantFacilitator.session_id == replacement_id,
        ).all()
        assert [a.user_id for a in assistants] == [assistant_user_id]

        original = db.get(Session, original_id)
        assert original is not None
        assert original.status == "cancelled"
        assert original.rescheduled_to_session_id == replacement_id
    finally:
        db.close()
