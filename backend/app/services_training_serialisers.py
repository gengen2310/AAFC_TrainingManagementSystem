"""Training response serialisers: sessions, parade nights, parade-night
notices, cadet class memberships, training classes, session audiences,
activity local overrides, FAQ entries and parade-night templates.

Moved verbatim from routers/training.py (stabilisation Phase 3, C5). Read-only
dict builders over already-loaded rows: no HTTP, no authorization.
"""
from __future__ import annotations

from .database import iso_z
from .models import (CadetClassMembership, ParadeNight, ParadeNightTemplate, Session,
                     SessionAudience, TrainingClass)
from .models.faq import FaqEntry
from .models.planning import ActivityLocalOverride


def _sess_dict(s: Session) -> dict:
    d = {c.name: getattr(s, c.name) for c in s.__table__.columns}
    d["session_id"] = s.id  # alias for Night Builder compatibility
    return d


def _pn_dict(pn: ParadeNight) -> dict:
    return {"parade_night_id": pn.id, "squadron_id": pn.squadron_id, "date": pn.date, "term": pn.term,
            "planning_year_id": pn.planning_year_id,
            "start_time": pn.start_time, "end_time": pn.end_time, "session_count": pn.session_count,
            "parade_type": pn.parade_type, "notes": pn.notes, "published_status": pn.published_status,
            "readiness_score": pn.readiness_score, "closeout_status": pn.closeout_status,
            "timing_template_id": pn.timing_template_id, "version": pn.version}


def _notice_out(n) -> dict:
    return {
        "notice_id": n.id,
        "parade_night_id": n.parade_night_id,
        "notice_text": n.notice_text,
        "audience": n.audience,
        "priority": n.priority,
        "created_by": n.created_by,
        "is_archived": n.is_archived,
        "version": n.version,
        "created_at": iso_z(n.created_at) if n.created_at else None,
        "updated_at": iso_z(n.updated_at) if n.updated_at else None,
    }


def _membership_dict(m: CadetClassMembership, tc: TrainingClass | None = None) -> dict:
    return {
        "membership_id": m.id, "cadet_id": m.cadet_id, "training_class_id": m.training_class_id,
        "training_class_name": tc.display_name if tc else None,
        "training_stage_id": tc.training_stage_id if tc else None,
        "start_date": m.start_date, "end_date": m.end_date, "active_status": m.active_status,
        "source": m.source, "version": m.version,
        "created_at": iso_z(m.created_at) if m.created_at else None,
    }


def _training_class_dict(c: TrainingClass) -> dict:
    return {
        "training_class_id": c.id,
        "squadron_id": c.squadron_id,
        "training_year_id": c.training_year_id,
        "training_stage_id": c.training_stage_id,
        "stage_code": c.stage_code,
        "display_name": c.display_name,
        "class_number": c.class_number,
        "start_date": c.start_date,
        "end_date": c.end_date,
        "expected_count": c.expected_count,
        "notes": c.notes,
        "is_archived": c.is_archived,
        "version": c.version,
    }


def _session_audience_dict(row: SessionAudience) -> dict:
    return {
        "session_audience_id": row.id,
        "session_id": row.session_id,
        "training_class_id": row.training_class_id,
        "outcome_override": row.outcome_override,
        "outcome_override_reason": row.outcome_override_reason,
    }


def _local_override_out(o: ActivityLocalOverride) -> dict:
    return {
        "override_id": o.id, "local_date_start": o.local_date_start, "local_date_end": o.local_date_end,
        "local_time_start": o.local_time_start, "local_time_end": o.local_time_end,
        "local_notes": o.local_notes, "is_hidden": o.is_hidden,
        "updated_by": o.updated_by, "version": o.version,
    }


def _faq_dict(f: FaqEntry) -> dict:
    return {
        "id": f.id,
        "category": f.category,
        "question": f.question,
        "answer_html": f.answer_html,
        "sort_order": f.sort_order,
        "is_published": f.is_published,
        "updated_at": f.updated_at,
    }


def _template_out(t: ParadeNightTemplate, include_sessions: bool = False) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "description": t.description,
        "squadron_id": t.squadron_id,
        "session_count": len(t.sessions) if t.sessions is not None else 0,
        "created_at": iso_z(t.created_at) if t.created_at else None,
        "sessions": [
            {
                "id": s.id,
                "period_number": s.period_number,
                "curriculum_item_id": s.curriculum_item_id,
                "custom_title": s.custom_title,
                "facilitator_id": s.facilitator_id,
                "training_area_id": s.training_area_id,
                "cadet_group": s.cadet_group,
                "notes": s.notes,
            }
            for s in t.sessions
        ] if include_sessions else None,
    }
