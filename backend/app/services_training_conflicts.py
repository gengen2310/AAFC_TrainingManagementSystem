"""Session resource-clash detection: facilitator, assistant and room
collisions within one parade-night period, with parallel delivery of the same
lesson (one teaching event recorded per class) not counted as a clash.

Moved verbatim from routers/training.py (stabilisation Phase 3, C5). Read-only:
no HTTP, no authorization -- callers decide what a returned clash means.
"""
from __future__ import annotations

from sqlalchemy.orm import Session as DBSession

from .models import Session
from .models.training import SessionAssistantFacilitator


def _is_parallel_delivery(body, sib) -> bool:
    """True when two sessions in the same period are one delivery, not a clash.

    A squadron routinely runs parallel Training Classes -- Senior 1 and Senior 2
    both taking the same lesson from the same instructor in the same room. That
    is one teaching event recorded as two sessions (the printed Weekly Program
    renders one session per class column), and the resource check used to reject
    it as a facilitator/room double-booking, which made those parade nights
    unsaveable.

    Same content is the test. If the two sessions teach different things, the
    instructor really would have to be in two places and it is a genuine clash.
    Rooms must also agree: the same lesson in two different rooms is not one
    event, so that still counts.
    """
    a_item, b_item = body.curriculum_item_id, sib.curriculum_item_id
    if a_item and b_item:
        same_content = a_item == b_item
    elif not a_item and not b_item:
        a_t = (body.custom_title or "").strip().lower()
        b_t = (sib.custom_title or "").strip().lower()
        same_content = bool(a_t) and a_t == b_t
    else:
        same_content = False
    if not same_content:
        return False
    # One lesson cannot happen in two rooms at once.
    if body.training_area_id and sib.training_area_id:
        return body.training_area_id == sib.training_area_id
    return True


def _resource_conflicts(db: DBSession, parade_night_id: str, period_number, body,
                        exclude_session_id: str | None = None) -> list[dict]:
    """Return lead/assistant/room collisions for the target period.

    Uses the incoming plural assistant list when supplied. On edits where the
    field is omitted, the currently persisted assistants are used instead.
    """
    q = db.query(Session).filter(
        Session.parade_night_id == parade_night_id,
        Session.period_number == period_number,
        Session.is_archived == False,  # noqa: E712
    )
    if exclude_session_id:
        q = q.filter(Session.id != exclude_session_id)
    sibling_sessions = q.all()
    sibling_ids = [s.id for s in sibling_sessions]

    if getattr(body, "assistant_facilitator_ids", None) is not None:
        our_asst_ids = set(body.assistant_facilitator_ids or [])
    elif exclude_session_id:
        our_asst_ids = {
            row.user_id for row in db.query(SessionAssistantFacilitator).filter(
                SessionAssistantFacilitator.session_id == exclude_session_id
            ).all()
        }
    else:
        our_asst_ids = set()

    sibling_asst_by_session: dict[str, set[str]] = {}
    if sibling_ids:
        for row in db.query(SessionAssistantFacilitator).filter(
            SessionAssistantFacilitator.session_id.in_(sibling_ids)
        ).all():
            sibling_asst_by_session.setdefault(row.session_id, set()).add(row.user_id)

    conflicts: list[dict] = []
    for sib in sibling_sessions:
        if _is_parallel_delivery(body, sib):
            continue
        sibling_assts = sibling_asst_by_session.get(sib.id, set())
        if body.facilitator_id and sib.facilitator_id == body.facilitator_id:
            conflicts.append({"type": "facilitator_clash", "session_id": sib.id,
                              "resource_id": sib.facilitator_id,
                              "resource_name": sib.facilitator_display_name_at_time})
        if body.facilitator_id and body.facilitator_id in sibling_assts:
            conflicts.append({"type": "facilitator_double_booked", "session_id": sib.id,
                              "resource_id": body.facilitator_id,
                              "resource_name": body.facilitator_id})
        if body.training_area_id and sib.training_area_id == body.training_area_id:
            conflicts.append({"type": "room_clash", "session_id": sib.id,
                              "resource_id": sib.training_area_id,
                              "resource_name": sib.training_area_name_at_time})
        if sib.facilitator_id and sib.facilitator_id in our_asst_ids:
            conflicts.append({"type": "facilitator_double_booked", "session_id": sib.id,
                              "resource_id": sib.facilitator_id,
                              "resource_name": sib.facilitator_display_name_at_time})
        for assistant_id in sorted(our_asst_ids & sibling_assts):
            conflicts.append({"type": "facilitator_double_booked", "session_id": sib.id,
                              "resource_id": assistant_id,
                              "resource_name": assistant_id})

    return conflicts
