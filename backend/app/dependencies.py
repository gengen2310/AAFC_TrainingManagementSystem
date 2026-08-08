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


def real_client_ip(request: Request) -> str:
    """The IP every per-IP security control (login lockout, API rate limiter,
    access logging) should key off.

    REM-125: this app is only ever reachable through Railway's own edge, which
    terminates TLS and forwards over plain HTTP -- so `request.client.host` is
    ALWAYS Railway's internal edge address (confirmed live: every request in the
    staging access log shows the identical "100.64.0.2" regardless of the real
    caller), never the actual end user. Every per-IP control keyed off the raw
    peer therefore shared ONE bucket across every user of the whole deployed
    application: 5 failed login attempts by anyone, anywhere, within the 5-minute
    window locked out login for everyone for 15 minutes (LOGIN_MAX_ATTEMPTS/
    LOGIN_WINDOW_SEC/LOGIN_LOCKOUT_SEC), and the API rate limiter's 300
    req/60s budget was likewise shared by the whole user base at once.

    Fix: take the left-most (original client) entry of X-Forwarded-For, the
    de facto standard header set by essentially every HTTP-layer proxy/load
    balancer including Railway's. Safe to trust here for two independent
    reasons, both confirmed live post-deploy (not just assumed): (1) Railway's
    network topology makes its own edge the ONLY thing that can ever open a
    direct connection to this container, so nothing external can inject a
    header at the hop this process actually sees; and (2) empirically,
    Railway's edge does not pass through a client-supplied X-Forwarded-For
    value at all -- a deliberately spoofed header sent in live staging testing
    was overwritten with the true observed connection IP, not appended to or
    trusted. Falls back to the raw peer address when the header is absent
    (local dev, tests, or any environment without a proxy in front)
    so existing behaviour there is unchanged.
    """
    fwd = request.headers.get("X-Forwarded-For")
    if fwd:
        first = fwd.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "anon"


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
    return {"ip": real_client_ip(request),
            "ua": request.headers.get("User-Agent")}
