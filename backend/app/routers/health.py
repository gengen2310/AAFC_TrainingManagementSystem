import logging
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session as DBSession
from ..database import get_db
from ..config import settings

router = APIRouter(prefix="/api/health", tags=["health"])


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
        return {"status": "ready", "squadrons": count}
    except Exception:  # pragma: no cover
        logging.exception("readiness check failed")
        return {"status": "not_ready", "error": "error"}


@router.get("/ui-config")
def ui_config():
    """Return public, non-secret frontend configuration values."""
    return {
        "planning_workspace_url": settings.PLANNING_WORKSPACE_URL or None,
        "training_year": settings.TRAINING_YEAR,
        "environment": settings.ENVIRONMENT,
    }
