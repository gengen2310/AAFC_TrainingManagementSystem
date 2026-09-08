"""Outcome / Needs Attention edge contracts found during remediation review.

These are test-only guards. They lock user-facing semantics already required by the
Training Officer workflow without changing production behaviour in this branch.
"""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import login
from tests.test_remediation_adjacent_integrity_guards import (
    _cadet,
    _db,
    _planning_year,
    _squadron,
    _training_class,
)


ADM703 = "ADMIN703"


def _parade_night(db, squadron, *, date_value: str):
    from app.models.training import ParadeNight

    py = _planning_year(db, squadron.id)
    pn = ParadeNight(
        squadron_id=squadron.id,
        wing_id=squadron.wing_id,
        planning_year_id=py.id,
        date=date_value,
        term="T1",
        notes="Outcome edge contract",
    )
    db.add(pn)
    db.commit()
    db.refresh(pn)
    return pn


def _session(db, squadron_id: str, parade_night_id: str, *, status: str, period: int = 1):
    from app.models.training import Session

    s = Session(
        squadron_id=squadron_id,
        parade_night_id=parade_night_id,
        period_number=period,
        status=status,
        custom_title=f"Outcome edge {uuid.uuid4().hex[:6]}",
        created_by="test",
        updated_by="test",
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def _membership(db, cadet_id: str, class_id: str, *, start_date: str, end_date: str | None = None):
    from app.models import CadetClassMembership

    m = CadetClassMembership(
        cadet_id=cadet_id,
        training_class_id=class_id,
        start_date=start_date,
        end_date=end_date,
        active_status=end_date is None,
        source="manual",
        created_by="test",
        updated_by="test",
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def test_past_draft_scheduled_session_appears_in_needs_attention(client):
    """Draft is still a scheduled/unfinalised Session once a period has been allocated."""
    headers = login(client, ADM703)
    db = _db()
    try:
        sq = _squadron(db, "703")
        if sq is None:
            pytest.skip("703 squadron is not seeded")
        pn = _parade_night(db, sq, date_value="2025-02-01")
        sess = _session(db, sq.id, pn.id, status="draft")
        session_id = sess.id
    finally:
        db.close()

    response = client.get("/api/sessions/needs-attention", headers=headers)
    assert response.status_code == 200, response.text
    returned_ids = {row["session_id"] for row in response.json()}
    assert session_id in returned_ids, (
        "Past scheduled/unfinalised Sessions must surface in Needs Attention; "
        "draft cannot disappear merely because it was never published"
    )


def test_legacy_not_delivered_session_maps_to_unresolved_cancelled_work(client):
    """Legacy richer status `not_delivered` is user-facing Cancelled work until explicitly rescheduled."""
    headers = login(client, ADM703)
    db = _db()
    try:
        sq = _squadron(db, "703")
        if sq is None:
            pytest.skip("703 squadron is not seeded")
        pn = _parade_night(db, sq, date_value="2025-02-02")
        sess = _session(db, sq.id, pn.id, status="not_delivered")
        sess.not_delivered_reason = "Legacy non-delivery requiring reschedule"
        db.commit()
        session_id = sess.id
    finally:
        db.close()

    response = client.get("/api/sessions/needs-attention", headers=headers)
    assert response.status_code == 200, response.text
    returned_ids = {row["session_id"] for row in response.json()}
    assert session_id in returned_ids, (
        "Compatibility statuses must map into the simple Training Officer workflow; "
        "not_delivered must remain actionable until a replacement exists"
    )


def test_future_cancelled_session_is_actionable_immediately(client):
    """A cancelled future lesson should be rescheduled now, not only after its original date passes."""
    headers = login(client, ADM703)
    db = _db()
    try:
        sq = _squadron(db, "703")
        if sq is None:
            pytest.skip("703 squadron is not seeded")
        pn = _parade_night(db, sq, date_value="2099-02-03")
        sess = _session(db, sq.id, pn.id, status="cancelled")
        sess.cancelled_reason = "Known in advance that lesson cannot proceed"
        db.commit()
        session_id = sess.id
    finally:
        db.close()

    response = client.get("/api/sessions/needs-attention", headers=headers)
    assert response.status_code == 200, response.text
    returned_ids = {row["session_id"] for row in response.json()}
    assert session_id in returned_ids, (
        "Cancelled Sessions remain Needs Attention until explicit reschedule, including "
        "when cancellation is known before the Parade Night date"
    )


def test_auto_completion_does_not_mark_non_delivered_audience_override_completed(client):
    """Parent Session delivery must not create false completions for a class whose override says it was not delivered."""
    headers = login(client, ADM703)
    db = _db()
    try:
        from app.models import SessionAudience

        sq = _squadron(db, "703")
        if sq is None:
            pytest.skip("703 squadron is not seeded")
        pn = _parade_night(db, sq, date_value="2025-03-01")
        delivered_class = _training_class(db, sq.id, "Delivered audience")
        missed_class = _training_class(db, sq.id, "Missed audience")
        cadet_ok = _cadet(db, sq.id, "OK703")
        cadet_missed = _cadet(db, sq.id, "MISS703")
        _membership(db, cadet_ok.id, delivered_class.id, start_date="2025-01-01")
        _membership(db, cadet_missed.id, missed_class.id, start_date="2025-01-01")

        sess = _session(db, sq.id, pn.id, status="planned")
        db.add(SessionAudience(session_id=sess.id, training_class_id=delivered_class.id))
        db.add(SessionAudience(
            session_id=sess.id,
            training_class_id=missed_class.id,
            outcome_override="cancelled_late",
            outcome_override_reason="This class did not receive the lesson",
        ))
        db.commit()
        session_id, ok_id, missed_id = sess.id, cadet_ok.id, cadet_missed.id
    finally:
        db.close()

    response = client.post(
        f"/api/sessions/{session_id}/deliver",
        json={"delivery_note": "Delivered to the class that actually received it"},
        headers=headers,
    )
    assert response.status_code == 200, response.text

    db = _db()
    try:
        from app.models.training import CadetSessionOutcome

        ok = db.query(CadetSessionOutcome).filter(
            CadetSessionOutcome.session_id == session_id,
            CadetSessionOutcome.cadet_id == ok_id,
        ).first()
        missed = db.query(CadetSessionOutcome).filter(
            CadetSessionOutcome.session_id == session_id,
            CadetSessionOutcome.cadet_id == missed_id,
        ).first()
        assert ok is not None and ok.status == "completed"
        assert missed is None or missed.status != "completed", (
            "Any non-delivered per-class SessionAudience outcome override must prevent "
            "derived Cadet completion for that class"
        )
    finally:
        db.close()


def test_manual_cadet_override_requires_membership_valid_on_parade_night_date(client):
    """Being in the target class later does not make the Cadet part of an earlier Session audience."""
    headers = login(client, ADM703)
    db = _db()
    try:
        from app.models import SessionAudience

        sq = _squadron(db, "703")
        if sq is None:
            pytest.skip("703 squadron is not seeded")
        pn = _parade_night(db, sq, date_value="2025-04-01")
        tc = _training_class(db, sq.id, "Date-aware audience")
        cadet = _cadet(db, sq.id, "DATE703")
        # Membership begins after the lesson date: this Cadet was not in the audience then.
        _membership(db, cadet.id, tc.id, start_date="2025-05-01")
        sess = _session(db, sq.id, pn.id, status="delivered")
        sess.delivery_notes = "Delivered before the Cadet joined the class"
        db.add(SessionAudience(session_id=sess.id, training_class_id=tc.id))
        db.commit()
        cadet_id, session_id = cadet.id, sess.id
    finally:
        db.close()

    response = client.post(
        f"/api/cadets/{cadet_id}/session-outcomes/{session_id}",
        json={"status": "absent", "override_reason": "Date-aware audience guard"},
        headers=headers,
    )
    assert response.status_code in (400, 404, 409), (
        "Manual Cadet outcome override must validate class membership on the actual "
        f"Parade Night date; got {response.status_code}: {response.text}"
    )
