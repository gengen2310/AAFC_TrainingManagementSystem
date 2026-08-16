from datetime import timedelta, datetime, timezone

from fastapi import APIRouter, Depends, Response, Request, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from ..database import get_db
from ..config import settings
from ..security import (verify_code, create_token, hash_code,
                        login_blocked_db, record_login_failure_db, record_login_success_db)
from ..database import utcnow
from ..models import User, AccessCode, Wing, Squadron, NationalEntity, ProxySession, SystemSetting
from ..dependencies import get_principal, client_meta, real_client_ip
from ..permissions import Principal
from ..services import audit

router = APIRouter(prefix="/api/auth", tags=["auth"])

_LOCKOUT_MSG = ("Account locked after too many incorrect attempts. "
                "Contact your Wing SOCAD for access.")


def _check_maintenance_login_gate(role: str, db: DBSession) -> None:
    """Block non-SA logins when maintenance is LOCKED and block_logins=True (MAINT-03).

    Called after code verification so the user's role is known. system_admin always
    passes through so they can re-authenticate even when block_logins is active.
    Phase logic is inlined to avoid circular import from main.py.
    """
    if role == "system_admin":
        return
    mm_row = db.get(SystemSetting, "maintenance_mode")
    if not mm_row or mm_row.value != "on":
        return
    bl_row = db.get(SystemSetting, "maintenance_block_logins")
    if not (bl_row and bl_row.value == "true"):
        return
    # Determine phase: PENDING if still within drain window, else LOCKED.
    pu_row = db.get(SystemSetting, "maintenance_pending_until")
    pending_until_iso = pu_row.value if pu_row else None
    phase = "locked"
    if pending_until_iso:
        try:
            pu = datetime.fromisoformat(pending_until_iso)
            if pu.tzinfo is None:
                pu = pu.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) < pu:
                phase = "pending"
        except ValueError:
            pass
    if phase != "locked":
        return
    msg_row = db.get(SystemSetting, "maintenance_message")
    msg = (msg_row.value if msg_row else None) or "System under maintenance. Please try again later."
    raise HTTPException(status_code=503, detail={"error": "maintenance_mode", "message": msg})
_LOCKOUT_THRESHOLD = 5
_LOCKOUT_HOURS = 24

_NATIONAL_ROLES = {"national_admin", "national_viewer", "system_admin", "auditor"}


class LoginIn(BaseModel):
    code: str = Field(max_length=128)
    user_id: str | None = None  # when provided, verification is scoped to this account only


class LookupIn(BaseModel):
    unit_type: str        # "squadron" | "wing" | "national"
    identifier: str | None = None  # squadron code or wing code; omit for national
    role: str


class ChangeCodeIn(BaseModel):
    user_id: str
    new_code: str


@router.post("/lookup")
def lookup(body: LookupIn, request: Request, db: DBSession = Depends(get_db)):
    """Resolve unit + role to a single account record without touching any credentials."""
    # R5-L01: rate-limit /lookup using the same IP-level bucket as /login so
    # that already-locked IPs cannot probe account existence, and 404 responses
    # count toward lockout to deter systematic account enumeration.
    key = real_client_ip(request)
    if login_blocked_db(key, db):
        raise HTTPException(429, detail={"error": "locked_out",
                                         "message": "Too many attempts. Try again later."})

    def _not_found() -> HTTPException:
        record_login_failure_db(key, db)
        return HTTPException(404, detail={"error": "not_found",
                                          "message": "No account found for that combination."})

    unit_type = (body.unit_type or "").strip()
    role = (body.role or "").strip()
    ident = (body.identifier or "").strip()

    if unit_type == "squadron":
        sqn = db.query(Squadron).filter(
            func.upper(Squadron.code) == ident.upper()
        ).first()
        if not sqn:
            raise _not_found()
        user = db.query(User).filter(
            User.squadron_id == sqn.id,
            User.role == role,
            User.active_status == True  # noqa: E712
        ).order_by(User.created_at.desc()).first()
    elif unit_type == "wing":
        wing = db.query(Wing).filter(
            func.upper(Wing.code) == ident.upper()
        ).first()
        if not wing:
            raise _not_found()
        user = db.query(User).filter(
            User.wing_id == wing.id,
            User.role == role,
            User.active_status == True  # noqa: E712
        ).order_by(User.created_at.desc()).first()
    elif unit_type == "national":
        if role not in _NATIONAL_ROLES:
            raise _not_found()
        user = db.query(User).filter(
            User.role == role,
            User.active_status == True  # noqa: E712
        ).order_by(User.created_at.desc()).first()
    else:
        raise _not_found()

    if not user:
        raise _not_found()
    return {"user_id": user.id, "display_name": user.display_name}


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: DBSession = Depends(get_db)):
    key = real_client_ip(request)
    if login_blocked_db(key, db):
        raise HTTPException(429, detail={"error": "locked_out",
                                         "message": "Too many attempts. Try again later."})
    code = (body.code or "").strip()

    if body.user_id:
        # Scoped path: verify only against the identified account.
        # This is the path taken by every production login (after /lookup).
        ac = db.query(AccessCode).filter(
            AccessCode.user_id == body.user_id,
            AccessCode.active_status == True  # noqa: E712
        ).first()
        # Per-account lockout check before touching the code
        if ac:
            _raise_if_locked(ac)
        if not ac or not verify_code(code, ac.code_hash):
            # R5-M19/M21: increment both per-account and per-IP counters on failure.
            # Per-account lockout guards targeted single-account attacks; IP throttle
            # guards high-volume scanning across multiple accounts from one source.
            if ac:
                ac.failed_attempts = (ac.failed_attempts or 0) + 1
                if ac.failed_attempts >= _LOCKOUT_THRESHOLD:
                    ac.locked_until = utcnow() + timedelta(hours=_LOCKOUT_HOURS)
                db.commit()
            record_login_failure_db(key, db)
            # Fallback: /lookup uses .first() which may return an older sibling
            # account when multiple active accounts share the same role in a
            # squadron. Scan bounded to the same unit+role scope so no
            # cross-scope escalation is possible.
            matched = _scoped_fallback_scan(body.user_id, code, db)
            if matched is None:
                raise HTTPException(401, detail={"error": "invalid_code"})
        else:
            matched = ac
    else:
        # Legacy scan-all path (used by tests; production always provides user_id via /lookup).
        matched = None
        for ac in db.query(AccessCode).filter(AccessCode.active_status == True).all():  # noqa: E712
            if verify_code(code, ac.code_hash):
                matched = ac
                break
        if not matched:
            record_login_failure_db(key, db)
            raise HTTPException(401, detail={"error": "invalid_code"})
        _raise_if_locked(matched)
        # R5-L04 (note): the scan-all path cannot increment a per-account counter on
        # failure because no account is identified until the code matches. IP-level
        # throttle (record_login_failure_db above) is the only defence on this path.
        # This path is test-only; production always provides user_id via /lookup,
        # which takes the per-account counter path above.

    record_login_success_db(key, db)
    user = db.get(User, matched.user_id)
    if not user or not user.active_status:
        raise HTTPException(401, detail={"error": "invalid_user"})
    _check_maintenance_login_gate(user.role, db)
    user.last_login_at = utcnow()
    matched.failed_attempts = 0
    matched.locked_until = None
    db.commit()
    token = create_token(user.id, {"role": user.role}, token_version=user.token_version)
    response.set_cookie(settings.COOKIE_NAME, token, httponly=True,
                        secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE,
                        max_age=settings.ACCESS_TOKEN_TTL_MIN * 60)
    meta = client_meta(request)
    p = Principal(user_id=user.id, role=user.role, wing_id=user.wing_id,
                  squadron_id=user.squadron_id, national_id=user.national_id)
    audit(db, p, object_type="auth", object_id=user.id, action="login", ip=meta["ip"], ua=meta["ua"])
    return {"token": token, "session": _me(user, db)}


def _raise_if_locked(ac: AccessCode):
    locked = ac.locked_until
    if locked is None:
        return
    now = utcnow().replace(tzinfo=None)
    locked_naive = locked.replace(tzinfo=None) if locked.tzinfo else locked
    if locked_naive > now:
        raise HTTPException(429, detail={"error": "locked_out", "message": _LOCKOUT_MSG})


def _scoped_fallback_scan(primary_user_id: str, code: str, db: DBSession) -> "AccessCode | None":
    """Try sibling accounts when /lookup returned the wrong user_id.

    /lookup uses .first() on a non-unique (squadron, role) filter, so when a
    squadron has multiple active accounts with the same role the returned user_id
    may not match the caller's code. Scan the other active accounts in the same
    unit+role scope and return the matching AccessCode, or None.

    Scope is intentionally narrow: only users sharing the primary user's exact
    (squadron_id OR wing_id OR national role) AND role are scanned. Cross-scope
    access is never possible via this path.
    """
    primary = db.get(User, primary_user_id)
    if not primary:
        return None
    role = primary.role
    if primary.squadron_id:
        siblings = db.query(User).filter(
            User.squadron_id == primary.squadron_id,
            User.role == role,
            User.active_status == True,  # noqa: E712
            User.id != primary_user_id,
        ).all()
    elif primary.wing_id:
        siblings = db.query(User).filter(
            User.wing_id == primary.wing_id,
            User.role == role,
            User.active_status == True,  # noqa: E712
            User.id != primary_user_id,
        ).all()
    else:
        siblings = db.query(User).filter(
            User.role == role,
            User.active_status == True,  # noqa: E712
            User.id != primary_user_id,
        ).all()
    for sibling in siblings:
        sib_ac = db.query(AccessCode).filter(
            AccessCode.user_id == sibling.id,
            AccessCode.active_status == True,  # noqa: E712
        ).first()
        if not sib_ac:
            continue
        locked = sib_ac.locked_until
        if locked is not None:
            now = utcnow().replace(tzinfo=None)
            locked_naive = locked.replace(tzinfo=None) if locked.tzinfo else locked
            if locked_naive > now:
                continue
        if verify_code(code, sib_ac.code_hash):
            return sib_ac
        # Do NOT increment failed_attempts on siblings — only the primary account
        # (targeted by the caller) should accumulate failure counts.  Incrementing
        # every sibling on mismatch created a DoS vector: 5 failed attempts against
        # any one national-scope account would lock every account of that role.
    return None


@router.post("/logout")
def logout(response: Response, request: Request, db: DBSession = Depends(get_db),
           p: Principal = Depends(get_principal)):
    # QUAL-004: an active Proxy/Delegated Intervention session must not silently persist
    # across logout+re-login -- get_principal re-attaches any active ProxySession for this
    # user_id on the very next authenticated request, regardless of which token is used, so
    # logging out is the actor's clearest signal that the elevated write context should end.
    active_proxy = (db.query(ProxySession)
                    .filter(ProxySession.actor_user_id == p.user_id, ProxySession.active == True)  # noqa: E712
                    .all())
    for ps in active_proxy:
        ps.active = False
    if active_proxy:
        db.commit()
        for ps in active_proxy:
            audit(db, p, object_type="proxy", object_id=ps.acting_squadron_id,
                  action=("proxy_exit_on_logout" if ps.mode == "proxy" else "intervention_exit_on_logout"))
    audit(db, p, object_type="auth", object_id=p.user_id, action="logout")
    response.delete_cookie(settings.COOKIE_NAME)
    return {"ok": True}


@router.get("/me")
def me(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    user = db.get(User, p.user_id)
    data = _me(user, db)
    if p.proxy_session_id:
        sq = db.get(Squadron, p.acting_squadron_id) if p.acting_squadron_id else None
        data["proxy"] = {
            "mode": p.proxy_mode,
            "acting_squadron_id": p.acting_squadron_id,
            "acting_squadron_code": sq.code if sq else None,
            "acting_squadron_name": (sq.short_name or sq.name) if sq else None,
            "acting_wing_id": p.acting_wing_id,
            "proxy_session_id": p.proxy_session_id,
        }
    else:
        data["proxy"] = None
    return {"session": data}


@router.post("/refresh")
def refresh(response: Response, request: Request, db: DBSession = Depends(get_db),
            p: Principal = Depends(get_principal)):
    """Sliding refresh: exchange a still-valid token for a fresh one.

    Decision (documented): access tokens are short-lived (ACCESS_TOKEN_TTL_MIN). Rather than a
    long-lived refresh token stored client-side, the frontend calls this endpoint while the current
    token is still valid to obtain a new one, so active users are not logged out mid-session. An
    EXPIRED token is rejected by get_principal (401) and the user must log in again — this bounds the
    window in which a leaked token is useful and avoids a second long-lived credential.
    """
    user = db.get(User, p.user_id)
    if not user or not user.active_status:
        raise HTTPException(401, detail={"error": "invalid_user"})
    token = create_token(user.id, {"role": user.role}, token_version=user.token_version)
    response.set_cookie(settings.COOKIE_NAME, token, httponly=True,
                        secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE,
                        max_age=settings.ACCESS_TOKEN_TTL_MIN * 60)
    return {"token": token, "session": _me(user, db)}


@router.post("/change-code")
def change_code(body: ChangeCodeIn, db: DBSession = Depends(get_db),
                p: Principal = Depends(get_principal)):
    is_self = body.user_id == p.user_id
    # Any authenticated user may change their own code.
    # Changing another user's code requires an admin role + management authority over that account.
    if not is_self and p.role not in ("system_admin", "national_admin", "wing_admin", "sqn_admin"):
        raise HTTPException(403, detail={"error": "forbidden"})
    target = db.get(User, body.user_id)
    if not target:
        raise HTTPException(404, detail={"error": "not_found"})
    # Scope check: the actor must have management authority over the target account.
    # (Mirrors the check in accounts.py:reset_code — prevents cross-scope code takeover.)
    if not is_self:
        from .accounts import _require_manage_authority
        _require_manage_authority(p, target, db)
    # Validate the new code: strip, non-empty, minimum length, maximum length.
    plain = (body.new_code or "").strip()
    if not plain:
        raise HTTPException(422, detail={"error": "invalid_code",
                                         "message": "Access code cannot be empty."})
    if len(plain) < 6:
        raise HTTPException(422, detail={"error": "invalid_code",
                                         "message": "Access code must be at least 6 characters."})
    if len(plain) > 128:
        raise HTTPException(422, detail={"error": "invalid_code",
                                         "message": "Access code is too long (maximum 128 characters)."})
    ac = db.query(AccessCode).filter(AccessCode.user_id == target.id).first()
    if not ac:
        ac = AccessCode(user_id=target.id, code_hash="", created_by=p.user_id)
        db.add(ac)
    ac.code_hash = hash_code(plain)
    ac.updated_at = utcnow()
    ac.updated_by = p.user_id
    target.token_version = (target.token_version or 0) + 1
    db.commit()
    action = "change_own_code" if is_self else "reset_access"
    new_info = {} if is_self else {"target_display_name": target.display_name, "target_role": target.role}
    audit(db, p, object_type="access_code", object_id=target.id, action=action, new=new_info)
    return {"ok": True}


@router.get("/organisations")
def list_organisations(db: DBSession = Depends(get_db)):
    """Public — returns Wing/Squadron list for the login selector.
    Returns only safe public data (codes + names). No users, codes, or hashes.
    """
    wings = (db.query(Wing)
               .filter(Wing.is_archived == False, Wing.active_status == True)
               .order_by(Wing.code)
               .all())
    result = []
    for wing in wings:
        sqns = (db.query(Squadron)
                  .filter(Squadron.wing_id == wing.id,
                          Squadron.is_archived == False,
                          Squadron.active_status == True)
                  .order_by(Squadron.unit_number, Squadron.code)
                  .all())
        result.append({
            "code": wing.code,
            "name": wing.name,
            "squadrons": [
                {"code": s.code, "name": s.name, "unit_type": s.unit_type}
                for s in sqns
            ],
        })
    return {"wings": result}


def _me(user: User, db: DBSession | None = None) -> dict:
    wing_code = None
    wing_name = None
    if user.wing_id and db:
        w = db.get(Wing, user.wing_id)
        if w:
            wing_code = w.code
            wing_name = w.name
    squadron_code = None
    if user.squadron_id and db:
        s = db.get(Squadron, user.squadron_id)
        if s:
            squadron_code = s.code
    return {"user_id": user.id, "display_name": user.display_name, "role": user.role,
            "wing_id": user.wing_id, "wing_code": wing_code, "wing_name": wing_name,
            "squadron_id": user.squadron_id, "squadron_code": squadron_code,
            "national_id": user.national_id,
            "is_wing": user.role in ("wing_viewer", "wing_admin"),
            "is_national": user.role in ("national_viewer", "national_admin", "system_admin", "auditor")}
