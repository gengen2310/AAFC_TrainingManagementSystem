import logging
import os
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session as DBSession
from ..database import get_db
from ..config import settings

router = APIRouter(prefix="/api/health", tags=["health"])

# REM-112: neither frontend service ever silently drifts behind main without a
# way to tell -- both inject RAILWAY_GIT_COMMIT_SHA into a build fingerprint at
# container start (see frontend/docker-entrypoint.sh, connected-frontend's
# equivalent). The backend had no equivalent at all, so a staging redeploy gap
# like REM-111/REM-112 (a merged endpoint 404ing on staging for ~24h because
# nothing had redeployed) could only be caught by a regression test happening
# to exercise the missing route, not by a direct check.
#
# RAILWAY_GIT_COMMIT_SHA is NOT reliable for this project's actual deploy
# method: confirmed live (2026-08-10) that it stays stale across `railway up`
# CLI uploads (this repo's real deployment mechanism for all 3 services, see
# docs/beta/00_release_state.md's own prior finding: "meta.commitSha: null...
# there is no git commit on record for what is actually running in
# production" for CLI-pushed deploys) -- it only reflects a GitHub-
# integration-triggered build, which this project's services don't use.
# APP_BUILD_COMMIT is a project-controlled variable instead: set explicitly
# via `railway variable set APP_BUILD_COMMIT=$(git rev-parse HEAD) ...`
# immediately before each `railway up` (see
# backend/scripts/check_staging_freshness.py's own docstring for the full
# deploy-step sequence). Falls back to RAILWAY_GIT_COMMIT_SHA in case a
# future deploy method DOES populate it correctly, then "local" for dev.
_BUILD_COMMIT = os.environ.get("APP_BUILD_COMMIT") or os.environ.get("RAILWAY_GIT_COMMIT_SHA", "local")


@router.get("")
def health():
    return {"status": "ok"}


@router.get("/db")
def health_db(db: DBSession = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "db": "ok"}
    except Exception:  # pragma: no cover
        # Unauthenticated endpoint -- never echo the raw driver exception (it
        # can include internal hostnames/schema details), just log it server-side.
        logging.exception("health_db check failed")
        return {"status": "degraded", "db": "error"}


@router.get("/ready")
def ready(db: DBSession = Depends(get_db)):
    from ..models import Squadron
    try:
        count = db.query(Squadron).count()
        return {"status": "ready", "squadrons": count, "commit": _BUILD_COMMIT}
    except Exception:  # pragma: no cover
        logging.exception("readiness check failed")
        return {"status": "not_ready", "error": "error", "commit": _BUILD_COMMIT}


@router.get("/ui-config")
def ui_config(db: DBSession = Depends(get_db)):
    """Return public, non-secret frontend configuration values, including maintenance state.

    maintenance_phase: "normal" | "pending" | "locked"
      normal  — no maintenance active
      pending — maintenance enabled but drain window in progress; writes not yet blocked
      locked  — maintenance fully active; writes blocked
    maintenance_pending_until: ISO timestamp (or null) — when pending phase ends
    maintenance_active: true when phase is "pending" OR "locked" (backward compat)
    """
    from ..models import SystemSetting
    from ..main import _compute_phase
    maint_row = db.get(SystemSetting, "maintenance_mode")
    # "on" is the canonical value set by enable_maintenance; guard "maintenance_enabled" (legacy/stale string)
    active = maint_row is not None and maint_row.value in ("on", "maintenance_enabled")
    maint_title_row = db.get(SystemSetting, "maintenance_title")
    maint_msg_row = db.get(SystemSetting, "maintenance_message")
    pu_row = db.get(SystemSetting, "maintenance_pending_until")
    pending_until_iso = pu_row.value if pu_row else None
    phase = _compute_phase(active, pending_until_iso)
    return {
        "planning_workspace_url": settings.PLANNING_WORKSPACE_URL or None,
        "training_year": settings.TRAINING_YEAR,
        "environment": settings.ENVIRONMENT,
        "maintenance_active": active,
        "maintenance_phase": phase,
        "maintenance_pending_until": pending_until_iso,
        "maintenance_title": (maint_title_row.value if maint_title_row else None) or "Maintenance",
        "maintenance_message": (maint_msg_row.value if maint_msg_row else None) or "System under maintenance. Please try again later.",
    }
