"""Individual Training Record attempt context for combined-class Sessions."""

from __future__ import annotations

import pytest

from tests.conftest import login
from tests.test_remediation_adjacent_integrity_guards import _cadet, _db, _planning_year, _squadron, _training_class
from tests.test_training_record_class_scope_contract import _squadron_phase
from tests.test_training_record_visibility_contract import _curriculum_item


ADM703 = "ADMIN703"


def test_individual_attempt_reports_the_cadets_actual_target_class_not_first_session_audience(client):
    """A combined Session can target A+B; a Cadet only in B must not have history labelled as A."""
    from app.models import CadetClassMembership, SessionAudience
    from app.models.training import CadetSessionOutcome, ParadeNight, Session

    headers = login(client, ADM703)
    phase_id, phase_name = _squadron_phase(client, "AUDIENCE-CONTEXT")

    db = _db()
    try:
        sq = _squadron(db, "703")
        if sq is None:
            pytest.skip("703 squadron is not seeded")
        py = _planning_year(db, sq.id)
        class_a = _training_class(db, sq.id, "Audience A", stage_id=phase_id)
        class_b = _training_class(db, sq.id, "Audience B", stage_id=phase_id)
        cadet = _cadet(db, sq.id, "AUDCTX")
        db.add(CadetClassMembership(
            cadet_id=cadet.id,
            training_class_id=class_b.id,
            start_date="2025-01-01",
            active_status=True,
            source="manual",
            created_by="test",
            updated_by="test",
        ))
        item = _curriculum_item(db, phase_name, title="Audience-context lesson")
        pn = ParadeNight(
            squadron_id=sq.id,
            wing_id=sq.wing_id,
            planning_year_id=py.id,
            date="2025-06-01",
            term="T2",
        )
        db.add(pn)
        db.flush()
        sess = Session(
            squadron_id=sq.id,
            parade_night_id=pn.id,
            period_number=1,
            status="delivered",
            curriculum_item_id=item.id,
            delivery_notes="Delivered jointly to two classes",
            created_by="test",
            updated_by="test",
        )
        db.add(sess)
        db.flush()
        # Deliberately insert the unrelated class first. A history implementation
        # that simply calls .first() on SessionAudience will report the wrong class.
        db.add(SessionAudience(session_id=sess.id, training_class_id=class_a.id))
        db.add(SessionAudience(session_id=sess.id, training_class_id=class_b.id))
        db.add(CadetSessionOutcome(
            cadet_id=cadet.id,
            session_id=sess.id,
            status="completed",
            completion_date=pn.date,
            source="derived",
            changed_by="test",
        ))
        db.commit()
        cadet_id, item_id, session_id = cadet.id, item.id, sess.id
        class_b_name = class_b.display_name
    finally:
        db.close()

    response = client.get(f"/api/cadets/{cadet_id}/training-record", headers=headers)
    assert response.status_code == 200, response.text
    item_row = next(
        row
        for phase in response.json().get("phases", [])
        for row in phase.get("items", [])
        if row.get("curriculum_item_id") == item_id
    )
    attempt = next(a for a in item_row.get("attempts", []) if a.get("session_id") == session_id)
    assert attempt.get("training_class") == class_b_name, (
        "Individual Training Record must resolve class context from the Cadet's membership "
        "on the Parade Night date, not whichever SessionAudience row happens to be first"
    )
