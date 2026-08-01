"""Account management and Flight administration.

Accounts:
  GET    /api/accounts            — list (scoped to actor's authority)
  POST   /api/accounts            — create (returns new code once)
  GET    /api/accounts/{id}       — single account
  PATCH  /api/accounts/{id}       — update display_name / role / flight_id
  POST   /api/accounts/{id}/reset-code  — generate or set new code (returned once)
  POST   /api/accounts/{id}/disable     — deactivate user
  POST   /api/accounts/{id}/reactivate  — reactivate user

Flights (Squadron-local groupings only — no tenancy, no permissions):
  GET    /api/flights              — list (scoped)
  POST   /api/flights              — create (sqn_admin or above)
  PATCH  /api/flights/{fid}        — rename / toggle active
  POST   /api/flights/{fid}/archive — soft-delete

Security invariants enforced here:
  • Plaintext codes are NEVER stored or returned except as a one-time response.
  • Code hashes are NEVER included in any response.
  • Actors may only manage accounts within their own authority scope.
  • Flight assignment never grants or restricts permissions — it is display-only.
  • Viewers and auditors are read-only (no create / update / reset / disable).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from ..database import get_db, utcnow
from ..models import User, AccessCode, Wing, Squadron, Flight, NationalEntity
from ..dependencies import get_principal
from ..permissions import Principal
from ..security import hash_code, generate_code
from ..services import audit
from ..permissions import ROLES as _ALL_ROLES

router = APIRouter(prefix="/api", tags=["accounts"])

# ─────────────────────────────────────────────
# Role authority maps
# ─────────────────────────────────────────────

# Which roles an actor may CREATE
_CREATE_AUTHORITY: dict[str, set[str]] = {
    "system_admin":   {"system_admin", "national_admin", "national_viewer",
                       "wing_admin", "wing_viewer", "sqn_admin", "sqn_general", "auditor"},
    "national_admin": {"national_admin", "national_viewer",
                       "wing_admin", "wing_viewer", "sqn_admin", "sqn_general", "auditor"},
    "wing_admin":     {"wing_viewer", "sqn_admin", "sqn_general"},
    "sqn_admin":      {"sqn_general"},
}

# Which roles an actor may read/manage
_READ_ROLES = {"sqn_admin", "wing_viewer", "wing_admin",
               "national_viewer", "national_admin", "system_admin", "auditor"}

_WRITE_ROLES = {"sqn_admin", "wing_admin", "national_admin", "system_admin"}

_NATIONAL_SCOPE_ROLES = {"national_admin", "national_viewer", "system_admin", "auditor"}
_WING_SCOPE_ROLES = {"wing_admin", "wing_viewer"}
_SQN_SCOPE_ROLES = {"sqn_admin", "sqn_general"}


def _scope_type(role: str) -> str:
    if role in _NATIONAL_SCOPE_ROLES:
        return "national"
    if role in _WING_SCOPE_ROLES:
        return "wing"
    return "squadron"


# ─────────────────────────────────────────────
# Scope authority checks
# ─────────────────────────────────────────────

def _require_write_actor(p: Principal) -> None:
    if p.role not in _WRITE_ROLES:
        raise HTTPException(403, detail={"error": "forbidden"})


def _validate_create_scope(p: Principal, target_role: str,
                            nat_id: str | None, wing_id: str | None, sqn_id: str | None,
                            db: DBSession) -> None:
    """Raise 403/404/422 if the actor is not permitted to create an account with this role+scope."""
    allowed = _CREATE_AUTHORITY.get(p.role, set())
    if target_role not in allowed:
        raise HTTPException(403, detail={"error": "forbidden",
                                          "message": f"Your role ({p.role}) cannot create {target_role} accounts."})

    scope = _scope_type(target_role)

    if scope == "national":
        pass  # no additional scope constraint — national_admin/system_admin verified above

    elif scope == "wing":
        if not wing_id:
            raise HTTPException(422, detail={"error": "wing_id_required"})
        w = db.get(Wing, wing_id)
        if not w or w.is_archived:
            raise HTTPException(404, detail={"error": "wing_not_found"})
        if p.role == "wing_admin" and wing_id != p.wing_id:
            raise HTTPException(403, detail={"error": "out_of_scope",
                                              "message": "Wing Admin can only create accounts in their own Wing."})

    elif scope == "squadron":
        if not sqn_id:
            raise HTTPException(422, detail={"error": "squadron_id_required"})
        sqn = db.get(Squadron, sqn_id)
        if not sqn or sqn.is_archived:
            raise HTTPException(404, detail={"error": "squadron_not_found"})
        if p.role == "wing_admin" and sqn.wing_id != p.wing_id:
            raise HTTPException(403, detail={"error": "out_of_scope",
                                              "message": "Wing Admin can only create accounts for SQNs in their Wing."})
        if p.role == "sqn_admin" and sqn_id != p.squadron_id:
            raise HTTPException(403, detail={"error": "out_of_scope",
                                              "message": "SQN Admin can only create accounts in their own Squadron."})


def _require_manage_authority(p: Principal, target: User, db: DBSession) -> None:
    """Raise 403 if actor lacks management authority over the target account."""
    allowed = _CREATE_AUTHORITY.get(p.role, set())
    if target.role not in allowed:
        raise HTTPException(403, detail={"error": "forbidden"})
    scope = _scope_type(target.role)
    if scope == "wing" and p.role == "wing_admin":
        if target.wing_id != p.wing_id:
            raise HTTPException(403, detail={"error": "out_of_scope"})
    elif scope == "squadron":
        if p.role == "wing_admin":
            sqn = db.get(Squadron, target.squadron_id)
            if not sqn or sqn.wing_id != p.wing_id:
                raise HTTPException(403, detail={"error": "out_of_scope"})
        elif p.role == "sqn_admin":
            if target.squadron_id != p.squadron_id:
                raise HTTPException(403, detail={"error": "out_of_scope"})


def _can_read_account(p: Principal, target: User, db: DBSession) -> bool:
    if p.role in ("national_admin", "national_viewer", "system_admin", "auditor"):
        return True
    if p.role in ("wing_admin", "wing_viewer"):
        if target.wing_id == p.wing_id:
            return True
        if target.squadron_id:
            sqn = db.get(Squadron, target.squadron_id)
            return sqn is not None and sqn.wing_id == p.wing_id
    if p.role in ("sqn_admin", "sqn_general"):
        return target.squadron_id == p.squadron_id
    return False


# ─────────────────────────────────────────────
# Response serialiser (never includes code_hash)
# ─────────────────────────────────────────────

def _account_out(u: User, db: DBSession) -> dict:
    ac = db.query(AccessCode).filter(AccessCode.user_id == u.id,
                                     AccessCode.active_status == True).first()  # noqa: E712
    # Resolve unit names
    sqn_code = sqn_name = wing_code = wing_name = nat_name = flight_name = None
    if u.squadron_id:
        s = db.get(Squadron, u.squadron_id)
        if s:
            sqn_code, sqn_name = s.code, s.name
    if u.wing_id:
        w = db.get(Wing, u.wing_id)
        if w:
            wing_code, wing_name = w.code, w.name
    if u.national_id:
        n = db.get(NationalEntity, u.national_id)
        if n:
            nat_name = n.short_name
    if u.flight_id:
        fl = db.get(Flight, u.flight_id)
        if fl:
            flight_name = fl.name

    return {
        "user_id": u.id,
        "display_name": u.display_name,
        "role": u.role,
        "scope_type": _scope_type(u.role),
        "national_id": u.national_id,
        "national_name": nat_name,
        "wing_id": u.wing_id,
        "wing_code": wing_code,
        "wing_name": wing_name,
        "squadron_id": u.squadron_id,
        "squadron_code": sqn_code,
        "squadron_name": sqn_name,
        "flight_id": u.flight_id,
        "flight_name": flight_name,
        "active_status": u.active_status,
        "is_archived": u.is_archived,
        "archived_at": u.archived_at.isoformat() if u.archived_at else None,
        "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        "created_at": u.created_at.isoformat() if u.created_at else None,
        "created_by": u.created_by,
        # Access-code metadata only (never hash, never plaintext)
        "code_active": ac.active_status if ac else False,
        "code_last_changed": ac.updated_at.isoformat() if ac and ac.updated_at else None,
        "code_changed_by": ac.updated_by if ac else None,
        "locked_until": ac.locked_until.isoformat() if ac and ac.locked_until else None,
    }


# ─────────────────────────────────────────────
# Pydantic schemas
# ─────────────────────────────────────────────

class AccountCreateIn(BaseModel):
    display_name: str
    role: str
    national_id: str | None = None
    wing_id: str | None = None
    squadron_id: str | None = None
    flight_id: str | None = None
    new_code: str | None = None   # if omitted, auto-generated


class AccountUpdateIn(BaseModel):
    display_name: str | None = None
    flight_id: str | None = None  # pass "" or null to clear


class ResetCodeIn(BaseModel):
    new_code: str | None = None   # if omitted, auto-generated


class FlightIn(BaseModel):
    name: str
    squadron_id: str


class FlightUpdateIn(BaseModel):
    name: str | None = None
    active_status: bool | None = None


# ─────────────────────────────────────────────
# Account endpoints
# ─────────────────────────────────────────────

@router.get("/accounts")
def list_accounts(wing_id: str | None = None, squadron_id: str | None = None,
                  flight_id: str | None = None, role: str | None = None,
                  active_status: bool | None = None, include_archived: bool = False,
                  db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    if p.role not in _READ_ROLES:
        raise HTTPException(403, detail={"error": "forbidden"})
    q = db.query(User)
    if not include_archived:
        q = q.filter(User.is_archived == False)  # noqa: E712

    # Scope filtering based on actor role
    if p.role in ("national_admin", "national_viewer", "system_admin", "auditor"):
        if wing_id:
            # Filter by wing: both direct wing users and sqn users in that wing
            sqns_in_wing = [s.id for s in db.query(Squadron).filter(Squadron.wing_id == wing_id)]
            q = q.filter((User.wing_id == wing_id) | (User.squadron_id.in_(sqns_in_wing)))
        if squadron_id:
            q = q.filter(User.squadron_id == squadron_id)
    elif p.role in ("wing_admin", "wing_viewer"):
        sqns_in_wing = [s.id for s in db.query(Squadron).filter(Squadron.wing_id == p.wing_id)]
        q = q.filter((User.wing_id == p.wing_id) | (User.squadron_id.in_(sqns_in_wing)))
        if squadron_id:
            q = q.filter(User.squadron_id == squadron_id)
    else:  # sqn_admin / sqn_general
        q = q.filter(User.squadron_id == p.squadron_id)

    if flight_id:
        q = q.filter(User.flight_id == flight_id)
    if role:
        q = q.filter(User.role == role)
    if active_status is not None:
        q = q.filter(User.active_status == active_status)

    users = q.order_by(User.display_name).all()
    return [_account_out(u, db) for u in users]


@router.post("/accounts")
def create_account(body: AccountCreateIn, db: DBSession = Depends(get_db),
                   p: Principal = Depends(get_principal)):
    _require_write_actor(p)
    if body.role not in _ALL_ROLES:
        raise HTTPException(422, detail={"error": "invalid_role"})

    name = body.display_name.strip()
    if not name:
        raise HTTPException(422, detail={"error": "invalid_display_name",
                                         "message": "Display name cannot be empty."})
    if len(name) > 100:
        raise HTTPException(422, detail={"error": "invalid_display_name",
                                         "message": "Display name cannot exceed 100 characters."})

    # Validate actor authority and scope
    _validate_create_scope(p, body.role, body.national_id, body.wing_id, body.squadron_id, db)

    # Flight assignment: only valid for squadron-scoped accounts, and must belong to correct SQN
    flight_id = None
    if body.flight_id:
        if _scope_type(body.role) != "squadron":
            raise HTTPException(422, detail={"error": "flight_only_for_squadron_scope"})
        fl = db.get(Flight, body.flight_id)
        if not fl or fl.is_archived:
            raise HTTPException(404, detail={"error": "flight_not_found"})
        if fl.squadron_id != body.squadron_id:
            raise HTTPException(422, detail={"error": "flight_not_in_squadron"})
        flight_id = fl.id

    # Derive nat_id for national-scope roles; derive wing_id from squadron for sqn-scope roles
    # so that p.wing_id is populated for wing calendar scope checks.
    nat_id = body.national_id
    wing_id = body.wing_id
    sqn_id = body.squadron_id
    if _scope_type(body.role) == "squadron" and not wing_id and sqn_id:
        sqn_obj = db.get(Squadron, sqn_id)
        if sqn_obj:
            wing_id = sqn_obj.wing_id
    if _scope_type(body.role) == "national" and not nat_id:
        nat = db.query(NationalEntity).first()
        nat_id = nat.id if nat else None

    u = User(display_name=name, role=body.role,
             national_id=nat_id, wing_id=wing_id, squadron_id=sqn_id,
             flight_id=flight_id, active_status=True, created_by=p.user_id)
    db.add(u)
    db.flush()  # get u.id

    # Generate or hash the initial code
    plain = body.new_code.strip() if body.new_code else generate_code()
    ac = AccessCode(user_id=u.id, code_hash=hash_code(plain),
                    active_status=True, created_by=p.user_id,
                    updated_by=p.user_id, updated_at=utcnow())
    db.add(ac)
    db.commit()

    audit(db, p, object_type="account", object_id=u.id, action="account_created",
          new={"role": body.role, "display_name": body.display_name})
    audit(db, p, object_type="access_code", object_id=u.id, action="code_generated")

    out = _account_out(u, db)
    # Return new code once only — it will not be retrievable again
    out["new_code"] = plain
    out["new_code_notice"] = "This code will not be shown again. Copy it now."
    return out


@router.get("/accounts/{uid}")
def get_account(uid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    if p.role not in _READ_ROLES:
        raise HTTPException(403, detail={"error": "forbidden"})
    u = db.get(User, uid)
    if not u or u.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    if not _can_read_account(p, u, db):
        raise HTTPException(403, detail={"error": "forbidden"})
    return _account_out(u, db)


@router.patch("/accounts/{uid}")
def update_account(uid: str, body: AccountUpdateIn, db: DBSession = Depends(get_db),
                   p: Principal = Depends(get_principal)):
    _require_write_actor(p)
    u = db.get(User, uid)
    if not u or u.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    _require_manage_authority(p, u, db)

    if body.display_name is not None:
        name = body.display_name.strip()
        if not name:
            raise HTTPException(422, detail={"error": "invalid_display_name",
                                             "message": "Display name cannot be empty."})
        if len(name) > 100:
            raise HTTPException(422, detail={"error": "invalid_display_name",
                                             "message": "Display name cannot exceed 100 characters."})
        u.display_name = name

    if body.flight_id is not None:
        if body.flight_id == "":
            u.flight_id = None
        else:
            if _scope_type(u.role) != "squadron":
                raise HTTPException(422, detail={"error": "flight_only_for_squadron_scope"})
            fl = db.get(Flight, body.flight_id)
            if not fl or fl.is_archived:
                raise HTTPException(404, detail={"error": "flight_not_found"})
            if fl.squadron_id != u.squadron_id:
                raise HTTPException(422, detail={"error": "flight_not_in_squadron"})
            u.flight_id = fl.id

    u.updated_by = p.user_id
    db.commit()
    audit(db, p, object_type="account", object_id=u.id, action="account_updated",
          new={"display_name": u.display_name, "flight_id": u.flight_id})
    return {"ok": True}


@router.post("/accounts/{uid}/reset-code")
def reset_code(uid: str, body: ResetCodeIn, db: DBSession = Depends(get_db),
               p: Principal = Depends(get_principal)):
    """Generate or set a new access code for the target account.

    The new code is returned ONCE in this response. It cannot be retrieved again.
    The existing code hash is never returned. The new code is stored as a hash only.
    """
    _require_write_actor(p)
    u = db.get(User, uid)
    if not u or u.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})

    # Self-service: any authenticated user may reset their own code
    if uid != p.user_id:
        _require_manage_authority(p, u, db)

    raw = (body.new_code or "").strip()
    if raw:
        if len(raw) < 6:
            raise HTTPException(422, detail={"error": "invalid_code",
                                             "message": "Access code must be at least 6 characters."})
        if len(raw) > 128:
            raise HTTPException(422, detail={"error": "invalid_code",
                                             "message": "Access code is too long (maximum 128 characters)."})
        plain = raw
    else:
        plain = generate_code()
    ac = db.query(AccessCode).filter(AccessCode.user_id == u.id).first()
    if not ac:
        ac = AccessCode(user_id=u.id, code_hash="", created_by=p.user_id)
        db.add(ac)
    ac.code_hash = hash_code(plain)
    ac.active_status = True
    ac.updated_at = utcnow()
    ac.updated_by = p.user_id
    u.token_version = (u.token_version or 0) + 1
    db.commit()

    action = "change_own_code" if uid == p.user_id else "reset_access"
    audit(db, p, object_type="access_code", object_id=u.id, action=action,
          new={"target_display_name": u.display_name, "target_role": u.role})

    return {
        "ok": True,
        "new_code": plain,
        "new_code_notice": "This code will not be shown again. Copy it now.",
    }


@router.post("/accounts/{uid}/disable")
def disable_account(uid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    _require_write_actor(p)
    u = db.get(User, uid)
    if not u or u.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    if uid == p.user_id:
        raise HTTPException(400, detail={"error": "cannot_disable_self"})
    _require_manage_authority(p, u, db)
    u.active_status = False
    u.updated_by = p.user_id
    # Also deactivate the access code so login is blocked immediately
    for ac in db.query(AccessCode).filter(AccessCode.user_id == u.id).all():
        ac.active_status = False
    db.commit()
    audit(db, p, object_type="account", object_id=u.id, action="account_disabled",
          new={"display_name": u.display_name, "role": u.role})
    return {"ok": True}


@router.post("/accounts/{uid}/reactivate")
def reactivate_account(uid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    _require_write_actor(p)
    u = db.get(User, uid)
    if not u or u.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    _require_manage_authority(p, u, db)
    u.active_status = True
    u.updated_by = p.user_id
    for ac in db.query(AccessCode).filter(AccessCode.user_id == u.id).all():
        ac.active_status = True
    db.commit()
    audit(db, p, object_type="account", object_id=u.id, action="account_reactivated",
          new={"display_name": u.display_name, "role": u.role})
    return {"ok": True}


def _last_active_system_admin_count(db: DBSession) -> int:
    return db.query(User).filter(User.role == "system_admin", User.active_status == True,  # noqa: E712
                                 User.is_archived == False).count()  # noqa: E712


@router.post("/accounts/{uid}/archive")
def archive_account(uid: str, reason: str | None = None, db: DBSession = Depends(get_db),
                    p: Principal = Depends(get_principal)):
    """Archive (not delete) a single account: active_status=False + is_archived=True.
    Reversible via .../restore. Extends the existing disable mechanism rather
    than a parallel one -- archiving implies disabling (access is revoked)."""
    _require_write_actor(p)
    u = db.get(User, uid)
    if not u or u.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    if uid == p.user_id:
        raise HTTPException(400, detail={"error": "cannot_archive_self"})
    _require_manage_authority(p, u, db)
    if u.role == "system_admin" and u.active_status and _last_active_system_admin_count(db) <= 1:
        raise HTTPException(409, detail={"error": "last_active_system_admin",
                                          "message": "Cannot archive the last active System Administrator."})
    u.active_status = False
    u.is_archived = True
    u.archived_at = utcnow()
    u.updated_by = p.user_id
    for ac in db.query(AccessCode).filter(AccessCode.user_id == u.id).all():
        ac.active_status = False
    db.commit()
    audit(db, p, object_type="account", object_id=u.id, action="account_archived",
          new={"display_name": u.display_name, "role": u.role}, reason=reason)
    return {"ok": True}


@router.post("/accounts/{uid}/restore")
def restore_account(uid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    """Restore an archived account directly to active (not merely un-archived-but-
    still-disabled) -- a restored account should be immediately usable pending a
    fresh decision to disable it again, not left in a confusing third state."""
    _require_write_actor(p)
    u = db.get(User, uid)
    if not u or not u.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    _require_manage_authority(p, u, db)
    u.is_archived = False
    u.archived_at = None
    u.active_status = True
    u.updated_by = p.user_id
    for ac in db.query(AccessCode).filter(AccessCode.user_id == u.id).all():
        ac.active_status = True
    db.commit()
    audit(db, p, object_type="account", object_id=u.id, action="account_restored",
          new={"display_name": u.display_name, "role": u.role})
    return {"ok": True}


class BatchArchiveIn(BaseModel):
    account_ids: list[str]
    reason: str
    effective_at: str | None = None  # audit-display only -- no job scheduler exists in this codebase
    confirm_session_revocation: bool = False


@router.post("/accounts/batch-archive")
def batch_archive_accounts(body: BatchArchiveIn, db: DBSession = Depends(get_db),
                           p: Principal = Depends(get_principal)):
    """Archive multiple accounts in one guided operation. Each account is its own
    commit (not one outer transaction) so one bad row's failure never discards
    already-decided, already-correct outcomes for the rest of the batch -- every
    item gets an explicit, inspectable per-item result, never a silent partial
    success. One batch_id correlates every row's audit entry plus one summary row."""
    import uuid as _uuid
    _require_write_actor(p)
    if not (body.reason or "").strip() or len(body.reason.strip()) < 10:
        raise HTTPException(400, detail={"error": "reason_required",
                                          "message": "A reason of at least 10 characters is required."})
    if not body.confirm_session_revocation:
        raise HTTPException(400, detail={"error": "session_revocation_not_confirmed",
                                          "message": "You must confirm that active sessions will be revoked."})
    if not body.account_ids:
        raise HTTPException(400, detail={"error": "no_accounts_selected"})

    batch_id = str(_uuid.uuid4())
    remaining_active_system_admins = _last_active_system_admin_count(db)
    results = []
    for uid in body.account_ids:
        try:
            u = db.get(User, uid)
            if not u:
                results.append({"account_id": uid, "result": "failed", "reason": "not_found"})
                continue
            if u.is_archived:
                results.append({"account_id": uid, "result": "already_archived",
                               "display_name": u.display_name, "role": u.role})
                continue
            if uid == p.user_id:
                results.append({"account_id": uid, "result": "skipped", "reason": "cannot_archive_self",
                               "display_name": u.display_name, "role": u.role})
                continue
            try:
                _require_manage_authority(p, u, db)
            except HTTPException:
                results.append({"account_id": uid, "result": "failed", "reason": "out_of_scope",
                               "display_name": u.display_name, "role": u.role})
                continue
            if u.role == "system_admin" and u.active_status:
                if remaining_active_system_admins <= 1:
                    results.append({"account_id": uid, "result": "skipped", "reason": "last_active_system_admin",
                                   "display_name": u.display_name, "role": u.role})
                    continue
                remaining_active_system_admins -= 1
            u.active_status = False
            u.is_archived = True
            u.archived_at = utcnow()
            u.updated_by = p.user_id
            for ac in db.query(AccessCode).filter(AccessCode.user_id == u.id).all():
                ac.active_status = False
            audit(db, p, object_type="account", object_id=u.id, action="account_archived",
                  new={"display_name": u.display_name, "role": u.role}, reason=body.reason,
                  batch_id=batch_id, commit=False)
            db.commit()
            results.append({"account_id": uid, "result": "archived",
                           "display_name": u.display_name, "role": u.role})
        except Exception as e:
            db.rollback()
            results.append({"account_id": uid, "result": "failed", "reason": str(e)})

    summary = {
        "archived": sum(1 for r in results if r["result"] == "archived"),
        "already_archived": sum(1 for r in results if r["result"] == "already_archived"),
        "skipped": sum(1 for r in results if r["result"] == "skipped"),
        "failed": sum(1 for r in results if r["result"] == "failed"),
    }
    audit(db, p, object_type="account_archive_batch", object_id=batch_id, action="batch_archive",
          new={"total": len(body.account_ids), **summary}, reason=body.reason, batch_id=batch_id)
    return {"ok": True, "batch_id": batch_id, "results": results, "summary": summary}


@router.post("/accounts/{uid}/unlock")
def unlock_account(uid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    """Reset the per-account login lockout for a user.

    Clears failed_attempts and locked_until on the user's active access code.
    Requires the same management authority as reset-code (wing_admin for squadron
    accounts in their wing, national_admin / system_admin for wider scope).
    """
    _require_write_actor(p)
    u = db.get(User, uid)
    if not u or u.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    _require_manage_authority(p, u, db)
    ac = db.query(AccessCode).filter(AccessCode.user_id == u.id,
                                     AccessCode.active_status == True).first()  # noqa: E712
    if not ac:
        raise HTTPException(404, detail={"error": "not_found"})
    ac.failed_attempts = 0
    ac.locked_until = None
    db.commit()
    audit(db, p, object_type="access_code", object_id=u.id, action="lockout_reset",
          new={"display_name": u.display_name, "role": u.role})
    return {"ok": True}


# ─────────────────────────────────────────────
# Flight endpoints (Squadron-local groupings)
# ─────────────────────────────────────────────

def _can_write_flight(p: Principal, sqn_id: str, db: DBSession) -> None:
    """Only sqn_admin (own SQN), wing_admin (own Wing), nat_admin, system_admin."""
    if p.role in ("national_admin", "system_admin"):
        return
    if p.role == "wing_admin":
        sqn = db.get(Squadron, sqn_id)
        if not sqn or sqn.wing_id != p.wing_id:
            raise HTTPException(403, detail={"error": "out_of_scope"})
        return
    if p.role == "sqn_admin":
        if sqn_id != p.squadron_id:
            raise HTTPException(403, detail={"error": "out_of_scope"})
        return
    raise HTTPException(403, detail={"error": "forbidden"})


@router.get("/flights")
def list_flights(squadron_id: str | None = None, db: DBSession = Depends(get_db),
                 p: Principal = Depends(get_principal)):
    q = db.query(Flight).filter(Flight.is_archived == False)  # noqa: E712
    if p.role in ("national_admin", "national_viewer", "system_admin", "auditor"):
        if squadron_id:
            q = q.filter(Flight.squadron_id == squadron_id)
    elif p.role in ("wing_admin", "wing_viewer"):
        sqn_ids = [s.id for s in db.query(Squadron).filter(Squadron.wing_id == p.wing_id)]
        q = q.filter(Flight.squadron_id.in_(sqn_ids))
        if squadron_id:
            q = q.filter(Flight.squadron_id == squadron_id)
    else:
        q = q.filter(Flight.squadron_id == p.squadron_id)
        if squadron_id and squadron_id != p.squadron_id:
            return []
    return [_flight_out(f, db) for f in q.order_by(Flight.name).all()]


@router.post("/flights")
def create_flight(body: FlightIn, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    _can_write_flight(p, body.squadron_id, db)
    f = Flight(squadron_id=body.squadron_id, name=body.name.strip(),
               active_status=True, created_by=p.user_id)
    db.add(f)
    db.commit()
    audit(db, p, object_type="flight", object_id=f.id, action="flight_created",
          new={"name": f.name, "squadron_id": f.squadron_id})
    return {**_flight_out(f, db), "ok": True}


@router.patch("/flights/{fid}")
def update_flight(fid: str, body: FlightUpdateIn, db: DBSession = Depends(get_db),
                  p: Principal = Depends(get_principal)):
    f = db.get(Flight, fid)
    if not f or f.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    _can_write_flight(p, f.squadron_id, db)
    if body.name is not None:
        f.name = body.name.strip()
    if body.active_status is not None:
        f.active_status = body.active_status
    f.updated_by = p.user_id
    db.commit()
    audit(db, p, object_type="flight", object_id=f.id, action="flight_updated")
    return {"ok": True}


@router.post("/flights/{fid}/archive")
def archive_flight(fid: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    f = db.get(Flight, fid)
    if not f or f.is_archived:
        raise HTTPException(404, detail={"error": "not_found"})
    _can_write_flight(p, f.squadron_id, db)
    # Clear flight assignment from any users first
    db.query(User).filter(User.flight_id == f.id).update({"flight_id": None}, synchronize_session=False)
    f.is_archived = True
    f.archived_at = utcnow()
    f.updated_by = p.user_id
    db.commit()
    audit(db, p, object_type="flight", object_id=f.id, action="flight_archived")
    return {"ok": True}


def _flight_out(f: Flight, db: DBSession | None = None) -> dict:
    sqn_code = sqn_name = None
    if db and f.squadron_id:
        s = db.get(Squadron, f.squadron_id)
        if s:
            sqn_code, sqn_name = s.code, s.name
    return {"flight_id": f.id, "squadron_id": f.squadron_id,
            "squadron_code": sqn_code, "squadron_name": sqn_name,
            "name": f.name, "active_status": f.active_status,
            "created_at": f.created_at.isoformat() if f.created_at else None}
