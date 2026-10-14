"""Training-class curriculum progress read model.

Shared by Training, Dashboard and Planning surfaces so one calculation governs
all three instead of importing private helpers from sibling routers.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import or_
from sqlalchemy.orm import Session as DBSession

from .models import (
    CurriculumItem,
    CurriculumPhase,
    Session,
    SessionAudience,
    Squadron,
    TrainingClass,
)

ITEM_STATUS_PRIORITY = [
    "delivered",
    "delivered_with_issue",
    "not_delivered",
    "cancelled",
    "planned",
    "rescheduled",
]


def class_curriculum_progress(db: DBSession, training_class: TrainingClass) -> dict:
    """Derive curriculum progress for one Training Class from canonical data."""
    stage = (
        db.get(CurriculumPhase, training_class.training_stage_id)
        if training_class.training_stage_id
        else None
    )
    stage_name = stage.name if stage else None
    squadron = db.get(Squadron, training_class.squadron_id)
    wing_id = squadron.wing_id if squadron else None

    conditions = [CurriculumItem.owning_level == "national"]
    if wing_id:
        conditions.append(
            (CurriculumItem.owning_level == "wing")
            & (CurriculumItem.wing_id == wing_id)
        )
    conditions.append(CurriculumItem.squadron_id == training_class.squadron_id)

    items = (
        db.query(CurriculumItem)
        .filter(
            CurriculumItem.is_archived == False,  # noqa: E712
            CurriculumItem.phase == stage_name,
            or_(*conditions),
        )
        .order_by(CurriculumItem.recommended_sequence)
        .all()
    )

    linked = (
        db.query(SessionAudience, Session)
        .join(Session, SessionAudience.session_id == Session.id)
        .filter(
            SessionAudience.training_class_id == training_class.id,
            Session.is_archived == False,  # noqa: E712
        )
        .all()
    )

    by_item: dict[str, list[dict]] = defaultdict(list)
    for audience, session in linked:
        if not session.curriculum_item_id:
            continue
        effective = audience.outcome_override or session.status or "planned"
        by_item[session.curriculum_item_id].append(
            {"session_id": session.id, "status": effective}
        )

    requirements = []
    summary = {
        "total": 0,
        "delivered": 0,
        "planned": 0,
        "not_delivered": 0,
        "cancelled": 0,
        "not_started": 0,
    }
    for item in items:
        sessions = by_item.get(item.id, [])
        if not sessions:
            status = "not_started"
        else:
            present = {row["status"] for row in sessions}
            status = next(
                (candidate for candidate in ITEM_STATUS_PRIORITY if candidate in present),
                "planned",
            )
        bucket = "delivered" if status in ("delivered", "delivered_with_issue") else status
        summary["total"] += 1
        summary[bucket] = summary.get(bucket, 0) + 1
        requirements.append(
            {
                "curriculum_id": item.id,
                "code": item.code,
                "title": item.title,
                "status": status,
                "sessions": sessions,
            }
        )

    return {
        "training_class_id": training_class.id,
        "training_stage_id": training_class.training_stage_id,
        "stage_name": stage_name,
        "requirements": requirements,
        "summary": summary,
    }
