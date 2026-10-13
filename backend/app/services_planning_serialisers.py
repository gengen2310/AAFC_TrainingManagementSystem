"""Planning response serialisers: planning years, parade nights in the
parade-dates shape, holidays, anchor events, locations, sessions (single and
batched via _session_out_context), conflicts, notices and CEA activities.

Moved verbatim from routers/planning.py (stabilisation Phase 3, C5). Read-only:
no HTTP, no authorization -- callers load and scope the rows first.
"""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from .database import iso_z
# One notice serialiser for both routers (R13, 2026-10-13); the planning copy
# lacked `version`, which the training copy (and optimistic locking) uses.
from .services_training_serialisers import _notice_out  # noqa: F401  (re-exported for routers/planning.py)
from .models import CurriculumItem, Facilitator, ParadeNight, SessionAudience, TrainingArea
from .models import Session as TrainingSession
from .models.custom_phases import CustomTrainingPhase
from .models.planning import (
    AnchorEvent, CeaActivity, HolidayPeriod, PlanningConflict, PlanningYear,
)
from .models.training import SessionCustomPhaseAudience


def _year_out(py: PlanningYear, unit_code: str | None = None,
              unit_name: str | None = None, wing_code: str | None = None) -> dict:
    return {
        "planning_year_id": py.id, "unit_id": py.unit_id, "wing_id": py.wing_id,
        "year": py.year, "name": py.name, "active_status": py.active_status,
        # Derived, not stored. state is filled by the caller that knows
        # which squadron the year is being viewed for; materialised says
        # a row exists, and is False for logical-only years.
        "state": None, "materialised": True,
        "unit_code": unit_code, "unit_name": unit_name, "wing_code": wing_code,
        "created_by": py.created_by, "updated_by": py.updated_by,
        "created_at": iso_z(py.created_at) if py.created_at else None,
        "updated_at": iso_z(py.updated_at) if py.updated_at else None,
        "version": py.version,
    }


def _night_out_as_date(pn: ParadeNight) -> dict:
    """Serialise a ParadeNight in the parade-dates response shape.

    parade_date_id = pn.id — backward-compat alias used by the React PW's
    ~40 references to pd.parade_date_id. Do not rename this field.
    parade_night_id = pn.id — same value; kept for callers that used the
    old linked-night field and now read the same record.
    """
    return {
        "parade_date_id": pn.id,
        "planning_year_id": pn.planning_year_id,
        "unit_id": pn.squadron_id,
        "parade_date": pn.date,
        "parade_type": pn.parade_type,
        "is_active": pn.is_active,
        "notes": pn.notes,
        "term": pn.term,
        "week_number": pn.week_number,
        "cancellation_reason": pn.cancellation_reason,
        "parade_night_id": pn.id,
    }


def _holiday_out(h: HolidayPeriod) -> dict:
    return {
        "holiday_id": h.id, "planning_year_id": h.planning_year_id,
        "jurisdiction": h.jurisdiction, "name": h.name,
        "start_date": h.start_date, "end_date": h.end_date,
        "holiday_type": getattr(h, "holiday_type", "school_holiday"),
        "affects_parade": h.affects_parade, "notes": h.notes,
    }


def _anchor_out(a: AnchorEvent) -> dict:
    return {
        "anchor_event_id": a.id, "planning_year_id": a.planning_year_id,
        "owning_level": a.owning_level, "wing_id": a.wing_id, "unit_id": a.unit_id,
        "event_name": a.event_name, "event_type": a.event_type, "importance": a.importance,
        "importance_level": getattr(a, "importance_level", None),
        "start_date": a.start_date, "end_date": a.end_date,
        # Flat audience fields (expected by frontend TS type)
        "audience_orientation": a.audience_orientation,
        "audience_initial": a.audience_initial,
        "audience_junior": a.audience_junior,
        "audience_intermediate": a.audience_intermediate,
        "audience_senior": a.audience_senior,
        "audience_staff_only": getattr(a, "audience_staff_only", False),
        "audience_proficient": getattr(a, "audience_proficient", False),
        "audience_first_years": getattr(a, "audience_first_years", False),
        # Nested audience object (kept for backward compatibility)
        "audience": {
            "orientation": a.audience_orientation, "initial": a.audience_initial,
            "junior": a.audience_junior, "intermediate": a.audience_intermediate,
            "senior": a.audience_senior,
            "staff_only": getattr(a, "audience_staff_only", False),
            "proficient": getattr(a, "audience_proficient", False),
            "first_years": getattr(a, "audience_first_years", False),
        },
        "cea_activity_id": getattr(a, "cea_activity_id", None),
        "nomination_end_date": getattr(a, "nomination_end_date", None),
        "unit_name": getattr(a, "unit_name", None),
        "planning_impact": a.planning_impact,
        "readiness_requirements": a.readiness_requirements,
        "notes": a.notes, "is_archived": a.is_archived,
        "created_by": a.created_by,
        "created_at": iso_z(a.created_at) if a.created_at else None,
        "version": a.version,
    }


def _location_out(loc: TrainingArea) -> dict:
    # Rooms merger (master transformation plan, Phase 1): Planning Workspace's
    # Rooms tab now reads/writes the same `training_areas` table connected-
    # frontend's Resources page uses, instead of the separate `planning_locations`
    # table. This also fixes a real, live bug: create_session/update_session's
    # room-resolution (`db.get(TrainingArea, body.location_id)`) only ever looked
    # up TrainingArea rows — a location_id from the old PlanningLocation-backed
    # endpoint silently failed to resolve, so a room picked in Planning Workspace
    # would not actually attach to the session. The response shape below is kept
    # identical to the old PlanningLocation-backed JSON so no frontend changes
    # are required.
    return {
        "location_id": loc.id, "unit_id": loc.squadron_id, "name": loc.name,
        "location_type": loc.type, "capacity": loc.capacity,
        "notes": loc.notes, "active_status": loc.active_status,
        "capabilities": loc.capabilities,
    }


def _session_out_context(db: DBSession, sessions: list) -> dict:
    """Pre-load everything _real_session_out() needs for MANY sessions in a
    constant number of queries. Serialising one session at a time issued ~5
    queries per session (measured: term planner 26 queries for 4 sessions, 66
    for 12), so a full training year cost ~1,200 queries per request. Output
    is identical with or without the context (pinned by a parity test)."""
    from .models.training import SessionAssistantFacilitator as _SAF
    ids = [s.id for s in sessions]
    ctx: dict = {"rooms": {}, "facs": {}, "saf": {}, "ci": {}, "aud": {}, "cpa": {}}
    if not ids:
        return ctx
    room_ids = {s.training_area_id for s in sessions if s.training_area_id and not s.training_area_name_at_time}
    if room_ids:
        ctx["rooms"] = {r.id: r.name for r in db.query(TrainingArea).filter(TrainingArea.id.in_(room_ids)).all()}
    saf_rows = db.query(_SAF).filter(_SAF.session_id.in_(ids)).all()
    for row in saf_rows:
        ctx["saf"].setdefault(row.session_id, []).append(row)
    fac_ids = {s.assistant_facilitator_id for s in sessions if s.assistant_facilitator_id} | {r.user_id for r in saf_rows}
    if fac_ids:
        ctx["facs"] = {f.id: f for f in db.query(Facilitator).filter(Facilitator.id.in_(fac_ids)).all()}
    ci_ids = {s.curriculum_item_id for s in sessions if s.curriculum_item_id}
    if ci_ids:
        ctx["ci"] = {c.id: c for c in db.query(CurriculumItem).filter(CurriculumItem.id.in_(ci_ids)).all()}
    ctx["aud"] = dict(db.query(SessionAudience.session_id, func.count(SessionAudience.id))
                      .filter(SessionAudience.session_id.in_(ids))
                      .group_by(SessionAudience.session_id).all())
    for sid, cp in (db.query(SessionCustomPhaseAudience.session_id, CustomTrainingPhase)
                    .join(CustomTrainingPhase, SessionCustomPhaseAudience.custom_phase_id == CustomTrainingPhase.id)
                    .filter(SessionCustomPhaseAudience.session_id.in_(ids)).all()):
        ctx["cpa"].setdefault(sid, []).append(cp)
    return ctx


def _real_session_out(
    s: TrainingSession, db: DBSession,
    ci_tier: "dict[str, dict] | None" = None,
    ctx: "dict | None" = None,
) -> dict:
    """Serialize a real training Session in the builder grid format.

    Bulk callers pass ctx from _session_out_context() (constant queries for the
    whole batch); single-session callers omit it and it queries directly."""
    room_name = s.training_area_name_at_time
    if not room_name and s.training_area_id:
        if ctx is not None:
            room_name = ctx["rooms"].get(s.training_area_id) or room_name
        else:
            ra = db.get(TrainingArea, s.training_area_id)
            if ra:
                room_name = ra.name
    from .models.training import SessionAssistantFacilitator as _SAF

    def _fac(fid):
        return ctx["facs"].get(fid) if ctx is not None else db.get(Facilitator, fid)

    asst_name: str | None = None
    if s.assistant_facilitator_id:
        af = _fac(s.assistant_facilitator_id)
        if af:
            asst_name = " ".join(x for x in [af.current_rank, af.first_name, af.last_name] if x)
    # Build assistant_facilitators list from the join table
    asst_rows = ctx["saf"].get(s.id, []) if ctx is not None else db.query(_SAF).filter_by(session_id=s.id).all()
    assistant_facilitators_list: list[dict] = []
    for row in asst_rows:
        f = _fac(row.user_id)
        if f:
            disp = " ".join(x for x in [f.current_rank, f.first_name, f.last_name] if x)
        else:
            disp = row.user_id
        assistant_facilitators_list.append({"user_id": row.user_id, "display_name": disp})
    # CLASS-21: curriculum core_status and is_optional for Foundation/Extension/Optional PW filters.
    # ci_tier pre-loaded by bulk callers (long-range endpoint); falls back to
    # identity-map PK lookup when not supplied (weekly-program, term-planner).
    core_status: str | None = None
    is_optional: bool = False
    if s.curriculum_item_id:
        if ci_tier is not None:
            t = ci_tier.get(s.curriculum_item_id)
            if t:
                core_status = t["core_status"]
                is_optional = t.get("is_optional", False)
        else:
            ci_obj = ctx["ci"].get(s.curriculum_item_id) if ctx is not None else db.get(CurriculumItem, s.curriculum_item_id)
            if ci_obj:
                core_status = ci_obj.core_status
                is_optional = ci_obj.is_optional
    return {
        "session_id": s.id,
        "parade_night_id": s.parade_night_id,
        "squadron_id": s.squadron_id,
        "cadet_group": s.cadet_group,
        "session_number": s.period_number,
        "part_number": s.part_number,
        "curriculum_id": s.curriculum_item_id,
        "curriculum_code": s.curriculum_code_at_time,
        "curriculum_title": s.curriculum_title_at_time,
        "activity_title": s.curriculum_title_at_time or s.custom_title,
        "facilitator_id": s.facilitator_id,
        "facilitator_name": s.facilitator_display_name_at_time,
        "assistant_facilitator_id": s.assistant_facilitator_id,
        "assistant_facilitator_name": asst_name,
        "assistant_facilitators": assistant_facilitators_list,
        "location_id": s.training_area_id,
        "location_name": room_name,
        "status": s.status,
        "notes": s.delivery_notes,
        "is_combined": (ctx["aud"].get(s.id, 0) if ctx is not None
                        else db.query(SessionAudience).filter(SessionAudience.session_id == s.id).count()) > 1,
        "custom_phase_audiences": [
            {"custom_phase_id": cp.id, "name": cp.name}
            for cp in (ctx["cpa"].get(s.id, []) if ctx is not None else [
                cp for _, cp in db.query(SessionCustomPhaseAudience, CustomTrainingPhase)
                .join(CustomTrainingPhase, SessionCustomPhaseAudience.custom_phase_id == CustomTrainingPhase.id)
                .filter(SessionCustomPhaseAudience.session_id == s.id)
                .all()])
        ],
        "override_conflict": False,
        "created_at": iso_z(s.created_at) if s.created_at else None,
        "version": s.version,
        "core_status": core_status,
        "is_optional": is_optional,
    }


def _conflict_out(c: PlanningConflict) -> dict:
    return {
        "conflict_id": c.id, "planning_year_id": c.planning_year_id,
        "parade_night_id": c.parade_night_id,
        "scheduled_session_id": c.scheduled_session_id,
        "conflict_type": c.conflict_type, "severity": c.severity,
        "message": c.message, "is_resolved": c.is_resolved,
        "override_reason": c.override_reason,
        "created_at": iso_z(c.created_at) if c.created_at else None,
    }


def _cea_activity_out(a: CeaActivity) -> dict:
    return {
        "id": a.id,
        "import_batch_id": a.import_batch_id,
        "planning_year_id": a.planning_year_id,
        "wing_id": a.wing_id,
        "unit_id": a.unit_id,
        "cea_activity_id": a.cea_activity_id,
        "activity_type": a.activity_type,
        "status_name": a.status_name,
        "parent_unit": a.parent_unit,
        "host_unit": a.host_unit,
        "activity_name": a.activity_name,
        "nomination_start_date": a.nomination_start_date,
        "nomination_end_date": a.nomination_end_date,
        "activity_start_date": a.activity_start_date,
        "activity_end_date": a.activity_end_date,
        "start_time": a.start_time,
        "end_time": a.end_time,
        "location": a.location,
        "activity_poc": a.activity_poc,
        "notes": a.notes,
        "source_type": a.source_type,
        "classification_status": a.classification_status,
        "importance": a.importance,
        "audience_staff_only": a.audience_staff_only,
        "audience_seniors": a.audience_seniors,
        "audience_proficient": a.audience_proficient,
        "audience_first_years": a.audience_first_years,
        "classified_by": a.classified_by,
        "classified_at": a.classified_at,
        "is_removed_from_cea": a.is_removed_from_cea,
        "is_archived": a.is_archived,
        "created_at": iso_z(a.created_at) if a.created_at else None,
    }
