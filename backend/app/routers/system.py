"""System Admin Console endpoints — system_admin role required for all privileged operations.

All state-changing actions are audited. No secrets, hashes, or access-code plaintext
are returned from any endpoint here.
"""
import logging
import os
import shutil
import subprocess
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session as DBSession

from ..config import settings
from ..database import get_db
from ..dependencies import get_principal
from ..database import utcnow
from ..models import (
    User, Wing, Squadron, AuditLog, SystemSetting, AccessCode, IpLoginAttempt, IpApiRequest,
    PlanningYear, ParadeDate, Session, CurriculumItem, NationalEntity, JobStatus,
)
from ..permissions import Principal, require_system_admin, require_audit_access
from ..security import generate_code, hash_code, reset_rate_limiter, reset_api_rate_limiter, reset_api_rate_limiter_db, reset_user_api_rate_limiter_db
from ..services import audit

router = APIRouter(prefix="/api/system", tags=["system"])

APP_VERSION = "17.1.1"
PACKAGE_VERSION = "v17.1"


# ── helpers ──────────────────────────────────────────────────────────────────

def _get_setting(db: DBSession, key: str, default: str | None = None) -> str | None:
    row = db.get(SystemSetting, key)
    return row.value if row else default


def _set_setting(db: DBSession, key: str, value: str | None, updated_by: str) -> None:
    row = db.get(SystemSetting, key)
    if row is None:
        row = SystemSetting(key=key)
        db.add(row)
    row.value = value
    row.updated_at = datetime.now(timezone.utc)
    row.updated_by = updated_by
    db.commit()


def _migration_head() -> str:
    """Return current Alembic revision, or 'unknown' if alembic is unavailable."""
    try:
        result = subprocess.run(
            ["python", "-m", "alembic", "current"],
            capture_output=True, text=True, timeout=10,
            cwd=Path(__file__).parent.parent.parent,
        )
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        return lines[-1] if lines else "unknown"
    except Exception:
        return "unknown"


def _db_type() -> str:
    url = settings.DATABASE_URL
    if url.startswith("sqlite"):
        return "SQLite (local demo)"
    if "postgres" in url or "pg" in url:
        return "PostgreSQL"
    return "other"


# ── GET /api/system/overview ──────────────────────────────────────────────────

@router.get("/overview")
def system_overview(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    require_system_admin(p)
    wings = db.query(Wing).count()
    sqns = db.query(Squadron).count()
    users = db.query(User).count()
    active_users = db.query(User).filter(User.active_status == True).count()  # noqa: E712
    maint = _get_setting(db, "maintenance_mode", "off")
    last_backup = _get_setting(db, "last_backup_at")
    return {
        "app_version": APP_VERSION,
        "package_version": PACKAGE_VERSION,
        "environment": settings.ENVIRONMENT,
        "db_type": _db_type(),
        "wings": wings,
        "squadrons": sqns,
        "users_total": users,
        "users_active": active_users,
        "maintenance_mode": maint == "on",
        "maintenance_message": _get_setting(db, "maintenance_message"),
        "maintenance_until": _get_setting(db, "maintenance_until"),
        "last_backup_at": last_backup,
    }


# ── GET /api/system/health ────────────────────────────────────────────────────

@router.get("/health")
def system_health(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    require_system_admin(p)
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    return {
        "backend": "ok",
        "db": "ok" if db_ok else "error",
        "db_type": _db_type(),
        "environment": settings.ENVIRONMENT,
        "cookie_secure": settings.COOKIE_SECURE,
        "cors_origins": settings.cors_origins,
    }


# ── GET /api/system/version ───────────────────────────────────────────────────

@router.get("/version")
def system_version(p: Principal = Depends(get_principal)):
    require_system_admin(p)
    return {"app_version": APP_VERSION, "package_version": PACKAGE_VERSION}


# ── GET /api/system/migrations ───────────────────────────────────────────────

@router.get("/migrations")
def system_migrations(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    """Return the live Alembic revision(s) from the alembic_version table.

    Used by the staging deployment gate to verify migration b2c3d4e5f6a7 applied.
    Requires system_admin. Returns:
      revisions       — list of version_num rows (empty list = no migration ever ran)
      is_single_head  — true when exactly one revision present (expected state)
      revision        — the single revision string, or null if 0 or >1 rows
    """
    require_system_admin(p)
    try:
        rows = db.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        revisions = [r[0] for r in rows]
    except Exception as exc:
        return {
            "revisions": [],
            "is_single_head": False,
            "revision": None,
            "error": str(exc),
        }
    single = len(revisions) == 1
    return {
        "revisions": revisions,
        "is_single_head": single,
        "revision": revisions[0] if single else None,
    }


# ── GET /api/system/maintenance ──────────────────────────────────────────────

@router.get("/maintenance")
def get_maintenance(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    require_system_admin(p)
    return {
        "enabled": _get_setting(db, "maintenance_mode", "off") == "on",
        "message": _get_setting(db, "maintenance_message"),
        "until": _get_setting(db, "maintenance_until"),
        "updated_at": _get_setting(db, "maintenance_updated_at"),
        "block_reads": _get_setting(db, "maintenance_block_reads", "false") == "true",
        "block_logins": _get_setting(db, "maintenance_block_logins", "false") == "true",
    }


class MaintenanceIn(BaseModel):
    message: str | None = None
    until: str | None = None
    confirm: str = ""
    block_reads: bool = False
    block_logins: bool = False


@router.post("/maintenance/enable")
def enable_maintenance(body: MaintenanceIn, db: DBSession = Depends(get_db),
                       p: Principal = Depends(get_principal)):
    require_system_admin(p)
    if body.confirm != "ENABLE MAINTENANCE":
        raise HTTPException(400, detail={"error": "confirmation_required",
                                         "message": "Provide confirm='ENABLE MAINTENANCE' to proceed."})
    _set_setting(db, "maintenance_mode", "on", p.user_id)
    _set_setting(db, "maintenance_message", body.message or "System under maintenance. Please try again later.", p.user_id)
    _set_setting(db, "maintenance_until", body.until, p.user_id)
    _set_setting(db, "maintenance_block_reads", "true" if body.block_reads else "false", p.user_id)
    _set_setting(db, "maintenance_block_logins", "true" if body.block_logins else "false", p.user_id)
    _set_setting(db, "maintenance_updated_at",
                 datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), p.user_id)
    # DEF-14: drain/cancel any in-flight background jobs before activating the
    # write-block so they don't fail silently mid-task.  The Celery integration
    # is currently a synchronous stub (see dispatcher.py / DEF-08), so no
    # real jobs are queued; this check guards the future real-Celery path.
    in_flight = (db.query(JobStatus)
                 .filter(JobStatus.status.in_(["queued", "running"]))
                 .all())
    drained_count = 0
    for j in in_flight:
        j.status = "cancelled"
        j.error_message = "Cancelled: maintenance mode activated."
        j.completed_at = utcnow()
        drained_count += 1
    if drained_count:
        db.commit()

    audit(db, p, object_type="system", object_id="maintenance",
          action="maintenance_enabled",
          new={"message": body.message, "until": body.until,
               "block_reads": body.block_reads, "block_logins": body.block_logins,
               "drained_jobs": drained_count})
    from ..main import invalidate_maintenance_cache
    invalidate_maintenance_cache()
    return {"enabled": True, "message": body.message, "until": body.until,
            "block_reads": body.block_reads, "block_logins": body.block_logins,
            "drained_jobs": drained_count}


@router.post("/maintenance/disable")
def disable_maintenance(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    require_system_admin(p)
    _set_setting(db, "maintenance_mode", "off", p.user_id)
    _set_setting(db, "maintenance_block_reads", "false", p.user_id)
    _set_setting(db, "maintenance_block_logins", "false", p.user_id)
    _set_setting(db, "maintenance_updated_at",
                 datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), p.user_id)
    audit(db, p, object_type="system", object_id="maintenance", action="maintenance_disabled")
    from ..main import invalidate_maintenance_cache
    invalidate_maintenance_cache()
    return {"enabled": False, "block_reads": False, "block_logins": False}


# ── GET /api/system/scope-map ─────────────────────────────────────────────────

@router.get("/scope-map")
def scope_map(include_archived: bool = False, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    """Active Wings/Squadrons by default, matching every sibling list endpoint
    (/api/wings, /api/squadrons, national_overview) — pass include_archived=true
    to also return archived rows (for an authorised "Show archived" view)."""
    require_system_admin(p)
    wings = db.query(Wing)
    if not include_archived:
        wings = wings.filter(Wing.is_archived == False)  # noqa: E712
    out = []
    for w in wings.all():
        sqns = db.query(Squadron).filter(Squadron.wing_id == w.id)
        if not include_archived:
            sqns = sqns.filter(Squadron.is_archived == False)  # noqa: E712
        out.append({
            "wing_id": w.id,
            "wing_name": w.name,
            "wing_code": getattr(w, "code", None),
            "wing_is_archived": w.is_archived,
            "squadrons": [
                {"id": s.id, "name": s.name,
                 "unit_type": getattr(s, "unit_type", None),
                 "active_status": s.active_status,
                 "is_archived": s.is_archived}
                for s in sqns.all()
            ],
        })
    return {"wings": out}


# ── GET /api/system/audit-summary ────────────────────────────────────────────

@router.get("/audit-summary")
def audit_summary(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal),
                  limit: int = 100, action: str | None = None,
                  role: str | None = None, since: str | None = None):
    require_audit_access(p)
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    if role:
        q = q.filter(AuditLog.role == role)
    if since:
        try:
            dt = datetime.fromisoformat(since)
            q = q.filter(AuditLog.timestamp >= dt)
        except ValueError:
            raise HTTPException(400, detail={"error": "invalid_since_format"})
    logs = q.order_by(AuditLog.timestamp.desc()).limit(min(limit, 500)).all()
    # Never return access-code hashes, JWT secrets, or plaintext secrets in audit output
    return {"count": len(logs), "logs": [
        {
            "id": e.id,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "user_id": e.user_id,
            "role": e.role,
            "scope": e.scope,
            "wing_id": e.wing_id,
            "squadron_id": e.squadron_id,
            "object_type": e.object_type,
            "object_id": e.object_id,
            "action": e.action,
            "ip_address": e.ip_address,
        }
        for e in logs
    ]}


# ── GET /api/system/backups ───────────────────────────────────────────────────

@router.get("/backups")
def list_backups(p: Principal = Depends(get_principal)):
    require_system_admin(p)
    backup_dir = Path(settings.BACKUP_DIR)
    db_type = _db_type()
    if not backup_dir.exists():
        return {"backups": [], "backup_dir": str(backup_dir), "db_type": db_type}
    files = sorted(backup_dir.glob("*.db"), key=lambda f: f.stat().st_mtime, reverse=True)
    return {"backups": [
        {"filename": f.name,
         "size_bytes": f.stat().st_size,
         "created_at": datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc).isoformat()}
        for f in files[:20]
    ], "backup_dir": str(backup_dir), "db_type": db_type}


@router.post("/backups")
def create_backup(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    require_system_admin(p)
    if not settings.DATABASE_URL.startswith("sqlite"):
        raise HTTPException(400, detail={
            "error": "not_sqlite",
            "message": "File-copy backup is only available for SQLite (local demo). "
                       "Use your managed PostgreSQL provider's backup tools in production."
        })
    db_path_raw = settings.DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "")
    db_path = (Path(__file__).parent.parent.parent / db_path_raw).resolve()
    if not db_path.exists():
        raise HTTPException(404, detail={"error": "db_not_found", "path": str(db_path)})

    backup_dir = Path(settings.BACKUP_DIR)
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"aafc_tms_backup_{ts}.db"
    shutil.copy2(db_path, dest)
    size = dest.stat().st_size
    created_at = datetime.now(timezone.utc).isoformat()
    _set_setting(db, "last_backup_at", created_at, p.user_id)
    audit(db, p, object_type="system", object_id="backup", action="backup_created",
          new={"filename": dest.name, "size_bytes": size})
    return {"filename": dest.name, "size_bytes": size, "created_at": created_at}


# ── GET /api/system/backups/pg-dump ──────────────────────────────────────────

@router.get("/backups/pg-dump")
def pg_dump_backup(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    """Stream a pg_dump (custom format) of the PostgreSQL database directly to the
    authenticated system_admin's browser. Nothing is written to the server filesystem.
    DATABASE_URL is never returned, logged, or exposed in any response.
    """
    require_system_admin(p)
    url = settings.DATABASE_URL
    if "postgres" not in url:
        raise HTTPException(400, detail={
            "error": "not_postgresql",
            "message": "pg_dump is only available for PostgreSQL databases.",
        })

    parsed = urllib.parse.urlparse(url)
    qs = dict(urllib.parse.parse_qsl(parsed.query))
    sslmode = qs.get("sslmode", "prefer")

    # Pass credentials via environment — never via command-line arguments.
    env = dict(os.environ)
    env["PGPASSWORD"] = urllib.parse.unquote(parsed.password or "")
    env.pop("DATABASE_URL", None)   # prevent subprocess from inheriting the full URI

    hostname = parsed.hostname or ""
    port = str(parsed.port or 5432)
    username = parsed.username or "postgres"
    dbname = (parsed.path or "/postgres").lstrip("/") or "postgres"

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"aafc_tms_staging_{ts}.dump"

    cmd = [
        "pg_dump",
        "--format=custom",
        "--host", hostname,
        "--port", port,
        "--username", username,
        "--dbname", dbname,
        "--no-password",
        f"--sslmode={sslmode}",
    ]

    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
        )
    except FileNotFoundError:
        raise HTTPException(503, detail={
            "error": "pg_dump_not_found",
            "message": "pg_dump is not installed in this environment. "
                       "Ensure postgresql-client is installed in the Docker image.",
        })

    # Audit before streaming; ignore DB errors here so the download still starts,
    # but log so a failed audit write for a system_admin backup download is never
    # silently invisible (CLAUDE.md: "system_admin actions must be audited").
    try:
        _set_setting(db, "last_backup_at", datetime.now(timezone.utc).isoformat(), p.user_id)
        audit(db, p, object_type="system", object_id="backup", action="pg_dump_initiated",
              new={"filename": filename})
    except Exception:
        logging.exception("Failed to write audit log for pg_dump_initiated by user_id=%s", p.user_id)

    def _generate():
        try:
            while True:
                chunk = proc.stdout.read(65536)
                if not chunk:
                    break
                yield chunk
        finally:
            proc.stdout.close()
            proc.wait()

    return StreamingResponse(
        _generate(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── POST /api/system/bootstrap-staging ───────────────────────────────────────

class BootstrapIn(BaseModel):
    wing_code: str | None = None   # defaults to the first active Wing in the DB
    sqn_code: str | None = None    # defaults to first active Squadron under that Wing
    sqn_name: str | None = None    # name to use when creating the squadron (if absent)


@router.post("/bootstrap-staging")
def bootstrap_staging(body: BootstrapIn | None = None,
                      db: DBSession = Depends(get_db),
                      p: Principal = Depends(get_principal)):
    """One-time setup helper for staging / development environments.

    Creates the first available squadron under the requested (or first) wing,
    plus one account each for national_admin, wing_admin, and sqn_admin if no
    active account of that role+scope already exists.

    Accepts optional JSON body: {"wing_code": "7WG", "sqn_code": "703", "sqn_name": "703 SQN AAFC"}
    If omitted, uses the first active Wing and first active Squadron found.

    Returns newly created accounts with one-time access codes. Codes are never
    stored in plaintext — only the hash is persisted. Rejected in production.
    """
    require_system_admin(p)
    if settings.is_prod:
        raise HTTPException(403, detail={
            "error": "not_allowed_in_production",
            "message": "Bootstrap is not available in the production environment.",
        })

    bdy = body or BootstrapIn()
    results = []
    created_accounts = []

    nat = db.query(NationalEntity).first()
    if not nat:
        raise HTTPException(422, detail={
            "error": "national_entity_missing",
            "message": "No NationalEntity found. Run migrations and initial seed first.",
        })

    # Resolve wing: use provided code, or fall back to first active Wing.
    wing_q = db.query(Wing).filter(Wing.is_archived == False)  # noqa: E712
    if bdy.wing_code:
        wing_q = wing_q.filter(Wing.code == bdy.wing_code)
    wing = wing_q.first()
    if not wing:
        detail_msg = (
            f"Wing '{bdy.wing_code}' not found." if bdy.wing_code
            else "No active Wing found. Create one first via System Console → Scope Map."
        )
        raise HTTPException(422, detail={"error": "wing_not_found", "message": detail_msg})

    # Resolve squadron: use provided code under this wing, or fall back to first active.
    sqn_q = db.query(Squadron).filter(Squadron.wing_id == wing.id, Squadron.is_archived == False)  # noqa: E712
    if bdy.sqn_code:
        sqn_q = sqn_q.filter(Squadron.code == bdy.sqn_code)
    sqn = sqn_q.first()
    sqn_created = False
    if not sqn:
        sqn_code = bdy.sqn_code or "001"
        sqn_name = bdy.sqn_name or f"{sqn_code} Squadron AAFC"
        sqn = Squadron(wing_id=wing.id, code=sqn_code, name=sqn_name,
                       short_name=f"{sqn_code} SQN", unit_type="standard_squadron",
                       active_status=True, created_by=p.user_id)
        db.add(sqn)
        db.flush()
        audit(db, p, object_type="squadron", object_id=sqn.id, action="create",
              new={"code": sqn_code, "name": sqn_name, "wing": wing.code,
                   "source": "staging_bootstrap"})
        sqn_created = True
    results.append({"type": "squadron", "code": sqn.code, "name": sqn.name, "created": sqn_created})

    account_specs = [
        {"role": "national_admin", "display_name": "National Admin",
         "national_id": nat.id, "wing_id": None, "squadron_id": None},
        {"role": "wing_admin", "display_name": f"{wing.code} Wing Admin",
         "national_id": None, "wing_id": wing.id, "squadron_id": None},
        {"role": "sqn_admin", "display_name": f"{sqn.code} SQN Admin",
         "national_id": None, "wing_id": wing.id, "squadron_id": sqn.id},
    ]

    for spec in account_specs:
        q = db.query(User).filter(User.role == spec["role"], User.is_archived == False)  # noqa: E712
        if spec["squadron_id"]:
            q = q.filter(User.squadron_id == spec["squadron_id"])
        elif spec["wing_id"]:
            q = q.filter(User.wing_id == spec["wing_id"])
        existing = q.first()

        if existing:
            results.append({"type": "account", "role": spec["role"],
                            "display_name": existing.display_name, "created": False})
            continue

        u = User(display_name=spec["display_name"], role=spec["role"],
                 national_id=spec["national_id"], wing_id=spec["wing_id"],
                 squadron_id=spec["squadron_id"], active_status=True,
                 created_by=p.user_id)
        db.add(u)
        db.flush()

        plain = generate_code()
        ac = AccessCode(user_id=u.id, code_hash=hash_code(plain), active_status=True,
                        created_by=p.user_id, updated_by=p.user_id, updated_at=utcnow())
        db.add(ac)

        audit(db, p, object_type="account", object_id=u.id, action="account_created",
              new={"role": spec["role"], "display_name": spec["display_name"],
                   "source": "staging_bootstrap"})
        audit(db, p, object_type="access_code", object_id=u.id, action="code_generated",
              new={"source": "staging_bootstrap"})

        results.append({"type": "account", "role": spec["role"],
                        "display_name": spec["display_name"], "created": True})
        created_accounts.append({"role": spec["role"], "display_name": spec["display_name"],
                                  "new_code": plain})

    db.commit()

    return {
        "environment": settings.ENVIRONMENT,
        "results": results,
        "accounts_created": created_accounts,
        "notice": "Codes shown here will NOT be retrievable again. Record each code now.",
    }


@router.post("/reset-rate-limits")
def reset_rate_limits(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    """Test/staging-only: clear all rate-limit and login-lockout state.

    DEFECT-004 (general-release qualification): repeated/rapid automated test
    runs (Playwright e2e, load/staging validation) against a long-lived backend
    process were tripping the general API rate limiter, the DB-backed per-IP
    login limiter, and the per-account lockout -- producing flaky 429s/423s
    unrelated to the feature under test, with "restart the backend" as the
    only prior workaround. backend/tests/conftest.py already resets all three
    in-process before every pytest test; this is the same reset exposed over
    HTTP so an external test runner (a separate process) can call it between
    test files/runs without weakening any limiter's real thresholds. Rejected
    in production, same guard as bootstrap-staging above.

    Requires a normal system_admin bearer token -- no alternate auth path.
    Known limitation: if the IP this endpoint would clear is *already* fully
    locked out before it's called, the caller cannot log in to obtain that
    token either (login_blocked_db is checked before code verification for
    every login attempt, including a correct system_admin code), so this
    specific endpoint cannot self-heal that one edge case. That is an
    accepted gap, not silently worked around: an authentication bypass for
    this endpoint was considered and deliberately rejected, since it would
    weaken the same login-lockout protection this endpoint exists to reset --
    see docs/beta/15_known_limitations.md. In practice this only occurs if a
    *previous* run left the IP locked out and this reset was never called at
    its own start; the existing 900s lockout window (or, if urgent, a manual
    backend restart) remains the fallback for that specific case.
    """
    require_system_admin(p)
    if settings.is_prod:
        raise HTTPException(403, detail={
            "error": "not_allowed_in_production",
            "message": "Rate-limit reset is not available in the production environment.",
        })
    reset_rate_limiter()
    reset_api_rate_limiter()
    reset_api_rate_limiter_db(db)  # DEF-10: clear DB-backed per-IP table
    reset_user_api_rate_limiter_db(db)  # DEF-11: clear DB-backed per-account table
    db.query(IpLoginAttempt).delete()
    for ac in db.query(AccessCode).all():
        ac.failed_attempts = 0
        ac.locked_until = None
    db.commit()
    audit(db, p, object_type="system", object_id="rate_limits", action="reset_rate_limits")
    return {"ok": True}
