"""Custom training phases — ad-hoc scheduling groups (Wing Band, Biathlon Team, etc.)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, and_

from ..database import get_db
from ..dependencies import get_principal
from ..permissions import Principal, require_role
from ..models.custom_phases import CustomTrainingPhase, CUSTOM_PHASE_SCOPE_TYPES
from .. import services

router = APIRouter()

_NATIONAL_ROLES = frozenset({"national_admin", "national_viewer", "auditor"})
_WING_ROLES = frozenset({"wing_admin", "wing_viewer"})


def _visible_phases(db, p: Principal) -> list[CustomTrainingPhase]:
    """Return phases visible to this principal (scope inheritance downward)."""
    q = db.query(CustomTrainingPhase).filter(CustomTrainingPhase.is_deleted == False)  # noqa: E712
    role = p.role
    if role == "system_admin":
        pass  # sees all
    elif role in _NATIONAL_ROLES:
        q = q.filter(CustomTrainingPhase.scope_type.in_(["system", "national"]))
    elif role in _WING_ROLES:
        q = q.filter(or_(
            CustomTrainingPhase.scope_type.in_(["system", "national"]),
            and_(CustomTrainingPhase.scope_type == "wing",
                 CustomTrainingPhase.scope_id == p.wing_id),
        ))
    else:  # sqn_admin, sqn_general
        q = q.filter(or_(
            CustomTrainingPhase.scope_type.in_(["system", "national"]),
            and_(CustomTrainingPhase.scope_type == "wing",
                 CustomTrainingPhase.scope_id == p.wing_id),
            and_(CustomTrainingPhase.scope_type == "squadron",
                 CustomTrainingPhase.scope_id == p.squadron_id),
        ))
    return q.order_by(CustomTrainingPhase.name).all()


def _phase_dict(ph: CustomTrainingPhase) -> dict:
    return {
        "custom_phase_id": ph.id,
        "name": ph.name,
        "scope_type": ph.scope_type,
        "scope_id": ph.scope_id,
        "applies_from": ph.applies_from,
        "applies_to": ph.applies_to,
        "created_by": ph.created_by,
    }


class CustomPhaseIn(BaseModel):
    name: str = Field(max_length=120)
    scope_type: str
    scope_id: str | None = None
    applies_from: str
    applies_to: str | None = None


class CustomPhaseUpdateIn(BaseModel):
    name: str | None = Field(default=None, max_length=120)
    applies_from: str | None = None
    applies_to: str | None = None


@router.get("/custom-training-phases")
def list_custom_phases(db=Depends(get_db), p: Principal = Depends(get_principal)):
    return [_phase_dict(ph) for ph in _visible_phases(db, p)]


@router.post("/custom-training-phases")
def create_custom_phase(body: CustomPhaseIn, db=Depends(get_db),
                        p: Principal = Depends(get_principal)):
    require_role(p, "sqn_admin", "wing_admin", "national_admin", "system_admin")
    if body.scope_type not in CUSTOM_PHASE_SCOPE_TYPES:
        raise HTTPException(400, detail={"error": "invalid_scope_type"})
    scope_id = body.scope_id
    if body.scope_type == "squadron":
        scope_id = p.squadron_id
    elif body.scope_type == "wing":
        if p.role not in ("wing_admin", "system_admin", "national_admin"):
            raise HTTPException(403, detail={"error": "insufficient_scope"})
        if p.role == "wing_admin":
            scope_id = p.wing_id  # force to own wing; ignore body.scope_id
        else:
            scope_id = body.scope_id or p.wing_id  # national_admin/system_admin may specify
    elif body.scope_type in ("national", "system"):
        if p.role not in ("national_admin", "system_admin"):
            raise HTTPException(403, detail={"error": "insufficient_scope"})
        scope_id = None
    ph = CustomTrainingPhase(
        name=body.name,
        scope_type=body.scope_type,
        scope_id=scope_id,
        applies_from=body.applies_from,
        applies_to=body.applies_to,
        created_by=p.user_id,
    )
    db.add(ph)
    db.commit()
    db.refresh(ph)
    services.audit(db, p, object_type="custom_training_phase", object_id=ph.id,
                   action="create")
    return _phase_dict(ph)


@router.patch("/custom-training-phases/{phase_id}")
def update_custom_phase(phase_id: str, body: CustomPhaseUpdateIn,
                        db=Depends(get_db), p: Principal = Depends(get_principal)):
    require_role(p, "sqn_admin", "wing_admin", "national_admin", "system_admin")
    ph = db.get(CustomTrainingPhase, phase_id)
    if not ph or ph.is_deleted:
        raise HTTPException(404, detail={"error": "not_found"})
    # Ownership guard: sqn_admin may only mutate their own squadron's phases;
    # wing_admin may only mutate their own wing's phases;
    # national_admin/system_admin have full access.
    if ph.scope_type == "squadron" and p.role == "sqn_admin" and ph.scope_id != p.squadron_id:
        raise HTTPException(403, detail={"error": "insufficient_scope"})
    if ph.scope_type == "wing" and p.role == "wing_admin" and ph.scope_id != p.wing_id:
        raise HTTPException(403, detail={"error": "insufficient_scope"})
    if body.name is not None:
        ph.name = body.name
    if body.applies_from is not None:
        ph.applies_from = body.applies_from
    if body.applies_to is not None:
        ph.applies_to = body.applies_to
    db.commit()
    db.refresh(ph)
    services.audit(db, p, object_type="custom_training_phase", object_id=ph.id,
                   action="update")
    return _phase_dict(ph)


@router.delete("/custom-training-phases/{phase_id}")
def delete_custom_phase(phase_id: str, db=Depends(get_db),
                        p: Principal = Depends(get_principal)):
    require_role(p, "sqn_admin", "wing_admin", "national_admin", "system_admin")
    ph = db.get(CustomTrainingPhase, phase_id)
    if not ph or ph.is_deleted:
        raise HTTPException(404, detail={"error": "not_found"})
    # Ownership guard: sqn_admin may only mutate their own squadron's phases;
    # wing_admin may only mutate their own wing's phases;
    # national_admin/system_admin have full access.
    if ph.scope_type == "squadron" and p.role == "sqn_admin" and ph.scope_id != p.squadron_id:
        raise HTTPException(403, detail={"error": "insufficient_scope"})
    if ph.scope_type == "wing" and p.role == "wing_admin" and ph.scope_id != p.wing_id:
        raise HTTPException(403, detail={"error": "insufficient_scope"})
    # Dependency gate: check if any sessions reference this phase.
    # Sessions link via custom_phase_id when that field is added (Task 8 extension);
    # for now, soft-delete is always safe.
    ph.is_deleted = True
    db.commit()
    services.audit(db, p, object_type="custom_training_phase", object_id=phase_id,
                   action="delete")
    return {"deleted": phase_id}
