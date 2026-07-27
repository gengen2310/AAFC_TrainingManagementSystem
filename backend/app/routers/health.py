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
    except Exception as e:  # pragma: no cover
        return {"status": "degraded", "db": str(e)}


@router.get("/ready")
def ready(db: DBSession = Depends(get_db)):
    from ..models import Squadron
    try:
        count = db.query(Squadron).count()
        return {"status": "ready", "squadrons": count}
    except Exception as e:  # pragma: no cover
        return {"status": "not_ready", "error": str(e)}


@router.get("/ui-config")
def ui_config():
    """Return public, non-secret frontend configuration values."""
    return {
        "planning_workspace_url": settings.PLANNING_WORKSPACE_URL or None,
        "training_year": settings.TRAINING_YEAR,
        "environment": settings.ENVIRONMENT,
    }
