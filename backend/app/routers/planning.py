"""TRGO Planning Module router.

Provides endpoints for annual training planning: planning years,
parade dates, holidays, anchor events, term planner, parade night
builder, scheduled sessions, locations, facilitators (planning view),
conflict detection, and weekly/long-range program output.
"""
from __future__ import annotations
import io, uuid
from datetime import date, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from ..database import get_db, utcnow
from ..models import (
    Wing, Squadron, CurriculumItem, Facilitator, AuditLog, ParadeNight, TrainingArea,
)
from ..models import Session as TrainingSession
from ..models.planning import (
    PlanningYear, ParadeDate, HolidayPeriod, AnchorEvent,
    AnchorPrepRule, AnchorPrepPlan, ScheduledSession,
    PlanningLocation, PlanningConflict,
    CADET_GROUPS, IMPORTANCE_LEVELS, EVENT_TYPES,
)
from ..models.training import TimingTemplate, TimingBlock
from ..dependencies import get_principal
from ..permissions import Principal, require_role, require_can_write_squadron
from ..services import audit
from .timing import _effective_template

router = APIRouter(prefix="/api/planning", tags=["planning"])

# ─────────────────────────────────────────────────────────────
# RBAC helpers
# ─────────────────────────────────────────────────────────────

_WRITE_BLOCKED = frozenset({"sqn_general", "wing_viewer", "national_viewer", "auditor"})
_NAT_ROLES     = frozenset({"national_admin", "system_admin"})
_WING_ROLES    = frozenset({"wing_admin", *_NAT_ROLES})
_ALL_ADMIN     = frozenset({"sqn_admin", "wing_admin", "national_admin", "system_admin"})


def _require_plan_write(p: Principal) -> None:
    if p.role in _WRITE_BLOCKED:
        raise HTTPException(403, detail={"error": "forbidden"})


def _require_year_access(p: Principal, py: PlanningYear, write: bool = False) -> None:
    """Enforce scope: sqn_admin → own sqn; wing_admin → own wing; nat → all."""
    if write and p.role in _WRITE_BLOCKED:
        raise HTTPException(403, detail={"error": "forbidden"})
    if p.role == "sqn_admin":
        if py.unit_id != p.squadron_id:
            raise HTTPException(403, detail={"error": "out_of_scope"})
    elif p.role == "wing_admin":
        if py.wing_id != p.wing_id:
            raise HTTPException(403, detail={"error": "out_of_scope"})
    elif p.role in ("wing_viewer", "national_viewer", "auditor"):
        if p.role == "wing_viewer" and py.wing_id != p.wing_id:
            raise HTTPException(403, detail={"error": "out_of_scope"})
    # nat/system: unrestricted


def _get_year_or_404(year_id: str, db: DBSession) -> PlanningYear:
    py = db.get(PlanningYear, year_id)
    if not py:
        raise HTTPException(404, detail={"error": "planning_year_not_found"})
    return py


def _find_or_create_parade_night(db: DBSession, unit_id: str, date_str: str, p: Principal) -> ParadeNight | None:
    """Find an existing ParadeNight for unit+date, or create one using the effective timing template."""
    if not unit_id:
        return None
    sq = db.get(Squadron, unit_id)
    if not sq:
        return None
    pn = db.query(ParadeNight).filter(
        ParadeNight.squadron_id == unit_id,
        ParadeNight.date == date_str,
        ParadeNight.is_archived == False,  # noqa: E712
    ).first()
    if pn:
        return pn
    # Create a new ParadeNight
    tmpl = _effective_template(db, unit_id, date_str)
    if tmpl:
        ip_count = sum(1 for b in tmpl.blocks if b.is_instructional_period)
        session_count = ip_count if ip_count > 0 else (sq.default_session_count or 3)
    else:
        session_count = sq.default_session_count or 3
    pn = ParadeNight(
        squadron_id=unit_id, wing_id=sq.wing_id, date=date_str, term=None,
        start_time=sq.default_start_time, end_time=sq.default_end_time,
        session_count=session_count, parade_type="normal",
        timing_template_id=tmpl.id if tmpl else None,
        created_by=p.user_id,
    )
    db.add(pn)
    db.flush()  # get ID without committing outer transaction
    return pn


# ─────────────────────────────────────────────────────────────
# Serialisers
# ─────────────────────────────────────────────────────────────

def _year_out(py: PlanningYear, unit_code: str | None = None,
              unit_name: str | None = None, wing_code: str | None = None) -> dict:
    return {
        "planning_year_id": py.id, "unit_id": py.unit_id, "wing_id": py.wing_id,
        "year": py.year, "name": py.name, "active_status": py.active_status,
        "unit_code": unit_code, "unit_name": unit_name, "wing_code": wing_code,
        "created_by": py.created_by, "updated_by": py.updated_by,
        "created_at": py.created_at.isoformat() if py.created_at else None,
        "updated_at": py.updated_at.isoformat() if py.updated_at else None,
    }


def _date_out(pd: ParadeDate) -> dict:
    return {
        "parade_date_id": pd.id, "planning_year_id": pd.planning_year_id,
        "unit_id": pd.unit_id, "parade_date": pd.parade_date,
        "parade_type": pd.parade_type, "is_active": pd.is_active, "notes": pd.notes,
        "term": getattr(pd, "term", None),
        "week_number": getattr(pd, "week_number", None),
        "cancellation_reason": getattr(pd, "cancellation_reason", None),
        "parade_night_id": pd.parade_night_id,
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
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


def _session_out(s: ScheduledSession, db: DBSession) -> dict:
    curr_code = curr_title = None
    if s.curriculum_id:
        ci = db.get(CurriculumItem, s.curriculum_id)
        if ci:
            curr_code, curr_title = ci.code, ci.title
    fac_name = None
    if s.facilitator_id:
        f = db.get(Facilitator, s.facilitator_id)
        if f:
            fac_name = f"{f.current_rank or ''} {f.last_name}".strip()
    loc_name = None
    if s.location_id:
        loc = db.get(PlanningLocation, s.location_id)
        if loc:
            loc_name = loc.name
    return {
        "scheduled_session_id": s.id, "parade_date_id": s.parade_date_id,
        "unit_id": s.unit_id, "cadet_group": s.cadet_group,
        "session_number": s.session_number, "curriculum_id": s.curriculum_id,
        "curriculum_code": curr_code, "curriculum_title": curr_title,
        "activity_title": s.activity_title or curr_title,
        "facilitator_id": s.facilitator_id, "facilitator_name": fac_name,
        "location_id": s.location_id, "location_name": loc_name,
        "is_combined": s.is_combined, "combined_groups": s.combined_groups or [],
        "override_conflict": s.override_conflict, "override_reason": s.override_reason,
        "status": s.status, "notes": s.notes,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _location_out(loc: PlanningLocation) -> dict:
    return {
        "location_id": loc.id, "unit_id": loc.unit_id, "name": loc.name,
        "location_type": loc.location_type, "capacity": loc.capacity,
        "notes": loc.notes, "active_status": loc.active_status,
    }


def _real_session_out(s: TrainingSession, db: DBSession) -> dict:
    """Serialize a real training Session in the builder grid format."""
    room_name = s.training_area_name_at_time
    if not room_name and s.training_area_id:
        ra = db.get(TrainingArea, s.training_area_id)
        if ra:
            room_name = ra.name
    return {
        "session_id": s.id,
        "parade_night_id": s.parade_night_id,
        "squadron_id": s.squadron_id,
        "cadet_group": s.cadet_group,
        "session_number": s.period_number,
        "curriculum_id": s.curriculum_item_id,
        "curriculum_code": s.curriculum_code_at_time,
        "curriculum_title": s.curriculum_title_at_time,
        "activity_title": s.curriculum_title_at_time or s.custom_title,
        "facilitator_id": s.facilitator_id,
        "facilitator_name": s.facilitator_display_name_at_time,
        "location_id": s.training_area_id,
        "location_name": room_name,
        "status": s.status,
        "notes": s.delivery_notes,
        "is_combined": False,
        "override_conflict": False,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _conflict_out(c: PlanningConflict) -> dict:
    return {
        "conflict_id": c.id, "planning_year_id": c.planning_year_id,
        "parade_date_id": c.parade_date_id,
        "scheduled_session_id": c.scheduled_session_id,
        "conflict_type": c.conflict_type, "severity": c.severity,
        "message": c.message, "is_resolved": c.is_resolved,
        "override_reason": c.override_reason,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


# ─────────────────────────────────────────────────────────────
# Planning Years
# ─────────────────────────────────────────────────────────────

class PlanningYearIn(BaseModel):
    year: int
    name: str
    unit_id: Optional[str] = None
    wing_id: Optional[str] = None
    active_status: bool = True


class PlanningYearUpdateIn(BaseModel):
    name: Optional[str] = None
    active_status: Optional[bool] = None


@router.get("/years")
def list_planning_years(
    unit_id: Optional[str] = None,
    wing_id: Optional[str] = None,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    q = db.query(PlanningYear)
    if p.role == "sqn_admin":
        q = q.filter(PlanningYear.unit_id == p.squadron_id)
    elif p.role in ("wing_admin", "wing_viewer"):
        q = q.filter(PlanningYear.wing_id == p.wing_id)
    if unit_id:
        q = q.filter(PlanningYear.unit_id == unit_id)
    if wing_id:
        q = q.filter(PlanningYear.wing_id == wing_id)
    years = q.order_by(PlanningYear.year.desc()).all()

    # Preload squadrons and wings for label enrichment
    sqn_ids = {py.unit_id for py in years if py.unit_id}
    wing_ids = {py.wing_id for py in years if py.wing_id}
    sqns = {s.id: s for s in db.query(Squadron).filter(Squadron.id.in_(sqn_ids)).all()} if sqn_ids else {}
    wings = {w.id: w for w in db.query(Wing).filter(Wing.id.in_(wing_ids)).all()} if wing_ids else {}

    out = []
    for py in years:
        sq = sqns.get(py.unit_id) if py.unit_id else None
        wg = wings.get(py.wing_id) if py.wing_id else None
        out.append(_year_out(py,
            unit_code=sq.code if sq else None,
            unit_name=sq.name if sq else None,
            wing_code=wg.code if wg else None,
        ))
    return out


@router.post("/years")
def create_planning_year(
    body: PlanningYearIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    _require_plan_write(p)
    unit_id = body.unit_id
    wing_id = body.wing_id
    if p.role == "sqn_admin":
        unit_id = p.squadron_id
        wing_id = p.wing_id
    elif p.role == "wing_admin":
        wing_id = p.wing_id
        if unit_id and unit_id != p.squadron_id:
            sqn = db.get(Squadron, unit_id)
            if not sqn or sqn.wing_id != p.wing_id:
                raise HTTPException(403, detail={"error": "out_of_scope"})
    py = PlanningYear(
        id=str(uuid.uuid4()), year=body.year, name=body.name,
        unit_id=unit_id, wing_id=wing_id, active_status=body.active_status,
        created_by=p.user_id, created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(py); db.commit()
    audit(db, p, object_type="planning_year", object_id=py.id, action="create",
          new={"year": body.year, "name": body.name})
    sq = db.get(Squadron, py.unit_id) if py.unit_id else None
    wg = db.get(Wing, py.wing_id) if py.wing_id else None
    return _year_out(py,
        unit_code=sq.code if sq else None, unit_name=sq.name if sq else None,
        wing_code=wg.code if wg else None)


@router.get("/years/{year_id}")
def get_planning_year(
    year_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py)
    sq = db.get(Squadron, py.unit_id) if py.unit_id else None
    wg = db.get(Wing, py.wing_id) if py.wing_id else None
    return _year_out(py,
        unit_code=sq.code if sq else None, unit_name=sq.name if sq else None,
        wing_code=wg.code if wg else None)


@router.patch("/years/{year_id}")
def update_planning_year(
    year_id: str,
    body: PlanningYearUpdateIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py, write=True)
    if body.name is not None:
        py.name = body.name
    if body.active_status is not None:
        py.active_status = body.active_status
    py.updated_by = p.user_id; py.updated_at = utcnow()
    db.commit()
    audit(db, p, object_type="planning_year", object_id=py.id, action="update")
    sq = db.get(Squadron, py.unit_id) if py.unit_id else None
    wg = db.get(Wing, py.wing_id) if py.wing_id else None
    return _year_out(py,
        unit_code=sq.code if sq else None, unit_name=sq.name if sq else None,
        wing_code=wg.code if wg else None)


# ─────────────────────────────────────────────────────────────
# Parade Dates
# ─────────────────────────────────────────────────────────────

class ParadeDateIn(BaseModel):
    parade_date: str  # ISO YYYY-MM-DD
    parade_type: str = "standard"
    is_active: bool = True
    notes: Optional[str] = None


class GenerateParadeDatesIn(BaseModel):
    weekday: int          # 0=Mon … 6=Sun
    start_date: str       # ISO YYYY-MM-DD
    end_date: str | None = None   # ISO YYYY-MM-DD; omit if max_repeats given
    parade_type: str = "standard"
    exclude_holidays: bool = True
    frequency: str = "weekly"          # weekly | fortnightly | monthly | daily
    excluded_dates: list[str] = []     # specific ISO dates to skip
    max_repeats: int | None = None     # alternative to end_date


@router.get("/years/{year_id}/parade-dates")
def list_parade_dates(
    year_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py)
    rows = db.query(ParadeDate).filter(ParadeDate.planning_year_id == year_id)\
             .order_by(ParadeDate.parade_date).all()
    # Annotate with holiday flags
    holidays = db.query(HolidayPeriod).filter(
        HolidayPeriod.planning_year_id == year_id,
        HolidayPeriod.affects_parade == True,  # noqa: E712
    ).all()
    def in_holiday(d: str) -> bool:
        for h in holidays:
            if h.start_date <= d <= h.end_date:
                return True
        return False
    out = []
    for pd in rows:
        r = _date_out(pd)
        r["in_holiday"] = in_holiday(pd.parade_date)
        out.append(r)
    return out


@router.post("/years/{year_id}/parade-dates")
def add_parade_date(
    year_id: str,
    body: ParadeDateIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py, write=True)
    pn = _find_or_create_parade_night(db, py.unit_id, body.parade_date, p)
    pd = ParadeDate(
        id=str(uuid.uuid4()), planning_year_id=year_id,
        unit_id=py.unit_id, parade_date=body.parade_date,
        parade_type=body.parade_type, is_active=body.is_active,
        notes=body.notes, parade_night_id=pn.id if pn else None,
        created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(pd); db.commit()
    audit(db, p, object_type="parade_date", object_id=pd.id, action="create",
          new={"date": body.parade_date})
    return _date_out(pd)


def _compute_candidate_dates(body: GenerateParadeDatesIn, holidays: list) -> list[str]:
    """Return ISO date strings that should become parade dates given the body parameters.

    Supports weekly, fortnightly, monthly (first weekday in month), and daily frequencies.
    excluded_dates and max_repeats are applied here. Holiday exclusion is optional.
    """
    try:
        start = date.fromisoformat(body.start_date)
    except ValueError:
        raise HTTPException(400, detail={"error": "invalid_date_format"})

    end: date | None = None
    if body.end_date:
        try:
            end = date.fromisoformat(body.end_date)
        except ValueError:
            raise HTTPException(400, detail={"error": "invalid_date_format"})

    if end is None and body.max_repeats is None:
        raise HTTPException(400, detail={
            "error": "end_date_or_max_repeats_required",
            "message": "Provide either end_date or max_repeats.",
        })

    excluded_set = set(body.excluded_dates or [])

    def in_holiday(d: date) -> bool:
        ds = d.isoformat()
        return any(h.start_date <= ds <= h.end_date for h in holidays)

    freq = (body.frequency or "weekly").lower()
    candidates: list[str] = []
    d = start
    last_occurrence: date | None = None

    while True:
        if end and d > end:
            break
        if body.max_repeats is not None and len(candidates) >= body.max_repeats:
            break

        include = False
        if freq == "daily":
            include = True
        elif freq in ("weekly", "fortnightly"):
            if d.weekday() == body.weekday:
                if freq == "weekly":
                    include = True
                else:
                    # fortnightly: every second occurrence
                    if last_occurrence is None or (d - last_occurrence).days >= 14:
                        include = True
        elif freq == "monthly":
            # First occurrence of weekday in the calendar month
            if d.weekday() == body.weekday:
                # Is this the first occurrence of this weekday in the month?
                if d.day <= 7:
                    include = True
        else:
            # Unknown frequency falls back to weekly
            if d.weekday() == body.weekday:
                include = True

        if include:
            ds = d.isoformat()
            skip = ds in excluded_set
            if body.exclude_holidays and in_holiday(d):
                skip = True
            if not skip:
                candidates.append(ds)
                last_occurrence = d

        d += timedelta(days=1)

    return candidates


@router.post("/years/{year_id}/preview-parade-dates")
def preview_parade_dates(
    year_id: str,
    body: GenerateParadeDatesIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Return candidate dates without creating them. Marks which already exist."""
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py)
    holidays = db.query(HolidayPeriod).filter(
        HolidayPeriod.planning_year_id == year_id,
        HolidayPeriod.affects_parade == True,  # noqa: E712
    ).all() if body.exclude_holidays else []
    existing = {
        pd.parade_date for pd in
        db.query(ParadeDate).filter(ParadeDate.planning_year_id == year_id).all()
    }
    candidates = _compute_candidate_dates(body, holidays)
    rows = [{"date": ds, "new": ds not in existing} for ds in candidates]
    return {"dates": rows, "new_count": sum(1 for r in rows if r["new"]), "total": len(rows)}


@router.post("/years/{year_id}/generate-parade-dates")
def generate_parade_dates(
    year_id: str,
    body: GenerateParadeDatesIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py, write=True)
    holidays = db.query(HolidayPeriod).filter(
        HolidayPeriod.planning_year_id == year_id,
        HolidayPeriod.affects_parade == True,  # noqa: E712
    ).all() if body.exclude_holidays else []

    existing = {
        pd.parade_date for pd in
        db.query(ParadeDate).filter(ParadeDate.planning_year_id == year_id).all()
    }
    candidates = _compute_candidate_dates(body, holidays)
    created = []
    for ds in candidates:
        if ds not in existing:
            pn = _find_or_create_parade_night(db, py.unit_id, ds, p)
            pd = ParadeDate(
                id=str(uuid.uuid4()), planning_year_id=year_id,
                unit_id=py.unit_id, parade_date=ds,
                parade_type=body.parade_type, is_active=True,
                parade_night_id=pn.id if pn else None,
                created_at=utcnow(), updated_at=utcnow(),
            )
            db.add(pd)
            existing.add(ds)
            created.append(ds)
    db.commit()
    audit(db, p, object_type="planning_year", object_id=year_id, action="generate_parade_dates",
          new={"count": len(created)})
    return {"ok": True, "created": len(created), "dates": created}


@router.delete("/parade-dates/{date_id}")
def delete_parade_date(
    date_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    pd = db.get(ParadeDate, date_id)
    if not pd:
        raise HTTPException(404, detail={"error": "not_found"})
    py = _get_year_or_404(pd.planning_year_id, db)
    _require_year_access(p, py, write=True)
    audit(db, p, object_type="parade_date", object_id=pd.id, action="delete",
          new={"date": pd.parade_date})
    db.delete(pd); db.commit()
    return {"ok": True}


# ─────────────────────────────────────────────────────────────
# Holidays
# ─────────────────────────────────────────────────────────────

class HolidayIn(BaseModel):
    name: str
    start_date: str
    end_date: str
    jurisdiction: Optional[str] = None
    holiday_type: str = "school_holiday"
    affects_parade: bool = True
    notes: Optional[str] = None


@router.get("/years/{year_id}/holidays")
def list_holidays(
    year_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py)
    rows = db.query(HolidayPeriod).filter(HolidayPeriod.planning_year_id == year_id)\
             .order_by(HolidayPeriod.start_date).all()
    return [_holiday_out(h) for h in rows]


@router.post("/years/{year_id}/holidays")
def add_holiday(
    year_id: str,
    body: HolidayIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py, write=True)
    h = HolidayPeriod(
        id=str(uuid.uuid4()), planning_year_id=year_id,
        jurisdiction=body.jurisdiction, name=body.name,
        start_date=body.start_date, end_date=body.end_date,
        holiday_type=body.holiday_type,
        affects_parade=body.affects_parade, notes=body.notes,
        created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(h); db.commit()
    audit(db, p, object_type="holiday_period", object_id=h.id, action="create",
          new={"name": body.name, "start": body.start_date, "end": body.end_date})
    return _holiday_out(h)


@router.delete("/holidays/{holiday_id}")
def delete_holiday(
    holiday_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    h = db.get(HolidayPeriod, holiday_id)
    if not h:
        raise HTTPException(404, detail={"error": "not_found"})
    py = _get_year_or_404(h.planning_year_id, db)
    _require_year_access(p, py, write=True)
    audit(db, p, object_type="holiday_period", object_id=h.id, action="delete",
          new={"name": h.name})
    db.delete(h); db.commit()
    return {"ok": True}


# ─────────────────────────────────────────────────────────────
# Anchor Events
# ─────────────────────────────────────────────────────────────

class AnchorEventIn(BaseModel):
    event_name: str
    event_type: str = "other"
    importance: str = "key_event"
    start_date: str
    end_date: Optional[str] = None
    owning_level: str = "unit"
    wing_id: Optional[str] = None
    unit_id: Optional[str] = None
    audience_orientation: bool = True
    audience_initial: bool = True
    audience_junior: bool = True
    audience_intermediate: bool = True
    audience_senior: bool = True
    planning_impact: Optional[str] = None
    readiness_requirements: Optional[str] = None
    notes: Optional[str] = None


class AnchorEventUpdateIn(BaseModel):
    event_name: Optional[str] = None
    importance: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    planning_impact: Optional[str] = None
    readiness_requirements: Optional[str] = None
    notes: Optional[str] = None


@router.get("/years/{year_id}/anchors")
def list_anchors(
    year_id: str,
    importance: Optional[str] = None,
    event_type: Optional[str] = None,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py)
    q = db.query(AnchorEvent).filter(
        AnchorEvent.planning_year_id == year_id,
        AnchorEvent.is_archived == False,  # noqa: E712
    )
    if importance:
        q = q.filter(AnchorEvent.importance == importance)
    if event_type:
        q = q.filter(AnchorEvent.event_type == event_type)
    return [_anchor_out(a) for a in q.order_by(AnchorEvent.start_date).all()]


@router.post("/years/{year_id}/anchors")
def create_anchor(
    year_id: str,
    body: AnchorEventIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py, write=True)
    wing_id = body.wing_id or py.wing_id
    unit_id = body.unit_id or py.unit_id
    a = AnchorEvent(
        id=str(uuid.uuid4()), planning_year_id=year_id,
        owning_level=body.owning_level,
        wing_id=wing_id, unit_id=unit_id,
        event_name=body.event_name, event_type=body.event_type,
        importance=body.importance,
        start_date=body.start_date, end_date=body.end_date,
        audience_orientation=body.audience_orientation,
        audience_initial=body.audience_initial,
        audience_junior=body.audience_junior,
        audience_intermediate=body.audience_intermediate,
        audience_senior=body.audience_senior,
        planning_impact=body.planning_impact,
        readiness_requirements=body.readiness_requirements,
        notes=body.notes,
        is_archived=False,
        created_by=p.user_id, created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(a); db.commit()
    audit(db, p, object_type="anchor_event", object_id=a.id, action="create",
          new={"name": body.event_name, "date": body.start_date, "importance": body.importance})
    return _anchor_out(a)


@router.patch("/anchors/{anchor_id}")
def update_anchor(
    anchor_id: str,
    body: AnchorEventUpdateIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    a = db.get(AnchorEvent, anchor_id)
    if not a or a.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    py = _get_year_or_404(a.planning_year_id, db)
    _require_year_access(p, py, write=True)
    for field in ("event_name", "importance", "start_date", "end_date",
                  "planning_impact", "readiness_requirements", "notes"):
        val = getattr(body, field)
        if val is not None:
            setattr(a, field, val)
    a.updated_by = p.user_id; a.updated_at = utcnow()
    db.commit()
    audit(db, p, object_type="anchor_event", object_id=a.id, action="update")
    return _anchor_out(a)


@router.delete("/anchors/{anchor_id}")
def archive_anchor(
    anchor_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    a = db.get(AnchorEvent, anchor_id)
    if not a:
        raise HTTPException(404, detail={"error": "not_found"})
    py = _get_year_or_404(a.planning_year_id, db)
    _require_year_access(p, py, write=True)
    a.is_archived = True; a.updated_at = utcnow()
    db.commit()
    audit(db, p, object_type="anchor_event", object_id=a.id, action="archive")
    return {"ok": True}


@router.get("/anchors/{anchor_id}/prep-suggestions")
def get_prep_suggestions(
    anchor_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Return rule-based preparation suggestions for this anchor event."""
    a = db.get(AnchorEvent, anchor_id)
    if not a or a.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    rules = db.query(AnchorPrepRule).filter(AnchorPrepRule.event_type == a.event_type).all()
    # Find parade dates in the prep window
    try:
        event_dt = date.fromisoformat(a.start_date)
    except ValueError:
        event_dt = None
    suggested_dates = []
    if event_dt:
        parade_dates = db.query(ParadeDate).filter(
            ParadeDate.planning_year_id == a.planning_year_id,
            ParadeDate.is_active == True,  # noqa: E712
        ).all()
        for r in rules:
            window_start = (event_dt - timedelta(weeks=r.weeks_before_max)).isoformat()
            window_end   = (event_dt - timedelta(weeks=r.weeks_before_min)).isoformat()
            candidates   = [pd.parade_date for pd in parade_dates
                            if window_start <= pd.parade_date <= window_end]
            suggested_dates.append({
                "subject_area": r.subject_area,
                "suggested_activity": r.suggested_activity,
                "weeks_before_min": r.weeks_before_min,
                "weeks_before_max": r.weeks_before_max,
                "candidate_parade_dates": sorted(candidates),
                "notes": r.notes,
            })
    return {
        "anchor_event_id": anchor_id,
        "event_name": a.event_name,
        "event_type": a.event_type,
        "start_date": a.start_date,
        "suggestions": suggested_dates,
    }


# ─────────────────────────────────────────────────────────────
# Term Planner
# ─────────────────────────────────────────────────────────────

_TERM_RANGES = {
    1: ("01-28", "04-11"),
    2: ("04-28", "06-27"),
    3: ("07-14", "09-19"),
    4: ("10-06", "12-12"),
}


@router.get("/years/{year_id}/term-planner")
def get_term_planner(
    year_id: str,
    term: Optional[int] = Query(None, ge=1, le=4),
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py)

    all_dates = db.query(ParadeDate).filter(
        ParadeDate.planning_year_id == year_id,
        ParadeDate.is_active == True,  # noqa: E712
    ).order_by(ParadeDate.parade_date).all()

    if term:
        t_start, t_end = _TERM_RANGES.get(term, ("01-01", "12-31"))
        yr = str(py.year)
        all_dates = [d for d in all_dates
                     if f"{yr}-{t_start}" <= d.parade_date <= f"{yr}-{t_end}"]

    anchors = db.query(AnchorEvent).filter(
        AnchorEvent.planning_year_id == year_id,
        AnchorEvent.is_archived == False,  # noqa: E712
    ).order_by(AnchorEvent.start_date).all()

    sessions_by_date: dict[str, list] = {}
    for pd in all_dates:
        real_sessions: list[dict] = []
        if pd.parade_night_id:
            pn_real = db.get(ParadeNight, pd.parade_night_id)
            if pn_real:
                ts = db.query(TrainingSession).filter(
                    TrainingSession.parade_night_id == pn_real.id,
                    TrainingSession.is_archived == False,  # noqa: E712
                ).all()
                real_sessions = [_real_session_out(s, db) for s in ts]
        sessions_by_date[pd.id] = real_sessions

    # Calculate per-term session capacity summary
    # capacity = parade nights × cadet groups × periods
    total_periods = sum(
        (db.get(ParadeNight, pd.parade_night_id).session_count if pd.parade_night_id and db.get(ParadeNight, pd.parade_night_id) else 3)
        for pd in all_dates
    )
    capacity = total_periods * len(CADET_GROUPS)
    filled = sum(len(v) for v in sessions_by_date.values())

    return {
        "planning_year_id": year_id,
        "year": py.year,
        "term": term,
        "parade_dates": [_date_out(d) for d in all_dates],
        "parade_count": len(all_dates),
        "session_capacity": capacity,
        "sessions_filled": filled,
        "sessions_remaining": max(0, capacity - filled),
        "anchors": [_anchor_out(a) for a in anchors],
        "sessions_by_parade_date": sessions_by_date,
    }


# ─────────────────────────────────────────────────────────────
# Parade Night Builder
# ─────────────────────────────────────────────────────────────

@router.get("/parade-dates/{date_id}/builder")
def get_builder(
    date_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    pd = db.get(ParadeDate, date_id)
    if not pd:
        raise HTTPException(404, detail={"error": "not_found"})
    py = _get_year_or_404(pd.planning_year_id, db)
    _require_year_access(p, py)

    # Use the linked real ParadeNight if available; otherwise fall back to planning-only data
    pn: ParadeNight | None = None
    if pd.parade_night_id:
        pn = db.get(ParadeNight, pd.parade_night_id)

    # Timing template blocks
    timing_blocks: list[dict] = []
    session_count = 3
    tmpl = None
    if pn and pn.timing_template_id:
        tmpl = db.get(TimingTemplate, pn.timing_template_id)
    if not tmpl and (pd.unit_id or (pn and pn.squadron_id)):
        unit_id = pd.unit_id or pn.squadron_id
        tmpl = _effective_template(db, unit_id, pd.parade_date)
    if tmpl:
        blocks = db.query(TimingBlock).filter(
            TimingBlock.timing_template_id == tmpl.id,
        ).order_by(TimingBlock.display_order).all()
        timing_blocks = [
            {
                "display_order": b.display_order, "block_name": b.block_name,
                "block_type": b.block_type, "start_time": b.start_time, "end_time": b.end_time,
                "duration_minutes": b.duration_minutes,
                "is_instructional_period": b.is_instructional_period,
                "period_number": b.period_number,
            }
            for b in blocks
        ]
        ip_count = sum(1 for b in blocks if b.is_instructional_period)
        if ip_count > 0:
            session_count = ip_count
    if pn and pn.session_count:
        session_count = pn.session_count

    # Pull real sessions from the linked ParadeNight
    real_sessions: list[dict] = []
    if pn:
        ts = db.query(TrainingSession).filter(
            TrainingSession.parade_night_id == pn.id,
            TrainingSession.is_archived == False,  # noqa: E712
        ).order_by(TrainingSession.period_number, TrainingSession.cadet_group).all()
        real_sessions = [_real_session_out(s, db) for s in ts]

    conflicts = db.query(PlanningConflict).filter(
        PlanningConflict.parade_date_id == date_id,
        PlanningConflict.is_resolved == False,  # noqa: E712
    ).all()

    return {
        "parade_date_id": date_id,
        "parade_night_id": pd.parade_night_id,
        "parade_date": pd.parade_date,
        "parade_type": pd.parade_type,
        "unit_id": pd.unit_id,
        "session_count": session_count,
        "timing_blocks": timing_blocks,
        "cadet_groups": list(CADET_GROUPS),
        "sessions": real_sessions,
        "conflicts": [_conflict_out(c) for c in conflicts],
    }


# ─────────────────────────────────────────────────────────────
# Scheduled Sessions
# ─────────────────────────────────────────────────────────────

class ScheduledSessionIn(BaseModel):
    cadet_group: str
    session_number: int
    curriculum_id: Optional[str] = None
    activity_title: Optional[str] = None
    facilitator_id: Optional[str] = None
    location_id: Optional[str] = None
    is_combined: bool = False
    combined_groups: Optional[list] = None
    override_conflict: bool = False
    override_reason: Optional[str] = None
    status: str = "draft"
    notes: Optional[str] = None


class ScheduledSessionUpdateIn(BaseModel):
    curriculum_id: Optional[str] = None
    activity_title: Optional[str] = None
    facilitator_id: Optional[str] = None
    location_id: Optional[str] = None
    is_combined: Optional[bool] = None
    combined_groups: Optional[list] = None
    override_conflict: Optional[bool] = None
    override_reason: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


@router.post("/parade-dates/{date_id}/sessions")
def create_session(
    date_id: str,
    body: ScheduledSessionIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    pd = db.get(ParadeDate, date_id)
    if not pd:
        raise HTTPException(404, detail={"error": "not_found"})
    py = _get_year_or_404(pd.planning_year_id, db)
    _require_year_access(p, py, write=True)
    if body.cadet_group not in CADET_GROUPS:
        raise HTTPException(422, detail={"error": "invalid_cadet_group"})

    unit_id = pd.unit_id or (py.unit_id if py.unit_id else p.squadron_id)
    if not pd.parade_night_id:
        # Auto-link to a real ParadeNight
        if unit_id:
            pn = _find_or_create_parade_night(db, unit_id, pd.parade_date, p)
            if pn:
                pd.parade_night_id = pn.id
                db.flush()

    if not pd.parade_night_id:
        raise HTTPException(400, detail={"error": "no_parade_night_linked",
                                         "detail": "This planning date has no linked parade night. "
                                                   "Generate parade dates to link them automatically."})

    pn = db.get(ParadeNight, pd.parade_night_id)
    if not pn:
        raise HTTPException(404, detail={"error": "parade_night_not_found"})

    # Resolve room ID from location_id (which may be a PlanningLocation or TrainingArea id)
    training_area_id = None
    if body.location_id:
        ta = db.get(TrainingArea, body.location_id)
        if ta:
            training_area_id = ta.id

    # Create a real Session record
    s = TrainingSession(
        parade_night_id=pn.id, squadron_id=pn.squadron_id,
        period_number=body.session_number, cadet_group=body.cadet_group,
        custom_title=body.activity_title, status="planned",
        delivery_notes=body.notes, created_by=p.user_id,
    )
    # Denormalize curriculum and facilitator
    if body.curriculum_id:
        ci = db.get(CurriculumItem, body.curriculum_id)
        if ci:
            s.curriculum_item_id = ci.id
            s.curriculum_code_at_time = ci.code
            s.curriculum_title_at_time = ci.title
            s.phase_at_time = ci.phase
            s.element_at_time = ci.element
    if body.facilitator_id:
        f = db.get(Facilitator, body.facilitator_id)
        if f:
            s.facilitator_id = f.id
            s.facilitator_display_name_at_time = " ".join(x for x in [f.current_rank, f.first_name, f.last_name] if x)
    if training_area_id:
        ra = db.get(TrainingArea, training_area_id)
        if ra:
            s.training_area_id = ra.id
            s.training_area_name_at_time = ra.name
    db.add(s); db.commit()
    _run_conflict_check(py.id, date_id, db)
    audit(db, p, object_type="session", object_id=s.id, action="create",
          new={"group": body.cadet_group, "session": body.session_number})
    return _real_session_out(s, db)


@router.patch("/sessions/{session_id}")
def update_session(
    session_id: str,
    body: ScheduledSessionUpdateIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    s = db.get(TrainingSession, session_id)
    if not s or s.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    pn = db.get(ParadeNight, s.parade_night_id) if s.parade_night_id else None
    if pn:
        require_can_write_squadron(p, pn.squadron_id, pn.wing_id)

    if body.curriculum_id is not None:
        if body.curriculum_id:
            ci = db.get(CurriculumItem, body.curriculum_id)
            if ci:
                s.curriculum_item_id = ci.id
                s.curriculum_code_at_time = ci.code
                s.curriculum_title_at_time = ci.title
                s.phase_at_time = ci.phase
                s.element_at_time = ci.element
        else:
            s.curriculum_item_id = None
            s.curriculum_code_at_time = None
            s.curriculum_title_at_time = None
    if body.activity_title is not None:
        s.custom_title = body.activity_title
    if body.facilitator_id is not None:
        if body.facilitator_id:
            f = db.get(Facilitator, body.facilitator_id)
            if f:
                s.facilitator_id = f.id
                s.facilitator_display_name_at_time = " ".join(x for x in [f.current_rank, f.first_name, f.last_name] if x)
        else:
            s.facilitator_id = None
            s.facilitator_display_name_at_time = None
    if body.location_id is not None:
        if body.location_id:
            ra = db.get(TrainingArea, body.location_id)
            if ra:
                s.training_area_id = ra.id
                s.training_area_name_at_time = ra.name
        else:
            s.training_area_id = None
            s.training_area_name_at_time = None
    if body.status is not None:
        s.status = body.status
    if body.notes is not None:
        s.delivery_notes = body.notes
    db.commit()
    audit(db, p, object_type="session", object_id=s.id, action="update")
    return _real_session_out(s, db)


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    s = db.get(TrainingSession, session_id)
    if not s or s.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    pn = db.get(ParadeNight, s.parade_night_id) if s.parade_night_id else None
    if pn:
        require_can_write_squadron(p, pn.squadron_id, pn.wing_id)
    s.is_archived = True
    db.commit()
    audit(db, p, object_type="session", object_id=s.id, action="delete")
    return {"ok": True}


# ─────────────────────────────────────────────────────────────
# Weekly Program
# ─────────────────────────────────────────────────────────────

@router.get("/parade-dates/{date_id}/weekly-program")
def get_weekly_program(
    date_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    pd = db.get(ParadeDate, date_id)
    if not pd:
        raise HTTPException(404, detail={"error": "not_found"})
    py = _get_year_or_404(pd.planning_year_id, db)
    _require_year_access(p, py)

    # Pull real sessions from linked ParadeNight
    real_sessions: list[dict] = []
    pn = db.get(ParadeNight, pd.parade_night_id) if pd.parade_night_id else None
    if pn:
        ts = db.query(TrainingSession).filter(
            TrainingSession.parade_night_id == pn.id,
            TrainingSession.is_archived == False,  # noqa: E712
        ).order_by(TrainingSession.period_number, TrainingSession.cadet_group).all()
        real_sessions = [_real_session_out(s, db) for s in ts]

    # Timing template for time labels
    timing_blocks: list[dict] = []
    tmpl = None
    if pn and pn.timing_template_id:
        tmpl = db.get(TimingTemplate, pn.timing_template_id)
    if not tmpl and pd.unit_id:
        tmpl = _effective_template(db, pd.unit_id, pd.parade_date)
    if tmpl:
        blocks = db.query(TimingBlock).filter(
            TimingBlock.timing_template_id == tmpl.id,
        ).order_by(TimingBlock.display_order).all()
        timing_blocks = [
            {
                "sequence": b.display_order, "name": b.block_name, "block_type": b.block_type,
                "start_time": b.start_time, "end_time": b.end_time,
                "duration_minutes": b.duration_minutes,
                "is_instructional": b.is_instructional_period,
                "period_number": b.period_number,
            }
            for b in blocks
        ]

    conflicts = db.query(PlanningConflict).filter(
        PlanningConflict.parade_date_id == date_id,
        PlanningConflict.is_resolved == False,  # noqa: E712
    ).all()

    audit(db, p, object_type="parade_date", object_id=date_id, action="view_weekly_program")
    return {
        "parade_date_id": date_id,
        "parade_night_id": pd.parade_night_id,
        "parade_date": pd.parade_date,
        "unit_id": pd.unit_id,
        "timing_blocks": timing_blocks,
        "sessions": real_sessions,
        "conflicts": [_conflict_out(c) for c in conflicts],
        "has_unresolved_conflicts": len(conflicts) > 0,
    }


# ─────────────────────────────────────────────────────────────
# Long Range View
# ─────────────────────────────────────────────────────────────

@router.get("/years/{year_id}/long-range")
def get_long_range(
    year_id: str,
    weeks: int = Query(default=8, ge=1, le=20),
    from_date: Optional[str] = None,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py)

    today = date.today().isoformat()
    start = from_date or today
    try:
        start_dt = date.fromisoformat(start)
    except ValueError:
        start_dt = date.today()
    end_dt = start_dt + timedelta(weeks=weeks)

    parade_dates = db.query(ParadeDate).filter(
        ParadeDate.planning_year_id == year_id,
        ParadeDate.is_active == True,  # noqa: E712
        ParadeDate.parade_date >= start_dt.isoformat(),
        ParadeDate.parade_date <= end_dt.isoformat(),
    ).order_by(ParadeDate.parade_date).all()

    anchors = db.query(AnchorEvent).filter(
        AnchorEvent.planning_year_id == year_id,
        AnchorEvent.is_archived == False,  # noqa: E712
        AnchorEvent.start_date >= start_dt.isoformat(),
        AnchorEvent.start_date <= end_dt.isoformat(),
    ).order_by(AnchorEvent.start_date).all()

    rows = []
    for pd_obj in parade_dates:
        real_sessions: list[dict] = []
        pn_real = db.get(ParadeNight, pd_obj.parade_night_id) if pd_obj.parade_night_id else None
        if pn_real:
            ts = db.query(TrainingSession).filter(
                TrainingSession.parade_night_id == pn_real.id,
                TrainingSession.is_archived == False,  # noqa: E712
            ).order_by(TrainingSession.period_number, TrainingSession.cadet_group).all()
            real_sessions = [_real_session_out(s, db) for s in ts]

        conflicts = db.query(PlanningConflict).filter(
            PlanningConflict.parade_date_id == pd_obj.id,
            PlanningConflict.is_resolved == False,  # noqa: E712
        ).all()

        rows.append({
            "parade_date": _date_out(pd_obj),
            "sessions": real_sessions,
            "session_count": len(real_sessions),
            "filled_slots": len([s for s in real_sessions if s.get("curriculum_title") or s.get("activity_title")]),
            "conflicts": [_conflict_out(c) for c in conflicts],
        })

    return {
        "planning_year_id": year_id,
        "from_date": start_dt.isoformat(),
        "to_date": end_dt.isoformat(),
        "weeks": weeks,
        "parade_dates": rows,
        "anchors": [_anchor_out(a) for a in anchors],
    }


# ─────────────────────────────────────────────────────────────
# Planning Locations
# ─────────────────────────────────────────────────────────────

class PlanningLocationIn(BaseModel):
    name: str
    location_type: str = "indoor"
    capacity: Optional[int] = None
    notes: Optional[str] = None
    unit_id: Optional[str] = None


class PlanningLocationUpdateIn(BaseModel):
    name: Optional[str] = None
    location_type: Optional[str] = None
    capacity: Optional[int] = None
    notes: Optional[str] = None
    active_status: Optional[bool] = None


@router.get("/locations")
def list_locations(
    unit_id: Optional[str] = None,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    q = db.query(PlanningLocation).filter(PlanningLocation.active_status == True)  # noqa: E712
    if p.role == "sqn_admin":
        q = q.filter(PlanningLocation.unit_id == p.squadron_id)
    elif p.role in ("wing_admin", "wing_viewer"):
        sqn_ids = [s.id for s in db.query(Squadron).filter(
            Squadron.wing_id == p.wing_id, Squadron.is_archived == False  # noqa: E712
        ).all()]
        q = q.filter(PlanningLocation.unit_id.in_(sqn_ids))
    if unit_id:
        q = q.filter(PlanningLocation.unit_id == unit_id)
    return [_location_out(loc) for loc in q.order_by(PlanningLocation.name).all()]


@router.post("/locations")
def create_location(
    body: PlanningLocationIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    _require_plan_write(p)
    unit_id = body.unit_id or p.squadron_id
    if p.role == "sqn_admin":
        unit_id = p.squadron_id
    loc = PlanningLocation(
        id=str(uuid.uuid4()), unit_id=unit_id, name=body.name,
        location_type=body.location_type, capacity=body.capacity,
        notes=body.notes, active_status=True,
        created_by=p.user_id, created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(loc); db.commit()
    audit(db, p, object_type="planning_location", object_id=loc.id, action="create",
          new={"name": body.name})
    return _location_out(loc)


@router.patch("/locations/{location_id}")
def update_location(
    location_id: str,
    body: PlanningLocationUpdateIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    loc = db.get(PlanningLocation, location_id)
    if not loc:
        raise HTTPException(404, detail={"error": "not_found"})
    _require_plan_write(p)
    if p.role == "sqn_admin" and loc.unit_id != p.squadron_id:
        raise HTTPException(403, detail={"error": "out_of_scope"})
    for field in ("name", "location_type", "capacity", "notes", "active_status"):
        val = getattr(body, field)
        if val is not None:
            setattr(loc, field, val)
    loc.updated_at = utcnow()
    db.commit()
    audit(db, p, object_type="planning_location", object_id=loc.id, action="update")
    return _location_out(loc)


# ─────────────────────────────────────────────────────────────
# Facilitators (planning view — references existing model)
# ─────────────────────────────────────────────────────────────

@router.get("/facilitators")
def list_planning_facilitators(
    unit_id: Optional[str] = None,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    q = db.query(Facilitator).filter(Facilitator.active_status == True)  # noqa: E712
    if p.role == "sqn_admin":
        q = q.filter(Facilitator.squadron_id == p.squadron_id)
    elif p.role in ("wing_admin", "wing_viewer"):
        q = q.filter(Facilitator.wing_id == p.wing_id)
    if unit_id:
        q = q.filter(Facilitator.squadron_id == unit_id)
    return [
        {
            "facilitator_id": f.id,
            "display_name": f"{f.current_rank or ''} {f.last_name}".strip(),
            "first_name": f.first_name, "last_name": f.last_name,
            "rank": f.current_rank, "type": f.type,
            "subject_areas": f.subject_areas or [],
            "max_sessions_per_night": f.max_sessions_per_night,
            "unit_id": f.squadron_id,
        }
        for f in q.order_by(Facilitator.last_name).all()
    ]


# ─────────────────────────────────────────────────────────────
# Conflict Detection
# ─────────────────────────────────────────────────────────────

def _run_conflict_check(year_id: str, date_id: str, db: DBSession) -> list[PlanningConflict]:
    """Detect conflicts for a single parade date, replacing previous non-resolved results."""
    db.query(PlanningConflict).filter(
        PlanningConflict.parade_date_id == date_id,
        PlanningConflict.is_resolved == False,  # noqa: E712
    ).delete(synchronize_session=False)

    pd_obj = db.get(ParadeDate, date_id)
    # Use real TrainingSession records for conflict detection
    real_sessions: list = []
    if pd_obj and pd_obj.parade_night_id:
        real_sessions = db.query(TrainingSession).filter(
            TrainingSession.parade_night_id == pd_obj.parade_night_id,
            TrainingSession.is_archived == False,  # noqa: E712
        ).all()

    conflicts = []

    def _conflict(ctype: str, severity: str, msg: str, sess_id=None):
        c = PlanningConflict(
            id=str(uuid.uuid4()), planning_year_id=year_id,
            parade_date_id=date_id, scheduled_session_id=sess_id,
            conflict_type=ctype, severity=severity, message=msg,
            is_resolved=False, created_at=utcnow(), updated_at=utcnow(),
        )
        conflicts.append(c)
        db.add(c)

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
    if pd_obj:
        holidays = db.query(HolidayPeriod).filter(
            HolidayPeriod.planning_year_id == year_id,
            HolidayPeriod.affects_parade == True,  # noqa: E712
        ).all()
        for h in holidays:
            if h.start_date <= pd_obj.parade_date <= h.end_date:
                _conflict("holiday_conflict", "warning",
                          f"This parade date falls within the '{h.name}' holiday period.")
                break

    db.commit()
    return conflicts


@router.get("/years/{year_id}/conflicts")
def get_conflicts(
    year_id: str,
    severity: Optional[str] = None,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py)
    q = db.query(PlanningConflict).filter(
        PlanningConflict.planning_year_id == year_id,
        PlanningConflict.is_resolved == False,  # noqa: E712
    )
    if severity:
        q = q.filter(PlanningConflict.severity == severity)
    return [_conflict_out(c) for c in q.order_by(PlanningConflict.created_at.desc()).all()]


class ConflictOverrideIn(BaseModel):
    override_reason: str


@router.post("/conflicts/{conflict_id}/override")
def override_conflict(
    conflict_id: str,
    body: ConflictOverrideIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    _require_plan_write(p)
    if not (body.override_reason or "").strip():
        raise HTTPException(422, detail={"error": "override_requires_reason"})
    c = db.get(PlanningConflict, conflict_id)
    if not c:
        raise HTTPException(404, detail={"error": "not_found"})
    c.is_resolved = True
    c.override_reason = body.override_reason
    c.resolved_by = p.user_id
    c.updated_at = utcnow()
    db.commit()
    audit(db, p, object_type="planning_conflict", object_id=c.id,
          action="conflict_override", reason=body.override_reason)
    return {"ok": True, "conflict_id": conflict_id}


@router.post("/years/{year_id}/run-checks")
def run_checks(
    year_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py, write=True)
    dates = db.query(ParadeDate).filter(
        ParadeDate.planning_year_id == year_id,
        ParadeDate.is_active == True,  # noqa: E712
    ).all()
    total = 0
    for pd_obj in dates:
        results = _run_conflict_check(year_id, pd_obj.id, db)
        total += len(results)
    return {"ok": True, "conflicts_detected": total}


# ─────────────────────────────────────────────────────────────
# Decision Guide
# ─────────────────────────────────────────────────────────────

@router.get("/years/{year_id}/decision-guide")
def get_decision_guide(
    year_id: str,
    date_id: Optional[str] = None,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py)

    today = date.today()
    checks = []

    # 1. Must Attend / Key Event in next 3 weeks
    window = (today + timedelta(weeks=3)).isoformat()
    upcoming = db.query(AnchorEvent).filter(
        AnchorEvent.planning_year_id == year_id,
        AnchorEvent.is_archived == False,  # noqa: E712
        AnchorEvent.start_date <= window,
        AnchorEvent.start_date >= today.isoformat(),
        AnchorEvent.importance.in_(["must_attend", "key_event"]),
    ).order_by(AnchorEvent.start_date).all()
    checks.append({
        "rule": 1,
        "question": "Is there a Must Attend or Key Event within the next 3 weeks?",
        "result": bool(upcoming),
        "detail": [a.event_name for a in upcoming],
        "action": "Schedule preparation lessons for these events." if upcoming else None,
    })

    # 2. Unscheduled groups
    if date_id:
        pd_obj = db.get(ParadeDate, date_id)
        if pd_obj:
            scheduled = set()
            if pd_obj.parade_night_id:
                scheduled = {
                    s.cadet_group for s in
                    db.query(TrainingSession).filter(
                        TrainingSession.parade_night_id == pd_obj.parade_night_id,
                        TrainingSession.is_archived == False,  # noqa: E712
                    ).all()
                    if s.cadet_group
                }
            missing = [g for g in CADET_GROUPS if g not in scheduled]
            checks.append({
                "rule": 3,
                "question": "Is there a cadet group with no mission assigned for this night?",
                "result": bool(missing),
                "detail": missing,
                "action": f"Assign sessions for: {', '.join(missing)}." if missing else None,
            })

    # 3. Active conflicts
    conflicts = db.query(PlanningConflict).filter(
        PlanningConflict.planning_year_id == year_id,
        PlanningConflict.severity == "critical",
        PlanningConflict.is_resolved == False,  # noqa: E712
    ).count()
    checks.append({
        "rule": 7,
        "question": "Are there unresolved critical conflicts?",
        "result": conflicts > 0,
        "detail": [f"{conflicts} critical conflict(s) unresolved"],
        "action": "Resolve or override all critical conflicts before publishing." if conflicts > 0 else None,
    })

    # 10. Is the night ready to publish?
    ready = not (conflicts > 0)
    checks.append({
        "rule": 10,
        "question": "Is the night ready to publish?",
        "result": ready,
        "detail": [],
        "action": None if ready else "Resolve all critical conflicts first.",
    })

    return {"planning_year_id": year_id, "checks": checks}


# ─────────────────────────────────────────────────────────────
# Prep Rules (read-only; seeded)
# ─────────────────────────────────────────────────────────────

@router.get("/prep-rules")
def list_prep_rules(
    event_type: Optional[str] = None,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    q = db.query(AnchorPrepRule)
    if event_type:
        q = q.filter(AnchorPrepRule.event_type == event_type)
    return [
        {
            "prep_rule_id": r.id, "event_type": r.event_type,
            "subject_area": r.subject_area, "suggested_activity": r.suggested_activity,
            "weeks_before_min": r.weeks_before_min, "weeks_before_max": r.weeks_before_max,
            "notes": r.notes,
        }
        for r in q.order_by(AnchorPrepRule.event_type, AnchorPrepRule.weeks_before_min).all()
    ]


# ─────────────────────────────────────────────────────────────
# V14 — Training Planner: Mission Scheduling View
# ─────────────────────────────────────────────────────────────

# WA school term date ranges (defaults; adjusted per school year by parade dates)
_WA_TERM_RANGES = {
    1: ("01-28", "04-11"),
    2: ("04-28", "06-27"),
    3: ("07-14", "09-19"),
    4: ("10-06", "12-12"),
}


def _term_for_date(date_str: str, year: int) -> str | None:
    """Return T1/T2/T3/T4 for a date based on WA default term boundaries."""
    for t, (ts, te) in _WA_TERM_RANGES.items():
        if f"{year}-{ts}" <= date_str <= f"{year}-{te}":
            return f"T{t}"
    return None


def _curriculum_scope_query(db: DBSession, p: Principal):
    """Return a query for CurriculumItem rows visible to this principal."""
    from sqlalchemy import or_
    q = db.query(CurriculumItem).filter(
        CurriculumItem.is_archived == False,  # noqa: E712
        CurriculumItem.active_status == True,  # noqa: E712
    )
    if p.role in ("sqn_admin", "sqn_general"):
        sqn = db.get(Squadron, p.squadron_id) if p.squadron_id else None
        wing_id = sqn.wing_id if sqn else None
        q = q.filter(or_(
            CurriculumItem.owning_level == "national",
            CurriculumItem.wing_id == wing_id,
            CurriculumItem.squadron_id == p.squadron_id,
        ))
    elif p.role in ("wing_admin", "wing_viewer"):
        q = q.filter(or_(
            CurriculumItem.owning_level == "national",
            CurriculumItem.wing_id == p.wing_id,
        ))
    # nat/system: all
    return q


@router.get("/years/{year_id}/missions")
def list_missions(
    year_id: str,
    phase: Optional[str] = None,
    element: Optional[str] = None,
    term: Optional[str] = None,
    status: Optional[str] = None,   # "scheduled" | "unscheduled"
    search: Optional[str] = None,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Training Planner: curriculum items with scheduling status for this planning year."""
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py)

    # Get all parade date IDs and their linked parade night IDs for this year
    pd_rows = db.query(ParadeDate).filter(
        ParadeDate.planning_year_id == year_id,
        ParadeDate.is_active == True,  # noqa: E712
    ).all()
    pn_to_pd: dict[str, ParadeDate] = {}
    for pd_obj in pd_rows:
        if pd_obj.parade_night_id:
            pn_to_pd[pd_obj.parade_night_id] = pd_obj

    # Pull all sessions for parade nights in this year
    pn_ids = list(pn_to_pd.keys())
    sessions_in_year: list[TrainingSession] = []
    if pn_ids:
        sessions_in_year = db.query(TrainingSession).filter(
            TrainingSession.parade_night_id.in_(pn_ids),
            TrainingSession.is_archived == False,  # noqa: E712
        ).all()

    # Index sessions by curriculum_item_id
    from collections import defaultdict
    sessions_by_ci: dict[str, list[TrainingSession]] = defaultdict(list)
    for s in sessions_in_year:
        if s.curriculum_item_id:
            sessions_by_ci[s.curriculum_item_id].append(s)

    # Build curriculum query
    q = _curriculum_scope_query(db, p)
    if phase:
        q = q.filter(CurriculumItem.phase == phase)
    if element:
        q = q.filter(CurriculumItem.element == element)
    if search:
        like = f"%{search}%"
        from sqlalchemy import or_
        q = q.filter(or_(
            CurriculumItem.code.ilike(like),
            CurriculumItem.title.ilike(like),
        ))

    items = q.order_by(CurriculumItem.phase, CurriculumItem.recommended_sequence, CurriculumItem.code).all()

    def _sess_summary(s: TrainingSession) -> dict:
        pd_obj = pn_to_pd.get(s.parade_night_id)
        room_name = s.training_area_name_at_time
        if not room_name and s.training_area_id:
            ra = db.get(TrainingArea, s.training_area_id)
            if ra:
                room_name = ra.name
        return {
            "session_id": s.id,
            "parade_night_id": s.parade_night_id,
            "parade_date": pd_obj.parade_date if pd_obj else None,
            "parade_date_id": pd_obj.id if pd_obj else None,
            "term": (pd_obj.term if pd_obj and pd_obj.term else
                     (_term_for_date(pd_obj.parade_date, py.year) if pd_obj else None)),
            "session_number": s.period_number,
            "part_number": s.part_number,
            "cadet_group": s.cadet_group,
            "facilitator_id": s.facilitator_id,
            "facilitator_name": s.facilitator_display_name_at_time,
            "location_id": s.training_area_id,
            "location_name": room_name,
            "status": s.status,
        }

    result = []
    for ci in items:
        scheduled = sessions_by_ci.get(ci.id, [])
        is_scheduled = len(scheduled) > 0

        # Filter by term if requested
        if term:
            matching = [s for s in scheduled
                        if pn_to_pd.get(s.parade_night_id) and
                        (_term_for_date(pn_to_pd[s.parade_night_id].parade_date, py.year) == term or
                         (pn_to_pd[s.parade_night_id].term == term))]
            if not matching and status == "scheduled":
                continue
        # Filter by status
        if status == "scheduled" and not is_scheduled:
            continue
        if status == "unscheduled" and is_scheduled:
            continue

        result.append({
            "curriculum_id": ci.id,
            "code": ci.code,
            "title": ci.title,
            "phase": ci.phase,
            "element": ci.element,
            "recommended_term": ci.recommended_term,
            "part_count": ci.part_count,
            "instructor_suitability": ci.instructor_suitability,
            "duration_minutes": ci.duration_minutes,
            "core_status": ci.core_status,
            "is_scheduled": is_scheduled,
            "scheduled_sessions": [_sess_summary(s) for s in scheduled],
            "scheduled_count": len(scheduled),
        })

    return {
        "planning_year_id": year_id,
        "year": py.year,
        "total": len(result),
        "scheduled_count": sum(1 for r in result if r["is_scheduled"]),
        "missions": result,
    }


# ─────────────────────────────────────────────────────────────
# V14 — Mission Assignment (creates real Session record)
# ─────────────────────────────────────────────────────────────

class MissionAssignIn(BaseModel):
    curriculum_id: str
    parade_date_id: str
    session_number: int
    cadet_group: str
    part_number: Optional[int] = None
    facilitator_id: Optional[str] = None
    training_area_id: Optional[str] = None
    notes: Optional[str] = None


@router.post("/years/{year_id}/assign-mission")
def assign_mission(
    year_id: str,
    body: MissionAssignIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Assign a curriculum mission to a parade night session (Training Planner action)."""
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py, write=True)

    if body.cadet_group not in CADET_GROUPS:
        raise HTTPException(422, detail={"error": "invalid_cadet_group"})

    ci = db.get(CurriculumItem, body.curriculum_id)
    if not ci:
        raise HTTPException(404, detail={"error": "curriculum_item_not_found"})

    pd_obj = db.get(ParadeDate, body.parade_date_id)
    if not pd_obj or pd_obj.planning_year_id != year_id:
        raise HTTPException(404, detail={"error": "parade_date_not_found"})

    unit_id = pd_obj.unit_id or py.unit_id
    if not pd_obj.parade_night_id and unit_id:
        pn_new = _find_or_create_parade_night(db, unit_id, pd_obj.parade_date, p)
        if pn_new:
            pd_obj.parade_night_id = pn_new.id
            db.flush()

    if not pd_obj.parade_night_id:
        raise HTTPException(400, detail={"error": "no_parade_night_linked"})

    pn = db.get(ParadeNight, pd_obj.parade_night_id)
    if not pn:
        raise HTTPException(404, detail={"error": "parade_night_not_found"})

    s = TrainingSession(
        parade_night_id=pn.id, squadron_id=pn.squadron_id,
        period_number=body.session_number,
        cadet_group=body.cadet_group,
        part_number=body.part_number,
        curriculum_item_id=ci.id,
        curriculum_code_at_time=ci.code,
        curriculum_title_at_time=ci.title,
        phase_at_time=ci.phase,
        element_at_time=ci.element,
        status="planned",
        delivery_notes=body.notes,
        created_by=p.user_id,
        created_at=utcnow(), updated_at=utcnow(),
    )
    if body.facilitator_id:
        f = db.get(Facilitator, body.facilitator_id)
        if f:
            s.facilitator_id = f.id
            s.facilitator_display_name_at_time = " ".join(x for x in [f.current_rank, f.first_name, f.last_name] if x)
    if body.training_area_id:
        ra = db.get(TrainingArea, body.training_area_id)
        if ra:
            s.training_area_id = ra.id
            s.training_area_name_at_time = ra.name

    db.add(s)
    db.commit()
    _run_conflict_check(year_id, body.parade_date_id, db)
    audit(db, p, object_type="session", object_id=s.id, action="assign_mission",
          new={"curriculum": ci.code, "date": pd_obj.parade_date, "session": body.session_number,
               "group": body.cadet_group})
    return _real_session_out(s, db)


# ─────────────────────────────────────────────────────────────
# V14 — Annual Program (full year view with term blocks)
# ─────────────────────────────────────────────────────────────

@router.get("/years/{year_id}/annual-program")
def get_annual_program(
    year_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Full-year calendar view: 4 term blocks, parade dates, holidays, activities."""
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py)

    all_dates = db.query(ParadeDate).filter(
        ParadeDate.planning_year_id == year_id,
    ).order_by(ParadeDate.parade_date).all()

    all_holidays = db.query(HolidayPeriod).filter(
        HolidayPeriod.planning_year_id == year_id,
    ).order_by(HolidayPeriod.start_date).all()

    all_anchors = db.query(AnchorEvent).filter(
        AnchorEvent.planning_year_id == year_id,
        AnchorEvent.is_archived == False,  # noqa: E712
    ).order_by(AnchorEvent.start_date).all()

    def _in_range(d: str, start: str, end: str) -> bool:
        return start <= d <= end

    # Build term blocks using WA defaults
    yr = str(py.year)
    terms = []
    for t_num, (ts, te) in sorted(_WA_TERM_RANGES.items()):
        t_start = f"{yr}-{ts}"
        t_end   = f"{yr}-{te}"
        term_label = f"T{t_num}"

        t_dates = [d for d in all_dates if t_start <= d.parade_date <= t_end]
        t_holidays = [h for h in all_holidays
                      if not (h.end_date < t_start or h.start_date > t_end)]
        t_anchors = [a for a in all_anchors
                     if _in_range(a.start_date, t_start, t_end)]

        # Per-date session fill summary
        date_summaries = []
        for pd_obj in t_dates:
            session_count = 0
            filled = 0
            pn = db.get(ParadeNight, pd_obj.parade_night_id) if pd_obj.parade_night_id else None
            if pn:
                sessions = db.query(TrainingSession).filter(
                    TrainingSession.parade_night_id == pn.id,
                    TrainingSession.is_archived == False,  # noqa: E712
                ).all()
                session_count = pn.session_count
                filled = len([s for s in sessions if s.curriculum_item_id or s.custom_title])
            in_hol = any(_in_range(pd_obj.parade_date, h.start_date, h.end_date)
                         for h in t_holidays if h.affects_parade)
            date_summaries.append({
                **_date_out(pd_obj),
                "term": term_label,
                "session_count": session_count,
                "filled_count": filled,
                "in_holiday": in_hol,
            })

        def _anchor_v14_out(a: AnchorEvent) -> dict:
            base = _anchor_out(a)
            base["importance_level"] = a.importance_level
            base["audience_staff_only"] = a.audience_staff_only
            base["audience_proficient"] = a.audience_proficient
            base["audience_first_years"] = a.audience_first_years
            base["cea_activity_id"] = a.cea_activity_id
            base["nomination_end_date"] = a.nomination_end_date
            base["unit_name"] = a.unit_name
            return base

        def _holiday_v14_out(h: HolidayPeriod) -> dict:
            base = _holiday_out(h)
            base["holiday_type"] = h.holiday_type
            return base

        terms.append({
            "term": term_label,
            "term_number": t_num,
            "start_date": t_start,
            "end_date": t_end,
            "parade_count": len(t_dates),
            "parade_dates": date_summaries,
            "holidays": [_holiday_v14_out(h) for h in t_holidays],
            "activities": [_anchor_v14_out(a) for a in t_anchors],
        })

    # Overall stats
    total_dates = len(all_dates)
    active_dates = sum(1 for d in all_dates if d.is_active)
    all_pn_ids = [d.parade_night_id for d in all_dates if d.parade_night_id]
    total_sessions = 0
    filled_sessions = 0
    if all_pn_ids:
        all_ts = db.query(TrainingSession).filter(
            TrainingSession.parade_night_id.in_(all_pn_ids),
            TrainingSession.is_archived == False,  # noqa: E712
        ).all()
        total_slots = sum(
            (db.get(ParadeNight, pnid).session_count if db.get(ParadeNight, pnid) else 3)
            for pnid in all_pn_ids
        ) * len(CADET_GROUPS)
        total_sessions = total_slots
        filled_sessions = len([s for s in all_ts if s.curriculum_item_id or s.custom_title])

    return {
        "planning_year_id": year_id,
        "year": py.year,
        "name": py.name,
        "total_parade_dates": total_dates,
        "active_parade_dates": active_dates,
        "total_session_slots": total_sessions,
        "filled_session_slots": filled_sessions,
        "terms": terms,
    }


# ─────────────────────────────────────────────────────────────
# V14 — Year Rollover
# ─────────────────────────────────────────────────────────────

class RolloverIn(BaseModel):
    target_year: Optional[int] = None   # defaults to source year + 1
    name: Optional[str] = None
    copy_holidays: bool = True
    carry_incomplete_sessions: bool = True


@router.post("/years/{year_id}/rollover")
def rollover_year(
    year_id: str,
    body: RolloverIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Create the next planning year with copied settings and regenerated parade dates."""
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py, write=True)

    target_year = body.target_year or (py.year + 1)
    new_name = body.name or f"{py.name} → {target_year}"

    # Check for existing year
    existing = db.query(PlanningYear).filter(
        PlanningYear.unit_id == py.unit_id,
        PlanningYear.year == target_year,
    ).first()
    if existing:
        raise HTTPException(409, detail={"error": "planning_year_already_exists",
                                         "existing_id": existing.id})

    new_py = PlanningYear(
        id=str(uuid.uuid4()),
        unit_id=py.unit_id, wing_id=py.wing_id,
        year=target_year, name=new_name,
        active_status=True,
        created_by=p.user_id, created_at=utcnow(), updated_at=utcnow(),
    )
    db.add(new_py)
    db.flush()

    # Copy holiday periods
    holidays_copied = 0
    if body.copy_holidays:
        old_holidays = db.query(HolidayPeriod).filter(
            HolidayPeriod.planning_year_id == year_id,
        ).all()
        year_delta = target_year - py.year
        for h in old_holidays:
            try:
                new_start = date.fromisoformat(h.start_date).replace(
                    year=date.fromisoformat(h.start_date).year + year_delta
                ).isoformat()
                new_end = date.fromisoformat(h.end_date).replace(
                    year=date.fromisoformat(h.end_date).year + year_delta
                ).isoformat()
            except (ValueError, AttributeError):
                new_start, new_end = h.start_date, h.end_date
            nh = HolidayPeriod(
                id=str(uuid.uuid4()), planning_year_id=new_py.id,
                jurisdiction=h.jurisdiction, name=h.name,
                start_date=new_start, end_date=new_end,
                holiday_type=h.holiday_type,
                affects_parade=h.affects_parade, notes=h.notes,
                created_at=utcnow(), updated_at=utcnow(),
            )
            db.add(nh)
            holidays_copied += 1

    # Copy parade dates (same weekday pattern, new year)
    dates_copied = 0
    old_dates = db.query(ParadeDate).filter(
        ParadeDate.planning_year_id == year_id,
        ParadeDate.is_active == True,  # noqa: E712
    ).order_by(ParadeDate.parade_date).all()
    year_delta = target_year - py.year
    for old_pd in old_dates:
        try:
            new_date_str = date.fromisoformat(old_pd.parade_date).replace(
                year=date.fromisoformat(old_pd.parade_date).year + year_delta
            ).isoformat()
        except (ValueError, AttributeError):
            continue
        pn_new = _find_or_create_parade_night(db, new_py.unit_id, new_date_str, p)
        npd = ParadeDate(
            id=str(uuid.uuid4()), planning_year_id=new_py.id,
            unit_id=new_py.unit_id, parade_date=new_date_str,
            parade_type=old_pd.parade_type, is_active=True,
            term=old_pd.term,
            parade_night_id=pn_new.id if pn_new else None,
            created_at=utcnow(), updated_at=utcnow(),
        )
        db.add(npd)
        dates_copied += 1

    # Carry forward incomplete sessions as draft assignments
    sessions_carried = 0
    if body.carry_incomplete_sessions:
        # Find sessions that were NOT delivered in the old year
        old_pn_ids = [d.parade_night_id for d in old_dates if d.parade_night_id]
        if old_pn_ids:
            incomplete = db.query(TrainingSession).filter(
                TrainingSession.parade_night_id.in_(old_pn_ids),
                TrainingSession.is_archived == False,  # noqa: E712
                TrainingSession.status.in_(["planned", "not_delivered"]),
                TrainingSession.curriculum_item_id.isnot(None),
            ).all()
            sessions_carried = len(incomplete)
            # We note them but don't auto-assign (planner should review)

    db.commit()
    audit(db, p, object_type="planning_year", object_id=new_py.id, action="rollover",
          new={"source_year": py.year, "target_year": target_year,
               "holidays_copied": holidays_copied, "dates_copied": dates_copied,
               "incomplete_sessions_noted": sessions_carried})

    return {
        "ok": True,
        "new_planning_year_id": new_py.id,
        "year": target_year,
        "name": new_name,
        "holidays_copied": holidays_copied,
        "parade_dates_copied": dates_copied,
        "incomplete_sessions_noted": sessions_carried,
    }


# ─────────────────────────────────────────────────────────────
# Spreadsheet Export — Annual Program + Schedule
# ─────────────────────────────────────────────────────────────

def _neutralise_cell(v):
    """Prevent CSV/formula injection in spreadsheet cells."""
    s = str(v) if v is not None else ""
    return ("'" + s) if s[:1] in ("=", "+", "-", "@") else s


@router.get("/years/{year_id}/export.xlsx")
def export_annual_program_xlsx(
    year_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Export the annual program (parade dates, holidays, anchors) as XLSX."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py)

    wb = openpyxl.Workbook()

    # Sheet 1 — Parade Dates
    ws1 = wb.active
    ws1.title = "Parade Dates"
    hdr_fill = PatternFill("solid", fgColor="002F65")
    hdr_font = Font(color="FFFFFF", bold=True)
    dates_headers = ["Date", "Day", "Type", "Active", "Notes", "Term"]
    ws1.append(dates_headers)
    for cell in ws1[1]:
        cell.fill = hdr_fill; cell.font = hdr_font
    all_dates = db.query(ParadeDate).filter(ParadeDate.planning_year_id == year_id).order_by(ParadeDate.parade_date).all()
    yr_str = str(py.year)
    def _term_label(ds: str) -> str:
        for t_num, (ts, te) in sorted(_WA_TERM_RANGES.items()):
            if f"{yr_str}-{ts}" <= ds <= f"{yr_str}-{te}":
                return f"T{t_num}"
        return ""
    for d in all_dates:
        try:
            dow = date.fromisoformat(d.parade_date).strftime("%A")
        except Exception:
            dow = ""
        ws1.append([d.parade_date, dow, d.parade_type or "standard",
                    "Yes" if d.is_active else "No",
                    _neutralise_cell(d.notes or ""), _term_label(d.parade_date)])

    # Sheet 2 — Holidays
    ws2 = wb.create_sheet("Holidays")
    ws2.append(["Name", "Start Date", "End Date", "Type", "Affects Parade"])
    for cell in ws2[1]:
        cell.fill = hdr_fill; cell.font = hdr_font
    for h in db.query(HolidayPeriod).filter(HolidayPeriod.planning_year_id == year_id).order_by(HolidayPeriod.start_date).all():
        ws2.append([_neutralise_cell(h.name), h.start_date, h.end_date,
                    h.holiday_type or "", "Yes" if h.affects_parade else "No"])

    # Sheet 3 — Anchor Events
    ws3 = wb.create_sheet("Anchor Events")
    ws3.append(["Name", "Start Date", "End Date", "Type", "Importance", "Location", "Notes"])
    for cell in ws3[1]:
        cell.fill = hdr_fill; cell.font = hdr_font
    for a in db.query(AnchorEvent).filter(AnchorEvent.planning_year_id == year_id, AnchorEvent.is_archived == False).order_by(AnchorEvent.start_date).all():  # noqa: E712
        ws3.append([_neutralise_cell(a.name), a.start_date, a.end_date or "",
                    a.event_type or "", a.importance_level or "",
                    _neutralise_cell(a.location or ""), _neutralise_cell(a.description or "")])

    bio = io.BytesIO(); wb.save(bio); bio.seek(0)
    audit(db, p, object_type="export", object_id=year_id, action="export",
          new={"type": "annual_program", "fmt": "xlsx"})
    fname = f"annual-program-{py.year}.xlsx"
    return StreamingResponse(bio, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename={fname}"})


@router.get("/years/{year_id}/schedule/export.xlsx")
def export_schedule_xlsx(
    year_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Export all scheduled sessions for a planning year as XLSX."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill
    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py)
    sq_id = p.acting_squadron_id or p.squadron_id

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Schedule"
    hdr_fill = PatternFill("solid", fgColor="002F65")
    hdr_font = Font(color="FFFFFF", bold=True)
    headers = ["Date", "Day", "Term", "Session", "Group", "Phase", "Code", "Title", "Facilitator", "Room", "Status"]
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = hdr_fill; cell.font = hdr_font

    yr_str = str(py.year)
    def _term_lbl(ds: str) -> str:
        for t_num, (ts, te) in sorted(_WA_TERM_RANGES.items()):
            if f"{yr_str}-{ts}" <= ds <= f"{yr_str}-{te}":
                return f"T{t_num}"
        return ""

    all_dates = db.query(ParadeDate).filter(
        ParadeDate.planning_year_id == year_id,
        ParadeDate.is_active == True,  # noqa: E712
    ).order_by(ParadeDate.parade_date).all()

    for pd_obj in all_dates:
        if not pd_obj.parade_night_id:
            continue
        pn = db.get(ParadeNight, pd_obj.parade_night_id)
        if not pn:
            continue
        try:
            dow = date.fromisoformat(pd_obj.parade_date).strftime("%A")
        except Exception:
            dow = ""
        term = _term_lbl(pd_obj.parade_date)
        sessions = db.query(TrainingSession).filter(
            TrainingSession.parade_night_id == pn.id,
            TrainingSession.is_archived == False,  # noqa: E712
            *([] if sq_id is None else [TrainingSession.squadron_id == sq_id]),
        ).order_by(TrainingSession.period_number).all()
        for s in sessions:
            ws.append([
                pd_obj.parade_date, dow, term,
                _neutralise_cell(s.period_number),
                _neutralise_cell(s.cadet_group or ""),
                _neutralise_cell(s.phase_at_time or ""),
                _neutralise_cell(s.curriculum_code_at_time or ""),
                _neutralise_cell(s.curriculum_title_at_time or s.custom_title or ""),
                _neutralise_cell(s.facilitator_display_name_at_time or ""),
                _neutralise_cell(s.training_area_name_at_time or ""),
                _neutralise_cell(s.status or "planned"),
            ])

    bio = io.BytesIO(); wb.save(bio); bio.seek(0)
    audit(db, p, object_type="export", object_id=year_id, action="export",
          new={"type": "schedule", "fmt": "xlsx"})
    fname = f"schedule-{py.year}.xlsx"
    return StreamingResponse(bio, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f"attachment; filename={fname}"})


@router.post("/years/{year_id}/schedule/import")
async def import_schedule_xlsx(
    year_id: str,
    preview: bool = Query(False),
    file: UploadFile = File(...),
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Import an edited schedule XLSX back into the planning year.

    Expected columns (case-insensitive): Date, Session, Group, Code, Title, Facilitator.
    Returns a row-level diff when preview=true; applies changes when preview=false.
    Only updates curriculum_item_id and custom_title — all other session fields are untouched.
    Permission-gated: same write rules as schedule edits.
    """
    import openpyxl
    from ..config import settings

    py = _get_year_or_404(year_id, db)
    _require_year_access(p, py, write=True)

    raw = await file.read()
    if len(raw) > settings.UPLOAD_MAX_MB * 1024 * 1024:
        raise HTTPException(413, detail={"error": "file_too_large"})
    try:
        wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    except Exception as exc:
        raise HTTPException(400, detail={"error": "unreadable_workbook", "message": str(exc)[:120]})

    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    raw_headers = next(rows_iter, None)
    if not raw_headers:
        raise HTTPException(400, detail={"error": "empty_sheet"})
    headers = [str(h).strip().lower() if h is not None else "" for h in raw_headers]

    def _col(name: str) -> int | None:
        aliases = {"date": ["date"], "session": ["session", "period", "session #", "period number"],
                   "group": ["group", "cadet group"], "code": ["code", "curriculum code"],
                   "title": ["title", "custom title"], "facilitator": ["facilitator"]}
        for a in aliases.get(name, [name]):
            if a in headers:
                return headers.index(a)
        return None

    ci = {k: _col(k) for k in ("date", "session", "group", "code", "title")}
    if ci["date"] is None or ci["session"] is None:
        raise HTTPException(400, detail={"error": "missing_required_columns",
                                         "message": "Sheet must have Date and Session columns"})

    # Build parade-date → parade-night index for this year
    all_pd = db.query(ParadeDate).filter(ParadeDate.planning_year_id == year_id).all()
    pd_by_date = {d.parade_date: d for d in all_pd}

    sq_id = p.acting_squadron_id or p.squadron_id

    preview_rows: list[dict] = []
    updated = skipped = not_found = 0

    for raw_row in rows_iter:
        if all(c is None for c in raw_row):
            continue
        def _cell(idx):
            if idx is None: return ""
            v = raw_row[idx] if idx < len(raw_row) else None
            return str(v).strip() if v is not None else ""

        date_val = _cell(ci["date"])
        session_val = _cell(ci["session"])
        group_val = _cell(ci["group"]) if ci["group"] is not None else ""
        code_val = _cell(ci["code"]) if ci["code"] is not None else ""
        title_val = _cell(ci["title"]) if ci["title"] is not None else ""

        if not date_val or not session_val:
            continue

        # Normalise date (handle date objects from openpyxl)
        try:
            if hasattr(date_val, "strftime"):
                date_str = date_val.strftime("%Y-%m-%d")
            else:
                date_str = str(date_val)[:10]
        except Exception:
            date_str = str(date_val)[:10]

        try:
            period = int(session_val)
        except (ValueError, TypeError):
            not_found += 1
            preview_rows.append({"date": date_str, "session": session_val, "group": group_val,
                                  "code": code_val, "title": title_val,
                                  "action": "not_found", "reason": "invalid_session_number"})
            continue

        pd_obj = pd_by_date.get(date_str)
        if not pd_obj or not pd_obj.parade_night_id:
            not_found += 1
            preview_rows.append({"date": date_str, "session": period, "group": group_val,
                                  "code": code_val, "title": title_val,
                                  "action": "not_found", "reason": "no_parade_night_on_date"})
            continue

        q = db.query(TrainingSession).filter(
            TrainingSession.parade_night_id == pd_obj.parade_night_id,
            TrainingSession.period_number == period,
            TrainingSession.is_archived == False,  # noqa: E712
        )
        if group_val:
            q = q.filter(TrainingSession.cadet_group == group_val)
        if sq_id:
            q = q.filter(TrainingSession.squadron_id == sq_id)
        sess_obj = q.first()

        if not sess_obj:
            not_found += 1
            preview_rows.append({"date": date_str, "session": period, "group": group_val,
                                  "code": code_val, "title": title_val,
                                  "action": "not_found", "reason": "no_session_record"})
            continue

        cur_code = sess_obj.curriculum_code_at_time or ""
        cur_title = sess_obj.curriculum_title_at_time or sess_obj.custom_title or ""

        # Resolve curriculum_item_id from code if provided
        new_ci_id = sess_obj.curriculum_item_id
        new_code = code_val or cur_code
        new_title = title_val or cur_title
        if code_val and code_val != cur_code:
            ci_match = db.query(CurriculumItem).filter(
                CurriculumItem.identifier == code_val,
                CurriculumItem.is_archived == False,  # noqa: E712
            ).first()
            if not ci_match:
                ci_match = db.query(CurriculumItem).filter(
                    CurriculumItem.code == code_val,
                    CurriculumItem.is_archived == False,  # noqa: E712
                ).first()
            if ci_match:
                new_ci_id = ci_match.id
                new_code = ci_match.identifier or ci_match.code
                new_title = ci_match.title

        changed = (new_ci_id != sess_obj.curriculum_item_id) or (new_title != cur_title)

        if not changed:
            skipped += 1
            preview_rows.append({"date": date_str, "session": period, "group": group_val,
                                  "code": new_code, "title": new_title,
                                  "current_code": cur_code, "current_title": cur_title,
                                  "action": "unchanged"})
            continue

        preview_rows.append({"date": date_str, "session": period, "group": group_val,
                              "code": new_code, "title": new_title,
                              "current_code": cur_code, "current_title": cur_title,
                              "action": "update"})

        if not preview:
            sess_obj.curriculum_item_id = new_ci_id
            sess_obj.curriculum_code_at_time = new_code
            sess_obj.curriculum_title_at_time = new_title
            if not code_val and title_val:
                sess_obj.curriculum_item_id = None
                sess_obj.custom_title = title_val
            updated += 1

    if not preview:
        db.commit()
        audit(db, p, object_type="schedule_import", object_id=year_id, action="import",
              new={"updated": updated, "skipped": skipped, "not_found": not_found})

    return {"ok": True, "preview": preview, "rows": preview_rows,
            "updated": updated, "skipped": skipped, "not_found": not_found}
