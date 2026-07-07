"""FastAPI application entrypoint with security headers, CORS lockdown and routers."""
import logging
import time as _time
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import init_db, SessionLocal
from .routers import auth, organisations, training, ops, health, program, export_import, accounts, timing, planning, system, wing_calendar

# ── Maintenance mode cache (avoid DB hit on every request) ──────────────────
_maint_cache: dict = {"active": False, "msg": "", "expires": 0.0}

def _maintenance_active() -> tuple[bool, str]:
    """Returns (is_active, message). Cached with 10-second TTL."""
    now = _time.monotonic()
    if now < _maint_cache["expires"]:
        return _maint_cache["active"], _maint_cache["msg"]
    try:
        from .models.operations import SystemSetting
        with SessionLocal() as db:
            row = db.get(SystemSetting, "maintenance_mode")
            msg_row = db.get(SystemSetting, "maintenance_message")
            active = (row.value == "on") if row else False
            msg = msg_row.value if msg_row else "System under maintenance. Please try again later."
        _maint_cache["active"] = active
        _maint_cache["msg"] = msg
        _maint_cache["expires"] = now + 10.0
    except Exception:
        return False, ""
    return _maint_cache["active"], _maint_cache["msg"]


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


app = FastAPI(title="AAFC Training Management System — National", version="17.1.0", lifespan=lifespan,
             docs_url=None, redoc_url=None, openapi_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
# Paths that must always be reachable so system_admin can disable maintenance mode
_MAINTENANCE_EXEMPT = frozenset({
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/me",
    "/api/auth/refresh",
    "/api/system/maintenance",
    "/api/system/maintenance/enable",
    "/api/system/maintenance/disable",
    "/api/health",
    "/api/health/db",
    "/api/health/ready",
    "/",
})


@app.middleware("http")
async def maintenance_gate(request: Request, call_next):
    """Block write operations for all non-system_admin users during maintenance mode."""
    if request.method not in _WRITE_METHODS:
        return await call_next(request)
    if request.url.path in _MAINTENANCE_EXEMPT:
        return await call_next(request)

    active, msg = _maintenance_active()
    if not active:
        return await call_next(request)

    # Maintenance is ON — check if the caller is system_admin via JWT.
    # Accept both the HTTP-only session cookie (browser) and the
    # Authorization: Bearer <token> header (API / programmatic clients).
    from .security import decode_token
    raw_token: str | None = None
    cookie = request.cookies.get(settings.COOKIE_NAME)
    if cookie:
        raw_token = cookie
    else:
        auth_hdr = request.headers.get("Authorization", "")
        if auth_hdr.startswith("Bearer "):
            raw_token = auth_hdr[7:]
    if raw_token:
        payload = decode_token(raw_token)
        if payload and payload.get("role") == "system_admin":
            return await call_next(request)

    return JSONResponse(
        status_code=503,
        content={
            "error": "maintenance_mode",
            "message": msg or "System under maintenance. Please try again later.",
        },
        headers={"Retry-After": "300"},
    )


@app.middleware("http")
async def access_log(request: Request, call_next):
    # Structured access log for monitoring / log aggregation (one line per request).
    # In production point LOG_LEVEL=INFO and ship stdout to your aggregator (e.g. Loki/CloudWatch).
    import time as _t
    start = _t.perf_counter()
    response = await call_next(request)
    dur_ms = round((_t.perf_counter() - start) * 1000, 1)
    client = request.client.host if request.client else "-"
    logging.getLogger("access").info(
        '{"method":"%s","path":"%s","status":%d,"dur_ms":%s,"client":"%s"}',
        request.method, request.url.path, response.status_code, dur_ms, client)
    response.headers["X-Response-Time-ms"] = str(dur_ms)
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
          planning.router, wing_calendar.router, system.router):
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
