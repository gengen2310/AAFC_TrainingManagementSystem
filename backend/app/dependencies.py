"""Request dependencies: build the Principal from the JWT (cookie or bearer)
and overlay any active proxy/intervention session from the database.
"""
import ipaddress

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


# RFC 6598 (Carrier-Grade NAT / shared address space) -- the range Railway's own internal
# edge/proxy address was directly observed in (100.64.0.2, from live staging access logs).
# Used below as a real, independently-verifiable guard, not a bare assumption: only trust
# X-Forwarded-For when the immediate connecting peer actually looks like Railway's own
# infrastructure, not from any arbitrary source that reaches this process.
_CGNAT_RANGE = ipaddress.ip_network("100.64.0.0/10")


def _looks_like_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


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

    Fix: take the left-most (original client) entry of X-Forwarded-For, the de
    facto standard header set by essentially every HTTP-layer proxy/load
    balancer including Railway's -- but with two hardenings a background
    security review of the first version of this fix correctly flagged as
    missing, not blindly trusting a client-suppliable header:

    1. Only trusted when the immediate connecting peer (`request.client.host`)
       is itself in the RFC 6598 CGNAT range Railway's own edge was directly
       observed using -- i.e. the request must already look like it came
       through Railway's proxy layer before its forwarded-for claim is used
       at all. A request whose raw peer is NOT in that range (some other,
       unexpected direct-connection path) falls back to the raw peer instead
       of trusting an arbitrary header -- this is a real, independently
       checkable condition, not an assumption about Railway's topology taken
       on faith. (A general community web search surfaced claims about
       Railway's proxy-header behaviour during this investigation, but those
       were third-party forum answers, not Railway's own documentation, and
       one even misstated the CGNAT range -- not treated as a trustworthy
       basis for a security control; this guard relies only on this
       deployment's own directly-observed behaviour and the well-established
       RFC 6598 block.)
    2. The extracted value must parse as a syntactically valid IP address
       (`ipaddress.ip_address`) before it is ever returned. Closes a log/
       audit-injection path the first version of this fix introduced: `client`
       feeds directly into main.py's hand-built access-log line with no
       escaping, so an unvalidated header value could break that line's JSON
       structure or inject fabricated fields. An attacker can still supply a
       fake-but-well-formed IP (an inherent limit of any header-based scheme,
       not new), but can no longer inject arbitrary log content or bypass
       hardening #1 with a non-IP payload.

    Falls back to the raw peer address when the header is absent, the peer
    isn't in the trusted range, or the header's value doesn't parse as an IP
    (local dev, tests, or any environment without a proxy in front) so
    existing behaviour there is unchanged.
    """
    peer = request.client.host if request.client else None
    trusted_peer = False
    if peer:
        try:
            trusted_peer = ipaddress.ip_address(peer) in _CGNAT_RANGE
        except ValueError:
            trusted_peer = False
    if trusted_peer:
        fwd = request.headers.get("X-Forwarded-For")
        if fwd:
            first = fwd.split(",")[0].strip()
            if first and _looks_like_ip(first):
                return first
    return peer or "anon"


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
