"""Audit logging (append-only) and the readiness scoring engine."""
import json
from sqlalchemy.orm import Session as DBSession

from .models import AuditLog
from .permissions import Principal
from .services_readiness import parade_night_readiness


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
