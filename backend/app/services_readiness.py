"""Single authoritative readiness computation for a parade night and its sessions.

Replaces three independently-computed "readiness" values that previously lived in
dashboard.py (_tonight_readiness, _upcoming_readiness) and services.py (score_parade)
plus a fourth, client-only formula (frontend squadronRisk()) — each had different
math and, critically, different zero-session handling, so a parade night with no
sessions could simultaneously read as "0% ready" in one place and "100% Ready" /
"fully staffed" in another. That was not a wording bug: the three formulas actually
disagreed.

Three axes, reported separately and NEVER collapsed into one number:
- planning_status:  is there a workable plan at all?
- delivery_outcome_summary: what actually happened, per session (a parade night's
  outcome is a distribution across sessions, not a single value)
- data_quality: can this record be trusted, independent of whether it's "ready"?

`parade_night_readiness([])` is the load-bearing case: a hard rule returns
"not_planned" before any percentage/score math can run, so an empty night can never
fall through to a "ready"/"100%" branch — the structural fix for the reported defect.
"""
from __future__ import annotations

PLANNING_STATUSES = ("not_planned", "partly_planned", "planned", "at_risk", "blocked")
DELIVERY_OUTCOMES = ("not_yet_due", "delivered", "delivered_with_issue", "cancelled",
                     "not_delivered", "rescheduled")
DATA_QUALITY_STATES = ("complete", "missing_required_information", "missing_outcome",
                       "missing_reason", "inconsistent_record")

# Statuses that represent a finished outcome — anything else is still "not yet due".
_TERMINAL_STATUSES = {"delivered", "delivered_with_issue", "cancelled", "cancelled_late",
                      "rescheduled", "not_delivered", "closed"}

_STATUS_TO_OUTCOME = {
    "planned": "not_yet_due", "draft": "not_yet_due", "published": "not_yet_due",
    "requires_review": "not_yet_due", "blocked": "not_yet_due",
    "delivered": "delivered", "delivered_with_issue": "delivered_with_issue",
    "cancelled": "cancelled", "cancelled_late": "cancelled",
    "not_delivered": "not_delivered", "rescheduled": "rescheduled",
    "closed": "delivered",
}

# Band labels kept only for legacy consumers reading a human-readable string; derived
# FROM planning_status, never computed independently.
_LEGACY_BAND = {
    "not_planned": "Not planned", "partly_planned": "Partly planned",
    "planned": "Ready", "at_risk": "Action required", "blocked": "Blocked",
}


def session_requirements(s: dict, has_conflict: bool = False) -> dict:
    """Named, independent readiness requirements for one session. Returns a
    dict with a boolean per requirement plus a plain-language `missing` list —
    never collapsed into a score. `equipment_tracked=False` is reported honestly:
    no per-session equipment model exists in this schema today, so we do not fake
    a boolean that would always silently pass."""
    checks = {
        "curriculum_assigned": bool(s.get("curriculum_item_id") or s.get("custom_title") or s.get("session_title")),
        "facilitator_assigned": bool(s.get("facilitator_id") or s.get("facilitator_display_name_at_time")),
        "room_assigned": bool(s.get("training_area_id") or s.get("training_area_name_at_time")),
        "timing_valid": True,  # no per-session start/end distinct from the parade night exists yet
        "no_critical_conflict": not has_conflict,
    }
    missing = []
    if not checks["curriculum_assigned"]:
        missing.append("curriculum item")
    if not checks["facilitator_assigned"]:
        missing.append("facilitator")
    if not checks["room_assigned"]:
        missing.append("room")
    if not checks["no_critical_conflict"]:
        missing.append("conflict must be resolved")
    complete_count = sum(1 for v in checks.values() if v)
    return {
        "checks": checks,
        "complete_count": complete_count,
        "total_count": len(checks),
        "missing": missing,
        "equipment_tracked": False,
    }


def session_delivery_outcome(s: dict) -> str:
    return _STATUS_TO_OUTCOME.get(s.get("status") or "planned", "not_yet_due")


def session_data_quality(s: dict, requirements: dict | None = None) -> str:
    status = s.get("status") or "planned"
    if status == "not_delivered" and not (s.get("not_delivered_reason") or "").strip():
        return "missing_reason"
    if status in ("cancelled", "cancelled_late") and not (s.get("cancelled_reason") or "").strip():
        return "missing_reason"
    reqs = requirements if requirements is not None else session_requirements(s)
    if reqs["missing"]:
        return "missing_required_information"
    return "complete"


def parade_night_readiness(sessions: list[dict], *, conflicts_by_session: dict | None = None) -> dict:
    """THE single authoritative entry point.

    `sessions`: list of dicts with at least id, period_number, curriculum_item_id,
    custom_title, session_title, facilitator_id, facilitator_display_name_at_time,
    training_area_id, training_area_name_at_time, status, not_delivered_reason,
    cancelled_reason.
    `conflicts_by_session`: optional {session_id: True} map of sessions with an
    unresolved hard conflict (e.g. double-booked facilitator/room).
    """
    conflicts_by_session = conflicts_by_session or {}

    if not sessions:
        # Hard rule, checked before any other computation: zero sessions is always
        # "not_planned" — never "ready", "100%", or "fully staffed".
        return {
            "planning_status": "not_planned",
            "delivery_outcome_summary": {k: 0 for k in DELIVERY_OUTCOMES},
            "data_quality": "complete",
            "sessions_total": 0,
            "sessions_ready": 0,
            "requirements_summary": "No sessions scheduled",
            "sessions": [],
            "legacy_score": 100,
            "legacy_band": _LEGACY_BAND["not_planned"],
        }

    per_session = []
    outcome_counts = {k: 0 for k in DELIVERY_OUTCOMES}
    quality_states = set()
    ready_count = 0
    any_conflict = False

    for s in sessions:
        sid = s.get("id")
        has_conflict = bool(conflicts_by_session.get(sid))
        reqs = session_requirements(s, has_conflict)
        outcome = session_delivery_outcome(s)
        quality = session_data_quality(s, reqs)
        outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
        quality_states.add(quality)
        is_ready = reqs["complete_count"] == reqs["total_count"]
        if is_ready:
            ready_count += 1
        if has_conflict:
            any_conflict = True
        per_session.append({
            "session_id": sid, "period_number": s.get("period_number"),
            "requirements": reqs, "delivery_outcome": outcome, "data_quality": quality,
            "ready": is_ready,
        })

    total = len(sessions)
    # "not_planned" is reserved exclusively for the zero-sessions case handled by the
    # hard rule above — a night that HAS sessions is never "not_planned" again, even
    # if none of them are ready yet; that's "at_risk" (worse than partly_planned,
    # since nothing at all is ready).
    if any_conflict:
        planning_status = "blocked"
    elif ready_count == total:
        planning_status = "planned"
    elif ready_count == 0:
        planning_status = "at_risk"
    else:
        planning_status = "partly_planned"

    if "inconsistent_record" in quality_states:
        data_quality = "inconsistent_record"
    elif "missing_reason" in quality_states:
        data_quality = "missing_reason"
    elif "missing_outcome" in quality_states:
        data_quality = "missing_outcome"
    elif "missing_required_information" in quality_states:
        data_quality = "missing_required_information"
    else:
        data_quality = "complete"

    legacy_score = round(ready_count / total * 100) if total else 100
    legacy_band = _LEGACY_BAND.get(planning_status, "Action required")

    return {
        "planning_status": planning_status,
        "delivery_outcome_summary": outcome_counts,
        "data_quality": data_quality,
        "sessions_total": total,
        "sessions_ready": ready_count,
        "requirements_summary": f"{ready_count} of {total} sessions ready",
        "sessions": per_session,
        "legacy_score": legacy_score,
        "legacy_band": legacy_band,
    }
