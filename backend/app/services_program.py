"""Cadet Program visibility/inheritance and coverage — backend-authoritative.

Visibility doctrine (spec §7):
  * National package items: visible to every Wing and Squadron.
  * Wing package items: visible only to Squadrons in that Wing.
  * Squadron-local items: schedulable only by that Squadron, but visible UPWARD
    to its Wing and to National for oversight. Peer Squadrons must NOT see them.
"""
from sqlalchemy.orm import Session as DBSession
from .models import ProgramItem, ProgramPackage, Session as TSession
from .permissions import Principal


def visible_items_for(db: DBSession, p: Principal, *, schedulable_only: bool = False):
    """Return the program items a principal may SEE (or schedule).

    schedulable_only=True restricts to items the principal's squadron can put on a
    parade night (national + own-wing + own-squadron-local).
    """
    q = db.query(ProgramItem).filter(ProgramItem.is_archived == False)  # noqa: E712
    items = q.all()
    out = []
    for it in items:
        if _can_see(p, it, schedulable_only):
            out.append(it)
    return out


def _can_see(p: Principal, it: ProgramItem, schedulable_only: bool) -> bool:
    scope = it.owning_scope
    # National user / auditor: see everything (oversight).
    if p.is_national:
        return True
    # Wing user: national items + items in their wing (incl. squadron-local upward).
    if p.is_wing:
        if scope == "national":
            return True
        return it.wing_id == p.wing_id
    # Squadron user (general/admin), possibly acting via proxy into a squadron.
    sq = p.acting_squadron_id or p.squadron_id
    wing = p.acting_wing_id or p.wing_id
    if scope == "national":
        return True
    if scope == "wing":
        return it.wing_id == wing
    if scope == "squadron":
        # Own local only; peers cannot see. (Upward visibility handled by wing/national branches.)
        return it.squadron_id == sq
    return False


def can_schedule(p: Principal, it: ProgramItem) -> bool:
    """Only a squadron context may schedule, and only items available to it."""
    sq = p.acting_squadron_id or p.squadron_id
    wing = p.acting_wing_id or p.wing_id
    if not sq:
        return False
    if it.owning_scope == "national":
        return True
    if it.owning_scope == "wing":
        return it.wing_id == wing
    if it.owning_scope == "squadron":
        return it.squadron_id == sq
    return False


# ── Coverage engine ──
def coverage_for_squadron(db: DBSession, squadron_id: str, wing_id: str | None,
                          items: list[ProgramItem]) -> dict:
    """Compute coverage of the given program items for a squadron, from sessions.

    Core coverage counts only core/required items; optional/extension are reported
    separately and never reduce core coverage unless marked *_required.
    """
    sessions = db.query(TSession).filter(TSession.squadron_id == squadron_id,
                                         TSession.is_archived == False).all()  # noqa: E712
    by_item: dict[str, list[str]] = {}
    by_code: dict[str, list[str]] = {}
    for s in sessions:
        if s.curriculum_item_id:
            by_item.setdefault(s.curriculum_item_id, []).append(s.status)
        if s.curriculum_code_at_time:
            by_code.setdefault(s.curriculum_code_at_time, []).append(s.status)

    def statuses_for(it: ProgramItem) -> list[str]:
        # Sessions reference curriculum_item_id; program items carry a code that may
        # match curriculum codes seeded from the same source.
        return by_item.get(it.id, []) or by_code.get(it.code, [])

    def is_core(it: ProgramItem) -> bool:
        return it.core_status in ("core", "wing_required", "national_required")

    core = [it for it in items if is_core(it)]
    ext = [it for it in items if not is_core(it)]

    def tally(group):
        delivered = scheduled = not_delivered = 0
        for it in group:
            sts = statuses_for(it)
            if sts:
                scheduled += 1
            if any(x in ("delivered", "delivered_with_issue") for x in sts):
                delivered += 1
            elif sts and all(x == "not_delivered" for x in sts):
                not_delivered += 1
        return {"available": len(group), "scheduled": scheduled, "delivered": delivered,
                "not_delivered": not_delivered, "never_scheduled": len(group) - scheduled}

    core_t = tally(core)
    ext_t = tally(ext)
    delivered_cov = round(core_t["delivered"] / core_t["available"] * 100) if core_t["available"] else 0
    planning_cov = round(core_t["scheduled"] / core_t["available"] * 100) if core_t["available"] else 0
    return {
        "squadron_id": squadron_id,
        "core": core_t, "extension": ext_t,
        "delivered_coverage_pct": delivered_cov,
        "planning_coverage_pct": planning_cov,
        "missing_learning_hub": sum(1 for it in items if not it.learning_hub_resource_id),
    }
