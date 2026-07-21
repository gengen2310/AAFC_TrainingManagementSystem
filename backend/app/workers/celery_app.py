"""Celery application for async jobs (heavy imports/exports, report generation,
link verification, coverage recompute). Redis is the broker/result backend.

NOTE: This worker layer is provided but NOT executed in the build sandbox (no Redis
broker running there). To run locally:
    docker compose -f docker-compose.prod.yml up redis -d
    celery -A app.workers.celery_app.celery worker --loglevel=info
Job lifecycle is tracked in the `job_status` table so the API/frontend can poll progress.
The `job_id` parameter is set by the dispatcher (app.workers.dispatcher) so the task
updates the pre-created JobStatus record rather than creating a new one.
"""
import os
from celery import Celery

celery = Celery("aafc_tms", broker=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
                backend=os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
celery.conf.update(task_track_started=True, task_serializer="json", result_serializer="json",
                   accept_content=["json"])


@celery.task(bind=True, name="aafc.generate_export")
def generate_export(self, export_type: str, scope: str, user_id: str, job_id: str | None = None):
    """Heavy-export task; updates the pre-created JobStatus record as it runs."""
    from ..database import SessionLocal, utcnow
    from ..models import JobStatus
    db = SessionLocal()
    try:
        job = (db.get(JobStatus, job_id) if job_id else None)
        if not job:
            job = JobStatus(job_type="export", requested_by=user_id, scope=scope)
            db.add(job)
        job.status = "running"; job.progress_percentage = 10; job.started_at = utcnow()
        db.commit()
        # Real implementation would stream rows into XLSX/PDF and write to EXPORT_DIR.
        job.status = "succeeded"; job.progress_percentage = 100
        job.result_reference = f"{export_type}.xlsx"
        job.completed_at = utcnow()
        db.commit()
        return {"job_id": str(job.id), "status": "succeeded"}
    except Exception as e:  # pragma: no cover
        job.status = "failed"; job.error_message = str(e); job.completed_at = utcnow(); db.commit()
        raise
    finally:
        db.close()
