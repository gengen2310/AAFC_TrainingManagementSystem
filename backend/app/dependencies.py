"""Request dependencies: build the Principal from the JWT (cookie or bearer)
and overlay any active proxy/intervention session from the database.
"""
from fastapi import Depends, Request, HTTPException
from sqlalchemy.orm import Session as DBSession

from .database import get_db
from .config import settings
from .security import decode_token
from .permissions import Principal
from .models import ProxySession, User


def _token_from_request(request: Request) -> str | None:
    # An explicit Authorization header takes precedence over the session cookie.
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return request.cookies.get(settings.COOKIE_NAME)


def get_principal(request: Request, db: DBSession = Depends(get_db)) -> Principal:
    token = _token_from_request(request)
    if not token:
        raise HTTPException(401, detail={"error": "auth_required"})
    payload = decode_token(token)
    if not payload:
        raise HTTPException(401, detail={"error": "invalid_or_expired"})
    user = db.get(User, payload.get("sub"))
    if not user or not user.active_status:
        raise HTTPException(401, detail={"error": "invalid_user"})
    if payload.get("tv", 0) != user.token_version:
        raise HTTPException(401, detail={"error": "session_revoked"})
    p = Principal(user_id=user.id, role=user.role, wing_id=user.wing_id,
                  squadron_id=user.squadron_id, national_id=user.national_id)
    # overlay active proxy/intervention
    ps = (db.query(ProxySession)
          .filter(ProxySession.actor_user_id == user.id, ProxySession.active == True)  # noqa: E712
          .order_by(ProxySession.created_at.desc()).first())
    if ps:
        p.proxy_session_id = ps.id
        p.proxy_mode = ps.mode
        p.acting_wing_id = ps.acting_wing_id
        p.acting_squadron_id = ps.acting_squadron_id
    return p


def client_meta(request: Request) -> dict:
    return {"ip": request.client.host if request.client else None,
            "ua": request.headers.get("User-Agent")}
