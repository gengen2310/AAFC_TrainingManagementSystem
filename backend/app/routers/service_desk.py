from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr, TypeAdapter, field_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session as DBSession

from ..database import get_db, utcnow
from ..models import Squadron, Wing, User, ServiceTicket, ServiceDeskEmailConfig
from ..models.service_desk_email_config import ServiceDeskEmailConfig as _EmailCfg
from ..dependencies import get_principal
from ..permissions import Principal, require_role
from ..services import audit
from ..email_service import send_ticket_notification, send_ticket_update_notification

_EMAIL = TypeAdapter(EmailStr)

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
    squadron_id: str | None = None
    wing_id: str | None = None
    # Display-only fallback for legacy/external clients. When this exactly names
    # an active Wing, the backend resolves and stores its authoritative wing_id.
    unit_name: str | None = None
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
    # Canonical assignment. Passing "" or null clears the assignment.
    assigned_to_user_id: str | None = None
    # Legacy snapshot/display field retained for old clients. New clients should
    # use assigned_to_user_id; when both are supplied the user relationship wins.
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

    @field_validator("notification_email", mode="before")
    @classmethod
    def validate_notification_email(cls, v):
        # "" clears the address (recipients skip blanks; there is no DELETE).
        # Anything else must be ONE valid address: an unvalidated typo saved
        # with 200 and every later ticket notification failed silently.
        v = (v or "").strip()
        if v:
            _EMAIL.validate_python(v)
        return v

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
        "wing_id": t.wing_id,
        "wing_name": t.wing.name if getattr(t, "wing", None) else None,
        "unit_name": t.unit_name or (t.squadron.name if t.squadron else (t.wing.name if getattr(t, "wing", None) else None)),
        "category": t.category or "other",
        "description": t.description,
        "status": t.status,
        "admin_notes": t.admin_notes,
        "assigned_to_user_id": t.assigned_to_user_id,
        "assigned_to_name": t.assigned_to_name,
        # These were the only endpoints that hand-built a Z suffix, which was
        # correct while columns returned naive datetimes. UTCDateTime now keeps
        # tzinfo and main.py's encoder emits the Z, so hand the value over
        # unformatted -- appending one here produced "+00:00Z".
        "created_at": t.created_at,
        "resolved_at": t.resolved_at,
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
    """Submit a new service ticket — public, no auth required.

    Unit scope is resolved server-side. A client cannot spoof another Wing by
    pairing a squadron_id with arbitrary display text.
    """
    resolved_wing_id: str | None = None
    resolved_squadron_id: str | None = None
    resolved_unit_name: str | None = None

    if body.squadron_id:
        sqn = db.query(Squadron).filter(
            Squadron.id == body.squadron_id,
            Squadron.is_archived == False,  # noqa: E712
        ).first()
        if not sqn:
            raise HTTPException(404, detail={"error": "squadron_not_found",
                                              "message": "Squadron not found or archived."})
        if body.wing_id and body.wing_id != sqn.wing_id:
            raise HTTPException(422, detail={"error": "unit_scope_mismatch"})
        resolved_squadron_id = sqn.id
        resolved_wing_id = sqn.wing_id
        resolved_unit_name = sqn.name
    elif body.wing_id:
        wing = db.query(Wing).filter(
            Wing.id == body.wing_id,
            Wing.is_archived == False,  # noqa: E712
        ).first()
        if not wing:
            raise HTTPException(404, detail={"error": "wing_not_found",
                                              "message": "Wing not found or archived."})
        resolved_wing_id = wing.id
        resolved_unit_name = wing.name
    elif body.unit_name:
        # Backward-compatible resolution for the existing public UI, which
        # historically submitted only the selected Wing's display name.
        unit_name = body.unit_name.strip()
        wing_matches = db.query(Wing).filter(
            Wing.name == unit_name,
            Wing.is_archived == False,  # noqa: E712
        ).all()
        if len(wing_matches) == 1:
            resolved_wing_id = wing_matches[0].id
            resolved_unit_name = wing_matches[0].name
        else:
            resolved_unit_name = unit_name
    else:
        raise HTTPException(422, detail={"error": "unit_required",
                                          "message": "A Squadron or Wing is required."})

    ticket = ServiceTicket(
        rank=body.rank,
        first_name=body.first_name,
        last_name=body.last_name,
        email=str(body.email).strip().lower(),
        squadron_id=resolved_squadron_id,
        wing_id=resolved_wing_id,
        unit_name=resolved_unit_name,
        category=body.category,
        description=body.description,
        status="open",
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

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
        "created_at": ticket.created_at,
    }
    try:
        send_ticket_notification(ticket_data, recipients)
    except Exception:
        pass  # email failure must not roll back a successfully persisted ticket

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

    if p.role in ("wing_admin", "wing_viewer"):
        # New rows carry ServiceTicket.wing_id directly; the outer join keeps
        # legacy squadron-only rows visible during/after migration.
        q = (
            q.outerjoin(Squadron, ServiceTicket.squadron_id == Squadron.id)
            .filter(or_(
                ServiceTicket.wing_id == p.wing_id,
                Squadron.wing_id == p.wing_id,
            ))
        )
    elif p.role == "sqn_admin":
        q = q.filter(ServiceTicket.squadron_id == p.squadron_id)
    # national_admin, national_viewer, system_admin see all — no additional filter

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

    # Wing Admin can action either a Squadron ticket in their Wing or a direct
    # Wing-level ticket. Legacy rows fall back to the Squadron relationship.
    ticket_wing_id = ticket.wing_id
    if not ticket_wing_id and ticket.squadron_id:
        sqn = db.get(Squadron, ticket.squadron_id)
        ticket_wing_id = sqn.wing_id if sqn else None
    if p.role == "wing_admin" and ticket_wing_id != p.wing_id:
        raise HTTPException(403, detail={"error": "forbidden"})

    old_snapshot = {
        "status": ticket.status,
        "admin_notes": ticket.admin_notes,
        "assigned_to_user_id": ticket.assigned_to_user_id,
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

    if "assigned_to_user_id" in body.model_fields_set:
        # Pydantic normally collapses an omitted optional field and an explicit
        # JSON null to the same Python value. Use model_fields_set so clients can
        # deliberately clear an assignment with either null or "".
        requested_id = (body.assigned_to_user_id or "").strip()
        if not requested_id:
            changed["assigned_to_user_id"] = None
            changed["assigned_to_name"] = None
            ticket.assigned_to_user_id = None
            ticket.assigned_to_name = None
        else:
            assignee = db.get(User, requested_id)
            if not assignee or assignee.is_archived or not assignee.active_status:
                raise HTTPException(422, detail={"error": "invalid_assignee"})
            if assignee.role not in ("system_admin", "national_admin", "wing_admin"):
                raise HTTPException(422, detail={"error": "invalid_assignee_role"})
            # Wing-admin ownership is meaningful only when the ticket has an
            # authoritative Wing. Never assign an unscoped legacy/free-text
            # ticket to a Wing administrator merely because its wing is unknown.
            if assignee.role == "wing_admin" and (
                not ticket_wing_id or assignee.wing_id != ticket_wing_id
            ):
                raise HTTPException(422, detail={"error": "assignee_out_of_scope"})
            if p.role == "wing_admin" and (
                assignee.role != "wing_admin" or assignee.wing_id != p.wing_id
            ):
                raise HTTPException(403, detail={"error": "assignee_out_of_scope"})
            changed["assigned_to_user_id"] = assignee.id
            changed["assigned_to_name"] = assignee.display_name
            ticket.assigned_to_user_id = assignee.id
            ticket.assigned_to_name = assignee.display_name
    elif body.assigned_to_name is not None:
        # Backward compatibility for pre-v70 clients is resolution-only: a
        # display name may identify a real eligible account, but arbitrary free
        # text must never become apparent ticket ownership.
        requested_name = body.assigned_to_name.strip()
        if not requested_name:
            changed["assigned_to_user_id"] = None
            changed["assigned_to_name"] = None
            ticket.assigned_to_user_id = None
            ticket.assigned_to_name = None
        else:
            candidates = db.query(User).filter(
                User.display_name == requested_name,
                User.active_status == True,   # noqa: E712
                User.is_archived == False,    # noqa: E712
                User.role.in_(("system_admin", "national_admin", "wing_admin")),
            ).all()
            if len(candidates) != 1:
                raise HTTPException(422, detail={
                    "error": "invalid_assignee",
                    "message": "Assigned To must identify one active support account.",
                })
            assignee = candidates[0]
            if assignee.role == "wing_admin" and (
                not ticket_wing_id or assignee.wing_id != ticket_wing_id
            ):
                raise HTTPException(422, detail={"error": "assignee_out_of_scope"})
            if p.role == "wing_admin" and (
                assignee.role != "wing_admin" or assignee.wing_id != p.wing_id
            ):
                raise HTTPException(403, detail={"error": "assignee_out_of_scope"})
            changed["assigned_to_user_id"] = assignee.id
            changed["assigned_to_name"] = assignee.display_name
            ticket.assigned_to_user_id = assignee.id
            ticket.assigned_to_name = assignee.display_name

    db.commit()

    audit(
        db, p,
        object_type="service_ticket",
        object_id=ticket_id,
        action="updated",
        old=old_snapshot,
        new={**old_snapshot, **changed},
    )

    # Status/assignment changes are material workflow events for the person who
    # opened the ticket. Admin notes are deliberately excluded from email.
    if "status" in changed or "assigned_to_name" in changed:
        try:
            send_ticket_update_notification(
                {
                    "ticket_id": ticket.id,
                    "email": ticket.email,
                    "category": ticket.category,
                    "status": ticket.status,
                    "assigned_to_name": ticket.assigned_to_name,
                },
                changed,
            )
        except Exception:
            pass
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
            "updated_at": c.updated_at,
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
    old_email = existing.notification_email if existing else None
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
        old={"scope": body.scope, "wing_id": body.wing_id, "notification_email": old_email},
        new={"scope": body.scope, "wing_id": body.wing_id, "notification_email": body.notification_email},
    )
    return {"ok": True}
