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
# to exercise the missing route, not by a direct check. Railway sets this env
# var automatically at runtime; "local" is the same fallback convention the
# frontends already use for local dev where it's unset.
_BUILD_COMMIT = os.environ.get("RAILWAY_GIT_COMMIT_SHA", "local")


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
def ui_config():
    """Return public, non-secret frontend configuration values."""
    return {
        "planning_workspace_url": settings.PLANNING_WORKSPACE_URL or None,
        "training_year": settings.TRAINING_YEAR,
        "environment": settings.ENVIRONMENT,
    }
