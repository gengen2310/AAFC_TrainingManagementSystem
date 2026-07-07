"""System Admin Console endpoints — system_admin role required for all privileged operations.

All state-changing actions are audited. No secrets, hashes, or access-code plaintext
are returned from any endpoint here.
"""
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
    User, Wing, Squadron, AuditLog, SystemSetting, AccessCode,
    PlanningYear, ParadeDate, Session, CurriculumItem, NationalEntity,
)
from ..permissions import Principal, require_system_admin, require_audit_access
from ..security import generate_code, hash_code
from ..services import audit

router = APIRouter(prefix="/api/system", tags=["system"])

APP_VERSION = "17.2.0"
PACKAGE_VERSION = "v17.2"


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
def system_migrations(p: Principal = Depends(get_principal)):
    require_system_admin(p)
    return {
        "expected_head": "r3s4t5u6v7w8",
        "current": _migration_head(),
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
    }


class MaintenanceIn(BaseModel):
    message: str | None = None
    until: str | None = None
    confirm: str = ""


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
    _set_setting(db, "maintenance_updated_at",
                 datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), p.user_id)
    audit(db, p, object_type="system", object_id="maintenance",
          action="maintenance_enabled",
          new={"message": body.message, "until": body.until})
    from ..main import invalidate_maintenance_cache
    invalidate_maintenance_cache()
    return {"enabled": True, "message": body.message, "until": body.until}


@router.post("/maintenance/disable")
def disable_maintenance(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    require_system_admin(p)
    _set_setting(db, "maintenance_mode", "off", p.user_id)
    _set_setting(db, "maintenance_updated_at",
                 datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), p.user_id)
    audit(db, p, object_type="system", object_id="maintenance", action="maintenance_disabled")
    from ..main import invalidate_maintenance_cache
    invalidate_maintenance_cache()
    return {"enabled": False}


# ── GET /api/system/scope-map ─────────────────────────────────────────────────

@router.get("/scope-map")
def scope_map(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    require_system_admin(p)
    wings = db.query(Wing).all()
    out = []
    for w in wings:
        sqns = db.query(Squadron).filter(Squadron.wing_id == w.id).all()
        out.append({
            "wing_id": w.id,
            "wing_name": w.name,
            "wing_code": getattr(w, "code", None),
            "squadrons": [
                {"id": s.id, "name": s.name,
                 "unit_type": getattr(s, "unit_type", None),
                 "active_status": s.active_status}
                for s in sqns
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

    # Audit before streaming; ignore DB errors here so the download still starts.
    try:
        _set_setting(db, "last_backup_at", datetime.now(timezone.utc).isoformat(), p.user_id)
        audit(db, p, object_type="system", object_id="backup", action="pg_dump_initiated",
              new={"filename": filename})
    except Exception:
        pass

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

@router.post("/bootstrap-staging")
def bootstrap_staging(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    """One-time setup helper for staging / development environments.

    Creates 703SQN under 7WG (if missing) and one account each for
    national_admin, wing_admin (7WG), and sqn_admin (703SQN) if no active
    account of that role+scope already exists.

    Returns newly created accounts with one-time access codes. Codes are never
    stored in plaintext — only the hash is persisted. Rejected in production.
    """
    require_system_admin(p)
    env = settings.ENVIRONMENT or ""
    if env.lower() == "production":
        raise HTTPException(403, detail={
            "error": "not_allowed_in_production",
            "message": "Bootstrap is not available in the production environment.",
        })

    results = []
    created_accounts = []

    nat = db.query(NationalEntity).first()
    if not nat:
        raise HTTPException(422, detail={
            "error": "national_entity_missing",
            "message": "No NationalEntity found. Run migrations and initial seed first.",
        })

    wing = db.query(Wing).filter(Wing.code == "7WG", Wing.is_archived == False).first()  # noqa: E712
    if not wing:
        raise HTTPException(422, detail={
            "error": "7WG_not_found",
            "message": "7WG not found. Create it first via System Console → Scope Map → Create Wing.",
        })

    # Create 703SQN if missing
    sqn = db.query(Squadron).filter(Squadron.code == "703", Squadron.is_archived == False).first()  # noqa: E712
    sqn_created = False
    if not sqn:
        sqn = Squadron(wing_id=wing.id, code="703", name="703 Squadron AAFC",
                       short_name="703 SQN", unit_type="standard_squadron",
                       active_status=True, created_by=p.user_id)
        db.add(sqn)
        db.flush()
        audit(db, p, object_type="squadron", object_id=sqn.id, action="create",
              new={"code": "703", "name": "703 Squadron AAFC", "wing": "7WG",
                   "source": "staging_bootstrap"})
        sqn_created = True
    results.append({"type": "squadron", "code": "703", "name": sqn.name, "created": sqn_created})

    account_specs = [
        {"role": "national_admin", "display_name": "National Admin",
         "national_id": nat.id, "wing_id": None, "squadron_id": None},
        {"role": "wing_admin", "display_name": "7WG Wing Admin",
         "national_id": None, "wing_id": wing.id, "squadron_id": None},
        {"role": "sqn_admin", "display_name": "703 SQN Admin",
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
        "environment": env,
        "results": results,
        "accounts_created": created_accounts,
        "notice": "Codes shown here will NOT be retrievable again. Record each code now.",
    }
