from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session as DBSession

from ..database import get_db, utcnow
from ..models import Squadron, Wing, ServiceTicket, ServiceDeskEmailConfig
from ..models.service_desk_email_config import ServiceDeskEmailConfig as _EmailCfg
from ..dependencies import get_principal
from ..permissions import Principal, require_role
from ..services import audit
from ..email_service import send_ticket_notification

router = APIRouter(prefix="/api", tags=["service_desk"])

_VALID_STATUSES = frozenset({"open", "in_progress", "resolved"})
_VALID_CATEGORIES = frozenset({
    "account_access", "training_data", "technical_error", "feature_request", "other"
})
_CATEGORY_LABELS = {
    "account_access": "Account Access",
    "training_data": "Training Data",
    "technical_error": "Technical Error",
    "feature_request": "Feature Request",
    "other": "Other",
}
_EDITABLE_ROLES = frozenset({"system_admin", "wing_admin", "national_admin"})


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class TicketCreateIn(BaseModel):
    rank: str
    first_name: str
    last_name: str
    email: EmailStr
    squadron_id: str | None = None  # null when submitting from wing/national context
    unit_name: str | None = None    # display name; derived from squadron if squadron_id given
    category: str = "other"
    description: str

    @field_validator("rank", "first_name", "last_name", mode="before")
    @classmethod
    def strip_and_require(cls, v):
        v = (v or "").strip()
        if not v:
            raise ValueError("field is required and must not be blank")
        return v

    @field_validator("category", mode="before")
    @classmethod
    def validate_category(cls, v):
        v = (v or "other").strip().lower()
        if v not in _VALID_CATEGORIES:
            return "other"
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
    assigned_to_name: str | None = None

    @field_validator("status", mode="before")
    @classmethod
    def validate_status(cls, v):
        if v is not None and v not in _VALID_STATUSES:
            raise ValueError(f"status must be one of: {', '.join(sorted(_VALID_STATUSES))}")
        return v


class EmailConfigIn(BaseModel):
    scope: str          # "system" | "national" | "wing"
    wing_id: str | None = None
    notification_email: str

    @field_validator("scope", mode="before")
    @classmethod
    def validate_scope(cls, v):
        if v not in ("system", "national", "wing"):
            raise ValueError("scope must be system, national, or wing")
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
        "unit_name": t.unit_name or (t.squadron.name if t.squadron else None),
        "category": t.category or "other",
        "description": t.description,
        "status": t.status,
        "admin_notes": t.admin_notes,
        "assigned_to_name": t.assigned_to_name,
        "created_at": t.created_at.isoformat() + "Z" if t.created_at else None,
        "resolved_at": t.resolved_at.isoformat() + "Z" if t.resolved_at else None,
    }


def _get_notification_recipients(db: DBSession, wing_id: str | None) -> list[str]:
    """Collect active notification email addresses for a new ticket."""
    scopes = ["system", "national"]
    if wing_id:
        scopes.append("wing")

    configs = db.query(_EmailCfg).filter(_EmailCfg.scope.in_(scopes)).all()
    emails: list[str] = []
    for cfg in configs:
        if cfg.scope == "wing" and cfg.wing_id != wing_id:
            continue
        if cfg.notification_email and cfg.notification_email.strip():
            emails.append(cfg.notification_email.strip())
    return list(dict.fromkeys(emails))  # deduplicate preserving order


# ── Public endpoints ──────────────────────────────────────────────────────────

@router.get("/public/squadrons")
def public_squadrons(db: DBSession = Depends(get_db)):
    """Active squadrons list — no auth required. Kept for backwards compatibility."""
    sqns = (
        db.query(Squadron)
        .filter(Squadron.is_archived == False)  # noqa: E712
        .order_by(Squadron.name)
        .all()
    )
    return [{"squadron_id": s.id, "name": s.name} for s in sqns]


@router.get("/public/units")
def public_units(db: DBSession = Depends(get_db)):
    """All active wings and squadrons for the ticket submission typeahead — no auth required."""
    wings = (
        db.query(Wing)
        .filter(Wing.is_archived == False)  # noqa: E712
        .order_by(Wing.name)
        .all()
    )
    squadrons = (
        db.query(Squadron)
        .filter(Squadron.is_archived == False)  # noqa: E712
        .order_by(Squadron.name)
        .all()
    )
    result = []
    for w in wings:
        result.append({"unit_id": w.id, "name": w.name, "type": "wing"})
    for s in squadrons:
        result.append({"unit_id": s.id, "name": s.name, "type": "squadron"})
    return result


# ── Ticket CRUD ───────────────────────────────────────────────────────────────

@router.post("/service-desk/tickets", status_code=201)
def create_ticket(body: TicketCreateIn, db: DBSession = Depends(get_db)):
    """Submit a new service ticket — public, no auth required."""
    resolved_wing_id: str | None = None
    resolved_unit_name: str | None = body.unit_name

    if body.squadron_id:
        sqn = db.query(Squadron).filter(
            Squadron.id == body.squadron_id,
            Squadron.is_archived == False  # noqa: E712
        ).first()
        if not sqn:
            raise HTTPException(404, detail={"error": "squadron_not_found",
                                              "message": "Squadron not found or archived."})
        resolved_wing_id = sqn.wing_id
        resolved_unit_name = resolved_unit_name or sqn.name
    elif not resolved_unit_name:
        raise HTTPException(422, detail={"error": "unit_required",
                                          "message": "Either squadron_id or unit_name is required."})

    ticket = ServiceTicket(
        rank=body.rank,
        first_name=body.first_name,
        last_name=body.last_name,
        email=body.email,
        squadron_id=body.squadron_id,
        unit_name=resolved_unit_name,
        category=body.category,
        description=body.description,
        status="open",
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    # Send notification email asynchronously — failure must not affect the response
    recipients = _get_notification_recipients(db, resolved_wing_id)
    ticket_data = {
        "ticket_id": ticket.id,
        "rank": ticket.rank,
        "first_name": ticket.first_name,
        "last_name": ticket.last_name,
        "email": ticket.email,
        "unit_name": resolved_unit_name,
        "category": ticket.category,
        "description": ticket.description,
        "created_at": ticket.created_at.isoformat() + "Z" if ticket.created_at else "",
    }
    try:
        send_ticket_notification(ticket_data, recipients)
    except Exception:
        pass  # already handled and logged inside send_ticket_notification

    return {"ok": True, "ticket_id": ticket.id}


@router.get("/service-desk/tickets")
def list_tickets(
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
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

    if category is not None:
        if category not in _VALID_CATEGORIES:
            raise HTTPException(400, detail={"error": "invalid_category"})
        q = q.filter(ServiceTicket.category == category)

    tickets = q.order_by(ServiceTicket.created_at.desc()).all()
    return [_ticket_out(t) for t in tickets]


@router.patch("/service-desk/tickets/{ticket_id}")
def update_ticket(
    ticket_id: str,
    body: TicketUpdateIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Update status, admin notes, and/or assignee.

    system_admin: all tickets.
    national_admin: all tickets.
    wing_admin: tickets belonging to their wing's squadrons only.
    """
    require_role(p, "system_admin", "national_admin", "wing_admin")

    ticket = db.get(ServiceTicket, ticket_id)
    if not ticket:
        raise HTTPException(404, detail={"error": "not_found"})

    # wing_admin scope check: the ticket's squadron must belong to their wing
    if p.role == "wing_admin":
        if not ticket.squadron_id:
            raise HTTPException(403, detail={"error": "forbidden"})
        sqn = db.get(Squadron, ticket.squadron_id)
        if not sqn or sqn.wing_id != p.wing_id:
            raise HTTPException(403, detail={"error": "forbidden"})

    old_snapshot = {
        "status": ticket.status,
        "admin_notes": ticket.admin_notes,
        "assigned_to_name": ticket.assigned_to_name,
    }
    changed: dict = {}

    if body.status is not None:
        changed["status"] = body.status
        ticket.status = body.status
        if body.status == "resolved" and ticket.resolved_at is None:
            ticket.resolved_at = utcnow()
        elif body.status != "resolved":
            ticket.resolved_at = None

    if body.admin_notes is not None:
        changed["admin_notes"] = body.admin_notes
        ticket.admin_notes = body.admin_notes

    if body.assigned_to_name is not None:
        changed["assigned_to_name"] = body.assigned_to_name
        ticket.assigned_to_name = body.assigned_to_name

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


# ── Email config ──────────────────────────────────────────────────────────────

@router.get("/service-desk/email-config")
def get_email_config(
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Return notification email configuration visible to this role."""
    require_role(p, "system_admin", "national_admin", "wing_admin")

    if p.role == "system_admin":
        configs = db.query(_EmailCfg).all()
    elif p.role == "national_admin":
        configs = db.query(_EmailCfg).filter(_EmailCfg.scope.in_(["system", "national"])).all()
    else:  # wing_admin
        configs = db.query(_EmailCfg).filter(
            (_EmailCfg.scope == "wing") & (_EmailCfg.wing_id == p.wing_id)
        ).all()

    return [
        {
            "id": c.id,
            "scope": c.scope,
            "wing_id": c.wing_id,
            "notification_email": c.notification_email,
            "updated_at": c.updated_at.isoformat() + "Z" if c.updated_at else None,
        }
        for c in configs
    ]


@router.put("/service-desk/email-config")
def upsert_email_config(
    body: EmailConfigIn,
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Create or update a notification email address for a scope."""
    require_role(p, "system_admin", "national_admin", "wing_admin")

    # Permission scope checks
    if p.role == "wing_admin":
        if body.scope != "wing" or body.wing_id != p.wing_id:
            raise HTTPException(403, detail={"error": "forbidden"})
    elif p.role == "national_admin":
        if body.scope not in ("national", "system"):
            raise HTTPException(403, detail={"error": "forbidden"})
        if body.scope == "system":
            # national_admin cannot change system_admin email
            raise HTTPException(403, detail={"error": "forbidden"})

    q = db.query(_EmailCfg).filter(_EmailCfg.scope == body.scope)
    if body.scope == "wing":
        if not body.wing_id:
            raise HTTPException(422, detail={"error": "wing_id required for wing scope"})
        q = q.filter(_EmailCfg.wing_id == body.wing_id)

    existing = q.first()
    if existing:
        existing.notification_email = body.notification_email
        existing.updated_at = utcnow()
        existing.updated_by_user_id = p.user_id if hasattr(p, "user_id") else None
    else:
        cfg = _EmailCfg(
            scope=body.scope,
            wing_id=body.wing_id if body.scope == "wing" else None,
            notification_email=body.notification_email,
            updated_by_user_id=p.user_id,
        )
        db.add(cfg)

    db.commit()

    audit(
        db, p,
        object_type="service_desk_email_config",
        object_id=f"{body.scope}:{body.wing_id or ''}",
        action="updated",
        old={},
        new={"scope": body.scope, "wing_id": body.wing_id, "notification_email": body.notification_email},
    )
    return {"ok": True}
