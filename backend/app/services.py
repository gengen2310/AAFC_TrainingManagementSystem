"""Audit logging (append-only) and the readiness scoring engine."""
import json
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from .database import Base
from .models import AuditLog, Squadron, Wing
from .permissions import Principal
from .services_readiness import parade_night_readiness


def visible_curriculum_items(db: DBSession, p: Principal) -> list:
    """The curriculum items this principal may read.

    Mirrors the scope rules GET /api/curriculum applies: national items always,
    own-wing items, own-squadron items -- and, for a national admin with no wing
    context, every wing's items for oversight.

    It exists so the export surface cannot drift from the page. The CSV/XLSX/PDF
    exports previously served ProgramItem through services_program; when
    CurriculumItem became the canonical entity (Part 41) the export had to move
    with it, and an export that applied different scope rules from the list it
    exports would be a quiet disclosure channel.
    """
    from sqlalchemy import or_
    from .models import CurriculumItem, Squadron

    sq_id = p.active_squadron_id
    wing_id = p.acting_wing_id or p.wing_id
    if sq_id:
        s = db.get(Squadron, sq_id)
        if s:
            wing_id = s.wing_id

    conditions = [CurriculumItem.owning_level == "national"]
    if wing_id:
        conditions.append(
            (CurriculumItem.owning_level == "wing") & (CurriculumItem.wing_id == wing_id))
    elif p.role in ("national_admin", "national_viewer", "system_admin", "auditor"):
        conditions.append(CurriculumItem.owning_level == "wing")
    if sq_id:
        conditions.append(
            (CurriculumItem.owning_level == "squadron") & (CurriculumItem.squadron_id == sq_id))

    return (db.query(CurriculumItem)
            .filter(or_(*conditions), CurriculumItem.is_archived == False)  # noqa: E712
            .order_by(CurriculumItem.recommended_sequence)
            .all())


def scoped_facilitator(db: DBSession, fid: str | None, squadron_id: str):
    """A Facilitator the given squadron owns, or None.

    Facilitator.squadron_id is a non-nullable FK -- facilitators are never
    shared between squadrons -- so the rule is exact equality. Session create,
    edit and assign-mission previously resolved caller-supplied facilitator_id
    with a bare db.get() and copied the rank and name onto the session, so 703
    could reference 705's facilitator and have 705's name written into 703's
    record: a cross-tenant read surfaced as a write.

    Out of scope returns None, the same as not-found, because these callers
    already no-op on a missing id and a distinct refusal would be an existence
    oracle. The same bug class was fixed for TrainingArea *edits* under REM-45;
    these are the session-write paths that fix did not reach.
    """
    from .models import Facilitator

    if not fid:
        return None
    f = db.get(Facilitator, fid)
    return f if f is not None and f.squadron_id == squadron_id else None


def scoped_training_area(db: DBSession, taid: str | None, squadron_id: str):
    """A TrainingArea the given squadron owns, or None. See scoped_facilitator --
    TrainingArea.squadron_id is likewise a non-nullable FK."""
    from .models import TrainingArea

    if not taid:
        return None
    ta = db.get(TrainingArea, taid)
    return ta if ta is not None and ta.squadron_id == squadron_id else None


def visible_curriculum_item(db: DBSession, p: Principal, cid: str | None):
    """The single-item form of visible_curriculum_items' scope rule.

    Lives next to the list version deliberately. That function's docstring makes
    the argument already -- a surface applying different scope rules from the
    list it mirrors is a quiet disclosure channel -- and a write path that
    resolves one id by primary key is exactly such a surface. Session create,
    session edit and assign-mission each did `db.get(CurriculumItem, id)` with
    no scope test, so a squadron could reference another squadron's LOCAL item
    and have its code and title denormalised onto their own session.

    Returns the item when the principal may see it, otherwise None. Out of scope
    is reported as not-found rather than as a distinct refusal: a separate
    "exists but not yours" answer is an existence oracle, and callers already
    treat a missing id as a no-op.

    National items belong to no squadron and stay visible to everyone -- the
    inheritance is the point, so scoping must not break it.
    """
    if not cid:
        return None
    from .models import CurriculumItem, Squadron

    item = db.get(CurriculumItem, cid)
    if item is None or item.is_archived:
        return None

    level = item.owning_level or "national"
    if level == "national":
        return item

    sq_id = p.active_squadron_id
    wing_id = p.acting_wing_id or p.wing_id
    if sq_id:
        sq = db.get(Squadron, sq_id)
        if sq:
            wing_id = sq.wing_id

    if level == "wing":
        if wing_id and item.wing_id == wing_id:
            return item
        # National-level oversight roles read every wing, as in the list form.
        if p.role in ("national_admin", "national_viewer", "system_admin", "auditor"):
            return item
        return None

    if level == "squadron":
        return item if sq_id and item.squadron_id == sq_id else None

    return None


def resolve_national_id(db: DBSession, p: Principal) -> str | None:
    """The national entity this principal belongs to.

    User.national_id is populated for national-level and wing accounts but not
    for squadron accounts, so for those it has to be derived through the org
    tree: squadron -> wing -> national. Proxy / Delegated Intervention is
    honoured, since an acting scope is the scope the caller is working in.

    Returns None only when nothing in the chain resolves. Callers must treat
    that as "national unknown" and fall back to their pre-national behaviour
    rather than filtering everything out.
    """
    if p.national_id:
        return p.national_id
    wing_id = p.acting_wing_id or p.wing_id
    if not wing_id:
        sq_id = p.acting_squadron_id or p.squadron_id
        if sq_id:
            sq = db.get(Squadron, sq_id)
            wing_id = sq.wing_id if sq else None
    if wing_id:
        w = db.get(Wing, wing_id)
        if w:
            return w.national_id
    return None


def audit(db: DBSession, principal: Principal | None, *, object_type: str, object_id: str | None,
          action: str, old=None, new=None, reason: str | None = None,
          ip: str | None = None, ua: str | None = None, commit: bool = True,
          batch_id: str | None = None) -> None:
    """Write an audit row. `commit=False` lets a caller fold the audit write into its
    own transaction (e.g. one atomic session edit + status change + audit record that
    must all succeed or all roll back together) instead of this always being a second,
    independent commit after the caller's own change is already durable.

    `batch_id` correlates multiple audit rows from one bulk operation (e.g. a
    batch account archive) plus one summary row sharing the same value, so the
    whole batch is queryable via GET /audit?... without a dedicated batch table."""
    entry = AuditLog(
        user_id=principal.user_id if principal else None,
        role=principal.role if principal else None,
        scope=("national" if principal and principal.is_national else "wing" if principal and principal.is_wing else "squadron") if principal else None,
        wing_id=principal.wing_id if principal else None,
        squadron_id=principal.squadron_id if principal else None,
        proxy_session_id=principal.proxy_session_id if principal else None,
        object_type=object_type, object_id=str(object_id) if object_id else None,
        action=action,
        old_value=json.dumps(old, default=str) if old is not None else None,
        new_value=json.dumps(new, default=str) if new is not None else None,
        reason=reason, ip_address=ip, user_agent=(ua or "")[:300] or None,
        batch_id=batch_id,
    )
    db.add(entry)
    if commit:
        db.commit()


def fk_dependents(db: DBSession, target_table: str, target_id: str) -> dict[str, int]:
    """Generic hard-delete safety check: find every table with a foreign key
    column pointing at `target_table`, and count rows where that column
    equals `target_id`. Used by permanent-delete endpoints (Wing/Squadron/
    Account) instead of a hand-maintained per-entity list of dependent
    tables -- a manually enumerated list silently drifts out of date as new
    models are added, and a missed one doesn't fail loudly: it lets
    db.delete() proceed and crash with an IntegrityError (or, on a backend
    that doesn't enforce FKs, silently orphan rows) instead of returning a
    clean 409. Walking Base.metadata's actual foreign keys means a newly
    added model with a FK to this entity is automatically covered.

    Returns {"table.column": count} for every table/column with at least
    one matching row; an empty dict means the delete is safe to proceed."""
    dependents: dict[str, int] = {}
    for table in Base.metadata.sorted_tables:
        for col in table.columns:
            for fk in col.foreign_keys:
                if fk.column.table.name != target_table:
                    continue
                count = db.execute(
                    select(func.count()).select_from(table).where(col == target_id)
                ).scalar()
                if count:
                    dependents[f"{table.name}.{col.name}"] = count
    return dependents


# ── Readiness engine ──
HARD = {
    "missing_facilitator": -20, "missing_room": -15, "missing_equipment": -15,
    "facilitator_clash": -25, "room_clash": -25, "no_oic": -30, "no_risk": -30,
    "retired_curriculum": -20, "outside_parade_time": -15, "no_expected_attendance": -10,
    "approval_missing": -25, "unresolved_issue_48h": -20,
}
SOFT = {
    "back_to_back": -5, "overused_month": -8, "room_near_capacity": -5,
    "recently_cancelled": -5, "no_change_note": -5, "attendance_trend_low": -5,
    "out_of_sequence": -8, "no_learning_outcome": -8,
}
BANDS = [(95, "Ready"), (85, "Ready with watch items"), (70, "Action required"),
         (50, "Staff intervention required"), (31, "Command decision required"),
         (0, "Do not proceed without review")]


def band(score: int) -> str:
    for t, label in BANDS:
        if score >= t:
            return label
    return "Do not proceed without review"


def score_parade(sessions: list[dict]) -> dict:
    """Legacy shape ({score, band, deductions}) kept for existing callers during
    migration. `score`/`band` are now DERIVED from services_readiness.
    parade_night_readiness() — the one authoritative computation — rather than
    computed independently, so this can no longer disagree with the Dashboard or
    any other consumer of that module (previously: this function returned "Ready"/
    100 for a parade night with zero sessions, since its deduction loop never ran
    on an empty list; that contradiction is now structurally impossible because
    parade_night_readiness() has a hard "zero sessions -> not_planned" rule checked
    before any score math). `deductions` remains itemized diagnostic detail — not
    currently rendered by either frontend (confirmed unused in both codebases) —
    computed the same way as before, since nothing scored/banded here depends on it."""
    deductions = []
    seen_fac, seen_room = {}, {}
    for s in sessions:
        label = f"P{s.get('period_number')}/{s.get('phase_at_time') or '?'}"
        if not s.get("facilitator_id") and not s.get("facilitator_display_name_at_time"):
            deductions.append({"pts": HARD["missing_facilitator"], "reason": f"{label}: no facilitator", "session_id": s.get("id")})
        if not s.get("training_area_id") and not s.get("training_area_name_at_time"):
            deductions.append({"pts": HARD["missing_room"], "reason": f"{label}: no room", "session_id": s.get("id")})
        if not s.get("expected_attendance"):
            deductions.append({"pts": HARD["no_expected_attendance"], "reason": f"{label}: no expected attendance", "session_id": s.get("id")})
        fid = s.get("facilitator_id")
        if fid:
            if fid in seen_fac:
                deductions.append({"pts": HARD["facilitator_clash"], "reason": f"{label}: facilitator double-booked", "session_id": s.get("id")})
            seen_fac[fid] = True
        rid = s.get("training_area_id")
        if rid:
            if rid in seen_room:
                deductions.append({"pts": HARD["room_clash"], "reason": f"{label}: room double-booked", "session_id": s.get("id")})
            seen_room[rid] = True
    result = parade_night_readiness(sessions)
    return {"score": result["legacy_score"], "band": result["legacy_band"], "deductions": deductions}


def publish_blockers(sessions: list[dict]) -> list[dict]:
    blockers = []
    if not sessions:
        return [{"reason": "No sessions on this parade night", "fix": "add_session"}]
    for s in sessions:
        label = f"P{s.get('period_number')}/{s.get('phase_at_time') or '?'}"
        if not (s.get("curriculum_item_id") or s.get("custom_title") or s.get("session_title")):
            blockers.append({"reason": f"{label}: no title or curriculum item", "fix": "edit_session", "session_id": s.get("id")})
        if not s.get("facilitator_id") and not s.get("facilitator_display_name_at_time"):
            blockers.append({"reason": f"{label}: no facilitator", "fix": "assign_facilitator", "session_id": s.get("id")})
        if not s.get("training_area_id") and not s.get("training_area_name_at_time"):
            blockers.append({"reason": f"{label}: no room/location", "fix": "assign_room", "session_id": s.get("id")})
    return blockers


def close_blockers(sessions: list[dict]) -> list[str]:
    final = {"delivered", "delivered_with_issue", "cancelled", "cancelled_late",
             "rescheduled", "not_delivered", "closed"}
    out = []
    for s in sessions:
        label = f"P{s.get('period_number')}"
        if s.get("status") not in final:
            out.append(f"{label}: not in a final status ({s.get('status')})")
        if s.get("status") == "not_delivered" and not s.get("not_delivered_reason"):
            out.append(f"{label}: not delivered without a reason")
        if s.get("status") in ("cancelled", "cancelled_late") and not s.get("cancelled_reason"):
            out.append(f"{label}: cancelled without a reason")
    return out
