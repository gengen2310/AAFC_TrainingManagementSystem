"""Flexible parade-night timing templates and per-night overrides.

TimingTemplate  — squadron-scoped, effective from/to date range, ordered blocks.
TimingBlock     — one ordered slot in a template (arrival, period, break, …).
                  is_instructional_period=True → generates a schedulable session.
                  'Flight Period' block_type is a timing slot before Period 1;
                  it is NOT the same as a Flight (squadron sub-group/account scope).
ParadeNightTimingOverride — links one parade night to a specific template without
                  altering the default future template.

Scope rules mirror the rest of the system:
  - SQN admin: own squadron only (or proxied squadron for wing/nat admin).
  - Wing/National admin: must enter Proxy / Delegated Intervention to write.
  - Viewers and Auditors: read-only via GET endpoints.
"""
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from ..database import get_db, utcnow
from ..models import (TimingTemplate, TimingBlock, ParadeNightTimingOverride,
                      ParadeNight, Squadron)
from ..models.training import BLOCK_TYPES
from ..dependencies import get_principal, client_meta
from ..permissions import Principal, require_can_view_squadron, require_can_write_squadron
from ..services import audit


def _check_version(obj, client_version: int | None) -> None:
    """Raise 409 if the client's version is stale (optimistic locking)."""
    if client_version is not None and obj.version != client_version:
        raise HTTPException(409, detail={
            "error": "version_conflict",
            "current_version": obj.version,
        })

router = APIRouter(prefix="/api", tags=["timing"])

_WRITE_BLOCKED = frozenset({"sqn_general", "wing_viewer", "national_viewer", "auditor"})
_TIME_RE = re.compile(r'^([01]\d|2[0-3]):([0-5]\d)$')


# ── helpers ───────────────────────────────────────────────────────────────────

def _valid_time(t: str | None) -> bool:
    return t is None or bool(_TIME_RE.match(t))


def _calc_duration(start: str | None, end: str | None) -> int | None:
    """Compute duration in minutes from HH:MM strings; None if not computable."""
    if not start or not end:
        return None
    try:
        sh, sm = int(start[:2]), int(start[3:5])
        eh, em = int(end[:2]), int(end[3:5])
        diff = (eh * 60 + em) - (sh * 60 + sm)
        return diff if diff > 0 else None
    except Exception:
        return None


def _block_dict(b: TimingBlock) -> dict:
    return {
        "timing_block_id": b.id,
        "timing_template_id": b.timing_template_id,
        "display_order": b.display_order,
        "block_name": b.block_name,
        "block_type": b.block_type,
        "start_time": b.start_time,
        "end_time": b.end_time,
        "duration_minutes": b.duration_minutes,
        "is_instructional_period": b.is_instructional_period,
        "period_number": b.period_number,
        "is_optional": b.is_optional,
        "notes": b.notes,
    }


def _template_dict(t: TimingTemplate, include_blocks: bool = True) -> dict:
    blocks = sorted(t.blocks, key=lambda b: b.display_order)
    d = {
        "timing_template_id": t.id,
        "squadron_id": t.squadron_id,
        "name": t.name,
        "effective_from": t.effective_from,
        "effective_to": t.effective_to,
        "is_default": t.is_default,
        "active_status": t.active_status,
        "notes": t.notes,
        "instructional_period_count": sum(1 for b in blocks if b.is_instructional_period),
        "version": t.version,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }
    if include_blocks:
        d["blocks"] = [_block_dict(b) for b in blocks]
    return d


def _effective_template(db: DBSession, squadron_id: str, date: str) -> TimingTemplate | None:
    """Return the timing template effective on the given ISO date for a squadron.

    Picks the most recent template whose effective_from <= date and whose
    effective_to is None or >= date. Past parade nights that were created with
    a different template are unaffected — this only controls new lookups.
    """
    candidates = (
        db.query(TimingTemplate)
        .filter(
            TimingTemplate.squadron_id == squadron_id,
            TimingTemplate.is_archived == False,    # noqa: E712
            TimingTemplate.active_status == True,   # noqa: E712
            TimingTemplate.effective_from <= date,
        )
        .order_by(TimingTemplate.effective_from.desc())
        .all()
    )
    for t in candidates:
        if t.effective_to is None or t.effective_to >= date:
            return t
    return None


def _active_squadron(p: Principal) -> str | None:
    if p.acting_squadron_id:
        return p.acting_squadron_id
    return p.squadron_id


def _validate_block_times(blocks) -> list[str]:
    """Return a list of warning strings. Non-critical — does not block save."""
    warnings = []
    prev_end_m: int | None = None
    prev_name = ""
    for b in blocks:
        name = b.block_name if hasattr(b, "block_name") else b.get("block_name", "?")
        start = b.start_time if hasattr(b, "start_time") else b.get("start_time")
        end = b.end_time if hasattr(b, "end_time") else b.get("end_time")

        if start and not _valid_time(start):
            warnings.append(f"Block '{name}': start_time '{start}' is not a valid HH:MM time.")
        if end and not _valid_time(end):
            warnings.append(f"Block '{name}': end_time '{end}' is not a valid HH:MM time.")

        if _valid_time(start) and _valid_time(end) and start and end:
            dur = _calc_duration(start, end)
            if dur is None or dur <= 0:
                warnings.append(f"Block '{name}': end_time is not after start_time.")
            if prev_end_m is not None:
                sh, sm = int(start[:2]), int(start[3:5])
                start_m = sh * 60 + sm
                if start_m < prev_end_m:
                    warnings.append(f"Block '{name}' overlaps with previous block '{prev_name}'.")
            if end and _valid_time(end):
                eh, em = int(end[:2]), int(end[3:5])
                prev_end_m = eh * 60 + em
                prev_name = name
    return warnings


def _replace_blocks(db: DBSession, template: TimingTemplate,
                    block_data: list, created_by: str | None) -> None:
    """Delete all existing blocks for template and insert new ones from block_data."""
    db.query(TimingBlock).filter(
        TimingBlock.timing_template_id == template.id
    ).delete(synchronize_session="fetch")
    db.flush()

    ip_counter = 0
    for i, bd in enumerate(block_data):
        # Validate block type against new taxonomy
        if bd.block_type not in BLOCK_TYPES:
            raise HTTPException(400, detail={
                "error": "invalid_block_type",
                "message": f"block_type '{bd.block_type}' is not valid. "
                           f"Valid types: {sorted(BLOCK_TYPES)}",
            })
        # Sync is_instructional_period with block_type
        is_ip = bd.block_type == "training_period"
        pnum = bd.period_number
        if is_ip and pnum is None:
            ip_counter += 1
            pnum = ip_counter
        dur = bd.duration_minutes
        if dur is None:
            dur = _calc_duration(bd.start_time, bd.end_time)
        btype = bd.block_type
        blk = TimingBlock(
            timing_template_id=template.id,
            display_order=bd.display_order if bd.display_order else i,
            block_name=bd.block_name,
            block_type=btype,
            start_time=bd.start_time,
            end_time=bd.end_time,
            duration_minutes=dur,
            is_instructional_period=is_ip,
            period_number=pnum,
            is_optional=bd.is_optional,
            notes=bd.notes,
            created_by=created_by,
        )
        db.add(blk)
    db.flush()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class BlockIn(BaseModel):
    display_order: int = 0
    block_name: str
    block_type: str = "other"  # was "custom" — updated for new taxonomy
    start_time: str | None = None
    end_time: str | None = None
    duration_minutes: int | None = None
    is_instructional_period: bool = False  # kept for compatibility; overridden by sync logic
    period_number: int | None = None
    is_optional: bool = False
    notes: str | None = None


class TemplateIn(BaseModel):
    name: str
    effective_from: str
    effective_to: str | None = None
    is_default: bool = False
    notes: str | None = None
    blocks: list[BlockIn] = []


class TemplatePatch(BaseModel):
    name: str | None = None
    effective_from: str | None = None
    effective_to: str | None = None
    is_default: bool | None = None
    notes: str | None = None
    blocks: list[BlockIn] | None = None
    version: int | None = None


class ApplyFromIn(BaseModel):
    effective_from: str
    reason: str | None = None


class OverrideIn(BaseModel):
    timing_template_id: str
    reason: str


# ── GET /api/timing-templates ─────────────────────────────────────────────────

@router.get("/timing-templates")
def list_timing_templates(
    squadron_id: str | None = None,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    sq_id = squadron_id or _active_squadron(p)
    if not sq_id:
        raise HTTPException(400, detail={"error": "no_squadron_scope",
                                         "message": "No squadron scope — enter Proxy or DI mode."})
    s = db.get(Squadron, sq_id)
    if not s:
        raise HTTPException(404, detail={"error": "not_found"})
    require_can_view_squadron(p, s.id, s.wing_id)

    templates = (
        db.query(TimingTemplate)
        .filter(TimingTemplate.squadron_id == sq_id,
                TimingTemplate.is_archived == False)  # noqa: E712
        .order_by(TimingTemplate.effective_from.desc())
        .all()
    )
    return [_template_dict(t) for t in templates]


# ── POST /api/timing-templates ────────────────────────────────────────────────

@router.post("/timing-templates")
def create_timing_template(
    body: TemplateIn,
    request: Request,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    if p.role in _WRITE_BLOCKED:
        raise HTTPException(403, detail={"error": "forbidden"})
    sq_id = _active_squadron(p)
    if not sq_id:
        raise HTTPException(400, detail={"error": "no_squadron_scope",
                                         "message": "No squadron scope — enter Proxy or DI mode."})
    s = db.get(Squadron, sq_id)
    if not s:
        raise HTTPException(404, detail={"error": "not_found"})
    require_can_write_squadron(p, s.id, s.wing_id)

    if not body.name.strip():
        raise HTTPException(400, detail={"error": "name_required",
                                         "message": "Template name is required."})
    if not body.effective_from:
        raise HTTPException(400, detail={"error": "effective_from_required",
                                         "message": "effective_from date is required."})

    warnings = _validate_block_times(body.blocks)
    t = TimingTemplate(
        squadron_id=sq_id,
        name=body.name.strip(),
        effective_from=body.effective_from,
        effective_to=body.effective_to,
        is_default=body.is_default,
        notes=body.notes,
        created_by=p.user_id,
    )
    db.add(t)
    db.flush()
    _replace_blocks(db, t, body.blocks, p.user_id)
    db.commit()
    db.refresh(t)

    meta = client_meta(request)
    audit(db, p, object_type="timing_template", object_id=t.id, action="create",
          new={"name": t.name, "effective_from": t.effective_from,
               "instructional_blocks": sum(1 for b in body.blocks if b.is_instructional_period)},
          ip=meta["ip"], ua=meta["ua"])

    return {**_template_dict(t), "warnings": warnings}


# ── GET /api/timing-templates/effective ── (must come before {tid} route)

@router.get("/timing-templates/effective")
def get_effective_template(
    date: str,
    squadron_id: str | None = None,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Return the timing template effective for a squadron on a given date.

    Used by the frontend when creating a new parade night to show the user
    how many instructional sessions the template defines.
    """
    sq_id = squadron_id or _active_squadron(p)
    if not sq_id:
        raise HTTPException(400, detail={"error": "no_squadron_scope"})
    s = db.get(Squadron, sq_id)
    if s:
        require_can_view_squadron(p, s.id, s.wing_id)

    t = _effective_template(db, sq_id, date)
    if not t:
        return {"template": None, "instructional_period_count": None,
                "message": "No timing template is set for this date."}
    return {"template": _template_dict(t),
            "instructional_period_count": sum(1 for b in t.blocks if b.is_instructional_period)}


# ── GET /api/timing-templates/{tid} ──────────────────────────────────────────

@router.get("/timing-templates/{tid}")
def get_timing_template(
    tid: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    t = db.get(TimingTemplate, tid)
    if not t or t.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    s = db.get(Squadron, t.squadron_id)
    if s:
        require_can_view_squadron(p, s.id, s.wing_id)
    return _template_dict(t)


# ── PATCH /api/timing-templates/{tid} ────────────────────────────────────────

@router.patch("/timing-templates/{tid}")
def update_timing_template(
    tid: str,
    body: TemplatePatch,
    request: Request,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    if p.role in _WRITE_BLOCKED:
        raise HTTPException(403, detail={"error": "forbidden"})
    t = db.get(TimingTemplate, tid)
    if not t or t.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    s = db.get(Squadron, t.squadron_id)
    if s:
        require_can_write_squadron(p, s.id, s.wing_id)

    _check_version(t, body.version)
    old = {"name": t.name, "effective_from": t.effective_from}
    warnings: list[str] = []
    if body.name is not None:
        t.name = body.name.strip()
    if body.effective_from is not None:
        t.effective_from = body.effective_from
    if body.effective_to is not None:
        t.effective_to = body.effective_to
    if body.is_default is not None:
        t.is_default = body.is_default
    if body.notes is not None:
        t.notes = body.notes
    if body.blocks is not None:
        warnings = _validate_block_times(body.blocks)
        _replace_blocks(db, t, body.blocks, p.user_id)
    t.updated_by = p.user_id
    t.version += 1
    db.commit()
    db.refresh(t)

    meta = client_meta(request)
    audit(db, p, object_type="timing_template", object_id=t.id, action="edit",
          old=old, new={"name": t.name, "effective_from": t.effective_from},
          ip=meta["ip"], ua=meta["ua"])

    return {**_template_dict(t), "warnings": warnings}


# ── POST /api/timing-templates/{tid}/archive ─────────────────────────────────

@router.post("/timing-templates/{tid}/archive")
def archive_timing_template(
    tid: str,
    request: Request,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    if p.role in _WRITE_BLOCKED:
        raise HTTPException(403, detail={"error": "forbidden"})
    t = db.get(TimingTemplate, tid)
    if not t or t.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    s = db.get(Squadron, t.squadron_id)
    if s:
        require_can_write_squadron(p, s.id, s.wing_id)

    t.is_archived = True
    t.archived_at = utcnow()
    t.updated_by = p.user_id
    db.commit()

    meta = client_meta(request)
    audit(db, p, object_type="timing_template", object_id=t.id, action="archive",
          new={"name": t.name}, ip=meta["ip"], ua=meta["ua"])
    return {"ok": True}


# ── POST /api/timing-templates/{tid}/apply-from-date ─────────────────────────

@router.post("/timing-templates/{tid}/apply-from-date")
def apply_from_date(
    tid: str,
    body: ApplyFromIn,
    request: Request,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Set this template as effective from a given date.

    Closes (sets effective_to) any currently-open template for the same squadron
    that would overlap. Past parade nights are NOT changed — only new creation will
    use the new template.
    """
    if p.role in _WRITE_BLOCKED:
        raise HTTPException(403, detail={"error": "forbidden"})
    t = db.get(TimingTemplate, tid)
    if not t or t.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    s = db.get(Squadron, t.squadron_id)
    if s:
        require_can_write_squadron(p, s.id, s.wing_id)

    # Close any open templates that start before or on the new effective_from
    overlapping = (
        db.query(TimingTemplate)
        .filter(
            TimingTemplate.squadron_id == t.squadron_id,
            TimingTemplate.id != tid,
            TimingTemplate.is_archived == False,  # noqa: E712
            TimingTemplate.effective_to == None,  # noqa: E711 — only open templates
            TimingTemplate.effective_from < body.effective_from,
        )
        .all()
    )
    # Compute the day before effective_from as the close date
    from datetime import date, timedelta
    eff = datetime.strptime(body.effective_from, "%Y-%m-%d").date()
    close_date = (eff - timedelta(days=1)).isoformat()
    for other in overlapping:
        other.effective_to = close_date
        other.updated_by = p.user_id

    t.effective_from = body.effective_from
    t.effective_to = None
    t.updated_by = p.user_id
    db.commit()

    meta = client_meta(request)
    audit(db, p, object_type="timing_template", object_id=t.id,
          action="apply_from_date",
          new={"effective_from": body.effective_from, "closed_templates": len(overlapping)},
          reason=body.reason, ip=meta["ip"], ua=meta["ua"])
    return {"ok": True, "effective_from": t.effective_from,
            "closed_previous_count": len(overlapping)}


# ── GET /api/parade-nights/{pnid}/timing ─────────────────────────────────────

@router.get("/parade-nights/{pnid}/timing")
def get_parade_timing(
    pnid: str,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Return the timing template in effect for a parade night.

    Checks for a one-night override first, then falls back to the effective
    default template for the parade night's squadron and date.
    """
    pn = db.get(ParadeNight, pnid)
    if not pn:
        raise HTTPException(404, detail={"error": "not_found"})
    require_can_view_squadron(p, pn.squadron_id, pn.wing_id)

    override = (
        db.query(ParadeNightTimingOverride)
        .filter(ParadeNightTimingOverride.parade_night_id == pnid,
                ParadeNightTimingOverride.is_archived == False)  # noqa: E712
        .first()
    )

    if override and override.timing_template_id:
        t = db.get(TimingTemplate, override.timing_template_id)
        if t and not t.is_archived:
            return {
                "source": "override",
                "override_id": override.id,
                "override_reason": override.reason,
                "template": _template_dict(t),
            }

    effective = _effective_template(db, pn.squadron_id, pn.date)
    if effective:
        return {"source": "default", "template": _template_dict(effective)}

    return {"source": "none", "template": None,
            "message": "No timing template is set for this squadron. "
                       "Using session_count from parade night directly."}


# ── POST /api/parade-nights/{pnid}/timing-override ───────────────────────────

@router.post("/parade-nights/{pnid}/timing-override")
def set_timing_override(
    pnid: str,
    body: OverrideIn,
    request: Request,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Set or replace a one-night timing override.

    Does not change the squadron's default future template.
    """
    if p.role in _WRITE_BLOCKED:
        raise HTTPException(403, detail={"error": "forbidden"})
    pn = db.get(ParadeNight, pnid)
    if not pn:
        raise HTTPException(404, detail={"error": "not_found"})
    require_can_write_squadron(p, pn.squadron_id, pn.wing_id)

    t = db.get(TimingTemplate, body.timing_template_id)
    if not t or t.is_archived:
        raise HTTPException(404, detail={"error": "timing_template_not_found",
                                         "message": "The referenced timing template was not found."})
    if not body.reason.strip():
        raise HTTPException(400, detail={"error": "reason_required",
                                         "message": "A reason is required for a timing override."})

    # Archive any existing override
    existing = (
        db.query(ParadeNightTimingOverride)
        .filter(ParadeNightTimingOverride.parade_night_id == pnid,
                ParadeNightTimingOverride.is_archived == False)  # noqa: E712
        .first()
    )
    if existing:
        existing.is_archived = True
        existing.archived_at = utcnow()
        existing.updated_by = p.user_id

    override = ParadeNightTimingOverride(
        parade_night_id=pnid,
        timing_template_id=body.timing_template_id,
        reason=body.reason.strip(),
        created_by=p.user_id,
    )
    db.add(override)
    db.commit()

    meta = client_meta(request)
    audit(db, p, object_type="parade_night_timing_override", object_id=override.id,
          action="create",
          new={"parade_night_id": pnid, "timing_template_id": body.timing_template_id,
               "reason": body.reason},
          ip=meta["ip"], ua=meta["ua"])
    return {"ok": True, "override_id": override.id}


# ── DELETE /api/parade-nights/{pnid}/timing-override ─────────────────────────

@router.delete("/parade-nights/{pnid}/timing-override")
def remove_timing_override(
    pnid: str,
    request: Request,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Remove a one-night timing override. The parade night reverts to the default template."""
    if p.role in _WRITE_BLOCKED:
        raise HTTPException(403, detail={"error": "forbidden"})
    pn = db.get(ParadeNight, pnid)
    if not pn:
        raise HTTPException(404, detail={"error": "not_found"})
    require_can_write_squadron(p, pn.squadron_id, pn.wing_id)

    override = (
        db.query(ParadeNightTimingOverride)
        .filter(ParadeNightTimingOverride.parade_night_id == pnid,
                ParadeNightTimingOverride.is_archived == False)  # noqa: E712
        .first()
    )
    if not override:
        raise HTTPException(404, detail={"error": "no_override",
                                         "message": "No active timing override found for this parade night."})

    override.is_archived = True
    override.archived_at = utcnow()
    override.updated_by = p.user_id
    db.commit()

    meta = client_meta(request)
    audit(db, p, object_type="parade_night_timing_override", object_id=override.id,
          action="remove", new={"parade_night_id": pnid}, ip=meta["ip"], ua=meta["ua"])
    return {"ok": True}

