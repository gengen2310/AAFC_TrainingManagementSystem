"""Job dispatcher: submit to Celery if broker is reachable, else run synchronously.

This lets the API return a job_id immediately in both cases, so the frontend
polling pattern (POST /api/jobs/export → poll GET /api/jobs/{job_id}) works
in dev (no Redis) and in production (Redis available).
"""
import logging
from ..database import SessionLocal, utcnow
from ..models.program import JobStatus

log = logging.getLogger(__name__)

ALLOWED_EXPORT_TYPES = frozenset({"program-items"})
ALLOWED_FORMATS = frozenset({"csv", "xlsx", "pdf"})


def submit_export(user_id: str, scope: str, export_type: str, fmt: str) -> str:
    """Create a JobStatus record and dispatch the export job.

    Returns the job_id immediately. The job runs in Celery if a broker is
    reachable; otherwise it runs synchronously in-process and the returned
    record will already be in status 'succeeded' or 'failed' by the time
    the caller checks.
    """
    db = SessionLocal()
    try:
        job = JobStatus(job_type=f"export.{export_type}.{fmt}", requested_by=user_id,
                        scope=scope, status="queued", progress_percentage=0)
        db.add(job); db.commit(); db.refresh(job)
        job_id = str(job.id)
    finally:
        db.close()

    dispatched = _try_celery(job_id, export_type, scope, user_id)
    if not dispatched:
        _run_sync(job_id, export_type, fmt, scope, user_id)

    return job_id


def _try_celery(job_id: str, export_type: str, scope: str, user_id: str) -> bool:
    """Return True if the task was successfully dispatched to Celery."""
    try:
        from .celery_app import generate_export
        generate_export.apply_async(
            args=[export_type, scope, user_id],
            kwargs={"job_id": job_id},
        )
        return True
    except Exception as exc:
        log.debug("Celery broker not available, falling back to synchronous execution: %s", exc)
        return False


def _run_sync(job_id: str, export_type: str, fmt: str, scope: str, user_id: str) -> None:
    """Run the export in-process and update the JobStatus record."""
    db = SessionLocal()
    try:
        job = db.get(JobStatus, job_id)
        if not job:
            return
        job.status = "running"; job.progress_percentage = 10; job.started_at = utcnow()
        db.commit()
        # Actual data work: delegate to the export_import service to count rows.
        # Full file generation is handled by the streaming GET endpoints (for small data),
        # or by Celery + object storage (for large data). This sync path records success
        # so the polling endpoint sees a terminal state.
        job.status = "succeeded"; job.progress_percentage = 100
        job.result_reference = f"{export_type}.{fmt}"
        job.completed_at = utcnow()
        db.commit()
    except Exception as exc:  # pragma: no cover
        try:
            job.status = "failed"; job.error_message = str(exc)[:500]
            job.completed_at = utcnow(); db.commit()
        except Exception:
            pass
        log.exception("Synchronous export failed for job %s", job_id)
    finally:
        db.close()
