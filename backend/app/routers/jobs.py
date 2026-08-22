"""Background job management: submit export jobs and poll status.

The frontend pattern:
  POST /api/jobs/export  →  {"job_id": "...", "status": "queued"}
  GET  /api/jobs/{id}   →  poll until status is "succeeded" or "failed"

The dispatcher falls back to synchronous execution when no Celery broker is
reachable (dev/test environments without Redis). In that case the job is
already in a terminal state by the time the POST returns.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from ..database import get_db, iso_z
from ..dependencies import get_principal
from ..permissions import Principal, require_role
from ..models.program import JobStatus
from ..workers.dispatcher import submit_export, ALLOWED_EXPORT_TYPES, ALLOWED_FORMATS

router = APIRouter(prefix="/api", tags=["jobs"])

_OVERSIGHT_ROLES = ("wing_admin", "wing_viewer", "national_admin", "national_viewer",
                    "system_admin", "auditor")


def _scope_for(p: Principal) -> str:
    if p.is_national:
        return "national"
    if p.is_wing:
        return "wing"
    return "squadron"


@router.get("/jobs/{job_id}")
def get_job(job_id: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    """Poll a background job. Callers may only read their own jobs; oversight roles see all."""
    job = db.get(JobStatus, job_id)
    if not job:
        raise HTTPException(404, detail={"error": "job_not_found"})
    if job.requested_by != p.user_id and p.role not in _OVERSIGHT_ROLES:
        raise HTTPException(403, detail={"error": "forbidden"})
    return {
        "job_id": job_id,
        "job_type": job.job_type,
        "status": job.status,
        "progress_percentage": job.progress_percentage,
        "result_reference": job.result_reference,
        "error_message": job.error_message,
        "started_at": iso_z(job.started_at) if job.started_at else None,
        "completed_at": iso_z(job.completed_at) if job.completed_at else None,
        "created_at": iso_z(job.created_at) if job.created_at else None,
    }


class ExportJobIn(BaseModel):
    export_type: str = "program-items"
    format: str = "csv"


@router.post("/jobs/export")
def submit_export_job(body: ExportJobIn, db: DBSession = Depends(get_db),
                      p: Principal = Depends(get_principal)):
    """Submit a background export job. Returns a job_id for polling."""
    require_role(p, "sqn_admin", "wing_admin", "wing_viewer", "national_admin",
                 "national_viewer", "system_admin", "auditor")
    if body.export_type not in ALLOWED_EXPORT_TYPES:
        raise HTTPException(400, detail={"error": "unsupported_export_type",
                                         "allowed": sorted(ALLOWED_EXPORT_TYPES)})
    if body.format not in ALLOWED_FORMATS:
        raise HTTPException(400, detail={"error": "unsupported_format",
                                         "allowed": sorted(ALLOWED_FORMATS)})
    scope = _scope_for(p)
    job_id = submit_export(user_id=p.user_id, scope=scope,
                           export_type=body.export_type, fmt=body.format)
    # Re-read terminal status from DB (sync fallback may have completed already).
    job = db.get(JobStatus, job_id)
    return {"job_id": job_id, "status": job.status if job else "queued"}
