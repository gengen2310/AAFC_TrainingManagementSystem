"""Timing-template domain helpers shared by multiple HTTP routers."""
from __future__ import annotations

from sqlalchemy.orm import Session as DBSession

from .models import TimingTemplate


def effective_template(
    db: DBSession, squadron_id: str, date: str
) -> TimingTemplate | None:
    """Return the active timing template effective on an ISO date.

    Picks the most recent template whose effective_from <= date and whose
    effective_to is either unset or >= date. This is a read-only domain rule;
    callers decide how the result affects their own endpoint workflow.
    """
    candidates = (
        db.query(TimingTemplate)
        .filter(
            TimingTemplate.squadron_id == squadron_id,
            TimingTemplate.is_archived == False,  # noqa: E712
            TimingTemplate.active_status == True,  # noqa: E712
            TimingTemplate.effective_from <= date,
        )
        .order_by(TimingTemplate.effective_from.desc())
        .all()
    )
    for template in candidates:
        if template.effective_to is None or template.effective_to >= date:
            return template
    return None
