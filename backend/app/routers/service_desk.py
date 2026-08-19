import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session as DBSession

from ..database import get_db, utcnow
from ..models import Squadron, ServiceTicket, AuditLog
from ..dependencies import get_principal
from ..permissions import Principal, require_role
from ..services import audit

router = APIRouter(prefix="/api", tags=["service_desk"])

_VALID_STATUSES = frozenset({"open", "in_progress", "resolved"})


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class TicketCreateIn(BaseModel):
    rank: str
    first_name: str
    last_name: str
    email: EmailStr
    squadron_id: str
    description: str

    @field_validator("rank", "first_name", "last_name", "squadron_id", mode="before")
    @classmethod
    def strip_and_require(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("field is required and must not be blank")
        return v

    @field_validator("description", mode="before")
    @classmethod
    def description_min_length(cls, v):
        v = (v or "").strip()
        if len(v) < 10:
            raise ValueError("description must be at least 10 characters")
        return v


class TicketUpdateIn(BaseModel):
    status: str | None = None
    admin_notes: str | None = None

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v):
        if v is not None and v not in _VALID_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(_VALID_STATUSES))}")
        return v


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ticket_out(t: ServiceTicket) -> dict:
    return {
        "ticket_id": t.id,
        "rank": t.rank,
        "first_name": t.first_name,
        "last_name": t.last_name,
        "email": t.email,
        "squadron_id": t.squadron_id,
        "squadron_name": t.squadron.name if t.squadron else None,
        "description": t.description,
        "status": t.status,
        "admin_notes": t.admin_notes,
        "created_at": t.created_at.isoformat() + "Z" if t.created_at else None,
        "resolved_at": t.resolved_at.isoformat() + "Z" if t.resolved_at else None,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/public/squadrons")
def public_squadrons(db: DBSession = Depends(get_db)):
    """Active squadrons list for pre-login ticket form — no auth required."""
    sqns = (
        db.query(Squadron)
        .filter(Squadron.is_archived == False)  # noqa: E712
        .order_by(Squadron.name)
        .all()
    )
    return [{"squadron_id": s.id, "name": s.name} for s in sqns]


@router.post("/service-desk/tickets", status_code=201)
def create_ticket(body: TicketCreateIn, db: DBSession = Depends(get_db)):
    """Submit a new service ticket — public, no auth required."""
    sqn = db.query(Squadron).filter(
        Squadron.id == body.squadron_id,
        Squadron.is_archived == False  # noqa: E712
    ).first()
    if not sqn:
        raise HTTPException(404, detail={"error": "squadron_not_found",
                                          "message": "Squadron not found or archived."})

    ticket = ServiceTicket(
        rank=body.rank,
        first_name=body.first_name,
        last_name=body.last_name,
        email=body.email,
        squadron_id=body.squadron_id,
        description=body.description,
        status="open",
    )
    db.add(ticket)
    db.commit()
    return {"ok": True, "ticket_id": ticket.id}


@router.get("/service-desk/tickets")
def list_tickets(
    status: str | None = Query(default=None),
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """List tickets, scoped by caller's role."""
    if p.role in ("auditor", "sqn_general"):
        raise HTTPException(403, detail={"error": "forbidden"})

    q = db.query(ServiceTicket)

    if p.role == "wing_admin":
        q = (
            q.join(Squadron, ServiceTicket.squadron_id == Squadron.id)
            .filter(Squadron.wing_id == p.wing_id)
        )
    elif p.role == "sqn_admin":
        q = q.filter(ServiceTicket.squadron_id == p.squadron_id)
    # national_admin and system_admin see all — no additional filter

    if status is not None:
        if status not in _VALID_STATUSES:
            raise HTTPException(400, detail={"error": "invalid_status"})
        q = q.filter(ServiceTicket.status == status)

    tickets = q.order_by(ServiceTicket.created_at.desc()).all()
    return [_ticket_out(t) for t in tickets]


@router.patch("/service-desk/tickets/{ticket_id}")
def update_ticket(
    ticket_id: str,
    body: TicketUpdateIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Update status and/or admin notes — system_admin only."""
    require_role(p, "system_admin")

    ticket = db.get(ServiceTicket, ticket_id)
    if not ticket:
        raise HTTPException(404, detail={"error": "not_found"})

    old_snapshot = {"status": ticket.status, "admin_notes": ticket.admin_notes}
    changed: dict = {}

    if body.status is not None:
        changed["status"] = body.status
        ticket.status = body.status
        if body.status == "resolved" and ticket.resolved_at is None:
            ticket.resolved_at = utcnow()
        elif body.status != "resolved":
            ticket.resolved_at = None

    if body.admin_notes is not None:
        changed["admin_notes_updated"] = True
        ticket.admin_notes = body.admin_notes

    db.commit()

    audit(
        db, p,
        object_type="service_ticket",
        object_id=ticket_id,
        action="updated",
        old=old_snapshot,
        new={**old_snapshot, **changed},
    )
    return {"ok": True}
