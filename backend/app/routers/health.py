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
def ui_config():
    """Return public, non-secret frontend configuration values."""
    return {
        "planning_workspace_url": settings.PLANNING_WORKSPACE_URL or None,
        "training_year": settings.TRAINING_YEAR,
        "environment": settings.ENVIRONMENT,
    }
