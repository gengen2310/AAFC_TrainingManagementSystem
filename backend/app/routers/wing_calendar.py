"""Wing HQ Calendar router.

Wing-level events are an authoritative planning source. Squadrons see them
as read-only overlays in Annual Program, Training Planner and Long Range views.

Permissions:
  - system_admin / national_admin: full access to any wing's events
  - wing_admin: full CRUD for their own wing only
  - sqn_admin / sqn_general / wing_viewer: read-only view of their wing's events
  - squadron_admin: can update their own squadron_event_status for a wing event
  - auditor: read-only
  - cross-scope IDOR denied on every write/read
"""
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy import cast, String
from sqlalchemy.orm import Session as DBSession

from ..database import get_db, utcnow, iso_z
from ..models import Wing, Squadron, CurriculumItem
from ..models.wing_calendar import (
    WingHQEvent, SquadronEventStatus, WingEventCurriculumLink,
    WING_EVENT_TYPES, PLANNING_IMPORTANCE_LEVELS, WING_EVENT_STATUS, SQN_STATUS_VALUES,
)
from ..dependencies import get_principal
from ..permissions import Principal, NATIONAL_LEVEL
from ..services import audit

router = APIRouter(prefix="/api/wing-calendar", tags=["wing-calendar"])

_WRITE_ROLES = frozenset({"wing_admin", "national_admin", "system_admin"})
_READ_ROLES  = frozenset({
    "sqn_admin", "sqn_general", "wing_admin", "wing_viewer",
    "national_admin", "national_viewer", "system_admin", "auditor",
})


# ─────────────────────────────────────────────────────────────
# RBAC helpers
# ─────────────────────────────────────────────────────────────

def _require_write(p: Principal, wing_id: str) -> None:
    if p.role not in _WRITE_ROLES:
        raise HTTPException(403, detail={"error": "forbidden"})
    if p.role == "wing_admin" and p.wing_id != wing_id:
        raise HTTPException(403, detail={"error": "out_of_scope"})


def _require_read(p: Principal, wing_id: str) -> None:
    if p.role not in _READ_ROLES:
        raise HTTPException(403, detail={"error": "forbidden"})
    # Scope enforcement for scoped roles
    if p.role in ("sqn_admin", "sqn_general") and p.wing_id != wing_id:
        raise HTTPException(403, detail={"error": "out_of_scope"})
    if p.role in ("wing_admin", "wing_viewer") and p.wing_id != wing_id:
        raise HTTPException(403, detail={"error": "out_of_scope"})


def _get_event_or_404(event_id: str, db: DBSession) -> WingHQEvent:
    e = db.get(WingHQEvent, event_id)
    if not e or e.is_archived:
        raise HTTPException(404, detail={"error": "event_not_found"})
    return e


# ─────────────────────────────────────────────────────────────
# Serialisers
# ─────────────────────────────────────────────────────────────

def _link_out(lnk: WingEventCurriculumLink, ci_code: str | None = None, ci_title: str | None = None) -> dict:
    return {
        "id": lnk.id,
        "curriculum_item_id": lnk.curriculum_item_id,
        "curriculum_code": ci_code,
        "curriculum_title": ci_title,
        "link_type": lnk.link_type,
        "notes": lnk.notes,
    }


def _sqn_status_out(ss: SquadronEventStatus | None) -> dict | None:
    if not ss:
        return None
    return {
        "status": ss.status,
        "notes": ss.notes,
        "reviewed_by": ss.reviewed_by,
        "reviewed_at": iso_z(ss.reviewed_at) if ss.reviewed_at else None,
        "local_activity_id": ss.local_activity_id,
    }


def _event_out(
    e: WingHQEvent,
    curriculum_links: list | None = None,
    sqn_status: dict | None = None,
    wing_code: str | None = None,
    wing_name: str | None = None,
) -> dict:
    return {
        "id": e.id,
        "wing_id": e.wing_id,
        "wing_code": wing_code,
        "wing_name": wing_name,
        "year": e.year,
        "title": e.title,
        "description": e.description,
        "event_type": e.event_type,
        "start_date": e.start_date,
        "end_date": e.end_date,
        "start_time": e.start_time,
        "end_time": e.end_time,
        "location": e.location,
        "source_system": e.source_system,
        "source_reference": e.source_reference,
        "source_event_code": e.source_event_code,
        "planning_importance": e.planning_importance,
        "audience": e.audience or [],
        "visibility": e.visibility,
        "status": e.status,
        "requires_squadron_action": e.requires_squadron_action,
        "is_planning_anchor": e.is_planning_anchor,
        "is_archived": e.is_archived,
        "notes": e.notes,
        "curriculum_links": curriculum_links or [],
        "squadron_status": sqn_status,
        "created_by": e.created_by,
        "updated_by": e.updated_by,
        "created_at": iso_z(e.created_at) if e.created_at else None,
        "updated_at": iso_z(e.updated_at) if e.updated_at else None,
    }


def _load_links(event_id: str, db: DBSession) -> list[dict]:
    links = db.query(WingEventCurriculumLink).filter(
        WingEventCurriculumLink.wing_event_id == event_id
    ).all()
    if not links:
        return []
    ci_ids = [lnk.curriculum_item_id for lnk in links]
    ci_map = {ci.id: ci for ci in db.query(CurriculumItem).filter(CurriculumItem.id.in_(ci_ids)).all()}
    return [_link_out(lnk, ci_map[lnk.curriculum_item_id].code if lnk.curriculum_item_id in ci_map else None,
                      ci_map[lnk.curriculum_item_id].title if lnk.curriculum_item_id in ci_map else None)
            for lnk in links]


def _load_links_for_events(event_ids: list[str], db: DBSession) -> dict[str, list[dict]]:
    """Batch-load curriculum links for a list of events — avoids N+1 on list endpoints."""
    if not event_ids:
        return {}
    links = db.query(WingEventCurriculumLink).filter(
        WingEventCurriculumLink.wing_event_id.in_(event_ids)
    ).all()
    ci_ids = list({lnk.curriculum_item_id for lnk in links})
    ci_map = {ci.id: ci for ci in db.query(CurriculumItem).filter(CurriculumItem.id.in_(ci_ids)).all()} if ci_ids else {}
    result: dict[str, list[dict]] = {eid: [] for eid in event_ids}
    for lnk in links:
        ci = ci_map.get(lnk.curriculum_item_id)
        result[lnk.wing_event_id].append(_link_out(lnk, ci.code if ci else None, ci.title if ci else None))
    return result


def _load_sqn_status(event_id: str, squadron_id: str | None, db: DBSession) -> dict | None:
    if not squadron_id:
        return None
    ss = db.query(SquadronEventStatus).filter(
        SquadronEventStatus.wing_event_id == event_id,
        SquadronEventStatus.squadron_id == squadron_id,
    ).first()
    return _sqn_status_out(ss)


# ─────────────────────────────────────────────────────────────
# Pydantic models
# ─────────────────────────────────────────────────────────────

def _validate_iso_date(v: str | None) -> str | None:
    if v is None:
        return v
    try:
        datetime.strptime(v, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"Date must be YYYY-MM-DD, got: {v!r}")
    return v


class WingEventIn(BaseModel):
    title: str
    description: Optional[str] = None
    event_type: str = "wing_event"
    start_date: str
    end_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None
    planning_importance: str = "key_event"
    audience: Optional[List[str]] = None
    visibility: str = "wing_only"
    status: str = "active"
    requires_squadron_action: bool = False
    is_planning_anchor: bool = False
    notes: Optional[str] = None
    source_system: Optional[str] = None
    source_reference: Optional[str] = None
    source_event_code: Optional[str] = None

    @field_validator("title")
    @classmethod
    def title_nonempty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty.")
        if len(v) > 300:
            raise ValueError("Title cannot exceed 300 characters.")
        return v

    @field_validator("start_date")
    @classmethod
    def start_date_iso(cls, v: str) -> str:
        _validate_iso_date(v)
        return v

    @field_validator("end_date")
    @classmethod
    def end_date_iso(cls, v: str | None) -> str | None:
        return _validate_iso_date(v)

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: str) -> str:
        if v not in WING_EVENT_STATUS:
            raise ValueError(f"status must be one of {sorted(WING_EVENT_STATUS)}")
        return v


class WingEventPatch(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    event_type: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    location: Optional[str] = None
    planning_importance: Optional[str] = None
    audience: Optional[List[str]] = None
    visibility: Optional[str] = None
    status: Optional[str] = None
    requires_squadron_action: Optional[bool] = None
    is_planning_anchor: Optional[bool] = None
    notes: Optional[str] = None

    @field_validator("title")
    @classmethod
    def title_nonempty(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty.")
        if len(v) > 300:
            raise ValueError("Title cannot exceed 300 characters.")
        return v

    @field_validator("start_date", "end_date")
    @classmethod
    def dates_iso(cls, v: str | None) -> str | None:
        return _validate_iso_date(v)

    @field_validator("status")
    @classmethod
    def status_valid(cls, v: str | None) -> str | None:
        if v is not None and v not in WING_EVENT_STATUS:
            raise ValueError(f"status must be one of {sorted(WING_EVENT_STATUS)}")
        return v


class CurriculumLinkIn(BaseModel):
    curriculum_item_id: str
    link_type: str = "covers"
    notes: Optional[str] = None


class SqnStatusIn(BaseModel):
    status: str
    notes: Optional[str] = None
    local_activity_id: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# LIST / GET
# ─────────────────────────────────────────────────────────────

@router.get("/events")
def list_wing_events(
    wing_id: Optional[str] = Query(default=None),
    year: Optional[int] = Query(default=None),
    event_type: Optional[str] = Query(default=None),
    planning_importance: Optional[str] = Query(default=None),
    audience: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """List Wing HQ events. Accessible to any user within the wing's scope.

    REM-13 Phase A: wing_id is now optional. Omitting it requests a true
    cross-wing National rollup (national_admin/national_viewer/system_admin/
    auditor only) -- previously the only way to see events from more than
    one wing was to fetch them one wing at a time client-side. A single
    wing_id.in_(...) query keeps pagination/filter semantics identical to
    the single-wing path (no N+1 loop needed for a flat list like this)."""
    if wing_id is None:
        if p.role not in NATIONAL_LEVEL:
            raise HTTPException(400, detail={"error": "wing_id_required"})
        wing_ids = [w.id for w in db.query(Wing).filter(Wing.is_archived == False).all()]  # noqa: E712
    else:
        _require_read(p, wing_id)
        wing_ids = [wing_id]

    q = db.query(WingHQEvent).filter(WingHQEvent.wing_id.in_(wing_ids))
    if not include_archived:
        q = q.filter(WingHQEvent.is_archived == False)  # noqa: E712
    if year:
        q = q.filter(WingHQEvent.year == year)
    if event_type:
        q = q.filter(WingHQEvent.event_type == event_type)
    if planning_importance:
        q = q.filter(WingHQEvent.planning_importance == planning_importance)
    if status:
        q = q.filter(WingHQEvent.status == status)
    else:
        q = q.filter(WingHQEvent.status != "cancelled")
    # Audience filter: push to DB as a JSON-string contains check (works for both
    # SQLite text and PostgreSQL JSON/JSONB); fall back gracefully on unsupported dialects.
    if audience:
        try:
            q = q.filter(cast(WingHQEvent.audience, String).contains(audience))
        except Exception:
            pass  # filter applied in Python below if the DB cast fails

    # R5-M18: when an audience filter is active, the DB contains() check is an
    # approximation (LIKE). Python re-filters precisely below. Applying DB
    # offset/limit before Python filtering produces pages shorter than requested.
    # Fix: fetch without pagination when audience is set, slice after Python filter.
    if audience:
        db_events = q.order_by(WingHQEvent.start_date, WingHQEvent.id).all()
    else:
        db_events = q.order_by(WingHQEvent.start_date, WingHQEvent.id).offset(offset).limit(limit).all()

    sqn_id = p.squadron_id
    links_map = _load_links_for_events([e.id for e in db_events], db)
    wing_map = {w.id: w for w in db.query(Wing).filter(Wing.id.in_(wing_ids)).all()}
    result = []
    for e in db_events:
        if audience:
            aud = e.audience or []
            if audience not in aud and "all_personnel" not in aud and "all_cadets" not in aud:
                continue
        w = wing_map.get(e.wing_id)
        result.append(_event_out(
            e,
            curriculum_links=links_map.get(e.id, []),
            sqn_status=_load_sqn_status(e.id, sqn_id, db),
            wing_code=w.code if w else None,
            wing_name=w.name if w else None,
        ))
    # Apply pagination after Python audience filter when audience was set
    if audience:
        result = result[offset:offset + limit]
    return result


@router.get("/events/{event_id}")
def get_wing_event(
    event_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    e = _get_event_or_404(event_id, db)
    _require_read(p, e.wing_id)
    return _event_out(
        e,
        curriculum_links=_load_links(e.id, db),
        sqn_status=_load_sqn_status(e.id, p.squadron_id, db),
    )


# ─────────────────────────────────────────────────────────────
# CREATE / UPDATE / ARCHIVE
# ─────────────────────────────────────────────────────────────

@router.post("/events")
def create_wing_event(
    wing_id: str = Query(...),
    body: WingEventIn = ...,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    _require_write(p, wing_id)
    wing = db.get(Wing, wing_id)
    if not wing:
        raise HTTPException(404, detail={"error": "wing_not_found"})

    if body.event_type not in WING_EVENT_TYPES:
        raise HTTPException(422, detail={"error": "invalid_event_type",
                                         "valid": list(WING_EVENT_TYPES)})
    if body.planning_importance not in PLANNING_IMPORTANCE_LEVELS:
        raise HTTPException(422, detail={"error": "invalid_planning_importance",
                                         "valid": list(PLANNING_IMPORTANCE_LEVELS)})

    # Year inferred from start_date if not explicitly given
    year = int(body.start_date[:4]) if body.start_date else datetime.now().year

    e = WingHQEvent(
        id=str(uuid.uuid4()),
        wing_id=wing_id,
        year=year,
        title=body.title.strip(),
        description=body.description,
        event_type=body.event_type,
        start_date=body.start_date,
        end_date=body.end_date,
        start_time=body.start_time,
        end_time=body.end_time,
        location=body.location,
        planning_importance=body.planning_importance,
        audience=body.audience,
        visibility=body.visibility,
        status=body.status,
        requires_squadron_action=body.requires_squadron_action,
        is_planning_anchor=body.is_planning_anchor,
        notes=body.notes,
        source_system=body.source_system,
        source_reference=body.source_reference,
        source_event_code=body.source_event_code,
        created_by=p.user_id,
        updated_by=p.user_id,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    audit(db, p, object_type="wing_hq_event", object_id=e.id, action="create",
          new={"title": e.title, "start_date": e.start_date, "event_type": e.event_type})
    return _event_out(e)


@router.patch("/events/{event_id}")
def update_wing_event(
    event_id: str,
    body: WingEventPatch,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    e = _get_event_or_404(event_id, db)
    _require_write(p, e.wing_id)

    old = {"title": e.title, "start_date": e.start_date, "status": e.status}
    if body.title is not None:
        e.title = body.title.strip()
    if body.description is not None:
        e.description = body.description
    if body.event_type is not None:
        if body.event_type not in WING_EVENT_TYPES:
            raise HTTPException(422, detail={"error": "invalid_event_type"})
        e.event_type = body.event_type
    if body.start_date is not None:
        e.start_date = body.start_date
    if body.end_date is not None:
        e.end_date = body.end_date
    if body.start_time is not None:
        e.start_time = body.start_time
    if body.end_time is not None:
        e.end_time = body.end_time
    if body.location is not None:
        e.location = body.location
    if body.planning_importance is not None:
        if body.planning_importance not in PLANNING_IMPORTANCE_LEVELS:
            raise HTTPException(422, detail={"error": "invalid_planning_importance"})
        e.planning_importance = body.planning_importance
    if body.audience is not None:
        e.audience = body.audience
    if body.visibility is not None:
        e.visibility = body.visibility
    if body.status is not None:
        e.status = body.status
    if body.requires_squadron_action is not None:
        e.requires_squadron_action = body.requires_squadron_action
    if body.is_planning_anchor is not None:
        e.is_planning_anchor = body.is_planning_anchor
    if body.notes is not None:
        e.notes = body.notes
    e.updated_by = p.user_id
    e.updated_at = utcnow()
    db.commit()
    audit(db, p, object_type="wing_hq_event", object_id=e.id, action="update",
          old=old, new={"title": e.title, "start_date": e.start_date, "status": e.status})
    return _event_out(e, curriculum_links=_load_links(e.id, db))


@router.post("/events/{event_id}/archive")
def archive_wing_event(
    event_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    e = _get_event_or_404(event_id, db)
    _require_write(p, e.wing_id)
    e.is_archived = True
    e.archived_at = utcnow()
    e.updated_by = p.user_id
    db.commit()
    audit(db, p, object_type="wing_hq_event", object_id=e.id, action="archive",
          new={"title": e.title})
    return {"ok": True}


@router.post("/events/{event_id}/restore")
def restore_wing_event(
    event_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """REM-133: Wing HQ Event archive existed with no restore counterpart.
    Cannot use _get_event_or_404 -- it excludes archived events by design
    (see its own is_archived check), which is exactly the row this endpoint
    needs to find."""
    e = db.get(WingHQEvent, event_id)
    if not e:
        raise HTTPException(404, detail={"error": "event_not_found"})
    _require_write(p, e.wing_id)
    if not e.is_archived:
        raise HTTPException(409, detail={"error": "not_archived"})
    e.is_archived = False
    e.archived_at = None
    e.updated_by = p.user_id
    db.commit()
    audit(db, p, object_type="wing_hq_event", object_id=e.id, action="restore",
          new={"title": e.title})
    return {"ok": True}


# ─────────────────────────────────────────────────────────────
# CURRICULUM LINKS
# ─────────────────────────────────────────────────────────────

@router.post("/events/{event_id}/curriculum-links")
def add_curriculum_link(
    event_id: str,
    body: CurriculumLinkIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    e = _get_event_or_404(event_id, db)
    _require_write(p, e.wing_id)

    ci = db.get(CurriculumItem, body.curriculum_item_id)
    if not ci:
        raise HTTPException(404, detail={"error": "curriculum_item_not_found"})

    existing = db.query(WingEventCurriculumLink).filter(
        WingEventCurriculumLink.wing_event_id == event_id,
        WingEventCurriculumLink.curriculum_item_id == body.curriculum_item_id,
    ).first()
    if existing:
        raise HTTPException(409, detail={"error": "link_already_exists"})

    lnk = WingEventCurriculumLink(
        id=str(uuid.uuid4()),
        wing_event_id=event_id,
        curriculum_item_id=body.curriculum_item_id,
        link_type=body.link_type,
        notes=body.notes,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(lnk)
    db.commit()
    audit(db, p, object_type="wing_event_curriculum_link", object_id=lnk.id, action="create",
          new={"event_id": event_id, "curriculum_item_id": body.curriculum_item_id,
               "curriculum_code": ci.code})
    return _link_out(lnk, ci.code, ci.title)


@router.delete("/events/{event_id}/curriculum-links/{curriculum_item_id}")
def remove_curriculum_link(
    event_id: str,
    curriculum_item_id: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    e = _get_event_or_404(event_id, db)
    _require_write(p, e.wing_id)

    lnk = db.query(WingEventCurriculumLink).filter(
        WingEventCurriculumLink.wing_event_id == event_id,
        WingEventCurriculumLink.curriculum_item_id == curriculum_item_id,
    ).first()
    if not lnk:
        raise HTTPException(404, detail={"error": "link_not_found"})
    db.delete(lnk)
    db.commit()
    audit(db, p, object_type="wing_event_curriculum_link", object_id=lnk.id, action="delete",
          new={"event_id": event_id, "curriculum_item_id": curriculum_item_id})
    return {"ok": True}


# ─────────────────────────────────────────────────────────────
# SQUADRON-SPECIFIC STATUS
# ─────────────────────────────────────────────────────────────

@router.patch("/events/{event_id}/squadron-status")
def update_squadron_status(
    event_id: str,
    body: SqnStatusIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Update this squadron's response status for a Wing HQ event.

    Only sqn_admin (or higher for their scope) can update their squadron's status.
    Status updates for 703SQN are independent from 704SQN.
    """
    if p.role not in ("sqn_admin", "wing_admin", "national_admin", "system_admin"):
        raise HTTPException(403, detail={"error": "forbidden"})

    e = _get_event_or_404(event_id, db)
    _require_read(p, e.wing_id)

    sqn_id = p.squadron_id
    if not sqn_id:
        raise HTTPException(400, detail={"error": "no_squadron_scope"})

    if body.status not in SQN_STATUS_VALUES:
        raise HTTPException(422, detail={"error": "invalid_status", "valid": list(SQN_STATUS_VALUES)})

    ss = db.query(SquadronEventStatus).filter(
        SquadronEventStatus.wing_event_id == event_id,
        SquadronEventStatus.squadron_id == sqn_id,
    ).first()

    if ss:
        ss.status = body.status
        ss.notes = body.notes
        ss.local_activity_id = body.local_activity_id
        ss.updated_at = utcnow()
        if body.status in ("reviewed", "preparation_planned"):
            ss.reviewed_by = p.user_id
            ss.reviewed_at = utcnow()
    else:
        ss = SquadronEventStatus(
            id=str(uuid.uuid4()),
            wing_event_id=event_id,
            squadron_id=sqn_id,
            status=body.status,
            notes=body.notes,
            local_activity_id=body.local_activity_id,
            reviewed_by=p.user_id if body.status in ("reviewed", "preparation_planned") else None,
            reviewed_at=utcnow() if body.status in ("reviewed", "preparation_planned") else None,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(ss)

    db.commit()
    audit(db, p, object_type="squadron_event_status", object_id=ss.id, action="update",
          new={"event_id": event_id, "squadron_id": sqn_id, "status": body.status})
    return _sqn_status_out(ss)


# ─────────────────────────────────────────────────────────────
# SQUADRON OVERLAY (used by Annual Program, Long Range)
# ─────────────────────────────────────────────────────────────

@router.get("/squadron-overlay")
def get_squadron_overlay(
    wing_id: str = Query(...),
    year: int = Query(...),
    squadron_id: Optional[str] = Query(default=None),
    importance: Optional[str] = Query(default=None),
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Return Wing HQ events for a given wing+year for squadron overlay display.

    Used by Annual Program page to show inherited Wing events alongside
    squadron parade nights without duplicating them.
    """
    _require_read(p, wing_id)

    q = db.query(WingHQEvent).filter(
        WingHQEvent.wing_id == wing_id,
        WingHQEvent.year == year,
        WingHQEvent.is_archived == False,  # noqa: E712
        WingHQEvent.status != "cancelled",
    )
    if importance:
        q = q.filter(WingHQEvent.planning_importance == importance)

    events = q.order_by(WingHQEvent.start_date).all()

    # Resolve which squadron's status to include; enforce scope.
    # active_squadron_id so that a Wing Admin in Proxy Mode sees the proxied
    # squadron's status rather than none at all -- wing accounts have no home
    # squadron, so squadron_id alone resolved to None here.
    sqn_id = squadron_id or p.active_squadron_id
    if squadron_id and squadron_id != p.active_squadron_id:
        # Cross-squadron status lookup only allowed for wing/national/system scope
        if p.role in ("sqn_admin", "sqn_general"):
            raise HTTPException(403, detail={"error": "out_of_scope"})
        if p.role in ("wing_admin", "wing_viewer"):
            sqn = db.get(Squadron, squadron_id)
            if not sqn or sqn.wing_id != p.wing_id:
                raise HTTPException(403, detail={"error": "out_of_scope"})

    links_map = _load_links_for_events([e.id for e in events], db)
    return [_event_out(
        e,
        curriculum_links=links_map.get(e.id, []),
        sqn_status=_load_sqn_status(e.id, sqn_id, db),
    ) for e in events]
