"""Celery application for async jobs (heavy imports/exports, report generation,
link verification, coverage recompute). Redis is the broker/result backend.

NOTE: This worker layer is provided but NOT executed in the build sandbox (no Redis
broker running there). To run locally:
    docker compose -f docker-compose.prod.yml up redis -d
    celery -A app.workers.celery_app.celery worker --loglevel=info
Job lifecycle is tracked in the `job_status` table so the API/frontend can poll progress.
"""
import os
from celery import Celery

celery = Celery("aafc_tms", broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
                backend=os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
celery.conf.update(task_track_started=True, task_serializer="json", result_serializer="json",
                   accept_content=["json"])


@celery.task(bind=True, name="aafc.generate_export")
def generate_export(self, export_type: str, scope: str, user_id: str):
    """Placeholder heavy-export task; updates JobStatus as it runs."""
    from ..database import SessionLocal
    from ..models import JobStatus
    db = SessionLocal()
    job = JobStatus(job_type="export", requested_by=user_id, scope=scope, status="running",
                    progress_percentage=10)
    db.add(job); db.commit()
    try:
        # Real implementation would stream rows into XLSX/PDF and write to EXPORT_DIR.
        job.status = "succeeded"; job.progress_percentage = 100
        job.result_reference = f"{export_type}.xlsx"
        db.commit()
        return {"job_id": job.id, "status": "succeeded"}
    except Exception as e:  # pragma: no cover
        job.status = "failed"; job.error_message = str(e); db.commit()
        raise
    finally:
        db.close()
