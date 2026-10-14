"""Adoption metrics: meaningful planning activity per Squadron, from the audit
log.

Moved verbatim from routers/dashboard.py (stabilisation, service extraction). Pure
read-side computation: no HTTP, no authorization -- callers resolve scope first.
"""
from __future__ import annotations

from datetime import datetime
from sqlalchemy.orm import Session as DBSession

from .models import AuditLog


_MEANINGFUL_OBJECT_TYPES = {
    "session", "parade_night", "parade_night_bulk", "facilitator",
    "training_area", "training_class", "session_audience",
    "cadet_class_membership", "planning_year", "PlanningNotice",
}


_MEANINGFUL_ACTIONS = {
    "create", "edit", "update", "publish", "close", "status_change",
    "bulk_mark_remaining_delivered", "absorb", "set",
}


def _adoption_for_squadron(db: DBSession, squadron_id: str, since: datetime) -> dict:
    rows = (
        db.query(
            AuditLog.user_id,
            AuditLog.object_type,
            AuditLog.action,
            AuditLog.timestamp,
        )
        .filter(
            AuditLog.squadron_id == squadron_id,
            AuditLog.timestamp >= since,
            AuditLog.object_type.in_(_MEANINGFUL_OBJECT_TYPES),
            AuditLog.action.in_(_MEANINGFUL_ACTIONS),
        )
        .all()
    )

    active_user_ids: set[str] = set()
    sessions_scheduled = 0
    outcomes_recorded = 0
    programs_published = 0
    facilitators_maintained = 0
    last_ts: datetime | None = None

    for r in rows:
        if r.user_id:
            active_user_ids.add(r.user_id)
        if r.timestamp and (last_ts is None or r.timestamp > last_ts):
            last_ts = r.timestamp
        ot = r.object_type or ""
        ac = r.action or ""
        if ot == "session" and ac == "create":
            sessions_scheduled += 1
        elif ot == "session" and ac == "status_change":
            outcomes_recorded += 1
        elif ot == "parade_night_bulk" and ac == "bulk_mark_remaining_delivered":
            outcomes_recorded += 1
        elif ot == "parade_night" and ac == "publish":
            programs_published += 1
        elif ot == "facilitator" and ac in ("create", "update", "absorb"):
            facilitators_maintained += 1

    return {
        "active_users": len(active_user_ids),
        "total_meaningful_actions": len(rows),
        "sessions_scheduled": sessions_scheduled,
        "outcomes_recorded": outcomes_recorded,
        "programs_published": programs_published,
        "facilitators_maintained": facilitators_maintained,
        "last_activity": last_ts.isoformat() if last_ts else None,
    }
