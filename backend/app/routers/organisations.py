from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from ..database import get_db, utcnow
from ..models import Wing, Squadron, ProxySession, AuditLog, NationalEntity, User
from ..models.organisations import UNIT_TYPES
from ..dependencies import get_principal, client_meta
from ..permissions import Principal, require_role, require_can_view_squadron, require_can_write_squadron, require_system_or_nat_admin
from ..services import audit

router = APIRouter(prefix="/api", tags=["organisations"])

_NAT_ADMIN_ROLES = frozenset({"national_admin", "system_admin"})


# ── Organisations ──
@router.get("/national/overview")
def national_overview(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    require_role(p, "national_viewer", "national_admin", "system_admin", "auditor")
    wings = db.query(Wing).filter(Wing.is_archived == False).all()  # noqa: E712
    out = []
    for w in wings:
        sqns = db.query(Squadron).filter(Squadron.wing_id == w.id, Squadron.is_archived == False).all()  # noqa: E712
        out.append({"wing_id": w.id, "code": w.code, "name": w.name, "squadrons": len(sqns)})
    return {"national": "AAFC", "wings": out, "wing_count": len(wings)}


@router.get("/wings")
def list_wings(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    q = db.query(Wing).filter(Wing.is_archived == False)  # noqa: E712
    wings = q.all()
    if not p.is_national:
        wings = [w for w in wings if w.id == p.wing_id]
    return [{"wing_id": w.id, "code": w.code, "name": w.name,
             "short_name": getattr(w, "short_name", w.code)} for w in wings]


class WingCreateIn(BaseModel):
    code: str
    name: str
    short_name: str | None = None


@router.post("/wings")
def create_wing(body: WingCreateIn, db: DBSession = Depends(get_db),
                p: Principal = Depends(get_principal)):
    if p.role not in _NAT_ADMIN_ROLES:
        raise HTTPException(403, detail={"error": "forbidden",
                                          "message": "Only NAT HQ admin can create Wings."})
    code = (body.code or "").strip().upper()
    if not code:
        raise HTTPException(400, detail={"error": "code_required"})
    if db.query(Wing).filter(Wing.code == code).first():
        raise HTTPException(409, detail={"error": "code_exists",
                                          "message": f"A Wing with code '{code}' already exists."})
    name = (body.name or code).strip()
    dup = db.query(Wing).filter(Wing.is_archived == False,  # noqa: E712
                                 Wing.name.ilike(name)).first()
    if dup:
        raise HTTPException(409, detail={"error": "name_exists",
                                          "message": f"An active Wing named '{name}' already exists (code '{dup.code}')."})
    nat = db.query(NationalEntity).first()
    if not nat:
        raise HTTPException(500, detail={"error": "no_national_entity"})
    w = Wing(national_id=nat.id, code=code, name=name,
             short_name=body.short_name or code, active_status=True,
             created_by=p.user_id)
    db.add(w); db.commit()
    audit(db, p, object_type="wing", object_id=w.id, action="create",
          new={"code": code, "name": w.name})
    return {"ok": True, "wing_id": w.id, "code": w.code, "name": w.name}


@router.post("/wings/{wing_id}/archive")
def archive_wing(wing_id: str, db: DBSession = Depends(get_db),
                 p: Principal = Depends(get_principal)):
    """Archive (soft-delete) a Wing. Requires system_admin or national_admin.
    Wings with active squadrons cannot be archived — deactivate squadrons first.
    """
    require_system_or_nat_admin(p)
    w = db.get(Wing, wing_id)
    if not w:
        raise HTTPException(404, detail={"error": "not_found"})
    if w.is_archived:
        raise HTTPException(409, detail={"error": "already_archived"})
    active_sqns = db.query(Squadron).filter(
        Squadron.wing_id == wing_id, Squadron.is_archived == False  # noqa: E712
    ).count()
    if active_sqns:
        raise HTTPException(409, detail={
            "error": "has_active_squadrons",
            "message": f"Cannot archive Wing with {active_sqns} active squadron(s). Archive squadrons first."
        })
    w.is_archived = True
    w.archived_at = datetime.now(timezone.utc)
    db.commit()
    audit(db, p, object_type="wing", object_id=w.id, action="archive",
          old={"code": w.code, "name": w.name})
    return {"ok": True, "wing_id": w.id, "archived": True}


@router.post("/wings/{wing_id}/restore")
def restore_wing(wing_id: str, db: DBSession = Depends(get_db),
                 p: Principal = Depends(get_principal)):
    """Restore a previously archived Wing. Requires system_admin or national_admin."""
    require_system_or_nat_admin(p)
    w = db.get(Wing, wing_id)
    if not w:
        raise HTTPException(404, detail={"error": "not_found"})
    if not w.is_archived:
        raise HTTPException(409, detail={"error": "not_archived"})
    w.is_archived = False
    w.archived_at = None
    db.commit()
    audit(db, p, object_type="wing", object_id=w.id, action="restore",
          new={"code": w.code, "name": w.name})
    return {"ok": True, "wing_id": w.id, "archived": False}


@router.get("/squadrons")
def list_squadrons(wing_id: str | None = None, unit_type: str | None = None,
                   db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    q = db.query(Squadron).filter(Squadron.is_archived == False)  # noqa: E712
    sqns = q.all()
    if p.is_national:
        pass
    elif p.is_wing:
        sqns = [s for s in sqns if s.wing_id == p.wing_id]
    else:
        sqns = [s for s in sqns if s.id == p.squadron_id]
    if wing_id:
        sqns = [s for s in sqns if s.wing_id == wing_id]
    if unit_type:
        sqns = [s for s in sqns if s.unit_type == unit_type]
    return [_sqn(s) for s in sqns]


class SquadronCreateIn(BaseModel):
    wing_id: str
    code: str
    name: str
    short_name: str | None = None
    unit_type: str = "standard_squadron"
    unit_number: str | None = None


@router.post("/squadrons")
def create_squadron(body: SquadronCreateIn, db: DBSession = Depends(get_db),
                    p: Principal = Depends(get_principal)):
    """Create a Squadron-equivalent training unit (standard_squadron, specialist_squadron,
    specialist_flight, or support_unit) under a Wing.

    NAT HQ admin / system_admin: any Wing.
    Wing admin: own Wing only.
    Other roles: 403.
    """
    if p.role not in {*_NAT_ADMIN_ROLES, "wing_admin"}:
        raise HTTPException(403, detail={"error": "forbidden",
                                          "message": "Only Wing or NAT HQ admin can create Squadrons / Specialist Units."})
    # Wing admin scope check
    if p.role == "wing_admin" and body.wing_id != p.wing_id:
        raise HTTPException(403, detail={"error": "out_of_scope",
                                          "message": "Wing Admin can only create units under their own Wing."})
    w = db.get(Wing, body.wing_id)
    if not w or w.is_archived:
        raise HTTPException(404, detail={"error": "wing_not_found"})

    unit_type = body.unit_type if body.unit_type in UNIT_TYPES else "standard_squadron"
    code = (body.code or "").strip().upper()
    if not code:
        raise HTTPException(400, detail={"error": "code_required"})
    if db.query(Squadron).filter(Squadron.code == code).first():
        raise HTTPException(409, detail={"error": "code_exists",
                                          "message": f"A unit with code '{code}' already exists."})
    name = (body.name or code).strip()
    dup = db.query(Squadron).filter(Squadron.wing_id == body.wing_id, Squadron.is_archived == False,  # noqa: E712
                                     Squadron.name.ilike(name)).first()
    if dup:
        raise HTTPException(409, detail={"error": "name_exists",
                                          "message": f"An active unit named '{name}' already exists in this Wing (code '{dup.code}')."})

    s = Squadron(wing_id=body.wing_id, code=code, name=name,
                 short_name=body.short_name or code, unit_type=unit_type,
                 unit_number=body.unit_number, active_status=True,
                 created_by=p.user_id)
    db.add(s); db.commit()
    audit(db, p, object_type="squadron", object_id=s.id, action="create",
          new={"code": code, "name": s.name, "unit_type": unit_type, "wing": w.code})
    return {"ok": True, **_sqn(s)}


@router.post("/squadrons/{squadron_id}/archive")
def archive_squadron(squadron_id: str, db: DBSession = Depends(get_db),
                     p: Principal = Depends(get_principal)):
    """Archive (soft-delete) a Squadron or Specialist Unit.
    system_admin and national_admin: any unit.
    wing_admin: only units in their own Wing.
    """
    if p.role not in {*_NAT_ADMIN_ROLES, "wing_admin"}:
        raise HTTPException(403, detail={"error": "forbidden"})
    s = db.get(Squadron, squadron_id)
    if not s:
        raise HTTPException(404, detail={"error": "not_found"})
    if p.role == "wing_admin" and s.wing_id != p.wing_id:
        raise HTTPException(403, detail={"error": "out_of_scope"})
    if s.is_archived:
        raise HTTPException(409, detail={"error": "already_archived"})
    active_accounts = db.query(User).filter(
        User.squadron_id == squadron_id, User.is_archived == False  # noqa: E712
    ).count()
    if active_accounts:
        raise HTTPException(409, detail={
            "error": "has_active_accounts",
            "message": f"Cannot archive unit with {active_accounts} active account(s) still assigned. Reassign or archive those accounts first."
        })
    s.is_archived = True
    s.archived_at = datetime.now(timezone.utc)
    db.commit()
    audit(db, p, object_type="squadron", object_id=s.id, action="archive",
          old={"code": s.code, "name": s.name})
    return {"ok": True, "squadron_id": s.id, "archived": True}


@router.post("/squadrons/{squadron_id}/restore")
def restore_squadron(squadron_id: str, db: DBSession = Depends(get_db),
                     p: Principal = Depends(get_principal)):
    """Restore a previously archived Squadron/Specialist Unit.
    system_admin and national_admin: any unit. wing_admin: only units in their own Wing."""
    if p.role not in {*_NAT_ADMIN_ROLES, "wing_admin"}:
        raise HTTPException(403, detail={"error": "forbidden"})
    s = db.get(Squadron, squadron_id)
    if not s:
        raise HTTPException(404, detail={"error": "not_found"})
    if p.role == "wing_admin" and s.wing_id != p.wing_id:
        raise HTTPException(403, detail={"error": "out_of_scope"})
    if not s.is_archived:
        raise HTTPException(409, detail={"error": "not_archived"})
    w = db.get(Wing, s.wing_id)
    if w and w.is_archived:
        raise HTTPException(409, detail={"error": "parent_wing_archived",
                                          "message": "Cannot restore a unit whose Wing is archived. Restore the Wing first."})
    s.is_archived = False
    s.archived_at = None
    db.commit()
    audit(db, p, object_type="squadron", object_id=s.id, action="restore",
          new={"code": s.code, "name": s.name})
    return {"ok": True, "squadron_id": s.id, "archived": False}


@router.get("/squadrons/{squadron_id}")
def get_squadron(squadron_id: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    s = db.get(Squadron, squadron_id)
    if not s:
        raise HTTPException(404, detail={"error": "not_found"})
    require_can_view_squadron(p, s.id, s.wing_id)
    return _sqn(s)


class SquadronUpdateIn(BaseModel):
    address: str | None = None
    default_parade_day: str | None = None
    default_start_time: str | None = None
    default_end_time: str | None = None
    default_session_count: int | None = None
    unit_type: str | None = None


@router.patch("/squadrons/{squadron_id}")
def update_squadron(squadron_id: str, body: SquadronUpdateIn, db: DBSession = Depends(get_db),
                    p: Principal = Depends(get_principal)):
    s = db.get(Squadron, squadron_id)
    if not s:
        raise HTTPException(404, detail={"error": "not_found"})
    require_can_write_squadron(p, s.id, s.wing_id)
    if body.address is not None:
        s.address = body.address
    if body.default_parade_day is not None:
        s.default_parade_day = body.default_parade_day
    if body.default_start_time is not None:
        s.default_start_time = body.default_start_time
    if body.default_end_time is not None:
        s.default_end_time = body.default_end_time
    if body.default_session_count is not None:
        s.default_session_count = body.default_session_count
    if body.unit_type is not None and body.unit_type in UNIT_TYPES:
        s.unit_type = body.unit_type
    db.commit()
    audit(db, p, object_type="squadron", object_id=s.id, action="update_settings")
    return {"ok": True}


@router.get("/users")
def list_users(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    require_role(p, "sqn_admin", "wing_admin", "national_admin", "system_admin")
    q = db.query(User).filter(User.active_status == True)  # noqa: E712
    if p.role == "sqn_admin":
        q = q.filter(User.squadron_id == p.squadron_id)
    elif p.role == "wing_admin":
        q = q.filter(User.wing_id == p.wing_id)
    # national_admin / system_admin: no additional filter
    users = q.order_by(User.display_name).all()
    return [_user(u, db) for u in users]


def _user(u: User, db: DBSession) -> dict:
    sqn_code: str | None = None
    wing_code: str | None = None
    if u.squadron_id:
        sqn = db.get(Squadron, u.squadron_id)
        if sqn:
            sqn_code = sqn.code
    if u.wing_id:
        wing = db.get(Wing, u.wing_id)
        if wing:
            wing_code = wing.code
    return {"user_id": u.id, "display_name": u.display_name, "role": u.role,
            "wing_id": u.wing_id, "squadron_id": u.squadron_id, "national_id": u.national_id,
            "squadron_code": sqn_code, "wing_code": wing_code}


def _sqn(s: Squadron) -> dict:
    return {"squadron_id": s.id, "wing_id": s.wing_id, "code": s.code, "name": s.name,
            "short_name": s.short_name, "unit_type": getattr(s, "unit_type", "standard_squadron"),
            "address": s.address, "default_parade_day": s.default_parade_day,
            "default_start_time": s.default_start_time, "default_end_time": s.default_end_time,
            "default_session_count": s.default_session_count, "active_status": s.active_status}


# ── Proxy / Delegated Intervention ──
class EnterIn(BaseModel):
    reason: str


@router.post("/proxy/enter/{squadron_id}")
def enter_proxy(squadron_id: str, body: EnterIn, request: Request,
                db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    if not (body.reason or "").strip():
        raise HTTPException(400, detail={"error": "reason_required"})
    s = db.get(Squadron, squadron_id)
    if not s:
        raise HTTPException(404, detail={"error": "not_found"})
    if p.role == "wing_admin":
        if s.wing_id != p.wing_id:
            raise HTTPException(403, detail={"error": "out_of_scope"})
        mode = "proxy"
    elif p.role in ("national_admin", "system_admin"):
        mode = "delegated_intervention"
    else:
        raise HTTPException(403, detail={"error": "forbidden"})
    # close any existing active sessions
    for old in db.query(ProxySession).filter(ProxySession.actor_user_id == p.user_id,
                                             ProxySession.active == True).all():  # noqa: E712
        old.active = False
    ps = ProxySession(actor_user_id=p.user_id, actor_role=p.role, mode=mode,
                      acting_wing_id=s.wing_id, acting_squadron_id=s.id, reason=body.reason, active=True)
    db.add(ps); db.commit()
    p.proxy_session_id = ps.id; p.proxy_mode = mode
    p.acting_wing_id = s.wing_id; p.acting_squadron_id = s.id
    meta = client_meta(request)
    audit(db, p, object_type="proxy", object_id=s.id,
          action=("proxy_enter" if mode == "proxy" else "intervention_enter"),
          new={"squadron": s.code}, reason=body.reason, ip=meta["ip"], ua=meta["ua"])
    return {"ok": True, "proxy": {"mode": mode, "acting_squadron_id": s.id, "proxy_session_id": ps.id}}


@router.post("/proxy/exit")
def exit_proxy(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    if not p.proxy_session_id:
        return {"ok": True}
    ps = db.get(ProxySession, p.proxy_session_id)
    if ps:
        ps.active = False; db.commit()
    audit(db, p, object_type="proxy", object_id=p.acting_squadron_id,
          action=("proxy_exit" if p.proxy_mode == "proxy" else "intervention_exit"))
    return {"ok": True}


@router.get("/proxy/current")
def current_proxy(p: Principal = Depends(get_principal)):
    if not p.proxy_session_id:
        return {"active": False}
    return {"active": True, "mode": p.proxy_mode, "acting_squadron_id": p.acting_squadron_id}


_AUDIT_READ_ROLES = frozenset({"auditor", "sqn_admin", "wing_admin", "national_admin", "system_admin"})

# ── Audit (read-only; auditor + wing/national admins) ──
@router.get("/audit")
def get_audit(object_type: str | None = None, object_id: str | None = None,
              limit: int = 300, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    if p.role not in _AUDIT_READ_ROLES:
        raise HTTPException(403, detail={"error": "forbidden"})
    q = db.query(AuditLog)
    if not p.is_national:
        if p.is_wing:
            q = q.filter(AuditLog.wing_id == p.wing_id)
        else:
            q = q.filter(AuditLog.squadron_id == p.squadron_id)
    if object_type:
        q = q.filter(AuditLog.object_type == object_type)
    if object_id:
        q = q.filter(AuditLog.object_id == object_id)
    rows = q.order_by(AuditLog.timestamp.desc()).limit(min(limit, 1000)).all()
    return [{"audit_id": r.id, "timestamp": r.timestamp.isoformat(), "role": r.role,
             "action": r.action, "object_type": r.object_type, "object_id": r.object_id,
             "reason": r.reason, "proxy_session_id": r.proxy_session_id} for r in rows]
