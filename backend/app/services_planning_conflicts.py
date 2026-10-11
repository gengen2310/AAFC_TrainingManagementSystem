"""Planning conflict detection for one parade night: facilitator and room
double-booking, empty cadet groups, holiday clashes and facilitator leave.

Moved verbatim from routers/planning.py (stabilisation Phase 3, C5). No HTTP and
no authorization -- callers resolve the planning year and its scope first.
_detect_conflicts reads only; _run_conflict_check persists its findings as
unresolved PlanningConflict rows (overridden ones are kept).
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session as DBSession

from .database import utcnow
from .models import Facilitator, ParadeNight, TrainingArea
from .models import Session as TrainingSession
from .models.planning import (
    CADET_GROUPS, HolidayPeriod, PlanningConflict, PlanningFacilitatorLeave,
)


def _detect_conflicts(year_id: str, night_id: str, db: DBSession) -> list[dict]:
    """Detect conflicts for one parade night. Reads only -- writes nothing.

    Split out of _run_conflict_check so the same rules can answer two
    different questions: "record what is wrong" (the persisted conflicts,
    which carry a user's override and reason) and "what is wrong right now"
    (the derived plan review, which must not write anything to answer a
    GET). Two copies of these rules would drift, and a review that
    disagreed with the recorded conflicts would be worse than no review.

    Anchored on ParadeNight since Phase B merged ParadeDate into it."""
    pn_obj = db.get(ParadeNight, night_id)
    # Use real TrainingSession records for conflict detection
    real_sessions: list = []
    if pn_obj:
        real_sessions = db.query(TrainingSession).filter(
            TrainingSession.parade_night_id == pn_obj.id,
            TrainingSession.is_archived == False,  # noqa: E712
        ).all()

    conflicts: list[dict] = []

    def _conflict(ctype: str, severity: str, msg: str, sess_id=None):
        conflicts.append({
            "conflict_type": ctype, "severity": severity, "message": msg,
            "scheduled_session_id": sess_id,
        })

    # Facilitator double-booking
    fac_map: dict[tuple, list] = {}
    for s in real_sessions:
        if s.facilitator_id:
            key = (s.facilitator_id, s.period_number)
            fac_map.setdefault(key, []).append(s)
    for (fid, snum), group in fac_map.items():
        if len(group) > 1:
            fac = db.get(Facilitator, fid)
            name = f"{fac.current_rank or ''} {fac.last_name}".strip() if fac else fid
            _conflict("facilitator_double_booked", "critical",
                      f"Facilitator {name} is assigned to multiple groups in session {snum}.",
                      group[0].id)

    # Room double-booking
    room_map: dict[tuple, list] = {}
    for s in real_sessions:
        if s.training_area_id:
            key = (s.training_area_id, s.period_number)
            room_map.setdefault(key, []).append(s)
    for (lid, snum), group in room_map.items():
        if len(group) > 1:
            ra = db.get(TrainingArea, lid)
            name = ra.name if ra else lid
            _conflict("room_double_booked", "critical",
                      f"Location '{name}' is assigned to multiple groups in session {snum}.",
                      group[0].id)

    # Empty sessions (group has no session for this night)
    scheduled_groups = {s.cadet_group for s in real_sessions}
    for grp in CADET_GROUPS:
        if grp not in scheduled_groups:
            _conflict("empty_session", "warning",
                      f"Cadet group '{grp}' has no session scheduled for this parade night.")

    # Anchor event without prep (checked at year level - skip per-date)

    # Holiday conflict
    if pn_obj:
        holidays = db.query(HolidayPeriod).filter(
            HolidayPeriod.planning_year_id == year_id,
            HolidayPeriod.affects_parade == True,  # noqa: E712
        ).all()
        for h in holidays:
            if h.start_date <= pn_obj.date <= h.end_date:
                _conflict("holiday_conflict", "warning",
                          f"This parade date falls within the '{h.name}' holiday period.")
                break

    # Facilitator on leave
    if pn_obj:
        fac_ids = {s.facilitator_id for s in real_sessions if s.facilitator_id}
        if fac_ids:
            leave_records = db.query(PlanningFacilitatorLeave).filter(
                PlanningFacilitatorLeave.facilitator_id.in_(fac_ids),
                PlanningFacilitatorLeave.is_archived == False,  # noqa: E712
                PlanningFacilitatorLeave.start_date <= pn_obj.date,
                PlanningFacilitatorLeave.end_date >= pn_obj.date,
            ).all()
            warned_facs: set[str] = set()
            for lv in leave_records:
                if lv.facilitator_id in warned_facs:
                    continue
                warned_facs.add(lv.facilitator_id)
                fac = db.get(Facilitator, lv.facilitator_id)
                name = f"{fac.current_rank or ''} {fac.last_name}".strip() if fac else lv.facilitator_id
                reason_part = f" ({lv.reason})" if lv.reason else ""
                affected = [s for s in real_sessions if s.facilitator_id == lv.facilitator_id]
                _conflict("facilitator_on_leave", "warning",
                          f"Facilitator {name} is on leave on this date{reason_part}.",
                          affected[0].id if affected else None)

    return conflicts


def _run_conflict_check(year_id: str, night_id: str, db: DBSession) -> list[PlanningConflict]:
    """Persist the detected conflicts for one parade night.

    Replaces previous UNRESOLVED results only: a conflict a user has overridden
    carries their reason and who they are, and re-running checks must never
    discard that."""
    db.query(PlanningConflict).filter(
        PlanningConflict.parade_night_id == night_id,
        PlanningConflict.is_resolved == False,  # noqa: E712
    ).delete(synchronize_session=False)

    rows = []
    for found in _detect_conflicts(year_id, night_id, db):
        c = PlanningConflict(
            id=str(uuid.uuid4()), planning_year_id=year_id,
            parade_night_id=night_id,
            scheduled_session_id=found["scheduled_session_id"],
            conflict_type=found["conflict_type"], severity=found["severity"],
            message=found["message"], is_resolved=False,
            created_at=utcnow(), updated_at=utcnow(),
        )
        rows.append(c)
        db.add(c)
    db.commit()
    return rows
