"""FastAPI application entrypoint with security headers, CORS lockdown and routers."""
import collections
import logging
import threading
import time as _time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import init_db, SessionLocal
from .routers import auth, organisations, training, ops, health, program, export_import, accounts, timing, planning, system, wing_calendar, jobs, dashboard, setup

# ── SEC-06: 5xx rate alerting ────────────────────────────────────────────────
# In-process rolling window; accurate for single-process (uvicorn) and
# per-worker for multi-process (gunicorn). A future Redis upgrade would give
# cross-worker aggregation, but structured log events are the primary artifact.
_5xx_times: collections.deque = collections.deque()
_5xx_lock = threading.Lock()
_5XX_WINDOW_SEC = 60
_5XX_ALERT_THRESHOLD = 5   # 5 server errors in 60 s triggers a structured warning
_sec_log = logging.getLogger("security")

# ── Maintenance mode cache (avoid DB hit on every request) ──────────────────
_maint_cache: dict = {
    "active": False, "msg": "", "block_reads": False, "block_logins": False,
    "pending_until": None,  # ISO timestamp; None = no drain period / immediate lock
    "expires": 0.0,
}

def _maintenance_active() -> tuple[bool, str, bool, bool, str, str | None]:
    """Returns (is_active, message, block_reads, block_logins, phase, pending_until).

    phase is one of:
      "normal"  — maintenance not active
      "pending" — maintenance enabled but still within the drain window; writes NOT yet blocked
      "locked"  — maintenance active and drain window has passed; writes blocked
    """
    import datetime as _dt
    now = _time.monotonic()
    if now < _maint_cache["expires"]:
        active = _maint_cache["active"]
        pending_until_iso = _maint_cache["pending_until"]
        phase = _compute_phase(active, pending_until_iso)
        return (active, _maint_cache["msg"], _maint_cache["block_reads"],
                _maint_cache["block_logins"], phase, pending_until_iso)
    try:
        from .models.operations import SystemSetting
        with SessionLocal() as db:
            row = db.get(SystemSetting, "maintenance_mode")
            msg_row = db.get(SystemSetting, "maintenance_message")
            br_row = db.get(SystemSetting, "maintenance_block_reads")
            bl_row = db.get(SystemSetting, "maintenance_block_logins")
            pu_row = db.get(SystemSetting, "maintenance_pending_until")
            active = (row.value == "on") if row else False
            msg = msg_row.value if msg_row else "System under maintenance. Please try again later."
            block_reads = (br_row.value == "true") if br_row else False
            block_logins = (bl_row.value == "true") if bl_row else False
            pending_until_iso = pu_row.value if pu_row else None
        _maint_cache["active"] = active
        _maint_cache["msg"] = msg
        _maint_cache["block_reads"] = block_reads
        _maint_cache["block_logins"] = block_logins
        _maint_cache["pending_until"] = pending_until_iso
        _maint_cache["expires"] = now + 10.0
    except Exception:
        return False, "", False, False, "normal", None
    phase = _compute_phase(active, pending_until_iso)
    return active, msg, block_reads, block_logins, phase, pending_until_iso


def _compute_phase(active: bool, pending_until_iso: str | None) -> str:
    """Compute maintenance phase from stored state and current wall-clock time."""
    if not active:
        return "normal"
    if not pending_until_iso:
        return "locked"
    try:
        import datetime as _dt
        from datetime import timezone as _tz
        pu = _dt.datetime.fromisoformat(pending_until_iso.replace("Z", "+00:00"))
        if _dt.datetime.now(_tz.utc) < pu:
            return "pending"
    except Exception:
        pass
    return "locked"


def invalidate_maintenance_cache() -> None:
    """Call after enabling/disabling maintenance so the middleware sees the change immediately."""
    _maint_cache["expires"] = 0.0

logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL, logging.INFO))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail closed: refuse to start in production with insecure configuration.
    problems = settings.validate_for_production()
    if problems:
        for p in problems:
            logging.critical("PRODUCTION CONFIG ERROR: %s", p)
        raise RuntimeError("Refusing to start: " + "; ".join(problems))
    # For SQLite/demo we create tables on startup. In production, run Alembic migrations.
    if settings.DATABASE_URL.startswith("sqlite"):
        init_db()
    yield


app = FastAPI(title="AAFC Training Management System — National", version="17.1.1", lifespan=lifespan,
             docs_url=None, redoc_url=None, openapi_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)


@app.middleware("http")
async def request_size_guard(request: Request, call_next):
    """Reject an oversized request from its Content-Length header, before any body is
    read into memory.

    REM-124: every file-upload endpoint (6 sites across planning.py/training.py) already
    checks `len(content) > UPLOAD_MAX_MB * 1024 * 1024` -- but only *after*
    `await file.read()` has already buffered the entire body in memory, so the existing
    checks bound what gets *processed*, not what gets *allocated*. The same applies to
    every other POST/PUT/PATCH/DELETE endpoint's implicit Pydantic JSON body parsing --
    FastAPI resolves the body alongside other dependencies (including auth), so this is
    reachable pre-authentication, not just on already-permission-checked upload routes.
    This middleware closes the common case (any client that sends an honest
    Content-Length, which is virtually all real clients and simple attackers) by
    rejecting before `call_next` -- so the body is never touched. It cannot catch a
    request that omits Content-Length and streams a large body via chunked transfer
    encoding while lying about its size; that residual is inherent to a header-based
    check and would require wrapping the ASGI receive channel to close, which is a
    larger change than this residual's likelihood/impact currently justifies.
    """
    cl = request.headers.get("content-length")
    if cl is not None:
        try:
            declared = int(cl)
        except ValueError:
            declared = None
        if declared is not None and declared > settings.MAX_REQUEST_BODY_MB * 1024 * 1024:
            return JSONResponse(status_code=413, content={"error": "request_too_large"})
    return await call_next(request)


_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# Always reachable regardless of maintenance flags — system_admin must be able to
# disable maintenance, sessions must be inspectable, health probes must not be blocked.
_MAINTENANCE_ALWAYS_EXEMPT = frozenset({
    "/api/auth/logout",
    "/api/auth/me",
    "/api/auth/refresh",
    # Login is exempt here; the handler applies block_logins after role is known
    # so system_admin can always log back in even when block_logins=True (MAINT-03).
    "/api/auth/login",
    "/api/system/maintenance",
    "/api/system/maintenance/enable",
    "/api/system/maintenance/disable",
    "/api/health",
    "/api/health/db",
    "/api/health/ready",
    "/",
})


def _extract_token(request: Request) -> str | None:
    cookie = request.cookies.get(settings.COOKIE_NAME)
    if cookie:
        return cookie
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


@app.middleware("http")
async def maintenance_gate(request: Request, call_next):
    """Gate requests during maintenance mode.

    Phases:
      pending — drain window in progress; writes NOT blocked; users see warning banner.
      locked  — drain window expired; writes blocked per existing rules.

    Default (block_reads=False, block_logins=False): blocks all write methods.
    With block_reads=True: also blocks GET requests.
    With block_logins=True: also blocks /api/auth/login.
    system_admin bypasses all maintenance gates.
    Always-exempt: health, maintenance management, logout, me, refresh.
    """
    active, msg, block_reads, block_logins, phase, _pending_until = _maintenance_active()
    if not active or phase == "pending":
        return await call_next(request)

    path = request.url.path
    method = request.method

    if path in _MAINTENANCE_ALWAYS_EXEMPT:
        return await call_next(request)

    is_write = method in _WRITE_METHODS
    is_login = path == "/api/auth/login"
    is_read = method == "GET"

    needs_gate = (
        (is_write and not is_login)       # all writes except login (login has its own gate)
        or (is_login and block_logins)    # login only gated when explicitly requested
        or (is_read and block_reads)      # reads only gated when explicitly requested
    )
    if not needs_gate:
        return await call_next(request)

    from .security import decode_token
    raw_token = _extract_token(request)
    if raw_token:
        payload = decode_token(raw_token)
        if payload and payload.get("role") == "system_admin":
            # Verify token_version matches DB so revoked system_admin tokens cannot
            # bypass the maintenance gate (the endpoint itself also checks via get_principal,
            # but defence-in-depth closes the gap at the gateway level).
            user_id = payload.get("sub")
            token_version = payload.get("tv")
            try:
                from .models import User
                with SessionLocal() as _db:
                    _u = _db.get(User, user_id)
                    if _u and _u.active_status and _u.token_version == token_version:
                        return await call_next(request)
            except Exception:
                pass  # fail closed — block on any DB error

    return JSONResponse(
        status_code=503,
        content={
            "error": "maintenance_mode",
            "message": msg or "System under maintenance. Please try again later.",
        },
        headers={"Retry-After": "300"},
    )


_RATE_LIMIT_EXEMPT = frozenset({
    "/api/auth/login",   # has its own DB-backed per-IP + per-account limiter
    "/api/health",
    "/api/health/db",
    "/api/health/ready",
    "/",
    # DEFECT-004: must stay reachable even once this exact limiter has been
    # tripped, or it can never recover a stuck test/CI client -- still fully
    # gated by require_system_admin + settings.is_prod inside the handler,
    # so exemption here only skips the per-IP counter, not auth or the
    # production guard.
    "/api/system/reset-rate-limits",
})


@app.middleware("http")
async def api_rate_limit(request: Request, call_next):
    """Per-IP sliding window rate limiter for all non-exempt API endpoints.

    Login has its own DB-backed limiter; health probes must never be blocked.
    All other /api/ routes share this limit to prevent automated bulk enumeration.

    DEFECT-004: CORS preflight (OPTIONS) requests are excluded from the count.
    They carry no credentials of consequence and touch no route/business logic
    -- counting them was silently halving the effective budget for any
    cross-origin caller (confirmed live: a single connected-frontend e2e spec
    file made 220 OPTIONS requests alongside 253 real GET/POST requests in
    45s, tripping the 300/60s limit on request volume that was, by real
    operation count, still well under it). This affects real cross-origin
    production traffic identically to test traffic, not just tests -- fixing
    the count is a correctness fix, not a threshold change; API_RATE_LIMIT
    and API_RATE_WINDOW_SEC are unchanged.
    """
    if (request.method != "OPTIONS" and request.url.path not in _RATE_LIMIT_EXEMPT
            and request.url.path.startswith("/api/")):
        from .dependencies import real_client_ip
        ip = real_client_ip(request)
        # DEF-10: use DB-backed rate limiter in production/staging so the limit
        # is shared across all gunicorn workers.  In development the in-memory
        # dict is faster and avoids DB overhead during the test suite.
        if settings.ENVIRONMENT.lower() in ("production", "prod", "staging"):
            from .security import check_api_rate_db
            from .database import SessionLocal
            db = SessionLocal()
            try:
                over = check_api_rate_db(ip, db)
            finally:
                db.close()
        else:
            from .security import check_api_rate
            over = check_api_rate(ip)
        if over:
            return JSONResponse(
                status_code=429,
                content={"error": "rate_limited",
                         "message": "Too many requests. Please slow down."},
                headers={"Retry-After": str(settings.API_RATE_WINDOW_SEC)},
            )
    return await call_next(request)


@app.middleware("http")
async def access_log(request: Request, call_next):
    # Structured access log for monitoring / log aggregation (one line per request).
    # In production point LOG_LEVEL=INFO and ship stdout to your aggregator (e.g. Loki/CloudWatch).
    # X-Request-ID: accepted from client if provided, otherwise generated. Echoed in response.
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    start = _time.perf_counter()
    response = await call_next(request)
    dur_ms = round((_time.perf_counter() - start) * 1000, 1)
    from .dependencies import real_client_ip
    client = real_client_ip(request)
    # R5-L02: escape path to prevent log injection via crafted URL paths breaking
    # the JSON structure or injecting fabricated log fields.
    safe_path = request.url.path.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")
    logging.getLogger("access").info(
        '{"method":"%s","path":"%s","status":%d,"dur_ms":%s,"client":"%s","req_id":"%s"}',
        request.method, safe_path, response.status_code, dur_ms, client, req_id)
    # SEC-06: 5xx rate alert — log a structured security warning when errors spike.
    if response.status_code >= 500:
        now_mono = _time.monotonic()
        with _5xx_lock:
            _5xx_times.append(now_mono)
            while _5xx_times and now_mono - _5xx_times[0] > _5XX_WINDOW_SEC:
                _5xx_times.popleft()
            count = len(_5xx_times)
        if count >= _5XX_ALERT_THRESHOLD:
            _sec_log.warning(
                '{"event":"security_alert","type":"5xx_spike","status":%d,'
                '"path":"%s","count_in_window":%d,"window_sec":%d}',
                response.status_code, request.url.path, count, _5XX_WINDOW_SEC)
    response.headers["X-Response-Time-ms"] = str(dur_ms)
    response.headers["X-Request-ID"] = req_id
    return response


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; connect-src 'self'")
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if settings.is_prod:
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    return response


for r in (health.router, auth.router, organisations.router, accounts.router,
          training.router, timing.router, ops.router, program.router, export_import.router,
          planning.router, wing_calendar.router, system.router, jobs.router,
          dashboard.router, setup.router):
    app.include_router(r)


@app.exception_handler(500)
async def server_error(request: Request, exc: Exception):  # pragma: no cover
    # Never leak internals/secrets in error responses.
    logging.exception("Unhandled error")
    return JSONResponse(status_code=500, content={"error": "internal_error"})


@app.get("/")
def root():
    return {"app": "AAFC Training Management System — National", "version": "17.1.0",
            "docs": "/docs", "health": "/api/health"}
