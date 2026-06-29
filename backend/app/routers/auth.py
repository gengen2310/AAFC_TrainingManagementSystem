from fastapi import APIRouter, Depends, Response, Request, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from ..database import get_db
from ..config import settings
from ..security import (verify_code, create_token, hash_code,
                        login_blocked, record_login_failure, record_login_success)
from ..database import utcnow
from ..models import User, AccessCode, Wing
from ..dependencies import get_principal, client_meta
from ..permissions import Principal
from ..services import audit

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    code: str


class ChangeCodeIn(BaseModel):
    user_id: str
    new_code: str


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: DBSession = Depends(get_db)):
    key = (request.client.host if request.client else "anon")
    if login_blocked(key):
        raise HTTPException(429, detail={"error": "locked_out",
                                         "message": "Too many attempts. Try again later."})
    code = (body.code or "").strip()
    matched = None
    for ac in db.query(AccessCode).filter(AccessCode.active_status == True).all():  # noqa: E712
        if verify_code(code, ac.code_hash):
            matched = ac
            break
    if not matched:
        record_login_failure(key)
        raise HTTPException(401, detail={"error": "invalid_code"})
    record_login_success(key)
    user = db.get(User, matched.user_id)
    if not user or not user.active_status:
        raise HTTPException(401, detail={"error": "invalid_user"})
    user.last_login_at = utcnow()
    db.commit()
    token = create_token(user.id, {"role": user.role})
    response.set_cookie(settings.COOKIE_NAME, token, httponly=True,
                        secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE,
                        max_age=settings.ACCESS_TOKEN_TTL_MIN * 60)
    meta = client_meta(request)
    p = Principal(user_id=user.id, role=user.role, wing_id=user.wing_id,
                  squadron_id=user.squadron_id, national_id=user.national_id)
    audit(db, p, object_type="auth", object_id=user.id, action="login", ip=meta["ip"], ua=meta["ua"])
    return {"token": token, "session": _me(user, db)}


@router.post("/logout")
def logout(response: Response, request: Request, db: DBSession = Depends(get_db),
           p: Principal = Depends(get_principal)):
    audit(db, p, object_type="auth", object_id=p.user_id, action="logout")
    response.delete_cookie(settings.COOKIE_NAME)
    return {"ok": True}


@router.get("/me")
def me(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    user = db.get(User, p.user_id)
    data = _me(user, db)
    data["proxy"] = ({"mode": p.proxy_mode, "acting_squadron_id": p.acting_squadron_id,
                      "acting_wing_id": p.acting_wing_id, "proxy_session_id": p.proxy_session_id}
                     if p.proxy_session_id else None)
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
    token = create_token(user.id, {"role": user.role})
    response.set_cookie(settings.COOKIE_NAME, token, httponly=True,
                        secure=settings.COOKIE_SECURE, samesite=settings.COOKIE_SAMESITE,
                        max_age=settings.ACCESS_TOKEN_TTL_MIN * 60)
    return {"token": token, "session": _me(user, db)}


@router.post("/change-code")
def change_code(body: ChangeCodeIn, db: DBSession = Depends(get_db),
                p: Principal = Depends(get_principal)):
    is_self = body.user_id == p.user_id
    # Any authenticated user may change their own code.
    # Changing another user's code requires an admin role.
    if not is_self and p.role not in ("system_admin", "national_admin", "wing_admin", "sqn_admin"):
        raise HTTPException(403, detail={"error": "forbidden"})
    target = db.get(User, body.user_id)
    if not target:
        raise HTTPException(404, detail={"error": "not_found"})
    ac = db.query(AccessCode).filter(AccessCode.user_id == target.id).first()
    if not ac:
        ac = AccessCode(user_id=target.id, code_hash="", created_by=p.user_id)
        db.add(ac)
    ac.code_hash = hash_code(body.new_code)
    ac.updated_at = utcnow()
    ac.updated_by = p.user_id
    db.commit()
    action = "change_own_code" if is_self else "reset_access"
    audit(db, p, object_type="access_code", object_id=target.id, action=action)
    return {"ok": True}


def _me(user: User, db: DBSession | None = None) -> dict:
    wing_code = None
    if user.wing_id and db:
        w = db.get(Wing, user.wing_id)
        if w:
            wing_code = w.code
    return {"user_id": user.id, "display_name": user.display_name, "role": user.role,
            "wing_id": user.wing_id, "wing_code": wing_code,
            "squadron_id": user.squadron_id, "national_id": user.national_id,
            "is_wing": user.role in ("wing_viewer", "wing_admin"),
            "is_national": user.role in ("national_viewer", "national_admin", "system_admin", "auditor")}
