from __future__ import annotations

import json as _json

from fastapi import APIRouter, Depends, Request, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session as DBSession

from ..database import get_db, utcnow
from ..models import (CurriculumItem, CurriculumElement, ParadeNight, Session, SessionStatusHistory,
                      Facilitator, FacilitatorRankHistory, TrainingArea, Equipment,
                      Activity, Cadet, Squadron, TimingTemplate, TimingBlock)
from ..models.training import ELEMENT_SCOPE_LEVELS
from .timing import _effective_template
from ..dependencies import get_principal, client_meta
from ..permissions import (Principal, require_can_view_squadron, require_can_write_squadron)
from ..services import (audit, score_parade, publish_blockers, close_blockers)

router = APIRouter(prefix="/api", tags=["training"])


def _check_version(obj, client_version: int | None) -> None:
    """Raise 409 if the client's version is stale (optimistic locking)."""
    if client_version is not None and obj.version != client_version:
        raise HTTPException(409, detail={
            "error": "version_conflict",
            "current_version": obj.version,
        })


VALID_STATUS = {"draft", "planned", "published", "delivered", "delivered_with_issue",
                "cancelled", "cancelled_late", "rescheduled", "not_delivered",
                "requires_review", "blocked", "closed"}


def _parse_json_list(val) -> list:
    """Return val as a list, JSON-parsing it if stored as a TEXT string (Postgres TEXT vs JSON/JSONB mismatch)."""
    if not val:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            result = _json.loads(val)
            return result if isinstance(result, list) else []
        except (_json.JSONDecodeError, TypeError):
            return []
    return []


def _active_squadron(p: Principal) -> str:
    """The squadron a write should target: proxy/intervention target, else home."""
    if p.acting_squadron_id:
        return p.acting_squadron_id
    return p.squadron_id


def _sess_dict(s: Session) -> dict:
    d = {c.name: getattr(s, c.name) for c in s.__table__.columns}
    d["session_id"] = s.id  # alias for Night Builder compatibility
    return d


# ── CURRICULUM ──
@router.get("/curriculum")
def list_curriculum(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    sq_id = _active_squadron(p)
    # Resolve the wing for the acting scope
    wing_id: str | None = p.acting_wing_id or p.wing_id
    if sq_id:
        s = db.get(Squadron, sq_id)
        if s:
            wing_id = s.wing_id

    from sqlalchemy import or_
    conditions = [CurriculumItem.owning_level == "national"]
    if wing_id:
        conditions.append(
            (CurriculumItem.owning_level == "wing") & (CurriculumItem.wing_id == wing_id))
    elif p.role in _NAT_ADMIN_ROLES:
        # National admin with no proxy/wing scope sees all wing curriculum across all wings
        conditions.append(CurriculumItem.owning_level == "wing")
    if sq_id:
        conditions.append(CurriculumItem.squadron_id == sq_id)

    items = db.query(CurriculumItem).filter(
        CurriculumItem.is_archived == False,  # noqa: E712
        or_(*conditions)
    ).order_by(CurriculumItem.recommended_sequence).all()

    # Preload all sessions for this squadron in one query, then group by curriculum_item_id.
    item_ids = [i.id for i in items]
    all_sess = db.query(Session).filter(
        Session.curriculum_item_id.in_(item_ids),
        Session.squadron_id == sq_id,
        Session.is_archived == False,  # noqa: E712
    ).all() if item_ids else []
    from collections import defaultdict
    sess_by_item: dict[str, list] = defaultdict(list)
    for s in all_sess:
        sess_by_item[s.curriculum_item_id].append(s)

    out = []
    for i in items:
        statuses = [s.status for s in sess_by_item[i.id]]
        out.append({"curriculum_id": i.id, "code": i.code, "identifier": i.identifier,
                    "part_number": i.part_number, "title": i.title, "phase": i.phase,
                    "element": i.element, "duration_minutes": i.duration_minutes,
                    "part_count": i.part_count, "instructor_suitability": i.instructor_suitability,
                    "core_status": i.core_status, "learning_hub_url": i.learning_hub_url,
                    "recommended_term": i.recommended_term, "owning_level": i.owning_level,
                    "wing_id": i.wing_id, "squadron_id": i.squadron_id,
                    "session_count": len(statuses), "progress": _progress(statuses)})
    return {"items": out}


def _progress(statuses: list[str]) -> str:
    if not statuses:
        return "unscheduled"
    if "delivered" in statuses or "delivered_with_issue" in statuses:
        return "delivered"
    if all(s in ("cancelled", "cancelled_late") for s in statuses):
        return "cancelled"
    if "rescheduled" in statuses:
        return "rescheduled"
    if "not_delivered" in statuses:
        return "not_delivered"
    return "planned"


@router.get("/curriculum/export.xlsx")
def export_curriculum_xlsx(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    """Export the visible curriculum catalogue as XLSX."""
    import io, openpyxl
    from fastapi.responses import StreamingResponse
    from openpyxl.styles import Font, PatternFill
    from ..services import audit as _audit

    sq_id = _active_squadron(p)
    wing_id: str | None = p.acting_wing_id or p.wing_id
    if sq_id:
        s = db.get(Squadron, sq_id)
        if s:
            wing_id = s.wing_id
    from sqlalchemy import or_
    conditions = [CurriculumItem.owning_level == "national"]
    if wing_id:
        conditions.append((CurriculumItem.owning_level == "wing") & (CurriculumItem.wing_id == wing_id))
    elif p.role in _NAT_ADMIN_ROLES:
        conditions.append(CurriculumItem.owning_level == "wing")
    if sq_id:
        conditions.append(CurriculumItem.squadron_id == sq_id)
    items = db.query(CurriculumItem).filter(
        CurriculumItem.is_archived == False,  # noqa: E712
        or_(*conditions)
    ).order_by(CurriculumItem.recommended_sequence).all()

    wb = openpyxl.Workbook()
    ws = wb.active; ws.title = "Curriculum"
    hdr_fill = PatternFill("solid", fgColor="002F65")
    hdr_font = Font(color="FFFFFF", bold=True)
    headers = ["Code", "Identifier", "Title", "Phase", "Element", "Duration (min)",
               "Core Status", "Instructor Suitability", "Recommended Term",
               "Owning Level", "Learning Hub URL"]
    ws.append(headers)
    for cell in ws[1]:
        cell.fill = hdr_fill; cell.font = hdr_font

    def _n(v):
        s = str(v) if v is not None else ""
        return ("'" + s) if s[:1] in ("=", "+", "-", "@") else s

    for i in items:
        ws.append([_n(i.code), _n(i.identifier), _n(i.title), _n(i.phase),
                   _n(i.element), i.duration_minutes or "",
                   _n(i.core_status or ""), _n(i.instructor_suitability or ""),
                   _n(i.recommended_term or ""), _n(i.owning_level),
                   _n(i.learning_hub_url or "")])

    bio = io.BytesIO(); wb.save(bio); bio.seek(0)
    _audit(db, p, object_type="export", object_id=None, action="export",
           new={"type": "curriculum", "fmt": "xlsx", "rows": len(items)})
    return StreamingResponse(bio,
                             media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": "attachment; filename=curriculum.xlsx"})


@router.get("/curriculum/{cid}/sessions")
def curriculum_sessions(cid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    sq_id = _active_squadron(p)
    sess = db.query(Session).filter(Session.curriculum_item_id == cid,
                                    Session.squadron_id == sq_id).all()
    return [_sess_dict(s) for s in sess]


# ── PARADE NIGHTS ──
class ParadeIn(BaseModel):
    date: str
    term: str | None = "T1"
    session_count: int | None = None  # None = use effective timing template or default
    parade_type: str | None = "normal"


@router.get("/parade-nights")
def list_parades(squadron_id: str | None = None, db: DBSession = Depends(get_db),
                 p: Principal = Depends(get_principal)):
    sq_id = squadron_id or _active_squadron(p)
    s = db.get(Squadron, sq_id)
    if s:
        require_can_view_squadron(p, s.id, s.wing_id)
    pns = db.query(ParadeNight).filter(ParadeNight.squadron_id == sq_id,
                                       ParadeNight.is_archived == False).order_by(ParadeNight.date).all()  # noqa: E712
    out = []
    for pn in pns:
        sess = db.query(Session).filter(Session.parade_night_id == pn.id,
                                        Session.is_archived == False).all()  # noqa: E712
        out.append({**_pn_dict(pn), "sessions": [_sess_dict(x) for x in sess]})
    return out


@router.get("/parade-nights/{pnid}")
def get_parade(pnid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    pn = db.get(ParadeNight, pnid)
    if not pn or pn.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    require_can_view_squadron(p, pn.squadron_id, pn.wing_id)
    sess = [_sess_dict(x) for x in db.query(Session).filter(Session.parade_night_id == pn.id,
                                                            Session.is_archived == False).all()]  # noqa: E712
    r = score_parade(sess)
    return {**_pn_dict(pn), "sessions": sess, "readiness": r, "publish_blockers": publish_blockers(sess)}


@router.post("/parade-nights")
def create_parade(body: ParadeIn, request: Request, db: DBSession = Depends(get_db),
                  p: Principal = Depends(get_principal)):
    sq_id = _active_squadron(p)
    # Roles that can never write squadron data get a clean 403 first.
    if p.role in ("sqn_general", "wing_viewer", "national_viewer", "auditor"):
        raise HTTPException(403, detail={"error": "forbidden"})
    if not sq_id:
        # Wing/National admins must enter Proxy / Delegated Intervention to gain a squadron scope.
        require_can_write_squadron(p, "none", None)
        raise HTTPException(400, detail={"error": "no_squadron_scope"})
    s = db.get(Squadron, sq_id)
    if not s:
        raise HTTPException(400, detail={"error": "no_squadron_scope"})
    require_can_write_squadron(p, s.id, s.wing_id)
    existing = db.query(ParadeNight).filter(
        ParadeNight.squadron_id == s.id,
        ParadeNight.date == body.date,
        ParadeNight.is_archived == False,  # noqa: E712
    ).first()
    if existing:
        raise HTTPException(409, detail={"error": "duplicate_date", "existing_id": existing.id})
    # Determine session count from effective timing template if one exists.
    # session_count in the body can still override (e.g. user explicitly changes it).
    effective_tmpl = _effective_template(db, s.id, body.date)
    if effective_tmpl and body.session_count is None:
        ip_count = sum(1 for b in effective_tmpl.blocks if b.is_instructional_period)
        session_count = ip_count if ip_count > 0 else (s.default_session_count or 3)
    else:
        session_count = body.session_count or s.default_session_count or 3

    pn = ParadeNight(squadron_id=s.id, wing_id=s.wing_id, date=body.date, term=body.term,
                     start_time=s.default_start_time, end_time=s.default_end_time,
                     session_count=session_count, parade_type=body.parade_type or "normal",
                     timing_template_id=effective_tmpl.id if effective_tmpl else None,
                     created_by=p.user_id)
    db.add(pn); db.commit()
    meta = client_meta(request)
    audit(db, p, object_type="parade_night", object_id=pn.id, action="create",
          new={"date": body.date}, ip=meta["ip"], ua=meta["ua"])
    return {"ok": True, "parade_night_id": pn.id}


def _pn_dict(pn: ParadeNight) -> dict:
    return {"parade_night_id": pn.id, "squadron_id": pn.squadron_id, "date": pn.date, "term": pn.term,
            "start_time": pn.start_time, "end_time": pn.end_time, "session_count": pn.session_count,
            "parade_type": pn.parade_type, "published_status": pn.published_status,
            "readiness_score": pn.readiness_score, "closeout_status": pn.closeout_status,
            "timing_template_id": pn.timing_template_id}


# ── SESSIONS ──
class SessionIn(BaseModel):
    parade_night_id: str
    period_number: int = 1
    cadet_group: str | None = None  # orientation/initial/junior/intermediate/senior
    phase_at_time: str | None = "B. Initial"
    curriculum_item_id: str | None = None
    custom_title: str | None = None
    facilitator_id: str | None = None
    training_area_id: str | None = None
    expected_attendance: int | None = None
    version: int | None = None


class StatusIn(BaseModel):
    status: str
    reason: str | None = None
    rescheduled_to_date: str | None = None
    actual_attendance: int | None = None


def _recompute(db: DBSession, pn: ParadeNight):
    sess = [_sess_dict(x) for x in db.query(Session).filter(Session.parade_night_id == pn.id,
                                                            Session.is_archived == False).all()]  # noqa: E712
    pn.readiness_score = score_parade(sess)["score"]
    db.commit()


@router.post("/sessions")
def create_session(body: SessionIn, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    pn = db.get(ParadeNight, body.parade_night_id)
    if not pn or pn.is_archived:
        raise HTTPException(404, detail={"error": "parade_night_not_found"})
    require_can_write_squadron(p, pn.squadron_id, pn.wing_id)
    s = Session(parade_night_id=pn.id, squadron_id=pn.squadron_id, period_number=body.period_number,
                cadet_group=body.cadet_group, phase_at_time=body.phase_at_time, custom_title=body.custom_title,
                expected_attendance=body.expected_attendance, status="planned", created_by=p.user_id)
    _denormalise(db, s, body.curriculum_item_id, body.facilitator_id, body.training_area_id)
    db.add(s); db.commit()
    _recompute(db, pn)
    audit(db, p, object_type="session", object_id=s.id, action="create")
    return {"ok": True, "session_id": s.id}


@router.put("/sessions/{sid}")
def edit_session(sid: str, body: SessionIn, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    s = db.get(Session, sid)
    if not s or s.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    pn = db.get(ParadeNight, s.parade_night_id)
    require_can_write_squadron(p, s.squadron_id, pn.wing_id if pn else None)
    _check_version(s, body.version)
    old = {"facilitator_id": s.facilitator_id, "training_area_id": s.training_area_id}
    s.period_number = body.period_number
    s.cadet_group = body.cadet_group
    s.phase_at_time = body.phase_at_time
    s.custom_title = body.custom_title
    s.expected_attendance = body.expected_attendance
    _denormalise(db, s, body.curriculum_item_id, body.facilitator_id, body.training_area_id)
    s.version += 1
    db.commit()
    if pn:
        _recompute(db, pn)
    # Edits after publication require a reason (recorded in audit).
    audit(db, p, object_type="session", object_id=s.id, action="edit", old=old,
          new={"facilitator_id": s.facilitator_id, "training_area_id": s.training_area_id})
    return {"ok": True}


@router.post("/sessions/{sid}/status")
def set_status(sid: str, body: StatusIn, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    s = db.get(Session, sid)
    if not s or s.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    pn = db.get(ParadeNight, s.parade_night_id)
    require_can_write_squadron(p, s.squadron_id, pn.wing_id if pn else None)
    if body.status not in VALID_STATUS:
        raise HTTPException(400, detail={"error": "invalid_status"})
    if body.status == "not_delivered" and not (body.reason or "").strip():
        raise HTTPException(400, detail={"error": "reason_required_not_delivered"})
    old = s.status
    s.status = body.status
    if body.status == "not_delivered":
        s.not_delivered_reason = body.reason
    if body.status in ("cancelled", "cancelled_late"):
        s.cancelled_reason = body.reason
    if body.status == "rescheduled":
        s.rescheduled_to_date = body.rescheduled_to_date
    if body.actual_attendance is not None:
        s.actual_attendance = body.actual_attendance
    db.add(SessionStatusHistory(session_id=s.id, old_status=old, new_status=body.status,
                                changed_by=p.user_id, reason=body.reason))
    db.commit()
    if pn:
        _recompute(db, pn)
    audit(db, p, object_type="session", object_id=s.id, action="status_change",
          old={"status": old}, new={"status": body.status}, reason=body.reason)
    return {"ok": True}


def _denormalise(db, s: Session, cid, fid, rid):
    if cid is not None:
        s.curriculum_item_id = cid
        c = db.get(CurriculumItem, cid) if cid else None
        if c:
            s.curriculum_code_at_time = c.code
            s.curriculum_title_at_time = c.title
            s.phase_at_time = c.phase
            s.element_at_time = c.element
    if fid is not None:
        s.facilitator_id = fid
        f = db.get(Facilitator, fid) if fid else None
        if f:
            s.facilitator_rank_at_time = f.current_rank
            s.facilitator_display_name_at_time = " ".join(x for x in [f.current_rank, f.first_name, f.last_name] if x)
        elif fid is None:
            s.facilitator_display_name_at_time = None
    if rid is not None:
        s.training_area_id = rid
        r = db.get(TrainingArea, rid) if rid else None
        s.training_area_name_at_time = r.name if r else None


@router.post("/parade-nights/{pnid}/publish")
def publish(pnid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    pn = db.get(ParadeNight, pnid)
    if not pn or pn.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    require_can_write_squadron(p, pn.squadron_id, pn.wing_id)
    sess = [_sess_dict(x) for x in db.query(Session).filter(Session.parade_night_id == pn.id,
                                                            Session.is_archived == False).all()]  # noqa: E712
    blockers = publish_blockers(sess)
    if blockers:
        raise HTTPException(409, detail={"error": "publish_blocked", "blockers": blockers})
    pn.published_status = True; pn.published_by = p.user_id; pn.published_at = utcnow()
    db.query(Session).filter(Session.parade_night_id == pn.id,
                             Session.status.in_(("draft", "planned"))).update({"status": "published"})
    db.commit()
    audit(db, p, object_type="parade_night", object_id=pn.id, action="publish")
    return {"ok": True}


@router.post("/parade-nights/{pnid}/close")
def close(pnid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    pn = db.get(ParadeNight, pnid)
    if not pn or pn.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    require_can_write_squadron(p, pn.squadron_id, pn.wing_id)
    sess = [_sess_dict(x) for x in db.query(Session).filter(Session.parade_night_id == pn.id,
                                                            Session.is_archived == False).all()]  # noqa: E712
    blockers = close_blockers(sess)
    if blockers:
        raise HTTPException(409, detail={"error": "close_blocked", "blockers": blockers})
    pn.closeout_status = "closed"; pn.closed_by = p.user_id; pn.closed_at = utcnow()
    db.commit()
    audit(db, p, object_type="parade_night", object_id=pn.id, action="close")
    return {"ok": True}


# ── FACILITATORS ──
_MAX_TAGS = 20
_MAX_TAG_LEN = 80


def _validate_subject_areas(raw: list[str] | None) -> list[str]:
    """Trim, deduplicate (case-insensitive), and enforce limits on tag list."""
    if not raw:
        return []
    seen: dict[str, str] = {}
    for item in raw:
        if not isinstance(item, str):
            raise HTTPException(422, detail={"error": "subject_areas_invalid",
                                             "message": "Each subject area must be a string."})
        tag = item.strip()
        if not tag:
            continue
        if len(tag) > _MAX_TAG_LEN:
            raise HTTPException(422, detail={"error": "subject_areas_invalid",
                                             "message": f"Tags must be {_MAX_TAG_LEN} characters or fewer."})
        seen.setdefault(tag.lower(), tag)
    result = list(seen.values())
    if len(result) > _MAX_TAGS:
        raise HTTPException(422, detail={"error": "subject_areas_invalid",
                                         "message": f"A maximum of {_MAX_TAGS} subject areas is allowed."})
    return result


class FacIn(BaseModel):
    first_name: str | None = None
    last_name: str
    current_rank: str | None = None
    type: str | None = "Staff"
    subject_areas: list[str] | None = None


@router.get("/facilitators")
def list_facs(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    sq_id = _active_squadron(p)
    facs = db.query(Facilitator).filter(Facilitator.squadron_id == sq_id,
                                        Facilitator.is_archived == False).all()  # noqa: E712
    out = []
    for f in facs:
        out.append({"facilitator_id": f.id, "first_name": f.first_name, "last_name": f.last_name,
                    "current_rank": f.current_rank, "type": f.type,
                    "subject_areas": _parse_json_list(f.subject_areas)})
    return out


@router.post("/facilitators")
def add_fac(body: FacIn, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    if p.role in _WRITE_BLOCKED:
        raise HTTPException(403, detail={"error": "forbidden"})
    sq_id = _active_squadron(p)
    if not sq_id:
        require_can_write_squadron(p, "none", None)
    s = db.get(Squadron, sq_id)
    if not s:
        raise HTTPException(400, detail={"error": "no_squadron_scope"})
    require_can_write_squadron(p, s.id, s.wing_id)
    f = Facilitator(squadron_id=s.id, wing_id=s.wing_id, first_name=body.first_name,
                    last_name=body.last_name, current_rank=body.current_rank, type=body.type or "Staff",
                    subject_areas=_validate_subject_areas(body.subject_areas))
    db.add(f); db.commit()
    db.add(FacilitatorRankHistory(facilitator_id=f.id, rank=body.current_rank, effective_from=str(utcnow().date())))
    db.commit()
    audit(db, p, object_type="facilitator", object_id=f.id, action="create")
    return {"ok": True, "facilitator_id": f.id}


class FacUpdateIn(BaseModel):
    subject_areas: list[str] | None = None
    type: str | None = None
    current_rank: str | None = None
    first_name: str | None = None
    last_name: str | None = None


@router.patch("/facilitators/{fid}")
def update_fac(fid: str, body: FacUpdateIn, db: DBSession = Depends(get_db),
               p: Principal = Depends(get_principal)):
    f = db.get(Facilitator, fid)
    if not f:
        raise HTTPException(404, detail={"error": "not_found"})
    require_can_write_squadron(p, f.squadron_id, f.wing_id)
    if body.subject_areas is not None:
        f.subject_areas = _validate_subject_areas(body.subject_areas)
    if body.type is not None:
        f.type = body.type
    if body.current_rank is not None:
        f.current_rank = body.current_rank
    if body.first_name is not None:
        f.first_name = body.first_name
    if body.last_name is not None:
        f.last_name = body.last_name
    db.commit()
    audit(db, p, object_type="facilitator", object_id=f.id, action="update",
          reason="subject-area tags" if body.subject_areas is not None else "update")
    return {"ok": True, "facilitator_id": f.id,
            "subject_areas": _parse_json_list(f.subject_areas)}


@router.get("/facilitators/{fid}/stats")
def fac_stats(fid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    f = db.get(Facilitator, fid)
    if not f:
        raise HTTPException(404, detail={"error": "not_found"})
    require_can_view_squadron(p, f.squadron_id, f.wing_id)
    sess = db.query(Session).filter(Session.facilitator_id == fid).all()
    counts, by_phase = {}, {}
    for s in sess:
        counts[s.status] = counts.get(s.status, 0) + 1
        by_phase[s.phase_at_time] = by_phase.get(s.phase_at_time, 0) + 1
    return {"facilitator": {"facilitator_id": f.id, "name": " ".join(x for x in [f.current_rank, f.first_name, f.last_name] if x)},
            "counts": counts, "by_phase": by_phase, "load_score": len(sess) * 2,
            "sessions": [_sess_dict(s) for s in sess]}


# ── RESOURCES ──
@router.get("/training-areas")
def list_rooms(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    sq_id = _active_squadron(p)
    rows = db.query(TrainingArea).filter(TrainingArea.squadron_id == sq_id,
                                         TrainingArea.is_archived == False).all()  # noqa: E712
    return [{"training_area_id": r.id, "name": r.name, "type": r.type, "capacity": r.capacity,
             "indoor_outdoor": r.indoor_outdoor} for r in rows]


@router.get("/equipment")
def list_equipment(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    sq_id = _active_squadron(p)
    rows = db.query(Equipment).filter(Equipment.squadron_id == sq_id,
                                      Equipment.is_archived == False).all()  # noqa: E712
    return [{"equipment_id": e.id, "name": e.name, "type": e.type, "quantity": e.quantity,
             "available_quantity": e.available_quantity} for e in rows]


@router.get("/resources/clashes")
def resource_clashes(date: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    """Detect room/facilitator double-booking on a given parade date."""
    sq_id = _active_squadron(p)
    pn = db.query(ParadeNight).filter(ParadeNight.squadron_id == sq_id, ParadeNight.date == date).first()
    clashes = []
    if pn:
        sess = db.query(Session).filter(Session.parade_night_id == pn.id).all()
        rooms, facs = {}, {}
        for s in sess:
            if s.training_area_id:
                rooms.setdefault(s.training_area_id, []).append(s.period_number)
            if s.facilitator_id:
                facs.setdefault(s.facilitator_id, []).append(s.period_number)
        for rid, periods in rooms.items():
            if len(periods) != len(set(periods)):
                clashes.append({"type": "room_clash", "resource_id": rid})
        for fid, periods in facs.items():
            if len(periods) != len(set(periods)):
                clashes.append({"type": "facilitator_clash", "resource_id": fid})
    return {"date": date, "clashes": clashes}


# ── CADETS (sensitive; sqn_general blocked) ──
@router.get("/cadets")
def list_cadets(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    if p.role == "sqn_general":
        raise HTTPException(403, detail={"error": "forbidden"})
    sq_id = _active_squadron(p)
    rows = db.query(Cadet).filter(Cadet.squadron_id == sq_id, Cadet.is_archived == False).all()  # noqa: E712
    # support_notes (sensitive) only for admins
    can_sensitive = p.role in ("sqn_admin", "wing_admin", "national_admin", "system_admin")
    out = []
    for c in rows:
        d = {"cadet_id": c.id, "service_number": c.service_number, "rank": c.rank,
             "first_name": c.first_name, "last_name": c.last_name, "phase": c.phase,
             "attendance_percentage": c.attendance_percentage,
             "sitrep_part_1_status": c.sitrep_part_1_status, "support_flag": c.support_flag}
        if can_sensitive:
            d["support_notes"] = c.support_notes
        out.append(d)
    if any(c.support_notes for c in rows) and can_sensitive:
        audit(db, p, object_type="cadet", object_id=sq_id, action="view_sensitive")
    return out


@router.get("/cadets/risk")
def cadet_risk(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    if p.role == "sqn_general":
        raise HTTPException(403, detail={"error": "forbidden"})
    sq_id = _active_squadron(p)
    rows = db.query(Cadet).filter(Cadet.squadron_id == sq_id, Cadet.is_archived == False).all()  # noqa: E712
    flags = []
    for c in rows:
        reasons = []
        if (c.attendance_percentage or 100) < 75:
            reasons.append("Attendance below 75%")
        if c.recent_attendance_trend == "declining":
            reasons.append("Attendance declining")
        if c.sitrep_part_1_status == "pending":
            reasons.append("SITREP Part 1 missing")
        if reasons:
            flags.append({"cadet": f"{c.rank} {c.first_name} {c.last_name}", "reasons": reasons})
    return flags


# ── PARADE NIGHT BUILDER ────────────────────────────────────────────────────
@router.get("/parade-nights/{pnid}/builder")
def parade_night_builder(pnid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    """Return timing template blocks + sessions grid (cadet_group × period_number) for Night Builder."""
    pn = db.get(ParadeNight, pnid)
    if not pn:
        raise HTTPException(404, detail={"error": "not_found"})
    require_can_view_squadron(p, pn.squadron_id, pn.wing_id)

    # Timing template blocks
    timing_blocks: list[dict] = []
    session_count = pn.session_count or 3
    tmpl = None
    if pn.timing_template_id:
        tmpl = db.get(TimingTemplate, pn.timing_template_id)
    if not tmpl:
        tmpl = _effective_template(db, pn.squadron_id, pn.date)
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

    sessions = db.query(Session).filter(
        Session.parade_night_id == pnid,
        Session.is_archived == False,  # noqa: E712
    ).order_by(Session.period_number, Session.cadet_group).all()

    return {
        "parade_night_id": pnid,
        "parade_date": pn.date,
        "parade_type": pn.parade_type,
        "squadron_id": pn.squadron_id,
        "session_count": session_count,
        "timing_template_id": tmpl.id if tmpl else None,
        "timing_blocks": timing_blocks,
        "cadet_groups": ["orientation", "initial", "junior", "intermediate", "senior"],
        "sessions": [_sess_dict(s) for s in sessions],
    }


# ── PARADE NIGHT DELETE ──────────────────────────────────────────────────────
@router.delete("/parade-nights/{pnid}")
def delete_parade(pnid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    pn = db.get(ParadeNight, pnid)
    if not pn:
        raise HTTPException(404, detail={"error": "not_found"})
    require_can_write_squadron(p, pn.squadron_id, pn.wing_id)
    pn.is_archived = True
    pn.archived_at = utcnow()
    db.query(Session).filter(Session.parade_night_id == pn.id).update(
        {"is_archived": True}, synchronize_session=False)
    db.commit()
    audit(db, p, object_type="parade_night", object_id=pn.id, action="archive")
    return {"ok": True}


# ── FACILITATOR DELETE ───────────────────────────────────────────────────────
@router.delete("/facilitators/{fid}")
def delete_fac(fid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    f = db.get(Facilitator, fid)
    if not f:
        raise HTTPException(404, detail={"error": "not_found"})
    require_can_write_squadron(p, f.squadron_id, f.wing_id)
    f.is_archived = True
    f.archived_at = utcnow()
    db.commit()
    audit(db, p, object_type="facilitator", object_id=f.id, action="archive")
    return {"ok": True}


# ── TRAINING AREA WRITE ──────────────────────────────────────────────────────
class TrainingAreaIn(BaseModel):
    name: str
    type: str | None = None
    capacity: int | None = None
    indoor_outdoor: str | None = None
    notes: str | None = None


class TrainingAreaUpdateIn(BaseModel):
    name: str | None = None
    type: str | None = None
    capacity: int | None = None
    indoor_outdoor: str | None = None
    notes: str | None = None


_WRITE_BLOCKED = ("sqn_general", "wing_viewer", "national_viewer", "auditor")


@router.post("/training-areas")
def create_room(body: TrainingAreaIn, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    if p.role in _WRITE_BLOCKED:
        raise HTTPException(403, detail={"error": "forbidden"})
    sq_id = _active_squadron(p)
    if not sq_id:
        require_can_write_squadron(p, "none", None)
    s = db.get(Squadron, sq_id)
    if not s:
        raise HTTPException(400, detail={"error": "no_squadron_scope"})
    require_can_write_squadron(p, s.id, s.wing_id)
    r = TrainingArea(squadron_id=s.id, name=body.name, type=body.type,
                     capacity=body.capacity, indoor_outdoor=body.indoor_outdoor, notes=body.notes)
    db.add(r)
    db.commit()
    audit(db, p, object_type="training_area", object_id=r.id, action="create")
    return {"ok": True, "training_area_id": r.id}


@router.patch("/training-areas/{rid}")
def update_room(rid: str, body: TrainingAreaUpdateIn, db: DBSession = Depends(get_db),
                p: Principal = Depends(get_principal)):
    r = db.get(TrainingArea, rid)
    if not r:
        raise HTTPException(404, detail={"error": "not_found"})
    s = db.get(Squadron, r.squadron_id)
    require_can_write_squadron(p, r.squadron_id, s.wing_id if s else None)
    if body.name is not None:
        r.name = body.name
    if body.type is not None:
        r.type = body.type
    if body.capacity is not None:
        r.capacity = body.capacity
    if body.indoor_outdoor is not None:
        r.indoor_outdoor = body.indoor_outdoor
    if body.notes is not None:
        r.notes = body.notes
    db.commit()
    audit(db, p, object_type="training_area", object_id=r.id, action="update")
    return {"ok": True, "training_area_id": r.id}


@router.delete("/training-areas/{rid}")
def delete_room(rid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    r = db.get(TrainingArea, rid)
    if not r:
        raise HTTPException(404, detail={"error": "not_found"})
    s = db.get(Squadron, r.squadron_id)
    require_can_write_squadron(p, r.squadron_id, s.wing_id if s else None)
    r.is_archived = True
    r.archived_at = utcnow()
    db.commit()
    audit(db, p, object_type="training_area", object_id=r.id, action="archive")
    return {"ok": True}


# ── EQUIPMENT WRITE ──────────────────────────────────────────────────────────
class EquipIn(BaseModel):
    name: str
    type: str | None = None
    quantity: int = 1
    notes: str | None = None


class EquipUpdateIn(BaseModel):
    name: str | None = None
    type: str | None = None
    quantity: int | None = None
    notes: str | None = None


@router.post("/equipment")
def create_equip(body: EquipIn, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    if p.role in _WRITE_BLOCKED:
        raise HTTPException(403, detail={"error": "forbidden"})
    sq_id = _active_squadron(p)
    if not sq_id:
        require_can_write_squadron(p, "none", None)
    s = db.get(Squadron, sq_id)
    if not s:
        raise HTTPException(400, detail={"error": "no_squadron_scope"})
    require_can_write_squadron(p, s.id, s.wing_id)
    e = Equipment(squadron_id=s.id, name=body.name, type=body.type,
                  quantity=body.quantity, available_quantity=body.quantity, notes=body.notes)
    db.add(e)
    db.commit()
    audit(db, p, object_type="equipment", object_id=e.id, action="create")
    return {"ok": True, "equipment_id": e.id}


@router.patch("/equipment/{eid}")
def update_equip(eid: str, body: EquipUpdateIn, db: DBSession = Depends(get_db),
                 p: Principal = Depends(get_principal)):
    e = db.get(Equipment, eid)
    if not e:
        raise HTTPException(404, detail={"error": "not_found"})
    s = db.get(Squadron, e.squadron_id)
    require_can_write_squadron(p, e.squadron_id, s.wing_id if s else None)
    if body.name is not None:
        e.name = body.name
    if body.type is not None:
        e.type = body.type
    if body.quantity is not None:
        e.quantity = body.quantity
        e.available_quantity = body.quantity
    if body.notes is not None:
        e.notes = body.notes
    db.commit()
    audit(db, p, object_type="equipment", object_id=e.id, action="update")
    return {"ok": True, "equipment_id": e.id}


@router.delete("/equipment/{eid}")
def delete_equip(eid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    e = db.get(Equipment, eid)
    if not e:
        raise HTTPException(404, detail={"error": "not_found"})
    s = db.get(Squadron, e.squadron_id)
    require_can_write_squadron(p, e.squadron_id, s.wing_id if s else None)
    e.is_archived = True
    e.archived_at = utcnow()
    db.commit()
    audit(db, p, object_type="equipment", object_id=e.id, action="archive")
    return {"ok": True}


# ── ACTIVITIES CRUD ──────────────────────────────────────────────────────────
class ActivityIn(BaseModel):
    activity_name: str
    activity_type: str | None = None
    date_start: str
    date_end: str | None = None
    time_start: str | None = None
    time_end: str | None = None
    location: str | None = None
    audience: list[str] | None = None
    notes: str | None = None


class ActivityUpdateIn(BaseModel):
    activity_name: str | None = None
    activity_type: str | None = None
    date_start: str | None = None
    date_end: str | None = None
    time_start: str | None = None
    time_end: str | None = None
    location: str | None = None
    audience: list[str] | None = None
    notes: str | None = None
    workflow_status: str | None = None
    cea_seq_nr: str | None = None


def _activity_out(a: Activity) -> dict:
    return {
        "activity_id": a.id, "activity_name": a.activity_name,
        "activity_type": a.activity_type, "date_start": a.date_start,
        "date_end": a.date_end, "time_start": a.time_start, "time_end": a.time_end,
        "location": a.location, "audience": a.audience or [],
        "notes": a.notes, "workflow_status": a.workflow_status,
        "cea_seq_nr": a.cea_seq_nr,
    }


@router.get("/activities")
def list_activities(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    sq_id = _active_squadron(p)
    rows = db.query(Activity).filter(Activity.squadron_id == sq_id,
                                     Activity.is_archived == False).order_by(Activity.date_start).all()  # noqa: E712
    return [_activity_out(a) for a in rows]


@router.post("/activities")
def create_activity(body: ActivityIn, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    if p.role in _WRITE_BLOCKED:
        raise HTTPException(403, detail={"error": "forbidden"})
    sq_id = _active_squadron(p)
    if not sq_id:
        require_can_write_squadron(p, "none", None)
    s = db.get(Squadron, sq_id)
    if not s:
        raise HTTPException(400, detail={"error": "no_squadron_scope"})
    require_can_write_squadron(p, s.id, s.wing_id)
    a = Activity(squadron_id=s.id, wing_id=s.wing_id, activity_name=body.activity_name,
                 activity_type=body.activity_type, date_start=body.date_start,
                 date_end=body.date_end, time_start=body.time_start, time_end=body.time_end,
                 location=body.location, audience=body.audience, notes=body.notes)
    db.add(a)
    db.commit()
    audit(db, p, object_type="activity", object_id=a.id, action="create")
    return {"ok": True, "activity_id": a.id}


@router.patch("/activities/{aid}")
def update_activity(aid: str, body: ActivityUpdateIn, db: DBSession = Depends(get_db),
                    p: Principal = Depends(get_principal)):
    a = db.get(Activity, aid)
    if not a:
        raise HTTPException(404, detail={"error": "not_found"})
    s = db.get(Squadron, a.squadron_id) if a.squadron_id else None
    require_can_write_squadron(p, a.squadron_id, s.wing_id if s else None)
    if body.activity_name is not None:
        a.activity_name = body.activity_name
    if body.activity_type is not None:
        a.activity_type = body.activity_type
    if body.date_start is not None:
        a.date_start = body.date_start
    if body.date_end is not None:
        a.date_end = body.date_end
    if body.time_start is not None:
        a.time_start = body.time_start
    if body.time_end is not None:
        a.time_end = body.time_end
    if body.location is not None:
        a.location = body.location
    if body.audience is not None:
        a.audience = body.audience
    if body.notes is not None:
        a.notes = body.notes
    if body.workflow_status is not None:
        a.workflow_status = body.workflow_status
    if body.cea_seq_nr is not None:
        a.cea_seq_nr = body.cea_seq_nr
    db.commit()
    audit(db, p, object_type="activity", object_id=a.id, action="update")
    return {"ok": True, "activity_id": a.id}


@router.delete("/activities/{aid}")
def delete_activity(aid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    a = db.get(Activity, aid)
    if not a:
        raise HTTPException(404, detail={"error": "not_found"})
    s = db.get(Squadron, a.squadron_id) if a.squadron_id else None
    require_can_write_squadron(p, a.squadron_id, s.wing_id if s else None)
    a.is_archived = True
    a.archived_at = utcnow()
    db.commit()
    audit(db, p, object_type="activity", object_id=a.id, action="archive")
    return {"ok": True}


# ── CURRICULUM ELEMENTS ──────────────────────────────────────────────────────

class ElementIn(BaseModel):
    name: str           # short code, e.g. "Air_Space"
    display_name: str   # human label, e.g. "Air & Space"
    scope_level: str = "national"
    wing_id: str | None = None
    squadron_id: str | None = None


def _can_create_element(p: Principal, scope_level: str,
                        wing_id: str | None = None, squadron_id: str | None = None) -> None:
    """Raise 403 if the actor cannot create an element at the requested scope."""
    if p.role in _WRITE_BLOCKED:
        raise HTTPException(403, detail={"error": "forbidden",
                                          "message": "Viewers and auditors cannot create elements."})
    if scope_level not in ELEMENT_SCOPE_LEVELS:
        raise HTTPException(400, detail={"error": "invalid_scope",
                                          "message": f"scope_level must be one of: {sorted(ELEMENT_SCOPE_LEVELS)}"})
    if scope_level == "system":
        if p.role != "system_admin":
            raise HTTPException(403, detail={"error": "forbidden",
                                              "message": "Only system_admin can create system-scope elements."})
    elif scope_level == "national":
        if p.role not in _NAT_ADMIN_ROLES:
            raise HTTPException(403, detail={"error": "forbidden",
                                              "message": "Only national_admin or system_admin can create national elements."})
    elif scope_level == "wing":
        if p.role not in _WING_WRITE_ROLES:
            raise HTTPException(403, detail={"error": "forbidden",
                                              "message": "Only wing_admin or above can create wing elements."})
        effective_wing = wing_id or p.wing_id
        if p.role == "wing_admin" and effective_wing != p.wing_id:
            raise HTTPException(403, detail={"error": "out_of_scope",
                                              "message": "Wing admin can only create elements for their own wing."})
    elif scope_level == "squadron":
        if p.role not in {*_WING_WRITE_ROLES, "sqn_admin"}:
            raise HTTPException(403, detail={"error": "forbidden"})
        if p.role == "sqn_admin" and squadron_id and squadron_id != p.squadron_id:
            raise HTTPException(403, detail={"error": "out_of_scope",
                                              "message": "Squadron admin can only create elements for their own squadron."})


def _visible_elements(db: DBSession, p: Principal) -> list[CurriculumElement]:
    """Return elements visible to this principal (scoped by role)."""
    from sqlalchemy import or_
    conditions = [
        CurriculumElement.scope_level == "national",
        CurriculumElement.scope_level == "system",
    ]
    wing_id = p.acting_wing_id or p.wing_id
    sq_id = p.acting_squadron_id or p.squadron_id
    if wing_id:
        conditions.append(
            (CurriculumElement.scope_level == "wing") & (CurriculumElement.wing_id == wing_id))
    elif p.role in _NAT_ADMIN_ROLES:
        conditions.append(CurriculumElement.scope_level == "wing")
    if sq_id:
        conditions.append(
            (CurriculumElement.scope_level == "squadron") & (CurriculumElement.squadron_id == sq_id))
    elif p.role == "wing_admin":
        pass  # wing admin: no sqn-scope elements unless proxied
    elif p.role in _NAT_ADMIN_ROLES:
        conditions.append(CurriculumElement.scope_level == "squadron")
    return db.query(CurriculumElement).filter(
        CurriculumElement.is_archived == False,  # noqa: E712
        CurriculumElement.active_status == True,  # noqa: E712
        or_(*conditions),
    ).order_by(CurriculumElement.scope_level, CurriculumElement.display_name).all()


@router.get("/curriculum/elements")
def list_elements(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    """Return all curriculum elements visible to the caller's scope."""
    return [{"element_id": e.id, "name": e.name, "display_name": e.display_name,
             "scope_level": e.scope_level, "wing_id": e.wing_id, "squadron_id": e.squadron_id}
            for e in _visible_elements(db, p)]


@router.post("/curriculum/elements")
def create_element(body: ElementIn, db: DBSession = Depends(get_db),
                   p: Principal = Depends(get_principal)):
    """Create a curriculum element at the requested scope."""
    scope = body.scope_level
    _can_create_element(p, scope, body.wing_id, body.squadron_id)
    name = (body.name or "").strip().replace(" ", "_")
    if not name:
        raise HTTPException(400, detail={"error": "name_required"})
    wing_id = body.wing_id or (p.wing_id if scope in ("wing", "squadron") else None)
    sq_id = body.squadron_id or (p.squadron_id if scope == "squadron" else None)
    # Idempotent: return existing element if same name + scope
    existing = db.query(CurriculumElement).filter(
        CurriculumElement.name == name,
        CurriculumElement.scope_level == scope,
        CurriculumElement.wing_id == wing_id,
        CurriculumElement.squadron_id == sq_id,
        CurriculumElement.is_archived == False,  # noqa: E712
    ).first()
    if existing:
        return {"ok": True, "element_id": existing.id, "name": existing.name,
                "display_name": existing.display_name, "scope_level": existing.scope_level, "existed": True}
    el = CurriculumElement(
        name=name, display_name=body.display_name or name,
        scope_level=scope, wing_id=wing_id, squadron_id=sq_id,
        active_status=True, created_by=p.user_id)
    db.add(el)
    db.commit()
    audit(db, p, object_type="curriculum_element", object_id=el.id, action="create",
          new={"name": name, "scope": scope})
    return {"ok": True, "element_id": el.id, "name": el.name,
            "display_name": el.display_name, "scope_level": el.scope_level, "existed": False}


@router.post("/curriculum/elements/{eid}/archive")
def archive_element(eid: str, db: DBSession = Depends(get_db),
                    p: Principal = Depends(get_principal)):
    el = db.get(CurriculumElement, eid)
    if not el:
        raise HTTPException(404, detail={"error": "not_found"})
    # Only the owning scope or above can archive
    _can_create_element(p, el.scope_level, el.wing_id, el.squadron_id)
    el.is_archived = True
    el.archived_at = utcnow()
    db.commit()
    audit(db, p, object_type="curriculum_element", object_id=el.id, action="archive")
    return {"ok": True}


def _upsert_element(db: DBSession, name: str, scope: str = "national",
                    wing_id: str | None = None, sq_id: str | None = None) -> str:
    """Find or create an element by name+scope; return its id. Used by workbook import."""
    name = (name or "").strip().replace(" ", "_")
    if not name:
        return None
    existing = db.query(CurriculumElement).filter(
        CurriculumElement.name == name,
        CurriculumElement.scope_level == scope,
        CurriculumElement.wing_id == wing_id,
        CurriculumElement.squadron_id == sq_id,
        CurriculumElement.is_archived == False,  # noqa: E712
    ).first()
    if existing:
        return existing.id
    el = CurriculumElement(name=name, display_name=name.replace("_", " "),
                            scope_level=scope, wing_id=wing_id, squadron_id=sq_id,
                            active_status=True)
    db.add(el)
    db.flush()  # get id without full commit
    return el.id


# ── CURRICULUM WRITE (SQN-owned items only) ──────────────────────────────────
class CurriculumIn(BaseModel):
    code: str
    title: str
    identifier: str | None = None  # globally unique mission key, e.g. "ORI-M01-01(2)"
    part_number: int = 1
    phase: str = "B. Initial"
    element: str | None = None
    recommended_term: str | None = None
    duration_minutes: int = 60
    part_count: int = 1
    instructor_suitability: str | None = None
    learning_hub_url: str | None = None
    wing_id: str | None = None  # NAT admins pass this for wing-owned curriculum


class CurriculumUpdateIn(BaseModel):
    title: str | None = None
    identifier: str | None = None
    part_number: int | None = None
    phase: str | None = None
    element: str | None = None
    recommended_term: str | None = None
    duration_minutes: int | None = None
    part_count: int | None = None
    instructor_suitability: str | None = None
    learning_hub_url: str | None = None


class CurriculumImportItem(BaseModel):
    identifier: str | None = None    # primary unique key
    code: str                         # Module_Code (may repeat across parts)
    part_number: int = 1
    title: str
    phase: str = "B. Initial"
    element: str | None = None
    duration_minutes: int = 60
    part_count: int = 1
    instructor_suitability: str | None = None
    learning_hub_url: str | None = None
    recommended_term: str | None = None
    # Scheduling fields — used to link to existing parade night sessions
    scheduled_date: str | None = None  # ISO date string e.g. "2026-02-13"
    session_number: int | None = None  # period number (1, 2, 3)
    facilitator_name: str | None = None
    location: str | None = None
    room: str | None = None


class CurriculumImportIn(BaseModel):
    items: List[CurriculumImportItem]
    squadron_id: str | None = None  # if provided, link scheduled items to this sqn
    owning_level: str = "national"  # national | wing | squadron


_NAT_ADMIN_ROLES = frozenset({"national_admin", "system_admin"})
_WING_WRITE_ROLES = frozenset({"wing_admin", "national_admin", "system_admin"})


def _find_existing_curriculum(db: DBSession, body: CurriculumIn,
                              owning_level: str,
                              wing_id: str | None = None,
                              squadron_id: str | None = None) -> CurriculumItem | None:
    """Find an existing (non-archived) curriculum item by identifier or (code, part_number).

    Multiple items can share the same code (Module_Code) for different parts, so
    code alone is never a uniqueness criterion. The check hierarchy is:
    1. If identifier is set: match by identifier + owning scope.
    2. Else: match by (code, part_number) + owning scope.
    """
    q = db.query(CurriculumItem).filter(
        CurriculumItem.owning_level == owning_level,
        CurriculumItem.is_archived == False)  # noqa: E712
    if owning_level == "wing":
        q = q.filter(CurriculumItem.wing_id == wing_id)
    elif owning_level == "squadron":
        q = q.filter(CurriculumItem.squadron_id == squadron_id)

    if body.identifier:
        return q.filter(CurriculumItem.identifier == body.identifier).first()
    # Fallback: (code, part_number) — allows same code with different parts
    return q.filter(
        CurriculumItem.code == body.code,
        CurriculumItem.part_number == body.part_number,
    ).first()


@router.post("/curriculum")
def create_curriculum(body: CurriculumIn, db: DBSession = Depends(get_db),
                      p: Principal = Depends(get_principal)):
    """Create a squadron-owned curriculum item (owning_level=squadron)."""
    if p.role in _WRITE_BLOCKED:
        raise HTTPException(403, detail={"error": "forbidden"})
    sq_id = _active_squadron(p)
    if not sq_id:
        raise HTTPException(400, detail={"error": "no_squadron_scope"})
    s = db.get(Squadron, sq_id)
    if not s:
        raise HTTPException(400, detail={"error": "no_squadron_scope"})
    require_can_write_squadron(p, s.id, s.wing_id)
    exists = _find_existing_curriculum(db, body, "squadron", squadron_id=sq_id)
    if exists:
        raise HTTPException(409, detail={
            "error": "already_exists",
            "message": f"Curriculum item '{body.identifier or body.code}' already exists.",
            "curriculum_id": exists.id,
        })
    ci = CurriculumItem(
        squadron_id=s.id, wing_id=s.wing_id, owning_level="squadron",
        identifier=body.identifier, code=body.code, part_number=body.part_number,
        title=body.title, phase=body.phase, element=body.element,
        recommended_term=body.recommended_term, duration_minutes=body.duration_minutes,
        part_count=body.part_count, instructor_suitability=body.instructor_suitability,
        learning_hub_url=body.learning_hub_url, core_status="additional")
    db.add(ci)
    db.commit()
    audit(db, p, object_type="curriculum_item", object_id=ci.id, action="create",
          new={"owning_level": "squadron"})
    return {"ok": True, "curriculum_id": ci.id}


@router.post("/curriculum/wing")
def create_wing_curriculum(body: CurriculumIn, db: DBSession = Depends(get_db),
                           p: Principal = Depends(get_principal)):
    """Create a Wing-owned curriculum item visible to all squadrons under that Wing."""
    if p.role not in _WING_WRITE_ROLES:
        raise HTTPException(403, detail={"error": "forbidden",
                                          "message": "Only Wing or NAT HQ admin can create Wing curriculum."})
    wing_id = body.wing_id or p.acting_wing_id or p.wing_id
    if not wing_id:
        raise HTTPException(400, detail={"error": "no_wing_scope",
                                          "message": "Provide wing_id in the request body or enter proxy mode first."})
    from ..models import Wing as WingModel
    w = db.get(WingModel, wing_id)
    if not w or w.is_archived:
        raise HTTPException(404, detail={"error": "wing_not_found"})
    exists = _find_existing_curriculum(db, body, "wing", wing_id=wing_id)
    if exists:
        raise HTTPException(409, detail={
            "error": "already_exists",
            "message": f"Curriculum item '{body.identifier or body.code}' already exists in this Wing.",
            "curriculum_id": exists.id,
        })
    ci = CurriculumItem(
        wing_id=wing_id, squadron_id=None, owning_level="wing",
        identifier=body.identifier, code=body.code, part_number=body.part_number,
        title=body.title, phase=body.phase, element=body.element,
        recommended_term=body.recommended_term, duration_minutes=body.duration_minutes,
        part_count=body.part_count, instructor_suitability=body.instructor_suitability,
        learning_hub_url=body.learning_hub_url, core_status="additional")
    db.add(ci)
    db.commit()
    audit(db, p, object_type="curriculum_item", object_id=ci.id, action="create",
          new={"owning_level": "wing", "wing_id": wing_id})
    return {"ok": True, "curriculum_id": ci.id}


@router.post("/curriculum/national")
def create_national_curriculum(body: CurriculumIn, db: DBSession = Depends(get_db),
                               p: Principal = Depends(get_principal)):
    """Create a National curriculum item visible to all Wings and Squadrons.

    Uniqueness is by identifier (if provided) or (code, part_number).
    Multiple parts of the same module share the same code but have distinct
    identifiers / part_numbers — they are NOT duplicates.
    """
    if p.role not in _NAT_ADMIN_ROLES:
        raise HTTPException(403, detail={"error": "forbidden",
                                          "message": "Only NAT HQ admin can create National curriculum."})
    exists = _find_existing_curriculum(db, body, "national")
    if exists:
        raise HTTPException(409, detail={
            "error": "already_exists",
            "message": f"Curriculum item '{body.identifier or body.code}' (part {body.part_number}) already exists.",
            "curriculum_id": exists.id,
        })
    ci = CurriculumItem(
        wing_id=None, squadron_id=None, owning_level="national",
        identifier=body.identifier, code=body.code, part_number=body.part_number,
        title=body.title, phase=body.phase, element=body.element,
        recommended_term=body.recommended_term, duration_minutes=body.duration_minutes,
        part_count=body.part_count, instructor_suitability=body.instructor_suitability,
        learning_hub_url=body.learning_hub_url, core_status="core")
    db.add(ci)
    db.commit()
    audit(db, p, object_type="curriculum_item", object_id=ci.id, action="create",
          new={"owning_level": "national"})
    return {"ok": True, "curriculum_id": ci.id}


@router.patch("/curriculum/{cid}")
def update_curriculum(cid: str, body: CurriculumUpdateIn, db: DBSession = Depends(get_db),
                      p: Principal = Depends(get_principal)):
    ci = db.get(CurriculumItem, cid)
    if not ci:
        raise HTTPException(404, detail={"error": "not_found"})
    # Ownership check by level
    if ci.owning_level == "national":
        if p.role not in _NAT_ADMIN_ROLES:
            raise HTTPException(403, detail={"error": "cannot_edit_national_curriculum"})
    elif ci.owning_level == "wing":
        if p.role not in _WING_WRITE_ROLES:
            raise HTTPException(403, detail={"error": "cannot_edit_wing_curriculum"})
        # NAT admins may edit any wing's curriculum; wing admins are scoped to their own wing
        if p.role not in _NAT_ADMIN_ROLES:
            actor_wing = p.acting_wing_id or p.wing_id
            if ci.wing_id != actor_wing:
                raise HTTPException(403, detail={"error": "out_of_scope"})
    else:
        sq_id = _active_squadron(p)
        if ci.squadron_id != sq_id:
            raise HTTPException(403, detail={"error": "forbidden"})
    if body.title is not None:
        ci.title = body.title
    if body.phase is not None:
        ci.phase = body.phase
    if body.element is not None:
        ci.element = body.element
    if body.recommended_term is not None:
        ci.recommended_term = body.recommended_term
    if body.duration_minutes is not None:
        ci.duration_minutes = body.duration_minutes
    if body.learning_hub_url is not None:
        ci.learning_hub_url = body.learning_hub_url
    db.commit()
    audit(db, p, object_type="curriculum_item", object_id=ci.id, action="update")
    return {"ok": True}


@router.delete("/curriculum/{cid}")
def delete_curriculum(cid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    ci = db.get(CurriculumItem, cid)
    if not ci:
        raise HTTPException(404, detail={"error": "not_found"})
    if ci.owning_level == "national":
        if p.role not in _NAT_ADMIN_ROLES:
            raise HTTPException(403, detail={"error": "cannot_delete_national_curriculum"})
    elif ci.owning_level == "wing":
        if p.role not in _WING_WRITE_ROLES:
            raise HTTPException(403, detail={"error": "cannot_delete_wing_curriculum"})
        if p.role not in _NAT_ADMIN_ROLES:
            actor_wing = p.acting_wing_id or p.wing_id
            if ci.wing_id != actor_wing:
                raise HTTPException(403, detail={"error": "out_of_scope"})
    else:
        sq_id = _active_squadron(p)
        if ci.squadron_id != sq_id:
            raise HTTPException(403, detail={"error": "forbidden"})
    ci.is_archived = True
    ci.archived_at = utcnow()
    db.commit()
    audit(db, p, object_type="curriculum_item", object_id=ci.id, action="archive")
    return {"ok": True}


# ── CURRICULUM BULK IMPORT ────────────────────────────────────────────────────

@router.post("/curriculum/import")
def import_curriculum(body: CurriculumImportIn, db: DBSession = Depends(get_db),
                      p: Principal = Depends(get_principal)):
    """Bulk upsert curriculum items.

    Uniqueness key: identifier (if set), else (code, part_number).
    Multiple rows may share the same code (Module_Code) for different parts —
    this is NOT a duplicate. A duplicate is a row whose identifier (or
    code+part_number combo) already exists in the database.

    For each item:
    - If not found: create.
    - If found and any field changed: update.
    - If found and identical: skip.

    Never raises 409 — returns per-item status in the response.

    If squadron_id is supplied and a row has a scheduled_date + session_number,
    the endpoint attempts to link the curriculum item to the corresponding
    parade-night session for that squadron.
    """
    if p.role not in _NAT_ADMIN_ROLES:
        raise HTTPException(403, detail={
            "error": "forbidden",
            "message": "Only national_admin or system_admin can bulk-import curriculum.",
        })

    owning_level = body.owning_level if body.owning_level in {"national", "wing", "squadron"} else "national"
    sqn_id = body.squadron_id

    created = updated = skipped = failed = 0
    results = []

    # Pre-fetch facilitators + training areas for schedule linking
    fac_by_name: dict[str, str] = {}  # display_name -> id
    room_by_name: dict[str, str] = {}  # name -> id
    if sqn_id:
        for f in db.query(Facilitator).filter(Facilitator.squadron_id == sqn_id).all():
            key = (f.display_name or "").strip().lower()
            if key:
                fac_by_name[key] = f.id
        for r in db.query(TrainingArea).filter(TrainingArea.squadron_id == sqn_id).all():
            key = (r.name or "").strip().lower()
            if key:
                room_by_name[key] = r.id

    for item in body.items:
        try:
            # Locate existing item
            q = db.query(CurriculumItem).filter(
                CurriculumItem.owning_level == owning_level,
                CurriculumItem.is_archived == False)  # noqa: E712
            if owning_level == "squadron":
                q = q.filter(CurriculumItem.squadron_id == sqn_id)

            existing: CurriculumItem | None = None
            if item.identifier:
                existing = q.filter(CurriculumItem.identifier == item.identifier).first()
            if existing is None:
                existing = q.filter(
                    CurriculumItem.code == item.code,
                    CurriculumItem.part_number == item.part_number,
                ).first()

            if existing is None:
                # Ensure the element exists in the managed table (idempotent)
                if item.element:
                    _upsert_element(db, item.element, scope="national")
                # CREATE
                ci = CurriculumItem(
                    owning_level=owning_level,
                    squadron_id=sqn_id if owning_level == "squadron" else None,
                    identifier=item.identifier,
                    code=item.code,
                    part_number=item.part_number,
                    title=item.title,
                    phase=item.phase or "B. Initial",
                    element=item.element,
                    duration_minutes=item.duration_minutes or 60,
                    part_count=item.part_count or 1,
                    instructor_suitability=item.instructor_suitability,
                    learning_hub_url=item.learning_hub_url,
                    recommended_term=item.recommended_term,
                    core_status="core" if owning_level == "national" else "additional",
                    active_status=True,
                )
                db.add(ci)
                db.flush()
                created += 1
                results.append({"identifier": item.identifier or item.code, "status": "created"})
            else:
                ci = existing
                # Check if any field changed
                changed = False
                for field, val in [
                    ("title", item.title),
                    ("phase", item.phase),
                    ("element", item.element),
                    ("duration_minutes", item.duration_minutes),
                    ("part_count", item.part_count),
                    ("instructor_suitability", item.instructor_suitability),
                    ("learning_hub_url", item.learning_hub_url),
                    ("recommended_term", item.recommended_term),
                    ("identifier", item.identifier),
                    ("part_number", item.part_number),
                ]:
                    if val is not None and getattr(ci, field) != val:
                        setattr(ci, field, val)
                        changed = True
                if changed:
                    updated += 1
                    results.append({"identifier": item.identifier or item.code, "status": "updated"})
                else:
                    skipped += 1
                    results.append({"identifier": item.identifier or item.code, "status": "skipped"})

            # Schedule linking: connect to parade night session if date provided
            if sqn_id and item.scheduled_date and item.session_number:
                _link_session(db, ci, sqn_id, item, fac_by_name, room_by_name)

        except Exception as exc:
            failed += 1
            results.append({
                "identifier": item.identifier or item.code,
                "status": "failed",
                "error": str(exc),
            })

    db.commit()

    summary = {"created": created, "updated": updated, "skipped": skipped, "failed": failed,
               "total": len(body.items)}
    audit(db, p, object_type="curriculum_item", object_id="import", action="bulk_import",
          new=summary)

    return {"ok": True, **summary, "results": results}


def _link_session(db: DBSession, ci: CurriculumItem, sqn_id: str,
                  item: CurriculumImportItem,
                  fac_by_name: dict, room_by_name: dict) -> None:
    """Try to find the parade-night session for this date/period and assign the curriculum item."""
    pn = db.query(ParadeNight).filter(
        ParadeNight.squadron_id == sqn_id,
        ParadeNight.date == item.scheduled_date,
        ParadeNight.is_archived == False,  # noqa: E712
    ).first()
    if not pn:
        return

    sess = db.query(Session).filter(
        Session.parade_night_id == pn.id,
        Session.period_number == item.session_number,
        Session.is_archived == False,  # noqa: E712
    ).first()
    if not sess:
        return

    # Only update if not already assigned to a different curriculum item
    if sess.curriculum_item_id and sess.curriculum_item_id != ci.id:
        return

    fac_id = None
    if item.facilitator_name:
        fac_id = fac_by_name.get(item.facilitator_name.strip().lower())

    room_id = None
    if item.room:
        room_id = room_by_name.get(item.room.strip().lower())

    sess.curriculum_item_id = ci.id
    sess.curriculum_code_at_time = ci.code
    sess.curriculum_title_at_time = ci.title
    sess.phase_at_time = ci.phase
    sess.element_at_time = ci.element
    if fac_id:
        sess.facilitator_id = fac_id
        sess.facilitator_display_name_at_time = item.facilitator_name
    elif item.facilitator_name:
        sess.facilitator_display_name_at_time = item.facilitator_name
    if room_id:
        sess.training_area_id = room_id
        sess.training_area_name_at_time = item.room
    elif item.room:
        sess.training_area_name_at_time = item.room


@router.post("/curriculum/import-xlsm")
async def import_curriculum_xlsm(
    file: UploadFile = File(...),
    squadron_id: str | None = None,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Accept an .xlsm workbook upload and import curriculum from 'zz - Program backend' sheet.

    Header row: 4. Unique key: Identifier (col 4), fallback (Module_Code, Part).
    Non-curriculum rows (missing Module_Code or Title) are silently skipped.
    """
    if p.role not in _NAT_ADMIN_ROLES:
        raise HTTPException(403, detail={"error": "forbidden",
                                         "message": "Only national_admin or system_admin can import curriculum."})

    content = await file.read()
    try:
        import io
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise HTTPException(400, detail={"error": "invalid_file",
                                          "message": f"Could not open workbook: {exc}"})

    sheet_name = "zz - Program backend"
    if sheet_name not in wb.sheetnames:
        raise HTTPException(400, detail={
            "error": "sheet_not_found",
            "message": f"Sheet '{sheet_name}' not found. Available: {wb.sheetnames}",
        })

    ws = wb[sheet_name]
    items = _parse_program_backend_sheet(ws)

    body = CurriculumImportIn(items=items, squadron_id=squadron_id, owning_level="national")
    return import_curriculum(body, db=db, p=p)


_VALID_PROGRAMS = frozenset({
    "A. Orientation", "B. Initial", "C. Junior", "D. Intermediate",
    "E. Senior", "I. Bronze", "J. Silver", "K. Gold", "M. CDT Skills",
})


def _parse_program_backend_sheet(ws) -> list[CurriculumImportItem]:
    """Parse 'zz - Program backend' worksheet rows into CurriculumImportItem objects.

    Header row: 4. Skips rows where Module_Code or Module_Title is blank,
    and rows where Program is not a recognised curriculum program.
    """
    from datetime import datetime as dt

    hdr_row = list(ws[4])
    HDR = {cell.value: idx for idx, cell in enumerate(hdr_row) if cell.value}

    def col(row, name: str, default=None):
        idx = HDR.get(name)
        return row[idx] if idx is not None and idx < len(row) else default

    items: list[CurriculumImportItem] = []
    for row in ws.iter_rows(min_row=5, values_only=True):
        if not any(v is not None for v in row[:10]):
            continue  # blank row

        program = col(row, 'Program')
        module_code = col(row, 'Module_Code')
        title = col(row, 'Module_Title')

        # Skip non-curriculum rows (header/name rows, non-programme programs)
        if not module_code or not title:
            continue
        if program and str(program).strip() not in _VALID_PROGRAMS:
            continue

        identifier = col(row, 'Identifier')
        part = col(row, 'Part')
        duration = col(row, 'Duration_Min')
        url = col(row, 'URL')
        suggested_parts = col(row, 'Suggested_#_Parts')
        elements = col(row, 'Elements')
        instr = col(row, 'Instructor_Suitability')
        scheduled = col(row, 'Scheduled')
        session_num = col(row, 'Session')

        # Convert scheduled datetime to ISO date string
        sched_date = None
        if scheduled:
            if isinstance(scheduled, dt):
                sched_date = scheduled.strftime('%Y-%m-%d')
            else:
                sched_date = str(scheduled)[:10] if scheduled else None

        items.append(CurriculumImportItem(
            identifier=str(identifier).strip() if identifier else None,
            code=str(module_code).strip().upper(),
            part_number=int(part) if part else 1,
            title=str(title).strip(),
            phase=str(program).strip() if program else "B. Initial",
            element=str(elements).strip() if elements else None,
            duration_minutes=int(duration) if duration else 60,
            part_count=int(suggested_parts) if suggested_parts else 1,
            instructor_suitability=str(instr).strip() if instr else None,
            learning_hub_url=str(url).strip() if url else None,
            scheduled_date=sched_date,
            session_number=int(session_num) if session_num else None,
            facilitator_name=str(col(row, 'Facilitator') or '').strip() or None,
            location=str(col(row, 'Location') or '').strip() or None,
            room=str(col(row, 'Room') or '').strip() or None,
        ))

    return items


# ── CSV CURRICULUM IMPORT ─────────────────────────────────────────────────────

_CSV_CURR_COL_MAP = {
    # CSV header (lower-stripped) → CurriculumImportItem field
    "training phase": "phase",
    "phase": "phase",
    "experiential code": "code",
    "code": "code",
    "module code": "code",
    "module_code": "code",
    "title": "title",
    "module title": "title",
    "module_title": "title",
    "elements": "element",
    "element": "element",
    "foundation or extension": "core_status",
    "type": "core_status",
    "instructor suitability": "instructor_suitability",
    "instructor_suitability": "instructor_suitability",
    "timing": "duration_minutes",
    "duration": "duration_minutes",
    "duration_min": "duration_minutes",
    "location": "location",
    "learning hub link": "learning_hub_url",
    "learning hub url": "learning_hub_url",
    "url": "learning_hub_url",
}


def _parse_duration(raw: str) -> int:
    """Parse a duration string like '60', '60 min', '1 hr', '1.5 hrs' → minutes."""
    if not raw:
        return 60
    raw = raw.strip().lower()
    import re
    m = re.match(r'(\d+(?:\.\d+)?)\s*(hr|hour|h)', raw)
    if m:
        return int(float(m.group(1)) * 60)
    m = re.match(r'(\d+)', raw)
    if m:
        return int(m.group(1))
    return 60


@router.post("/curriculum/import-csv")
async def import_curriculum_csv(
    file: UploadFile = File(...),
    owning_level: str = "national",
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Import curriculum from a CSV file.

    Expected columns (case-insensitive, order-independent):
    Training Phase, Experiential Code, Title, Elements,
    Foundation or Extension, Instructor Suitability, Timing,
    Location, Learning Hub Link

    Returns the same summary as /curriculum/import.
    """
    import csv, io
    if p.role not in _NAT_ADMIN_ROLES:
        raise HTTPException(403, detail={
            "error": "forbidden",
            "message": "Only national_admin or system_admin can import curriculum.",
        })

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    items: list[CurriculumImportItem] = []
    parse_errors: list[str] = []

    for i, row in enumerate(reader, start=2):
        # Normalise headers to lower-stripped
        norm = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
        mapped: dict = {}
        for hdr, field in _CSV_CURR_COL_MAP.items():
            if hdr in norm and norm[hdr]:
                mapped[field] = norm[hdr]

        code = mapped.get("code", "").upper()
        title = mapped.get("title", "")
        if not code or not title:
            parse_errors.append(f"Row {i}: missing code or title — skipped.")
            continue

        # duration: parse "60 min", "1 hr", bare integer
        dur_raw = mapped.get("duration_minutes", "60")
        duration = _parse_duration(dur_raw)

        # core_status: "Foundation" → "core", "Extension" → "additional"
        cs_raw = mapped.get("core_status", "").lower()
        core_status = "core" if "foundation" in cs_raw or cs_raw in ("core", "f") else "additional"

        items.append(CurriculumImportItem(
            code=code,
            title=title,
            phase=mapped.get("phase", "B. Initial"),
            element=mapped.get("element") or None,
            duration_minutes=duration,
            instructor_suitability=mapped.get("instructor_suitability") or None,
            learning_hub_url=mapped.get("learning_hub_url") or None,
            location=mapped.get("location") or None,
        ))

    if not items:
        msg = "No valid rows found. " + "; ".join(parse_errors[:5]) if parse_errors else "File is empty or contains no data rows."
        raise HTTPException(400, detail={"error": "csv_parse_failed", "message": msg})

    import_body = CurriculumImportIn(items=items, owning_level=owning_level)
    result = import_curriculum(import_body, db, p)
    result["parse_errors"] = parse_errors
    return result


# ── CEA ACTIVITY IMPORT ───────────────────────────────────────────────────────

_CEA_DATE_FMTS = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d %b %Y"]


def _parse_cea_date(raw: str) -> str | None:
    """Parse a CEA export date to ISO YYYY-MM-DD."""
    if not raw:
        return None
    from datetime import datetime
    for fmt in _CEA_DATE_FMTS:
        try:
            return datetime.strptime(raw.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return raw.strip()[:10] or None


def _parse_cea_time(raw: str) -> str | None:
    """Normalise a time string to HH:MM:SS (8 chars max)."""
    if not raw:
        return None
    raw = raw.strip()
    # Accept HH:MM, HH:MM:SS, H:MM
    parts = raw.split(":")
    if len(parts) >= 2:
        try:
            hh = int(parts[0])
            mm = int(parts[1])
            return f"{hh:02d}:{mm:02d}"
        except ValueError:
            pass
    return raw[:8] or None


@router.post("/activities/import-cea")
async def import_activities_cea(
    file: UploadFile = File(...),
    preview: bool = False,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Import activities from a CEA export CSV.

    Expected columns (case-insensitive):
    SeqNr, Name, Start date, Start time, End date, End time,
    Unit, Location, Activity Notes

    Deduplication: if a row's SeqNr already exists in the squadron's
    activities, that row is skipped (not duplicated).

    If preview=true, returns parsed rows without writing to the database.
    Permissions: squadron_admin or higher (writes to the active squadron).
    """
    import csv, io
    if p.role in _WRITE_BLOCKED:
        raise HTTPException(403, detail={"error": "forbidden"})

    sq_id = _active_squadron(p)
    if not sq_id:
        raise HTTPException(400, detail={"error": "no_squadron_scope"})
    s = db.get(Squadron, sq_id)
    if not s:
        raise HTTPException(400, detail={"error": "no_squadron_scope"})
    if not preview:
        require_can_write_squadron(p, s.id, s.wing_id)

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    parse_errors: list[str] = []
    preview_rows: list[dict] = []
    created = skipped = failed = 0

    # Load existing seq numbers for deduplication
    existing_seq = {
        a.cea_seq_nr for a in
        db.query(Activity.cea_seq_nr).filter(
            Activity.squadron_id == sq_id,
            Activity.cea_seq_nr.isnot(None),
            Activity.is_archived == False,  # noqa: E712
        ).all()
        if a.cea_seq_nr
    }

    for i, row in enumerate(reader, start=2):
        norm = {k.strip().lower(): (v or "").strip() for k, v in row.items()}

        seq_nr = norm.get("seqnr") or norm.get("seq nr") or norm.get("seq_nr") or norm.get("seq") or ""
        name = norm.get("name") or norm.get("activity name") or norm.get("activity") or ""
        date_start_raw = norm.get("start date") or norm.get("startdate") or norm.get("start_date") or ""
        time_start_raw = norm.get("start time") or norm.get("starttime") or norm.get("start_time") or ""
        date_end_raw = norm.get("end date") or norm.get("enddate") or norm.get("end_date") or ""
        time_end_raw = norm.get("end time") or norm.get("endtime") or norm.get("end_time") or ""
        unit = norm.get("unit") or ""
        location = norm.get("location") or ""
        notes = norm.get("activity notes") or norm.get("notes") or norm.get("activity_notes") or ""

        if not name or not date_start_raw:
            parse_errors.append(f"Row {i}: missing Name or Start date — skipped.")
            continue

        date_start = _parse_cea_date(date_start_raw)
        date_end = _parse_cea_date(date_end_raw) if date_end_raw else None
        time_start = _parse_cea_time(time_start_raw) if time_start_raw else None
        time_end = _parse_cea_time(time_end_raw) if time_end_raw else None

        if not date_start:
            parse_errors.append(f"Row {i}: unrecognised date format '{date_start_raw}' — skipped.")
            continue

        row_data = {
            "cea_seq_nr": seq_nr or None,
            "activity_name": name,
            "date_start": date_start,
            "date_end": date_end,
            "time_start": time_start,
            "time_end": time_end,
            "location": location or None,
            "notes": (notes + (f"\nUnit: {unit}" if unit else "")).strip() or None,
            "activity_type": "CEA",
            "status": "duplicate" if seq_nr and seq_nr in existing_seq else "new",
        }

        if preview:
            preview_rows.append(row_data)
            continue

        if seq_nr and seq_nr in existing_seq:
            skipped += 1
            continue

        try:
            a = Activity(
                squadron_id=s.id, wing_id=s.wing_id,
                activity_name=name, activity_type="CEA",
                date_start=date_start, date_end=date_end,
                time_start=time_start, time_end=time_end,
                location=location or None,
                notes=(notes + (f"\nUnit: {unit}" if unit else "")).strip() or None,
                cea_seq_nr=seq_nr or None,
            )
            db.add(a)
            if seq_nr:
                existing_seq.add(seq_nr)
            created += 1
        except Exception as exc:
            failed += 1
            parse_errors.append(f"Row {i}: save failed — {exc}")

    if preview:
        return {"ok": True, "preview": True, "rows": preview_rows, "parse_errors": parse_errors}

    db.commit()
    audit(db, p, object_type="activity", object_id="cea_import", action="bulk_import",
          new={"created": created, "skipped": skipped, "failed": failed})

    return {
        "ok": True, "preview": False,
        "created": created, "skipped": skipped, "failed": failed,
        "total": created + skipped + failed,
        "parse_errors": parse_errors,
    }
