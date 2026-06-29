import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from ..database import get_db, utcnow
from ..models import (ProgramPackage, ProgramItem, LearningHubResource, Phase,
                      PromotionRequest, Squadron)
from ..dependencies import get_principal
from ..permissions import Principal, require_role
from ..services import audit
from ..services_program import visible_items_for, can_schedule, coverage_for_squadron

router = APIRouter(prefix="/api", tags=["cadet-program"])


def _item_dict(it: ProgramItem) -> dict:
    return {"id": it.id, "code": it.code, "title": it.title, "owning_scope": it.owning_scope,
            "wing_id": it.wing_id, "squadron_id": it.squadron_id, "phase_name_at_time": it.phase_name_at_time,
            "element": it.element, "core_status": it.core_status,
            "foundation_or_extension": it.foundation_or_extension, "duration_minutes": it.duration_minutes,
            "learning_hub_resource_id": it.learning_hub_resource_id, "version": it.version,
            "status": it.status, "package_id": it.package_id}


# ── PHASES ──
@router.get("/phases")
def list_phases(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    rows = db.query(Phase).filter(Phase.active_status == True).order_by(Phase.display_order).all()  # noqa: E712
    return [{"id": ph.id, "name": ph.name, "short_name": ph.short_name, "display_order": ph.display_order,
             "is_core": ph.is_core, "is_extension": ph.is_extension, "learning_hub_url": ph.learning_hub_url}
            for ph in rows]


# ── PACKAGES ──
class PackageIn(BaseModel):
    title: str
    description_internal: str | None = None
    program_year: int | None = 2026


def _scope_for(p: Principal) -> tuple[str, str | None, str | None]:
    """Resolve the owning scope for a package the principal is creating."""
    if p.role in ("national_admin", "system_admin"):
        return "national", None, None
    if p.role == "wing_admin":
        return "wing", p.wing_id, None
    if p.role == "sqn_admin":
        return "squadron", p.wing_id, p.squadron_id
    raise HTTPException(403, detail={"error": "forbidden"})


@router.get("/program-packages")
def list_packages(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    pkgs = db.query(ProgramPackage).filter(ProgramPackage.is_archived == False).all()  # noqa: E712
    out = []
    for k in pkgs:
        # visibility: national to all; wing to its wing; squadron-local to that sqn + upward
        if k.owning_scope == "national" or p.is_national:
            pass
        elif k.owning_scope == "wing":
            if not (p.is_national or k.wing_id == (p.acting_wing_id or p.wing_id)):
                continue
        elif k.owning_scope == "squadron":
            sq = p.acting_squadron_id or p.squadron_id
            if p.is_wing:
                if k.wing_id != p.wing_id:
                    continue
            elif not p.is_national and k.squadron_id != sq:
                continue
        out.append({"id": k.id, "title": k.title, "owning_scope": k.owning_scope, "wing_id": k.wing_id,
                    "squadron_id": k.squadron_id, "program_year": k.program_year, "version": k.version,
                    "status": k.status})
    return out


@router.post("/program-packages")
def create_package(body: PackageIn, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    scope, wing, sqn = _scope_for(p)
    k = ProgramPackage(title=body.title, description_internal=body.description_internal,
                       owning_scope=scope, wing_id=wing, squadron_id=sqn,
                       program_year=body.program_year or 2026, status="draft", created_by=p.user_id)
    db.add(k); db.commit()
    audit(db, p, object_type="program_package", object_id=k.id, action="create", new={"scope": scope})
    return {"ok": True, "id": k.id, "owning_scope": scope}


def _require_owner(p: Principal, k: ProgramPackage):
    """Only the owning scope may modify a package (no silent cross-scope edits)."""
    if k.owning_scope == "national" and p.role in ("national_admin", "system_admin"):
        return
    if k.owning_scope == "wing" and p.role == "wing_admin" and k.wing_id == p.wing_id:
        return
    if k.owning_scope == "squadron" and p.role == "sqn_admin" and k.squadron_id == p.squadron_id:
        return
    raise HTTPException(403, detail={"error": "forbidden", "message": "Only the owning scope may modify this package."})


def _lifecycle(action, new_status, audit_action):
    def handler(pkg_id: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
        k = db.get(ProgramPackage, pkg_id)
        if not k:
            raise HTTPException(404, detail={"error": "not_found"})
        _require_owner(p, k)
        k.status = new_status
        if new_status == "published":
            k.published_by = p.user_id; k.published_at = utcnow()
        if new_status == "approved":
            k.approved_by = p.user_id
        db.commit()
        audit(db, p, object_type="program_package", object_id=k.id, action=audit_action, new={"status": new_status})
        return {"ok": True, "status": new_status}
    return handler


router.add_api_route("/program-packages/{pkg_id}/submit-review", _lifecycle("submit", "review", "submit_review"), methods=["POST"])
router.add_api_route("/program-packages/{pkg_id}/approve", _lifecycle("approve", "approved", "approve"), methods=["POST"])
router.add_api_route("/program-packages/{pkg_id}/publish", _lifecycle("publish", "published", "publish"), methods=["POST"])
router.add_api_route("/program-packages/{pkg_id}/retire", _lifecycle("retire", "retired", "retire"), methods=["POST"])
router.add_api_route("/program-packages/{pkg_id}/archive", _lifecycle("archive", "archived", "archive"), methods=["POST"])


# ── ITEMS ──
class ItemIn(BaseModel):
    package_id: str
    code: str
    title: str
    phase_name_at_time: str | None = None
    element: str | None = None
    core_status: str | None = "core"
    foundation_or_extension: str | None = "foundation"
    duration_minutes: int | None = 60
    learning_hub_resource_id: str | None = None


@router.get("/program-items")
def list_items(schedulable: bool = False, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    items = visible_items_for(db, p, schedulable_only=schedulable)
    return [_item_dict(it) for it in items]


@router.get("/program-items/{item_id}")
def get_item(item_id: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    it = db.get(ProgramItem, item_id)
    if not it:
        raise HTTPException(404, detail={"error": "not_found"})
    from ..services_program import _can_see
    if not _can_see(p, it, False):
        raise HTTPException(403, detail={"error": "forbidden"})
    return _item_dict(it)


@router.post("/program-items")
def create_item(body: ItemIn, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    k = db.get(ProgramPackage, body.package_id)
    if not k:
        raise HTTPException(404, detail={"error": "package_not_found"})
    _require_owner(p, k)
    it = ProgramItem(package_id=k.id, owning_scope=k.owning_scope, national_id=k.national_id,
                     wing_id=k.wing_id, squadron_id=k.squadron_id, code=body.code, title=body.title,
                     phase_name_at_time=body.phase_name_at_time, element=body.element,
                     core_status=body.core_status or "core",
                     foundation_or_extension=body.foundation_or_extension or "foundation",
                     duration_minutes=body.duration_minutes or 60,
                     learning_hub_resource_id=body.learning_hub_resource_id, created_by=p.user_id)
    db.add(it); db.commit()
    audit(db, p, object_type="program_item", object_id=it.id, action="create")
    return {"ok": True, "id": it.id}


@router.post("/program-items/{item_id}/retire")
def retire_item(item_id: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    it = db.get(ProgramItem, item_id)
    if not it:
        raise HTTPException(404, detail={"error": "not_found"})
    k = db.get(ProgramPackage, it.package_id)
    _require_owner(p, k)
    it.status = "retired"; db.commit()
    audit(db, p, object_type="program_item", object_id=it.id, action="retire")
    return {"ok": True}


# ── LEARNING HUB RESOURCES ──
@router.get("/learning-hub-resources")
def list_lh(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    rows = db.query(LearningHubResource).all()
    linked = {it.learning_hub_resource_id for it in db.query(ProgramItem).all() if it.learning_hub_resource_id}
    return [{"id": r.id, "title": r.title, "url": r.url, "phase": r.phase, "resource_type": r.resource_type,
             "requires_login": r.requires_login, "verification_status": r.verification_status,
             "linked": r.id in linked} for r in rows]


@router.get("/learning-hub-resources/missing")
def lh_missing(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    items = visible_items_for(db, p)
    missing = [_item_dict(it) for it in items if not it.learning_hub_resource_id]
    return {"count": len(missing), "items": missing}


# ── COVERAGE ──
@router.get("/program-coverage/squadron")
def coverage_squadron(squadron_id: str | None = None, db: DBSession = Depends(get_db),
                      p: Principal = Depends(get_principal)):
    sq = squadron_id or p.acting_squadron_id or p.squadron_id
    if not sq:
        raise HTTPException(400, detail={"error": "no_squadron"})
    s = db.get(Squadron, sq)
    if not s:
        raise HTTPException(404, detail={"error": "not_found"})
    # view scoping
    if not (p.is_national or (p.is_wing and s.wing_id == p.wing_id) or (sq == (p.acting_squadron_id or p.squadron_id))):
        raise HTTPException(403, detail={"error": "forbidden"})
    # items available to that squadron context
    items = [it for it in db.query(ProgramItem).filter(ProgramItem.is_archived == False).all()  # noqa: E712
             if it.owning_scope == "national" or (it.owning_scope == "wing" and it.wing_id == s.wing_id)
             or (it.owning_scope == "squadron" and it.squadron_id == sq)]
    return coverage_for_squadron(db, sq, s.wing_id, items)


@router.get("/program-coverage/wing")
def coverage_wing(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    require_role(p, "wing_viewer", "wing_admin", "national_viewer", "national_admin", "system_admin", "auditor")
    wing_id = p.wing_id if p.is_wing else None
    q = db.query(Squadron).filter(Squadron.is_archived == False)  # noqa: E712
    if wing_id:
        q = q.filter(Squadron.wing_id == wing_id)
    out = []
    for s in q.all():
        items = [it for it in db.query(ProgramItem).filter(ProgramItem.is_archived == False).all()  # noqa: E712
                 if it.owning_scope == "national" or (it.owning_scope == "wing" and it.wing_id == s.wing_id)
                 or (it.owning_scope == "squadron" and it.squadron_id == s.id)]
        cov = coverage_for_squadron(db, s.id, s.wing_id, items)
        out.append({"squadron_id": s.id, "code": s.code, "short_name": s.short_name,
                    "delivered_coverage_pct": cov["delivered_coverage_pct"],
                    "planning_coverage_pct": cov["planning_coverage_pct"],
                    "core_available": cov["core"]["available"], "core_delivered": cov["core"]["delivered"]})
    return {"squadrons": out}


# ── PROMOTION ──
class PromoteIn(BaseModel):
    program_item_id: str
    reason: str


@router.post("/program-promotion/squadron-to-wing")
def promote_sq_to_wing(body: PromoteIn, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    require_role(p, "sqn_admin")
    it = db.get(ProgramItem, body.program_item_id)
    if not it or it.squadron_id != p.squadron_id:
        raise HTTPException(403, detail={"error": "forbidden"})
    pr = PromotionRequest(program_item_id=it.id, from_scope="squadron", to_scope="wing",
                          requested_by=p.user_id, reason=body.reason)
    db.add(pr); db.commit()
    audit(db, p, object_type="promotion_request", object_id=pr.id, action="create", reason=body.reason)
    return {"ok": True, "id": pr.id}


@router.get("/program-promotion/requests")
def list_promotions(db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    rows = db.query(PromotionRequest).all()
    return [{"id": r.id, "program_item_id": r.program_item_id, "from_scope": r.from_scope,
             "to_scope": r.to_scope, "status": r.status, "reason": r.reason} for r in rows]


@router.post("/program-promotion/{req_id}/approve")
def approve_promotion(req_id: str, db: DBSession = Depends(get_db), p: Principal = Depends(get_principal)):
    pr = db.get(PromotionRequest, req_id)
    if not pr:
        raise HTTPException(404, detail={"error": "not_found"})
    if pr.to_scope == "wing":
        require_role(p, "wing_admin")
    else:
        require_role(p, "national_admin", "system_admin")
    src = db.get(ProgramItem, pr.program_item_id)
    # create a new owned copy at the higher scope; original stays intact (history)
    copy = ProgramItem(package_id=src.package_id, owning_scope=pr.to_scope, code=src.code,
                       title=src.title, phase_name_at_time=src.phase_name_at_time, element=src.element,
                       core_status=src.core_status, duration_minutes=src.duration_minutes,
                       wing_id=(p.wing_id if pr.to_scope == "wing" else None),
                       learning_hub_resource_id=src.learning_hub_resource_id, created_by=p.user_id,
                       internal_notes=f"Promoted from {pr.from_scope} item {src.id}")
    db.add(copy)
    pr.status = "approved"; pr.decided_by = p.user_id
    db.commit()
    audit(db, p, object_type="promotion_request", object_id=pr.id, action="approve", new={"new_item": copy.id})
    return {"ok": True, "new_item_id": copy.id}
