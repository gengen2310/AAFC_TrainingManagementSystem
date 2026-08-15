"""Dashboard chart-data endpoints.

Returns chart-ready JSON structures for the Frontend Dashboard.
Every response follows the ChartSpec shape defined below so the
frontend can render charts without reconstructing complex metrics.

Scope: auto-detected from Principal.
  sqn_admin / sqn_general   → squadron scope
  wing_admin / wing_viewer  → wing scope  (squadron_id query param = override)
  national_*                → national scope
  system_admin              → national scope

Endpoints:
  GET /api/dashboard/charts          primary chart bundle (tactical + operational)
  GET /api/dashboard/charts/strategic  strategic / long-range charts (deferred load)
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from ..database import get_db
from ..dependencies import get_principal
from ..models import (
    ParadeNight, Session, Facilitator, Squadron, Wing,
    CurriculumItem, Equipment, TrainingArea, PlanningFacilitatorLeave,
    CurriculumPhase, CurriculumElement, TrainingClass, AuditLog,
)
from ..permissions import Principal, require_role, require_can_view_squadron, require_can_view_wing
from ..services_readiness import parade_night_readiness, session_requirements
from .training import _view_squadron_id, _class_curriculum_progress

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# ── constants ─────────────────────────────────────────────────────────────────

_PHASES = [
    "A. Orientation", "B. Initial", "C. Junior",
    "D. Intermediate", "E. Senior",
    "I. Bronze", "J. Silver", "K. Gold",
]
_DELIVERED = {"delivered", "delivered_with_issue"}
_TERMINAL = {"delivered", "delivered_with_issue", "not_delivered", "cancelled", "rescheduled"}
_STATUS_COLORS = {
    "delivered": "#2e7d32",
    "delivered_with_issue": "#558b2f",
    "not_delivered": "#455560",
    "cancelled": "#e51937",
    "rescheduled": "#f57c00",
    "planned": "#51b0e3",
}


_logger = logging.getLogger(__name__)


def _safe_chart(chart_id: str, builder, *args, **kwargs) -> dict:
    """Run one chart builder in isolation -- an exception in any single
    builder previously 500'd the ENTIRE /api/dashboard/charts response,
    taking every other chart down with it even though only one was actually
    broken. Catches and logs server-side (full traceback, never sent to the
    client), returning a distinct ChartSpec-shaped failure marker instead so
    the frontend can render "this chart failed" for just this one chart."""
    try:
        return builder(*args, **kwargs)
    except Exception:
        _logger.exception("Dashboard chart builder failed: %s", chart_id)
        return {
            "chart_id": chart_id,
            "title": chart_id.replace("_", " ").title(),
            "chart_type": "error",
            "data": [],
            "error": True,
            "empty_state": "This chart could not be loaded. Try refreshing.",
        }


# ── scope helpers ─────────────────────────────────────────────────────────────

def _scope(p: Principal) -> str:
    if p.is_national or p.is_system_admin or p.is_auditor:
        return "national"
    if p.is_wing:
        return "wing"
    return "squadron"


def _sqn_ids_for_wing(db: DBSession, wing_id: str) -> list[str]:
    """All active squadron IDs in the given wing."""
    return [
        r.id for r in db.query(Squadron.id)
        .filter(Squadron.wing_id == wing_id, Squadron.is_archived == False)  # noqa: E712
        .all()
    ]


def _wing_ids_for_national(db: DBSession) -> list[dict]:
    """All active wings with id + code."""
    rows = db.query(Wing.id, Wing.code, Wing.name).filter(Wing.is_archived == False).all()  # noqa: E712
    return [{"id": r.id, "code": r.code, "name": r.name} for r in rows]


_WINDOW_LABELS = {
    "week": "This Week", "term": "This Term", "semester": "Semester",
    "year": "Training Year",
}


def _date_window(window: str) -> tuple[str, str]:
    """Return (start_date_iso, end_date_iso) for the given window label."""
    today = date.today()
    if window == "week":
        return (today - timedelta(days=7)).isoformat(), (today + timedelta(days=7)).isoformat()
    if window == "semester":
        return (today - timedelta(days=182)).isoformat(), (today + timedelta(days=30)).isoformat()
    if window == "year":
        return f"{today.year}-01-01", f"{today.year}-12-31"
    # default: term ≈ last 90 days + next 30 days
    return (today - timedelta(days=90)).isoformat(), (today + timedelta(days=30)).isoformat()


def _iso_week(d: str) -> str:
    """Return YYYY-Www label for an ISO date string."""
    dt = date.fromisoformat(d)
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


# ── chart builders: squadron ───────────────────────────────────────────────────

def _weekly_outcomes(sessions: list, pns: list) -> dict:
    """Stacked bar: sessions by outcome per parade-night week."""
    pn_map = {pn.id: pn.date for pn in pns}
    weeks: dict[str, dict] = defaultdict(lambda: {
        "label": "", "delivered": 0, "delivered_with_issue": 0,
        "not_delivered": 0, "cancelled": 0, "rescheduled": 0, "planned": 0,
    })
    for s in sessions:
        pn_date = pn_map.get(s.parade_night_id)
        if not pn_date:
            continue
        wk = _iso_week(pn_date)
        bucket = weeks[wk]
        bucket["label"] = wk
        st = s.status or "planned"
        if st in bucket:
            bucket[st] += 1
    data = sorted(weeks.values(), key=lambda r: r["label"])
    total = sum(r["delivered"] + r["delivered_with_issue"] for r in data)
    return {
        "chart_id": "weekly_outcomes",
        "title": "Training delivered each week",
        "explanation": "Sessions delivered, cancelled or not delivered per week.",
        "question": "Are we delivering the planned training program reliably?",
        "chart_type": "stacked_bar",
        "x_axis": "Week",
        "y_axis": "Sessions",
        "series": [
            {"key": "delivered", "label": "Delivered", "color": _STATUS_COLORS["delivered"]},
            {"key": "delivered_with_issue", "label": "Delivered (with issue)", "color": _STATUS_COLORS["delivered_with_issue"]},
            {"key": "not_delivered", "label": "Not Delivered", "color": _STATUS_COLORS["not_delivered"]},
            {"key": "cancelled", "label": "Cancelled", "color": _STATUS_COLORS["cancelled"]},
            {"key": "rescheduled", "label": "Rescheduled", "color": _STATUS_COLORS["rescheduled"]},
            {"key": "planned", "label": "Planned", "color": _STATUS_COLORS["planned"]},
        ],
        "data": data,
        "insight": f"{total} sessions delivered across {len(data)} weeks." if data else None,
        "empty_state": "No sessions recorded for this period.",
        "drill_down": {"route": "parade-nights", "filters": {}},
        "permission_scope": "squadron",
    }


def _delivery_trend(sessions: list, pns: list, weeks: int = 12) -> dict:
    """Line chart: delivery reliability % for the last N weeks."""
    today = date.today()
    pn_map = {pn.id: pn.date for pn in pns}
    # Build per-week buckets (terminal sessions only)
    wk_buckets: dict[str, dict] = defaultdict(lambda: {"delivered": 0, "total": 0})
    for s in sessions:
        if s.status not in _TERMINAL:
            continue
        pn_date = pn_map.get(s.parade_night_id)
        if not pn_date:
            continue
        d = date.fromisoformat(pn_date)
        if d > today:
            continue  # skip future
        wk = _iso_week(pn_date)
        wk_buckets[wk]["total"] += 1
        if s.status in _DELIVERED:
            wk_buckets[wk]["delivered"] += 1

    # Build the rolling 12-week window (cutoff = 12 weeks ago)
    cutoff = today - timedelta(weeks=weeks)
    def _week_start(wk: str) -> date:
        """Convert 'YYYY-Www' to the Monday of that ISO week."""
        # wk format: "2026-W30"
        year = int(wk[:4])
        week = int(wk[6:])
        # ISO week 1 day 1 of that year
        jan4 = date(year, 1, 4)
        start_of_week1 = jan4 - timedelta(days=jan4.weekday())
        return start_of_week1 + timedelta(weeks=week - 1)

    recent = {k: v for k, v in wk_buckets.items() if _week_start(k) >= cutoff}

    data = []
    for wk in sorted(recent):
        b = recent[wk]
        not_del = b["total"] - b["delivered"]
        pct = round(b["delivered"] / b["total"] * 100) if b["total"] else None
        nd_pct = round(not_del / b["total"] * 100) if b["total"] else None
        data.append({
            "label": wk,
            "reliability_pct": pct,
            "not_delivered_pct": nd_pct,
            "delivered": b["delivered"],
            "not_delivered": not_del,
            "total": b["total"],
        })

    # Insight: trend direction + N/D rate
    insight = None
    valid = [d for d in data if d["reliability_pct"] is not None]
    if len(valid) >= 4:
        last4_rel = [v["reliability_pct"] for v in valid[-4:]]
        first4_rel = [v["reliability_pct"] for v in valid[:4]]
        avg_nd = round(sum(v["not_delivered_pct"] or 0 for v in valid[-4:]) / 4)
        if sum(last4_rel) / 4 > sum(first4_rel) / 4 + 5:
            insight = f"Delivery reliability has improved over the past four weeks (non-delivery rate {avg_nd}%)."
        elif sum(last4_rel) / 4 < sum(first4_rel) / 4 - 5:
            insight = f"Delivery reliability has declined recently — non-delivery rate {avg_nd}% over the past four weeks. Review causes."
        elif avg_nd >= 20:
            insight = f"Delivery is stable but the non-delivery rate remains {avg_nd}% — review causes."

    return {
        "chart_id": "delivery_trend",
        "title": "Delivery reliability trend",
        "explanation": "Percentage of scheduled sessions delivered each week over the past 12 weeks.",
        "question": "Is our delivery reliability improving or declining?",
        "chart_type": "line",
        "x_axis": "Week",
        "y_axis": "Reliability %",
        "thresholds": {"green": 80, "amber": 60, "red": 0},
        "data": data,
        "insight": insight,
        "empty_state": "Not enough delivery history to show a trend.",
        "drill_down": {"route": "parade-nights"},
        "permission_scope": "squadron",
    }


def _phases_for_squadron(db: DBSession, sq_id: str | None) -> list[str]:
    """Governed phase names visible to a given squadron (national/system +
    that squadron's own wing + the squadron's own custom phases), in
    training-progression order. Scoped to the VIEWED squadron, not the
    calling principal -- a wing/national/system_admin viewing a different
    squadron's dashboard must see that squadron's phases, not their own.
    Mirrors training.py's _visible_phases() visibility rule but resolved
    from a squadron_id instead of a Principal, since dashboard chart
    builders view squadrons other than the caller's own."""
    from sqlalchemy import or_
    conditions = [CurriculumPhase.scope_level.in_(["system", "national"])]
    sq = db.get(Squadron, sq_id) if sq_id else None
    if sq and sq.wing_id:
        conditions.append((CurriculumPhase.scope_level == "wing") & (CurriculumPhase.wing_id == sq.wing_id))
    if sq_id:
        conditions.append((CurriculumPhase.scope_level == "squadron") & (CurriculumPhase.squadron_id == sq_id))
    rows = db.query(CurriculumPhase).filter(
        CurriculumPhase.is_archived == False,  # noqa: E712
        CurriculumPhase.active_status == True,  # noqa: E712
        or_(*conditions),
    ).order_by(CurriculumPhase.sort_order, CurriculumPhase.scope_level, CurriculumPhase.display_name).all()
    return [ph.name for ph in rows] or _PHASES  # fall back if the catalogue is somehow empty


def _elements_for_squadron(db: DBSession, sq_id: str | None) -> list[str]:
    """CLASS-12: governed element names visible to a given squadron (national/
    system + that squadron's own wing + the squadron's own custom elements).
    Mirrors _phases_for_squadron exactly, for CurriculumElement instead of
    CurriculumPhase -- same visibility rule (training.py's _visible_elements()),
    resolved from a squadron_id rather than a Principal for the same reason.
    Unlike phases, there is no fixed national element catalogue to fall back
    to if the governed catalogue is empty -- elements are squadron-defined
    category tags, not a fixed training-progression sequence, so an empty
    catalogue here correctly means "no elements defined yet", not a bug."""
    from sqlalchemy import or_
    conditions = [CurriculumElement.scope_level.in_(["system", "national"])]
    sq = db.get(Squadron, sq_id) if sq_id else None
    if sq and sq.wing_id:
        conditions.append((CurriculumElement.scope_level == "wing") & (CurriculumElement.wing_id == sq.wing_id))
    if sq_id:
        conditions.append((CurriculumElement.scope_level == "squadron") & (CurriculumElement.squadron_id == sq_id))
    rows = db.query(CurriculumElement).filter(
        CurriculumElement.is_archived == False,  # noqa: E712
        CurriculumElement.active_status == True,  # noqa: E712
        or_(*conditions),
    ).order_by(CurriculumElement.scope_level, CurriculumElement.display_name).all()
    return [el.name for el in rows]


def _curriculum_progress(sessions: list, curr_items: list, phases: list[str]) -> dict:
    """Horizontal stacked bar: delivered vs not-delivered vs planned per phase.

    `phases` must be the full governed phase catalogue for the squadron being
    viewed (see _phases_for_squadron) -- previously this iterated a hardcoded
    8-phase constant, so any custom wing/squadron phase was silently dropped
    from the chart entirely rather than shown at 0%."""
    # Count from sessions
    phase_data: dict[str, dict] = {
        ph: {"phase": ph, "delivered": 0, "delivered_with_issue": 0,
             "not_delivered": 0, "cancelled": 0, "planned": 0, "total_items": 0}
        for ph in phases
    }
    for s in sessions:
        ph = s.phase_at_time
        if ph and ph in phase_data:
            st = s.status or "planned"
            if st in ("delivered", "delivered_with_issue", "not_delivered", "cancelled", "planned", "rescheduled"):
                key = st if st in phase_data[ph] else "planned"
                phase_data[ph][key] += 1

    # Total curriculum items per phase
    for ci in curr_items:
        ph = ci.phase
        if ph and ph in phase_data:
            phase_data[ph]["total_items"] += 1

    data = [phase_data[ph] for ph in phases]
    total_del = sum(d["delivered"] + d["delivered_with_issue"] for d in data)
    total_planned = sum(d["planned"] for d in data)
    insight = None
    if total_del > 0 and total_planned > 0:
        insight = f"{total_del} sessions delivered; {total_planned} still planned."

    return {
        "chart_id": "curriculum_progress",
        "title": "Curriculum progress by phase",
        "explanation": "Sessions recorded per curriculum phase — delivered, planned, and not delivered.",
        "question": "Which phases are progressing and which are behind?",
        "chart_type": "stacked_bar_horizontal",
        "x_axis": "Sessions",
        "y_axis": "Phase",
        "series": [
            {"key": "delivered", "label": "Delivered", "color": _STATUS_COLORS["delivered"]},
            {"key": "delivered_with_issue", "label": "Delivered (issue)", "color": _STATUS_COLORS["delivered_with_issue"]},
            {"key": "not_delivered", "label": "Not Delivered", "color": _STATUS_COLORS["not_delivered"]},
            {"key": "cancelled", "label": "Cancelled", "color": _STATUS_COLORS["cancelled"]},
            {"key": "planned", "label": "Planned", "color": _STATUS_COLORS["planned"]},
        ],
        "data": data,
        "insight": insight,
        "empty_state": "No curriculum sessions have been recorded yet.",
        "drill_down": {"route": "parade-nights", "filters": {"phase": "{{phase}}"}},
        "permission_scope": "squadron",
    }


def _element_curriculum_progress(sessions: list, curr_items: list, elements: list[str]) -> dict:
    """CLASS-12: the element-scoped sibling of _curriculum_progress above --
    identical shape and logic, keyed by CurriculumItem.element/Session.
    element_at_time instead of .phase/.phase_at_time. Answers "how much
    Ground School (or any other element) have we delivered", which previously
    had no direct answer -- element-level FILTERING already existed (Mission
    Backlog's own element query param), but no AGGREGATION did.

    Kept as a SEPARATE chart rather than changing _curriculum_progress's own
    shape in place -- same capability-preservation reasoning as
    _class_curriculum_progress_summary's own docstring: connected-frontend
    already renders charts.curriculum_progress via a fixed data shape, so
    this is purely additive, not a replacement.

    `elements` is the governed element catalogue for the squadron being
    viewed (see _elements_for_squadron) -- if empty (no elements defined for
    this squadron/wing/national scope yet), returns a genuinely empty chart
    rather than guessing at any default categories, since unlike phases
    there is no fixed national element catalogue to fall back to."""
    element_data: dict[str, dict] = {
        el: {"element": el, "delivered": 0, "delivered_with_issue": 0,
             "not_delivered": 0, "cancelled": 0, "planned": 0, "total_items": 0}
        for el in elements
    }
    for s in sessions:
        el = s.element_at_time
        if el and el in element_data:
            st = s.status or "planned"
            if st in ("delivered", "delivered_with_issue", "not_delivered", "cancelled", "planned", "rescheduled"):
                key = st if st in element_data[el] else "planned"
                element_data[el][key] += 1

    for ci in curr_items:
        el = ci.element
        if el and el in element_data:
            element_data[el]["total_items"] += 1

    data = [element_data[el] for el in elements]
    total_del = sum(d["delivered"] + d["delivered_with_issue"] for d in data)
    total_planned = sum(d["planned"] for d in data)
    insight = None
    if total_del > 0 and total_planned > 0:
        insight = f"{total_del} sessions delivered; {total_planned} still planned."

    return {
        "chart_id": "element_curriculum_progress",
        "title": "Curriculum progress by element",
        "explanation": "Sessions recorded per curriculum element (subject/category) — delivered, planned, and not delivered.",
        "question": "Which subject areas are progressing and which are behind?",
        "chart_type": "stacked_bar_horizontal",
        "x_axis": "Sessions",
        "y_axis": "Element",
        "series": [
            {"key": "delivered", "label": "Delivered", "color": _STATUS_COLORS["delivered"]},
            {"key": "delivered_with_issue", "label": "Delivered (issue)", "color": _STATUS_COLORS["delivered_with_issue"]},
            {"key": "not_delivered", "label": "Not Delivered", "color": _STATUS_COLORS["not_delivered"]},
            {"key": "cancelled", "label": "Cancelled", "color": _STATUS_COLORS["cancelled"]},
            {"key": "planned", "label": "Planned", "color": _STATUS_COLORS["planned"]},
        ],
        "data": data,
        "insight": insight,
        "empty_state": "No curriculum elements have been defined for this squadron yet.",
        "drill_down": {"route": "activities", "filters": {"element": "{{element}}"}},
        "permission_scope": "squadron",
    }


# Addendum §75's threshold: a class more than this many percentage points
# below its own stage's aggregate is surfaced as an exception, so the
# aggregate can never quietly hide one struggling class behind a healthy
# blended number.
_CLASS_BEHIND_THRESHOLD_PP = 15


def _class_curriculum_progress_summary(db: DBSession, sq_id: str) -> dict:
    """Curriculum progress per Training Class, grouped by Training Stage
    (CLASS-07) -- the class-aware sibling of _curriculum_progress above,
    which still shows one blended bar per Stage regardless of how many
    parallel classes it has. Kept as a SEPARATE chart rather than changing
    _curriculum_progress's own shape in place: connected-frontend already
    renders charts.curriculum_progress via a fixed data shape
    (index.html's _chartStackedBarH consumer) -- changing that shape would
    be a capability regression for a chart real users already read, not an
    improvement (.claude/rules/capability-preservation.md). This chart is
    purely additive.

    Derives everything from CLASS-01/03/04's existing data -- no new state,
    per addendum §44."""
    classes = db.query(TrainingClass).filter(
        TrainingClass.squadron_id == sq_id, TrainingClass.is_archived == False,  # noqa: E712
    ).order_by(TrainingClass.sequence, TrainingClass.display_name).all()

    stages: dict[str, dict] = {}
    for c in classes:
        prog = _class_curriculum_progress(db, c)
        stage_id = prog["training_stage_id"]
        entry = stages.setdefault(stage_id, {
            "stage_name": prog["stage_name"] or "Unnamed stage",
            "classes": [],
            "total_delivered": 0,
            "total_applicable": 0,
        })
        delivered, total = prog["summary"]["delivered"], prog["summary"]["total"]
        entry["classes"].append({
            "training_class_id": c.id, "display_name": c.display_name,
            "delivered": delivered, "total": total,
            "coverage_pct": round(100 * delivered / total) if total else None,
        })
        entry["total_delivered"] += delivered
        entry["total_applicable"] += total

    data = []
    behind_classes: list[dict] = []
    for stage_id, entry in stages.items():
        coverage_pct = (round(100 * entry["total_delivered"] / entry["total_applicable"])
                        if entry["total_applicable"] else None)
        if coverage_pct is not None:
            for cls in entry["classes"]:
                if cls["coverage_pct"] is not None and cls["coverage_pct"] <= coverage_pct - _CLASS_BEHIND_THRESHOLD_PP:
                    behind_classes.append({
                        "stage_name": entry["stage_name"], "display_name": cls["display_name"],
                        "coverage_pct": cls["coverage_pct"], "stage_coverage_pct": coverage_pct,
                    })
        data.append({
            "stage_id": stage_id, "stage": entry["stage_name"],
            "class_count": len(entry["classes"]), "coverage_pct": coverage_pct,
            "delivered": entry["total_delivered"], "total": entry["total_applicable"],
            "classes": entry["classes"],
        })
    data.sort(key=lambda d: d["stage"])

    insight = None
    if behind_classes:
        names = ", ".join(f"{b['display_name']} ({b['coverage_pct']}%)" for b in behind_classes[:3])
        insight = f"{len(behind_classes)} class(es) significantly behind their stage average: {names}."
    elif data:
        insight = f"{len(data)} Training Stage(s) with active classes; no class is significantly behind its stage average."

    return {
        "chart_id": "class_curriculum_progress",
        "title": "Curriculum progress by Training Class",
        "explanation": ("Curriculum requirement coverage per Training Stage, broken down by "
                        "Training Class -- each class's own progress is tracked independently, "
                        "even when several classes share the same Stage."),
        "question": "Which Training Classes are behind on their curriculum, even if their Stage looks healthy overall?",
        "chart_type": "bar_with_drilldown",
        "x_axis": "Training Stage",
        "y_axis": "Coverage (%)",
        "data": data,
        "classes_behind": behind_classes,
        "insight": insight,
        "empty_state": ("No Training Classes have been set up yet. Set up Training Classes for a "
                        "Training Stage before class-level curriculum progress can be shown."),
        "drill_down": {"route": "training-classes", "filters": {"stage_id": "{{stage_id}}"}},
        "permission_scope": "squadron",
    }


def _class_enrollment_distribution(db: DBSession, sq_id: str) -> dict:
    """Class size overview — shows expected_count per Training Class, grouped
    by Training Stage. Answers 'How many cadets are in each class, and are
    sizes balanced across parallel classes in the same Stage?'

    Uses TrainingClass.expected_count (set by sqn_admin when creating or
    editing a class). Where expected_count is NULL the class is flagged as
    'not set' — a data quality prompt, not an error. No cadet-level tracking
    is required; the chart is useful from day 1 of class setup.

    Phase 6 analytics requirement: class distributions."""
    classes = db.query(TrainingClass).filter(
        TrainingClass.squadron_id == sq_id,
        TrainingClass.is_archived == False,  # noqa: E712
    ).order_by(TrainingClass.sequence, TrainingClass.display_name).all()

    if not classes:
        return {
            "chart_id": "class_enrollment",
            "chart_type": "class_enrollment",
            "title": "Training Class sizes",
            "data": [], "insight": None,
            "empty_state": ("No Training Classes configured. Set up Training Classes to see class "
                            "size information here."),
            "permission_scope": "squadron",
        }

    stages: dict[str, dict] = {}
    total_known = 0
    missing_count = 0
    for c in classes:
        stage_id = c.training_stage_id
        if stage_id not in stages:
            phase = db.query(CurriculumPhase).filter(CurriculumPhase.id == stage_id).first()
            stages[stage_id] = {
                "stage": phase.display_name if phase else "Unnamed stage",
                "stage_id": stage_id,
                "classes": [],
                "total_expected": 0,
            }
        entry = stages[stage_id]
        count = c.expected_count
        entry["classes"].append({
            "display_name": c.display_name,
            "training_class_id": c.id,
            "expected_count": count,
        })
        if count is not None:
            entry["total_expected"] += count
            total_known += count
        else:
            missing_count += 1

    data = sorted(stages.values(), key=lambda s: s["stage"])

    if missing_count:
        insight = (f"{missing_count} class(es) have no expected size set. "
                   f"Edit each class to add an expected cadet count.")
    elif total_known:
        insight = (f"{sum(len(s['classes']) for s in data)} active Training Class(es) "
                   f"with a total of {total_known} expected cadets.")
    else:
        insight = None

    return {
        "chart_id": "class_enrollment",
        "chart_type": "class_enrollment",
        "title": "Training Class sizes",
        "explanation": ("Expected cadet count per Training Class, grouped by Training Stage. "
                        "Use this to check whether parallel classes are roughly balanced in size "
                        "and whether room capacity matches the largest class."),
        "question": "How many cadets are in each Training Class, and are sizes balanced?",
        "data": data,
        "insight": insight,
        "empty_state": "No Training Classes configured.",
        "permission_scope": "squadron",
    }


_UNKNOWN_PHASE_LABEL = "Missing phase (needs information)"


def _curriculum_backlog(sessions: list, pns: list) -> dict:
    """Ranked bar: phases with most undelivered sessions relative to historical parade nights.

    A session with no phase_at_time recorded is a data-quality gap, not an
    operational finding — it is shown in the chart (so the missed-session count
    isn't silently hidden) but is never allowed to be the chart's headline insight,
    and is labelled/coloured distinctly from a real phase name."""
    today_str = date.today().isoformat()
    pn_map = {pn.id: pn.date for pn in pns}
    # Past parade nights only
    past_pn_ids = {pn.id for pn in pns if pn.date < today_str}

    phase_cnt: dict[str, int] = defaultdict(int)
    for s in sessions:
        if s.parade_night_id not in past_pn_ids:
            continue
        if s.status not in ("not_delivered", "cancelled", "rescheduled"):
            continue
        ph = s.phase_at_time or _UNKNOWN_PHASE_LABEL
        phase_cnt[ph] += 1

    data = sorted(
        [{"label": ph, "count": cnt,
          "color": "#8a93a6" if ph == _UNKNOWN_PHASE_LABEL else "#e51937",
          "data_quality_gap": ph == _UNKNOWN_PHASE_LABEL}
         for ph, cnt in phase_cnt.items()],
        key=lambda x: -x["count"],
    )

    real_data = [d for d in data if not d["data_quality_gap"]]
    missing_count = next((d["count"] for d in data if d["data_quality_gap"]), 0)
    insight = None
    if real_data:
        insight = f"The largest backlog is in {real_data[0]['label']} ({real_data[0]['count']} sessions)."
    elif missing_count:
        insight = f"{missing_count} missed session(s) have no phase recorded — cannot rank by phase yet."
    if missing_count and real_data:
        insight += f" ({missing_count} additional session(s) are missing a phase and need information.)"

    return {
        "chart_id": "curriculum_backlog",
        "title": "Curriculum backlog by phase",
        "explanation": "Sessions not delivered or cancelled on past parade nights, ranked by phase.",
        "question": "Where is the training backlog accumulating?",
        "chart_type": "bar_horizontal",
        "x_axis": "Missed sessions",
        "y_axis": "Phase",
        "data": data,
        "insight": insight,
        "empty_state": "No backlog — all past sessions were delivered.",
        "drill_down": {"route": "parade-nights", "filters": {"status": "not_delivered"}},
        "permission_scope": "squadron",
    }


_REASON_NOT_RECORDED_LABEL = "Reason not recorded (needs information)"


def _cancellation_reasons(sessions: list, pns: list) -> dict:
    """Ranked bar: most common cancellation / not-delivered reasons.

    A session with no reason recorded is a data-quality gap, not itself an
    operational cause of disruption — it is shown (so the count isn't hidden) but
    is never allowed to be the chart's "most common cause" headline, and is
    labelled/coloured distinctly from a real, named reason."""
    today_str = date.today().isoformat()
    pn_map = {pn.id: pn.date for pn in pns}
    reason_cnt: dict[str, int] = defaultdict(int)

    for s in sessions:
        pn_date = pn_map.get(s.parade_night_id, "")
        if pn_date >= today_str:
            continue
        reason = None
        if s.status == "cancelled":
            reason = (s.cancelled_reason or "").strip() or _REASON_NOT_RECORDED_LABEL
        elif s.status == "not_delivered":
            reason = (s.not_delivered_reason or "").strip() or _REASON_NOT_RECORDED_LABEL
        if reason:
            # Truncate long free-text to first sentence / 60 chars
            if reason != _REASON_NOT_RECORDED_LABEL:
                reason = reason[:60] + ("…" if len(reason) > 60 else "")
            reason_cnt[reason] += 1

    data = sorted(
        [{"label": r, "count": c,
          "data_quality_gap": r == _REASON_NOT_RECORDED_LABEL,
          "drill_id": "__no_reason__" if r == _REASON_NOT_RECORDED_LABEL else r}
         for r, c in reason_cnt.items()],
        key=lambda x: -x["count"],
    )[:12]  # top 12

    real_data = [d for d in data if not d["data_quality_gap"]]
    missing_count = next((d["count"] for d in data if d["data_quality_gap"]), 0)
    insight = None
    if real_data:
        top = real_data[0]
        insight = f"Most common cause: \"{top['label']}\" ({top['count']} sessions)."
        if missing_count:
            insight += f" ({missing_count} additional session(s) have no reason recorded.)"
    elif missing_count:
        insight = f"{missing_count} cancelled/not-delivered session(s) have no reason recorded yet."

    return {
        "chart_id": "cancellation_reasons",
        "title": "Cancellation and not-delivered reasons",
        "explanation": "Why sessions were not delivered, ranked by frequency.",
        "question": "What is causing the most disruptions to our training program?",
        "chart_type": "bar_horizontal",
        "x_axis": "Sessions",
        "y_axis": "Reason",
        "data": data,
        "insight": insight,
        "empty_state": "No cancellations or not-delivered sessions in this period.",
        "drill_down": {"route": "parade-nights", "filters": {"status": "not_delivered"}},
        "permission_scope": "squadron",
    }


def _facilitator_workload(sessions: list) -> dict:
    """Ranked bar: sessions per facilitator (delivered + planned)."""
    fac_data: dict[str, dict] = {}
    for s in sessions:
        fname = s.facilitator_display_name_at_time or s.facilitator_id
        if not fname:
            continue
        key = s.facilitator_id or fname
        if key not in fac_data:
            fac_data[key] = {"name": fname, "delivered": 0, "planned": 0, "not_delivered": 0, "cancelled": 0, "total": 0}
        d = fac_data[key]
        st = s.status or "planned"
        if st in _DELIVERED:
            d["delivered"] += 1
        elif st == "planned":
            d["planned"] += 1
        elif st == "not_delivered":
            d["not_delivered"] += 1
        elif st == "cancelled":
            d["cancelled"] += 1
        d["total"] += 1

    data = sorted(fac_data.values(), key=lambda x: -x["total"])[:15]

    # Insight: over-reliance
    insight = None
    if len(data) >= 2:
        top = data[0]
        total_all = sum(d["total"] for d in data)
        if total_all > 0 and top["total"] / total_all > 0.4:
            insight = f"{top['name']} is carrying {round(top['total']/total_all*100)}% of all assigned sessions."

    return {
        "chart_id": "facilitator_workload",
        "title": "Facilitator workload",
        "explanation": "Sessions assigned per facilitator — delivered, planned, and not delivered.",
        "question": "Is facilitator workload evenly distributed or concentrated on one person?",
        "chart_type": "bar_horizontal",
        "value_key": "total",
        "x_axis": "Sessions",
        "y_axis": "Facilitator",
        "series": [
            {"key": "delivered", "label": "Delivered", "color": _STATUS_COLORS["delivered"]},
            {"key": "planned", "label": "Planned", "color": _STATUS_COLORS["planned"]},
            {"key": "not_delivered", "label": "Not Delivered", "color": _STATUS_COLORS["not_delivered"]},
            {"key": "cancelled", "label": "Cancelled", "color": _STATUS_COLORS["cancelled"]},
        ],
        "data": data,
        "insight": insight,
        "empty_state": "No facilitator assignments recorded for this period.",
        "drill_down": {"route": "parade-nights"},
        "permission_scope": "squadron",
    }


def _facilitator_status_distribution(facs: list, leave_rows: list) -> dict:
    """Donut: facilitators by current availability status.

    Derived from the data actually available on the Facilitator/PlanningFacilitatorLeave
    models — active_status plus any leave period covering today. There is no separate
    "assigned"/"backup" flag on the model, so this reports the three statuses the data
    can support: on leave, available, unavailable (inactive).
    """
    today_str = date.today().isoformat()
    on_leave_ids = {
        lv.facilitator_id for lv in leave_rows
        if lv.start_date <= today_str <= lv.end_date
    }
    counts = {"on_leave": 0, "available": 0, "unavailable": 0}
    for f in facs:
        if not f.active_status:
            counts["unavailable"] += 1
        elif f.id in on_leave_ids:
            counts["on_leave"] += 1
        else:
            counts["available"] += 1

    data = [
        {"status": "available", "label": "Available", "count": counts["available"], "color": "#2e7d32"},
        {"status": "on_leave", "label": "On leave", "count": counts["on_leave"], "color": "#f57f17"},
        {"status": "unavailable", "label": "Unavailable", "count": counts["unavailable"], "color": "#78909c"},
    ]
    insight = None
    total = sum(counts.values())
    if total and counts["on_leave"] / total > 0.25:
        insight = f"{counts['on_leave']} of {total} facilitators are currently on leave."

    return {
        "chart_id": "facilitator_status_distribution",
        "title": "Facilitator status",
        "explanation": "Current availability of all facilitators on the roster.",
        "question": "How many facilitators are actually available right now?",
        "chart_type": "donut",
        "data": data,
        "insight": insight,
        "empty_state": "No facilitators on the roster.",
        "drill_down": {"route": "facilitators"},
        "permission_scope": "squadron",
    }


def _facilitator_repeated_gaps(sessions: list, pn_date_by_id: dict, weeks: int = 8) -> dict:
    """Ranked bar: subject areas/elements with unfilled (unstaffed) sessions in recent weeks."""
    cutoff = (date.today() - timedelta(weeks=weeks)).isoformat()
    gap_counts: dict[str, int] = defaultdict(int)
    for s in sessions:
        if s.facilitator_id:
            continue
        if getattr(s, "status", None) not in ("planned", "not_delivered"):
            continue
        parade_date = pn_date_by_id.get(s.parade_night_id)
        if parade_date and parade_date < cutoff:
            continue
        label = s.element_at_time or s.curriculum_title_at_time or "Unclassified"
        gap_counts[label] += 1

    data = sorted(
        [{"label": k, "count": v} for k, v in gap_counts.items()],
        key=lambda x: -x["count"],
    )[:10]

    insight = None
    if data:
        top = data[0]
        insight = f"{top['label']} has the most unfilled sessions ({top['count']}) in the last {weeks} weeks."

    return {
        "chart_id": "facilitator_repeated_gaps",
        "title": "Repeated facilitator gaps",
        "explanation": f"Subject areas with the most unstaffed sessions in the last {weeks} weeks.",
        "question": "Where do we repeatedly fail to find a facilitator?",
        "chart_type": "bar_horizontal",
        "x_axis": "Unfilled sessions",
        "y_axis": "Subject area",
        "data": data,
        "insight": insight,
        "empty_state": f"No unstaffed sessions in the last {weeks} weeks.",
        "drill_down": {"route": "parade-nights", "filters": {"status": "unstaffed"}},
        "permission_scope": "squadron",
    }


def _facilitator_leave_impact(facs: list, leave_rows: list, all_pns: list, all_sessions: list) -> dict:
    """Ranked bar: upcoming sessions assigned to a facilitator that fall inside
    their own recorded leave — the "who needs a substitute" chart (master
    transformation plan Block 9 / addendum section DD). Confirmed as a genuine
    gap: nothing else cross-references PlanningFacilitatorLeave against a
    facilitator's own upcoming session assignments."""
    today_str = date.today().isoformat()
    pn_date_by_id = {pn.id: pn.date for pn in all_pns}
    fac_name = {
        f.id: f"{(f.current_rank + ' ') if f.current_rank else ''}{f.first_name} {f.last_name}"
        for f in facs
    }
    upcoming_leave = [lv for lv in leave_rows if lv.end_date >= today_str]
    impact_counts: dict[str, int] = defaultdict(int)
    for lv in upcoming_leave:
        name = fac_name.get(lv.facilitator_id)
        if not name:
            continue
        for s in all_sessions:
            if s.facilitator_id != lv.facilitator_id or s.status != "planned":
                continue
            pd = pn_date_by_id.get(s.parade_night_id)
            if pd and lv.start_date <= pd <= lv.end_date:
                impact_counts[name] += 1

    data = sorted(
        [{"label": k, "count": v} for k, v in impact_counts.items() if v > 0],
        key=lambda x: -x["count"],
    )[:15]

    insight = None
    if data:
        top = data[0]
        insight = f"{top['label']} has {top['count']} upcoming session(s) scheduled during recorded leave — arrange a substitute."

    return {
        "chart_id": "facilitator_leave_impact",
        "title": "Sessions needing a substitute",
        "explanation": "Upcoming sessions assigned to a facilitator during their own recorded leave.",
        "question": "Which upcoming sessions need a substitute facilitator arranged?",
        "chart_type": "bar_horizontal",
        "x_axis": "Sessions affected",
        "y_axis": "Facilitator",
        "data": data,
        "insight": insight,
        "empty_state": "No upcoming sessions clash with recorded facilitator leave.",
        "drill_down": {"route": "facilitator-schedule"},
        "permission_scope": "squadron",
    }


def _session_to_readiness_dict(s) -> dict:
    """Adapt a Session ORM row to the plain dict services_readiness.
    parade_night_readiness() expects."""
    return {
        "id": s.id, "period_number": s.period_number,
        "curriculum_item_id": s.curriculum_item_id, "custom_title": s.custom_title,
        "session_title": s.session_title,
        "facilitator_id": s.facilitator_id, "facilitator_display_name_at_time": s.facilitator_display_name_at_time,
        "training_area_id": s.training_area_id, "training_area_name_at_time": s.training_area_name_at_time,
        "status": s.status, "not_delivered_reason": s.not_delivered_reason, "cancelled_reason": s.cancelled_reason,
    }


def _tonight_readiness(pns: list, sessions: list, facs: list, rooms: list) -> dict:
    """Tonight's / next parade night readiness card — sourced entirely from
    services_readiness.parade_night_readiness(), the single authoritative
    computation also used by _upcoming_readiness, training.py's _recompute/
    get_parade, and ops.py's reports/wing-overview. A zero-session night is
    "not_planned" here structurally (parade_night_readiness's own hard rule),
    never "ready to run" — this closes the exact contradiction this pass found:
    the old inline math could show 0% next to "Tonight's program is ready to run."
    because `issues` was empty (no unfilled slots to report) on an empty night."""
    today_str = date.today().isoformat()
    upcoming_pns = sorted([pn for pn in pns if pn.date >= today_str], key=lambda p: p.date)
    if not upcoming_pns:
        return {
            "chart_id": "tonight",
            "chart_type": "readiness_card",
            "data": None,
            "empty_state": "No upcoming parade night scheduled.",
            "permission_scope": "squadron",
        }

    next_pn = upcoming_pns[0]
    pn_sessions = [s for s in sessions if s.parade_night_id == next_pn.id]
    readiness = parade_night_readiness([_session_to_readiness_dict(s) for s in pn_sessions])

    issues = []
    unfilled_fac = [s for s in pn_sessions if not s.facilitator_id]
    if unfilled_fac:
        ph_list = ", ".join(s.phase_at_time or "?" for s in unfilled_fac[:3])
        issues.append({
            "type": "facilitator_gap",
            "severity": "high" if len(unfilled_fac) >= 2 else "medium",
            "message": f"{len(unfilled_fac)} session(s) still need a facilitator ({ph_list}).",
            "action": "Assign facilitators in Parade Nights.",
        })

    unfilled_room = [s for s in pn_sessions if not s.training_area_id]
    if unfilled_room:
        issues.append({
            "type": "room_gap",
            "severity": "medium",
            "message": f"{len(unfilled_room)} session(s) have no room assigned.",
            "action": "Assign training areas in Parade Nights.",
        })

    fac_filled = sum(1 for s in pn_sessions if s.facilitator_id)
    room_filled = sum(1 for s in pn_sessions if s.training_area_id)
    total_sess = readiness["sessions_total"]

    if readiness["planning_status"] == "not_planned":
        plain = "No sessions are scheduled for the next parade night."
    elif readiness["planning_status"] == "planned":
        plain = "Tonight's program is ready to run."
    elif readiness["planning_status"] == "blocked":
        plain = f"Tonight's program has an unresolved conflict — {readiness['requirements_summary']}."
    else:
        plain = f"Tonight's program can run, but {readiness['requirements_summary']} — {len(issues)} item(s) need attention."

    return {
        "chart_id": "tonight",
        "title": "Tonight's readiness",
        "explanation": plain,
        "question": "Is tonight's parade night ready to run?",
        "chart_type": "readiness_card",
        "data": {
            "date": next_pn.date,
            "term": next_pn.term,
            "planning_status": readiness["planning_status"],
            "data_quality": readiness["data_quality"],
            "overall_pct": readiness["legacy_score"],
            "sessions_total": total_sess,
            "sessions_ready": readiness["sessions_ready"],
            "fac_filled": fac_filled,
            "fac_total": total_sess,
            "room_filled": room_filled,
            "room_total": total_sess,
            "sessions": [
                {
                    "id": s.id,
                    "period": s.period_number,
                    "phase": s.phase_at_time,
                    "title": s.curriculum_title_at_time or s.custom_title or s.phase_at_time,
                    "facilitator": s.facilitator_display_name_at_time or None,
                    "room": s.training_area_name_at_time or None,
                    "status": s.status,
                    "ready": bool(s.facilitator_id),
                }
                for s in sorted(pn_sessions, key=lambda x: x.period_number or 0)
            ],
            "issues": issues,
        },
        "insight": plain,
        "empty_state": "No sessions planned for the next parade night.",
        "drill_down": {"route": "parade-nights", "filters": {"date": next_pn.date}},
        "permission_scope": "squadron",
    }


def _session_outcomes_distribution(sessions: list) -> dict:
    """Donut/bar: overall session status distribution for the period."""
    counts = defaultdict(int)
    for s in sessions:
        counts[s.status or "planned"] += 1
    total = sum(counts.values())

    data = [
        {"status": st, "label": lb, "count": counts.get(st, 0),
         "pct": round(counts.get(st, 0) / total * 100) if total else 0,
         "color": _STATUS_COLORS.get(st, "#ccc")}
        for st, lb in [
            ("delivered", "Delivered"),
            ("delivered_with_issue", "Delivered (with issue)"),
            ("not_delivered", "Not Delivered"),
            ("cancelled", "Cancelled"),
            ("rescheduled", "Rescheduled"),
            ("planned", "Planned"),
        ]
    ]
    del_count = counts.get("delivered", 0) + counts.get("delivered_with_issue", 0)
    insight = None
    if total > 0:
        pct = round(del_count / total * 100)
        if pct >= 80:
            insight = f"{pct}% of sessions were delivered — strong program delivery."
        elif pct >= 60:
            insight = f"{pct}% of sessions delivered — some disruption this period."
        else:
            insight = f"Only {pct}% of sessions delivered — review causes of disruption."

    return {
        "chart_id": "session_outcomes",
        "title": "Session outcomes",
        "explanation": "Overall distribution of session outcomes for the selected period.",
        "question": "What proportion of our sessions are being delivered?",
        "chart_type": "donut",
        "data": data,
        "insight": insight,
        "empty_state": "No sessions recorded for this period.",
        "drill_down": {"route": "parade-nights"},
        "permission_scope": "squadron",
    }


def _upcoming_readiness(pns: list, sessions: list) -> dict:
    """Card grid: next 8 parade nights, using the same authoritative
    parade_night_readiness() as _tonight_readiness. Previously this computed its
    own staffing-only ratio and could report "All upcoming parade nights are fully
    staffed" even when some nights had zero sessions (an empty night contributed
    unstaffed=0, which read as "staffed") — a zero-session night is now
    "not_planned" and is excluded from the fully-staffed claim below."""
    today_str = date.today().isoformat()
    upcoming = sorted([pn for pn in pns if pn.date >= today_str], key=lambda p: p.date)[:8]
    pn_sessions: dict[str, list] = defaultdict(list)
    for s in sessions:
        pn_sessions[s.parade_night_id].append(s)

    data = []
    for pn in upcoming:
        sess = pn_sessions.get(pn.id, [])
        readiness = parade_night_readiness([_session_to_readiness_dict(s) for s in sess])
        unstaffed = sum(1 for s in sess if not s.facilitator_id)
        data.append({
            "date": pn.date,
            "term": pn.term,
            "planning_status": readiness["planning_status"],
            "data_quality": readiness["data_quality"],
            "sessions_total": readiness["sessions_total"],
            "sessions_ready": readiness["sessions_ready"],
            "unstaffed": unstaffed,
            "readiness_pct": readiness["legacy_score"],
            "published": pn.published_status,
        })

    # "Fully staffed" can only be claimed about nights that actually have sessions —
    # a not_planned (zero-session) night is neither staffed nor unstaffed, it's simply
    # not yet planned, and must never count toward a "fully staffed" claim either way.
    planned_nights = [d for d in data if d["planning_status"] != "not_planned"]
    unplanned_count = sum(1 for d in data if d["planning_status"] == "not_planned")
    if not data:
        insight = None
    elif any(d["unstaffed"] > 0 for d in planned_nights):
        insight = f"{sum(1 for d in planned_nights if d['unstaffed'] > 0)} upcoming nights have unstaffed sessions."
    elif unplanned_count:
        insight = f"All planned nights are fully staffed, but {unplanned_count} upcoming night(s) have no sessions scheduled yet."
    elif planned_nights:
        insight = "All upcoming parade nights are fully staffed."
    else:
        insight = "No upcoming parade nights are planned yet."

    return {
        "chart_id": "upcoming_readiness",
        "title": "Upcoming parade night readiness",
        "explanation": "Staffing readiness for the next eight parade nights.",
        "question": "Are upcoming parade nights fully staffed?",
        "chart_type": "readiness_grid",
        "data": data,
        "insight": insight,
        "empty_state": "No upcoming parade nights scheduled.",
        "drill_down": {"route": "parade-nights"},
        "permission_scope": "squadron",
    }


# ── chart builders: wing ──────────────────────────────────────────────────────

def _squadron_readiness(db: DBSession, wing_id: str, window_start: str, window_end: str) -> dict:
    """Wing: ranked bar of squadron readiness (% sessions delivered)."""
    sqns = db.query(Squadron).filter(
        Squadron.wing_id == wing_id,
        Squadron.is_archived == False,  # noqa: E712
    ).all()

    data = []
    for sqn in sqns:
        pns = db.query(ParadeNight).filter(
            ParadeNight.squadron_id == sqn.id,
            ParadeNight.date >= window_start,
            ParadeNight.date <= window_end,
        ).all()
        pn_ids = [pn.id for pn in pns]
        if not pn_ids:
            data.append({"label": sqn.code, "name": sqn.short_name, "readiness_pct": 0, "total": 0, "delivered": 0})
            continue
        sessions = db.query(Session).filter(
            Session.parade_night_id.in_(pn_ids),
            Session.is_archived == False,  # noqa: E712
        ).all()
        total = len([s for s in sessions if s.status in _TERMINAL])
        delivered = sum(1 for s in sessions if s.status in _DELIVERED)
        pct = round(delivered / total * 100) if total else 0
        data.append({
            "label": sqn.code,
            "name": sqn.short_name,
            "readiness_pct": pct,
            "total": total,
            "delivered": delivered,
            "squadron_id": sqn.id,
        })

    data.sort(key=lambda x: -x["readiness_pct"])
    insight = None
    if data:
        best = data[0]
        worst = data[-1]
        if best["readiness_pct"] - worst["readiness_pct"] > 20:
            insight = f"{best['label']} is leading at {best['readiness_pct']}%; {worst['label']} is lowest at {worst['readiness_pct']}%."

    return {
        "chart_id": "squadron_readiness",
        "title": "Squadron delivery readiness",
        "explanation": "Percentage of sessions delivered by squadron for the selected period.",
        "question": "Which squadrons are delivering their program reliably?",
        "chart_type": "bar_horizontal",
        "x_axis": "Delivery reliability %",
        "y_axis": "Squadron",
        "data": data,
        "insight": insight,
        "empty_state": "No delivery data for any squadron in this period.",
        "drill_down": {"route": "parade-nights", "filters": {"squadron_id": "{{squadron_id}}"}},
        "permission_scope": "wing",
    }


def _squadron_delivery_comparison(db: DBSession, wing_id: str, window_start: str, window_end: str) -> dict:
    """Wing: grouped bar comparing squadron session counts by outcome."""
    sqns = db.query(Squadron).filter(
        Squadron.wing_id == wing_id,
        Squadron.is_archived == False,  # noqa: E712
    ).all()

    data = []
    for sqn in sqns:
        pns = db.query(ParadeNight).filter(
            ParadeNight.squadron_id == sqn.id,
            ParadeNight.date >= window_start,
            ParadeNight.date <= window_end,
        ).all()
        pn_ids = [pn.id for pn in pns]
        sessions = db.query(Session).filter(
            Session.parade_night_id.in_(pn_ids),
            Session.is_archived == False,  # noqa: E712
        ).all() if pn_ids else []
        delivered = sum(1 for s in sessions if s.status in _DELIVERED)
        not_del = sum(1 for s in sessions if s.status == "not_delivered")
        cancelled = sum(1 for s in sessions if s.status == "cancelled")
        planned = sum(1 for s in sessions if s.status == "planned")
        data.append({
            "label": sqn.code,
            "name": sqn.short_name,
            "delivered": delivered,
            "not_delivered": not_del,
            "cancelled": cancelled,
            "planned": planned,
        })

    return {
        "chart_id": "squadron_delivery_comparison",
        "title": "Squadron session outcomes comparison",
        "explanation": "Delivered, not delivered and cancelled sessions for each squadron.",
        "question": "How does session delivery compare across squadrons?",
        "chart_type": "grouped_bar",
        "x_axis": "Sessions",
        "y_axis": "Squadron",
        "series": [
            {"key": "delivered", "label": "Delivered", "color": _STATUS_COLORS["delivered"]},
            {"key": "not_delivered", "label": "Not Delivered", "color": _STATUS_COLORS["not_delivered"]},
            {"key": "cancelled", "label": "Cancelled", "color": _STATUS_COLORS["cancelled"]},
            {"key": "planned", "label": "Planned", "color": _STATUS_COLORS["planned"]},
        ],
        "data": data,
        "empty_state": "No session data for this period.",
        "drill_down": {"route": "parade-nights"},
        "permission_scope": "wing",
    }


def _wing_subject_area_gaps(db: DBSession, wing_id: str) -> dict:
    """Wing: heatmap of facilitator subject-area coverage per squadron."""
    sqns = db.query(Squadron).filter(
        Squadron.wing_id == wing_id,
        Squadron.is_archived == False,  # noqa: E712
    ).all()

    # Collect all subject areas used across the wing
    facs_all = db.query(Facilitator).filter(
        Facilitator.wing_id == wing_id,
        Facilitator.active_status == True,  # noqa: E712
        Facilitator.is_archived == False,  # noqa: E712
    ).all()

    subject_areas: set[str] = set()
    for f in facs_all:
        for sa in (f.subject_areas or []):
            subject_areas.add(sa)
    subject_areas = sorted(subject_areas)

    # For each squadron × subject area: count qualified facilitators
    rows = []
    for sqn in sqns:
        facs_sqn = [f for f in facs_all if f.squadron_id == sqn.id]
        cells = []
        for sa in subject_areas:
            count = sum(1 for f in facs_sqn if sa in (f.subject_areas or []))
            risk = "ok" if count >= 3 else "warn" if count >= 1 else "critical"
            cells.append({"label": sa, "subject_area": sa, "count": count, "risk": risk})
        rows.append({"label": sqn.code, "name": sqn.short_name, "cells": cells})

    critical_gaps = sum(
        1 for row in rows for cell in row["cells"] if cell["risk"] == "critical"
    )
    insight = (
        f"{critical_gaps} squadron × subject-area combination(s) have no qualified facilitator."
        if critical_gaps else
        "All squadrons have at least one facilitator per subject area."
    ) if rows else None

    return {
        "chart_id": "wing_subject_area_gaps",
        "title": "Wing subject-area facilitator coverage",
        "explanation": "Number of qualified facilitators per subject area per squadron.",
        "question": "Where are the staffing gaps across the Wing?",
        "chart_type": "heatmap",
        "columns": subject_areas,
        "data": rows,
        "insight": insight,
        "empty_state": "No facilitator subject-area data available.",
        "permission_scope": "wing",
    }


# ── chart builders: national ──────────────────────────────────────────────────

def _wing_readiness_comparison(db: DBSession, window_start: str, window_end: str) -> dict:
    """National: ranked bar of wing delivery readiness."""
    wings = db.query(Wing).filter(Wing.is_archived == False).all()  # noqa: E712
    data = []
    for wing in wings:
        sqn_ids = [r.id for r in db.query(Squadron.id).filter(
            Squadron.wing_id == wing.id,
            Squadron.is_archived == False,  # noqa: E712
        ).all()]
        if not sqn_ids:
            continue
        pns = db.query(ParadeNight).filter(
            ParadeNight.wing_id == wing.id,
            ParadeNight.date >= window_start,
            ParadeNight.date <= window_end,
        ).all()
        pn_ids = [pn.id for pn in pns]
        if not pn_ids:
            data.append({"label": wing.code, "name": wing.name, "readiness_pct": 0, "total": 0})
            continue
        sessions = db.query(Session).filter(
            Session.parade_night_id.in_(pn_ids),
            Session.is_archived == False,  # noqa: E712
        ).all()
        total = len([s for s in sessions if s.status in _TERMINAL])
        delivered = sum(1 for s in sessions if s.status in _DELIVERED)
        pct = round(delivered / total * 100) if total else 0
        data.append({
            "label": wing.code, "name": wing.name,
            "readiness_pct": pct, "total": total, "delivered": delivered,
            "wing_id": wing.id,
        })

    data.sort(key=lambda x: -x["readiness_pct"])
    return {
        "chart_id": "wing_readiness",
        "title": "Wing delivery readiness",
        "explanation": "Percentage of sessions delivered by Wing for the selected period.",
        "question": "Which Wings are delivering their training program most reliably?",
        "chart_type": "bar_horizontal",
        "x_axis": "Delivery reliability %",
        "y_axis": "Wing",
        "data": data,
        "empty_state": "No delivery data for any Wing in this period.",
        "drill_down": {"route": "parade-nights"},
        "permission_scope": "national",
    }


# ── command dashboard: Wing / National (Sections A + B) ────────────────────────
# Extends the existing Squadron dashboard upward — the Wing dashboard aggregates
# Squadron information, the National dashboard aggregates Wing information.
# Every chart aggregates the underlying counts first and never averages
# per-unit percentages. Every chart carries the operational metadata (purpose/
# measure/action/data_confidence) the command dashboard design requires, not
# just a title and a number — see docs/release/qualification_gap_register.md
# for the requirement this implements.

_RISK_CATEGORY_LABELS = {
    "no_facilitator": "No facilitator confirmed",
    "no_facility": "No facility confirmed",
    "curriculum_not_allocated": "Curriculum not allocated",
    "activity_conflict": "Activity scheduling conflict",
    "holiday_conflict": "Falls within a holiday period",
}
_RISK_CATEGORY_ACTIONS = {
    "no_facilitator": "Assign a facilitator in Parade Nights before the session date.",
    "no_facility": "Assign a training area in Parade Nights before the session date.",
    "curriculum_not_allocated": "Allocate a curriculum item to this session.",
    "activity_conflict": "Review the scheduling conflict with the affected Activity.",
    "holiday_conflict": "Confirm whether this parade night should proceed during the holiday period.",
}


def _command_child_units(db: DBSession, scope: str, wing_id: str | None) -> list[dict]:
    """Rows for the command dashboard: Squadrons for a Wing view, Wings for a
    National view. Archived units excluded, matching every other list
    endpoint in this codebase."""
    if scope == "wing":
        rows = db.query(Squadron).filter(
            Squadron.wing_id == wing_id, Squadron.is_archived == False,  # noqa: E712
        ).order_by(Squadron.code).all()
        return [{"id": r.id, "code": r.code, "name": r.short_name or r.name, "kind": "squadron"} for r in rows]
    rows = db.query(Wing).filter(Wing.is_archived == False).order_by(Wing.code).all()  # noqa: E712
    return [{"id": r.id, "code": r.code, "name": r.name, "kind": "wing"} for r in rows]


def _unit_session_filter(kind: str, unit_id: str):
    """SQLAlchemy filter clause selecting ParadeNight rows owned by one child unit."""
    if kind == "squadron":
        return ParadeNight.squadron_id == unit_id
    return ParadeNight.wing_id == unit_id


def _unit_pns_and_sessions(db: DBSession, kind: str, unit_id: str, window_start: str, window_end: str):
    pns = db.query(ParadeNight).filter(
        _unit_session_filter(kind, unit_id),
        ParadeNight.date >= window_start, ParadeNight.date <= window_end,
        ParadeNight.is_archived == False,  # noqa: E712
    ).all()
    pn_ids = [pn.id for pn in pns]
    sessions = db.query(Session).filter(
        Session.parade_night_id.in_(pn_ids), Session.is_archived == False,  # noqa: E712
    ).all() if pn_ids else []
    return pns, sessions


def _next_unit_readiness(db: DBSession, kind: str, unit_id: str) -> dict | None:
    """Next programmed parade night for one child unit and its readiness
    computation — services_readiness.parade_night_readiness(), the same single
    authoritative computation the Squadron dashboard's own "tonight" card
    uses. Returns None if nothing is programmed yet (never fabricates a 0%)."""
    today_str = date.today().isoformat()
    pns = db.query(ParadeNight).filter(
        _unit_session_filter(kind, unit_id),
        ParadeNight.date >= today_str, ParadeNight.is_archived == False,  # noqa: E712
    ).order_by(ParadeNight.date).all()
    if not pns:
        return None
    next_pn = pns[0]
    sessions = db.query(Session).filter(
        Session.parade_night_id == next_pn.id, Session.is_archived == False,  # noqa: E712
    ).all()
    readiness = parade_night_readiness([_session_to_readiness_dict(s) for s in sessions])
    return {"parade_night": next_pn, "readiness": readiness}


def _unit_readiness_trend(db: DBSession, kind: str, unit_id: str, current_pct: int | None) -> str:
    """Compare the upcoming parade night's readiness to the most recently
    completed one — a genuine trend from real prior data, not a guess.
    Returns 'up' | 'down' | 'flat' | 'no_data'. A None current_pct (the
    upcoming night itself has zero sessions — "not_planned") always yields
    'no_data': there is nothing numeric to compare."""
    if current_pct is None:
        return "no_data"
    today_str = date.today().isoformat()
    prev_pns = db.query(ParadeNight).filter(
        _unit_session_filter(kind, unit_id),
        ParadeNight.date < today_str, ParadeNight.is_archived == False,  # noqa: E712
    ).order_by(ParadeNight.date.desc()).limit(1).all()
    if not prev_pns:
        return "no_data"
    prev_sessions = db.query(Session).filter(
        Session.parade_night_id == prev_pns[0].id, Session.is_archived == False,  # noqa: E712
    ).all()
    prev_readiness = parade_night_readiness([_session_to_readiness_dict(s) for s in prev_sessions])
    if prev_readiness["planning_status"] == "not_planned":
        # The previous PN also had zero sessions — legacy_score there is the
        # same fabricated-100 legacy value, not a real prior readiness to
        # compare against.
        return "no_data"
    prev_pct = prev_readiness["legacy_score"]
    if current_pct > prev_pct:
        return "up"
    if current_pct < prev_pct:
        return "down"
    return "flat"


def _matrix_cell(numerator: int | None, denominator: int | None, missing_label: str,
                  data_available: bool = True, unavailable_reason: str | None = None) -> dict:
    """One cell of a readiness matrix column: status/numerator/denominator/
    warning/exception_reason — honestly distinguishing "no data" from "zero"
    rather than collapsing both into the same 0%."""
    if not data_available:
        return {"status": "no_data", "numerator": None, "denominator": None, "pct": None,
                "warning": False, "exception_reason": unavailable_reason or "Data not available.",
                "data_available": False}
    if not denominator:
        return {"status": "no_data", "numerator": 0, "denominator": 0, "pct": None,
                "warning": False, "exception_reason": "No sessions scheduled.", "data_available": True}
    pct = round(numerator / denominator * 100)
    if numerator == denominator:
        status, warning, reason = "ok", False, None
    elif numerator == 0:
        status, warning, reason = "critical", True, f"No sessions have {missing_label}."
    else:
        status, warning = "warning", True
        reason = f"{denominator - numerator} of {denominator} session(s) missing {missing_label}."
    return {"status": status, "numerator": numerator, "denominator": denominator, "pct": pct,
            "warning": warning, "exception_reason": reason, "data_available": True}


def _readiness_matrix(db: DBSession, scope: str, units: list[dict]) -> dict:
    """A1 — Next parade night readiness matrix. Wing view: rows = Squadrons.
    National view: rows = Wings."""
    rows = []
    reporting = 0
    for u in units:
        next_r = _next_unit_readiness(db, u["kind"], u["id"])
        if next_r is None:
            rows.append({
                "unit_id": u["id"], "label": u["code"], "name": u["name"], "status": "no_data",
                "sessions_planned": _matrix_cell(0, 0, "n/a"),
                "curriculum_allocated": _matrix_cell(None, None, "curriculum allocated", False,
                                                      "No parade night programmed yet."),
                "facilitator_confirmed": _matrix_cell(None, None, "a facilitator", False,
                                                       "No parade night programmed yet."),
                "facility_confirmed": _matrix_cell(None, None, "a facility", False,
                                                    "No parade night programmed yet."),
                "equipment_confirmed": _matrix_cell(None, None, "equipment", False,
                                                     "Equipment confirmation is not tracked per session in this system."),
                "overall_readiness": _matrix_cell(0, 0, "n/a"),
                "trend": "no_data", "last_update": None,
                "exception_reason": "No upcoming parade night programmed.",
            })
            continue
        reporting += 1
        readiness = next_r["readiness"]
        sess = readiness["sessions"]
        total = readiness["sessions_total"]
        curriculum_n = sum(1 for s in sess if s["requirements"]["checks"]["curriculum_assigned"])
        facilitator_n = sum(1 for s in sess if s["requirements"]["checks"]["facilitator_assigned"])
        facility_n = sum(1 for s in sess if s["requirements"]["checks"]["room_assigned"])
        # legacy_score is hard-coded to 100 for a zero-session ("not_planned")
        # parade night by services_readiness.py's own explicit design (a
        # legacy-consumer compatibility value) — it must NEVER be read as "100%
        # ready" here, which is exactly the class of bug that module's own
        # docstring documents fixing elsewhere. A not-planned night reports no
        # numeric readiness at all, honestly, rather than a fabricated 100%.
        overall_pct = None if readiness["planning_status"] == "not_planned" else readiness["legacy_score"]
        trend = _unit_readiness_trend(db, u["kind"], u["id"], overall_pct)
        overall_status = {"planned": "ok", "partly_planned": "warning", "at_risk": "critical",
                          "blocked": "critical", "not_planned": "no_data"}[readiness["planning_status"]]
        rows.append({
            "unit_id": u["id"], "label": u["code"], "name": u["name"], "status": overall_status,
            "sessions_planned": {"status": "ok", "numerator": total, "denominator": None, "pct": None,
                                 "warning": False, "exception_reason": None, "data_available": True},
            "curriculum_allocated": _matrix_cell(curriculum_n, total, "a curriculum item"),
            "facilitator_confirmed": _matrix_cell(facilitator_n, total, "a facilitator"),
            "facility_confirmed": _matrix_cell(facility_n, total, "a facility"),
            "equipment_confirmed": _matrix_cell(None, None, "equipment", False,
                                                 "Equipment confirmation is not tracked per session in this system."),
            "overall_readiness": {
                "status": overall_status, "numerator": readiness["sessions_ready"], "denominator": total,
                "pct": overall_pct, "warning": overall_status != "ok",
                "exception_reason": None if overall_status == "ok" else readiness["requirements_summary"],
                "data_available": True,
            },
            "trend": trend,
            "last_update": next_r["parade_night"].updated_at.isoformat()
                if getattr(next_r["parade_night"], "updated_at", None) else None,
            "exception_reason": None if overall_status == "ok" else readiness["requirements_summary"],
        })

    at_risk = sum(1 for r in rows if r["status"] in ("critical", "warning"))
    unit_noun = "Squadrons" if scope == "wing" else "Wings"
    insight = (f"{at_risk} of {len(rows)} {unit_noun} have an unresolved readiness gap for their next parade night."
               if rows else None)
    return {
        "chart_id": "readiness_matrix",
        "title": "Next parade night readiness",
        "purpose": "Determine whether subordinate units can deliver the next programmed training activity and identify matters requiring immediate command attention.",
        "measure": "Sessions with a curriculum item, facilitator and facility confirmed, against the total sessions programmed for each unit's next parade night.",
        "assessment": insight or "No subordinate units report an upcoming parade night.",
        "action": "Direct corrective action, coordinate support, approve an alternate arrangement, accept identified risk, or initiate intervention for units showing a readiness gap.",
        "question": "Which subordinate formations or units are ready to deliver the next training activity?",
        "chart_type": "readiness_matrix",
        "columns": ["sessions_planned", "curriculum_allocated", "facilitator_confirmed",
                    "facility_confirmed", "equipment_confirmed", "overall_readiness"],
        "data": rows,
        "insight": insight,
        "empty_state": "No subordinate units in scope.",
        "drill_down": {"route": "parade-nights",
                       "filters": ({"squadron_id": "{{unit_id}}"} if scope == "wing" else {"wing_id": "{{unit_id}}"})},
        "data_confidence": {"units_reporting": reporting, "units_expected": len(units),
                            "completeness_pct": round(reporting / len(units) * 100) if units else None},
    }


def _risk_forecast(db: DBSession, scope: str, wing_id: str | None, units: list[dict]) -> dict:
    """A2 — Eight-week training risk forecast. Real, non-fabricated risk
    categories only: no_facilitator/no_facility/curriculum_not_allocated are
    derived directly from session_requirements(); activity_conflict from the
    Activity model; holiday_conflict from HolidayPeriod (affects_parade=True).
    Equipment availability has no per-session confirmation model in this
    schema — reported as a distinct, honestly-labelled data-confidence gap,
    never fabricated."""
    from ..models import Activity, HolidayPeriod, PlanningYear

    today = date.today()
    horizon = (today + timedelta(weeks=8)).isoformat()
    today_str = today.isoformat()

    unit_ids = [u["id"] for u in units]
    unit_by_id = {u["id"]: u for u in units}

    # Activities in the forecast window, grouped by owning unit + date.
    if scope == "wing":
        activities = db.query(Activity).filter(
            Activity.squadron_id.in_(unit_ids), Activity.date_start >= today_str,
            Activity.date_start <= horizon, Activity.is_archived == False,  # noqa: E712
        ).all() if unit_ids else []
        activity_dates: dict[str, set[str]] = defaultdict(set)
        for a in activities:
            if a.squadron_id:
                activity_dates[a.squadron_id].add(a.date_start)
    else:
        activities = db.query(Activity).filter(
            Activity.wing_id.in_(unit_ids), Activity.date_start >= today_str,
            Activity.date_start <= horizon, Activity.is_archived == False,  # noqa: E712
        ).all() if unit_ids else []
        activity_dates = defaultdict(set)
        for a in activities:
            if a.wing_id:
                activity_dates[a.wing_id].add(a.date_start)

    # Holiday periods affecting parade nights, resolved via each unit's own
    # PlanningYear(s) — a real, existing model, not a fabricated check.
    holiday_ranges_by_unit: dict[str, list[tuple[str, str]]] = defaultdict(list)
    if scope == "wing":
        pys = db.query(PlanningYear).filter(PlanningYear.unit_id.in_(unit_ids)).all() if unit_ids else []
        py_to_unit = {py.id: py.unit_id for py in pys}
    else:
        pys = db.query(PlanningYear).filter(PlanningYear.wing_id.in_(unit_ids)).all() if unit_ids else []
        py_to_unit = {py.id: py.wing_id for py in pys}
    if pys:
        holidays = db.query(HolidayPeriod).filter(
            HolidayPeriod.planning_year_id.in_(list(py_to_unit.keys())),
            HolidayPeriod.affects_parade == True,  # noqa: E712
            HolidayPeriod.end_date >= today_str, HolidayPeriod.start_date <= horizon,
        ).all()
        for h in holidays:
            unit_id = py_to_unit.get(h.planning_year_id)
            if unit_id:
                holiday_ranges_by_unit[unit_id].append((h.start_date, h.end_date))

    items = []
    for u in units:
        pns, sessions = _unit_pns_and_sessions(db, u["kind"], u["id"], today_str, horizon)
        pn_date_by_id = {pn.id: pn.date for pn in pns}
        sess_by_pn: dict[str, list] = defaultdict(list)
        for s in sessions:
            sess_by_pn[s.parade_night_id].append(s)
        for pn in pns:
            pn_sessions = sess_by_pn.get(pn.id, [])
            reqs_per_session = [session_requirements(_session_to_readiness_dict(s)) for s in pn_sessions]
            no_fac = sum(1 for r in reqs_per_session if not r["checks"]["facilitator_assigned"])
            no_fac_ct = sum(1 for r in reqs_per_session if not r["checks"]["room_assigned"])
            no_curr = sum(1 for r in reqs_per_session if not r["checks"]["curriculum_assigned"])
            has_activity_conflict = pn.date in activity_dates.get(u["id"], set())
            has_holiday_conflict = any(start <= pn.date <= end for start, end in holiday_ranges_by_unit.get(u["id"], []))
            severity = "high" if pn.date <= (today + timedelta(weeks=2)).isoformat() else "medium"
            for cat, count in (("no_facilitator", no_fac), ("no_facility", no_fac_ct), ("curriculum_not_allocated", no_curr)):
                if count:
                    items.append({
                        "date": pn.date, "unit_id": u["id"], "unit_label": u["code"],
                        "parade_night_id": pn.id, "category": cat,
                        "category_label": _RISK_CATEGORY_LABELS[cat],
                        "affected_sessions": count, "severity": severity,
                        "action": _RISK_CATEGORY_ACTIONS[cat],
                    })
            if has_activity_conflict:
                items.append({
                    "date": pn.date, "unit_id": u["id"], "unit_label": u["code"],
                    "parade_night_id": pn.id, "category": "activity_conflict",
                    "category_label": _RISK_CATEGORY_LABELS["activity_conflict"],
                    "affected_sessions": len(pn_sessions), "severity": severity,
                    "action": _RISK_CATEGORY_ACTIONS["activity_conflict"],
                })
            if has_holiday_conflict:
                items.append({
                    "date": pn.date, "unit_id": u["id"], "unit_label": u["code"],
                    "parade_night_id": pn.id, "category": "holiday_conflict",
                    "category_label": _RISK_CATEGORY_LABELS["holiday_conflict"],
                    "affected_sessions": len(pn_sessions), "severity": severity,
                    "action": _RISK_CATEGORY_ACTIONS["holiday_conflict"],
                })

    items.sort(key=lambda x: x["date"])

    weekly: dict[str, dict] = defaultdict(lambda: {"label": "", **{c: 0 for c in _RISK_CATEGORY_LABELS}})
    for it in items:
        wk = _iso_week(it["date"])
        weekly[wk]["label"] = wk
        weekly[wk][it["category"]] += 1
    weekly_data = sorted(weekly.values(), key=lambda r: r["label"])

    insight = None
    if items:
        by_cat: dict[str, int] = defaultdict(int)
        for it in items:
            by_cat[it["category"]] += 1
        top_cat = max(by_cat, key=by_cat.get)
        insight = f"{len(items)} risk item(s) identified in the next 8 weeks — most common: {_RISK_CATEGORY_LABELS[top_cat]} ({by_cat[top_cat]})."

    return {
        "chart_id": "risk_forecast",
        "title": "Eight-week training risk forecast",
        "purpose": "Identify what programmed training is at risk within the next eight weeks, before forecast deficiencies become failed training outcomes.",
        "measure": "Parade nights in the next 8 weeks with an unresolved facilitator, facility, curriculum, activity-conflict or holiday-conflict deficiency.",
        "assessment": insight or "No risk items identified in the next 8 weeks.",
        "action": "Act on flagged items before the affected parade night, prioritising items marked high severity (within 2 weeks).",
        "question": "What programmed training is at risk within the next eight weeks?",
        "chart_type": "risk_timeline",
        "weekly": weekly_data,
        "data": items[:200],
        "insight": insight,
        "empty_state": "No training risk identified in the next 8 weeks.",
        "drill_down": {"route": "parade-nights", "filters": {"date": "{{date}}"}},
        "data_confidence": {
            "categories_tracked": list(_RISK_CATEGORY_LABELS.keys()),
            "categories_not_available": ["equipment_unavailable"],
            "note": "Equipment availability is not confirmed per session in this system — not included above.",
        },
    }


def _immediate_issues(risk_items: list[dict], units: list[dict], scope: str) -> dict:
    """A3 — Immediate issues requiring support, ranked by unit. Reuses the
    near-term (next 2 weeks) slice of A2's real risk items — no separate
    fabricated count."""
    by_unit: dict[str, dict] = {u["id"]: {"unit_id": u["id"], "label": u["code"], "name": u["name"],
                                          **{c: 0 for c in _RISK_CATEGORY_LABELS}, "total": 0}
                                for u in units}
    for it in risk_items:
        if it["severity"] != "high":
            continue
        row = by_unit.get(it["unit_id"])
        if row is None:
            continue
        row[it["category"]] += it["affected_sessions"]
        row["total"] += it["affected_sessions"]

    data = sorted([r for r in by_unit.values() if r["total"] > 0], key=lambda x: -x["total"])
    unit_noun = "Squadron" if scope == "wing" else "Wing"
    insight = f"{data[0]['label']} currently requires the greatest command attention ({data[0]['total']} unresolved item(s))." if data else None

    return {
        "chart_id": "immediate_issues",
        "title": "Immediate issues requiring support",
        "purpose": "Identify which subordinate formation or unit currently requires the greatest command attention.",
        "measure": "Unresolved facilitator, facility, curriculum, and scheduling-conflict items due within the next 2 weeks, by unit.",
        "assessment": insight or f"No {unit_noun.lower()} currently has an unresolved issue due within 2 weeks.",
        "action": "Establish support and intervention priorities, starting with the highest-ranked unit.",
        "question": f"Which subordinate formation or unit currently requires the greatest command attention?",
        "chart_type": "stacked_bar_horizontal",
        "x_axis": "Unresolved items (next 2 weeks)",
        "y_axis": unit_noun,
        "series": [{"key": k, "label": v} for k, v in _RISK_CATEGORY_LABELS.items()],
        "data": data,
        "insight": insight,
        "empty_state": "No immediate issues requiring support.",
        "drill_down": {"route": "parade-nights",
                       "filters": ({"squadron_id": "{{unit_id}}"} if scope == "wing" else {"wing_id": "{{unit_id}}"})},
    }


def _command_weekly_delivered(all_sessions: list, all_pns: list) -> dict:
    """B1 — Training delivered each week, aggregated across the whole scope
    (all subordinate units' sessions combined, counted first — not averaged)."""
    chart = _weekly_outcomes(all_sessions, all_pns)
    chart.update({
        "purpose": "Assess whether the approved training program is being delivered across all subordinate units.",
        "measure": "Sessions by outcome (delivered / delivered with issue / cancelled / not delivered / planned) per week, summed across all subordinate units.",
        "assessment": chart.get("insight") or "No sessions recorded for this period.",
        "action": "Investigate degradation, confirm recovery, or note sustained delivery performance to command.",
    })
    return chart


def _command_reliability_trend(all_sessions: list, all_pns: list) -> dict:
    """B2 — Delivery reliability, 12-week trend, aggregated across scope.
    Thresholds are labelled explicitly, not colour-only."""
    chart = _delivery_trend(all_sessions, all_pns)
    chart.update({
        "purpose": "Assess whether delivery reliability across subordinate units is improving, stable or deteriorating.",
        "measure": "Delivered sessions divided by sessions due for delivery, aggregated across all subordinate units, per week.",
        "assessment": chart.get("insight") or "Not enough delivery history to assess a trend.",
        "action": "Assess whether command action is producing the required effect; escalate if reliability is deteriorating.",
        "threshold_labels": {
            "80": "80% or greater — meeting reference.",
            "60": "60–79% — command attention required.",
            "0": "Below 60% — significant delivery deficiency.",
        },
    })
    return chart


def _outcomes_by_unit(db: DBSession, scope: str, units: list[dict], window_start: str, window_end: str) -> dict:
    """B3 — Session outcomes by subordinate scope, 100%-stacked. Wing view:
    one bar per Squadron. National view: one bar per Wing. Raw counts are
    kept alongside percentages — the denominator is never hidden."""
    rows = []
    for u in units:
        _, sessions = _unit_pns_and_sessions(db, u["kind"], u["id"], window_start, window_end)
        counts = {"delivered": 0, "delivered_with_issue": 0, "cancelled": 0, "not_delivered": 0, "outstanding": 0}
        for s in sessions:
            st = s.status or "planned"
            if st in ("delivered", "delivered_with_issue", "cancelled", "not_delivered"):
                counts[st] += 1
            else:
                counts["outstanding"] += 1
        total = sum(counts.values())
        pct = {k: (round(v / total * 100) if total else 0) for k, v in counts.items()}
        rows.append({"unit_id": u["id"], "label": u["code"], "name": u["name"],
                     "total": total, "counts": counts, "pct": pct})

    unit_noun = "Squadron" if scope == "wing" else "Wing"
    isolated = sum(1 for r in rows if r["total"] and r["pct"]["delivered"] + r["pct"]["delivered_with_issue"] < 60)
    insight = (f"{isolated} of {len(rows)} {unit_noun}s below 60% delivered this period."
               if rows and isolated else ("Delivery performance is consistent across all units." if rows else None))

    return {
        "chart_id": "outcomes_by_unit",
        "title": f"Session outcomes by {unit_noun.lower()}",
        "purpose": "Determine whether reduced delivery performance is isolated to one unit or systemic across the formation.",
        "measure": "Delivered, delivered-with-issue, cancelled, not-delivered and outstanding sessions per unit, shown as a percentage of that unit's own total.",
        "assessment": insight or "No session data for this period.",
        "action": "Determine the appropriate level of command action — local correction for an isolated unit, coordinated action if systemic.",
        "question": "Is reduced delivery performance isolated or systemic?",
        "chart_type": "stacked_bar_horizontal_100",
        "x_axis": "% of sessions",
        "y_axis": unit_noun,
        "series": [
            {"key": "delivered", "label": "Delivered", "color": _STATUS_COLORS["delivered"]},
            {"key": "delivered_with_issue", "label": "Delivered (with issue)", "color": _STATUS_COLORS["delivered_with_issue"]},
            {"key": "cancelled", "label": "Cancelled", "color": _STATUS_COLORS["cancelled"]},
            {"key": "not_delivered", "label": "Not Delivered", "color": _STATUS_COLORS["not_delivered"]},
            {"key": "outstanding", "label": "Outcome outstanding", "color": "#b0b7bb"},
        ],
        "data": rows,
        "insight": insight,
        "empty_state": "No session data for this period.",
        "drill_down": {"route": "parade-nights",
                       "filters": ({"squadron_id": "{{unit_id}}"} if scope == "wing" else {"wing_id": "{{unit_id}}"})},
    }


def _cancellation_pareto(all_sessions: list) -> dict:
    """B4 — Cancellation and non-delivery causes, aggregated across scope,
    with cumulative percentage (a genuine Pareto chart, not just a ranked bar)."""
    today_str = date.today().isoformat()
    reason_cnt: dict[str, int] = defaultdict(int)
    for s in all_sessions:
        reason = None
        if s.status == "cancelled":
            reason = (s.cancelled_reason or "").strip() or _REASON_NOT_RECORDED_LABEL
        elif s.status == "not_delivered":
            reason = (s.not_delivered_reason or "").strip() or _REASON_NOT_RECORDED_LABEL
        if reason:
            if reason != _REASON_NOT_RECORDED_LABEL:
                reason = reason[:60] + ("…" if len(reason) > 60 else "")
            reason_cnt[reason] += 1

    ranked = sorted(reason_cnt.items(), key=lambda x: -x[1])[:12]
    total = sum(c for _, c in ranked)
    running = 0
    data = []
    for label, count in ranked:
        running += count
        data.append({
            "label": label, "count": count,
            "data_quality_gap": label == _REASON_NOT_RECORDED_LABEL,
            "drill_id": "__no_reason__" if label == _REASON_NOT_RECORDED_LABEL else label,
            "cumulative_pct": round(running / total * 100) if total else 0,
        })

    real_data = [d for d in data if not d["data_quality_gap"]]
    insight = None
    if real_data:
        insight = f"Most common cause: \"{real_data[0]['label']}\" ({real_data[0]['count']} sessions, {real_data[0]['cumulative_pct']}% cumulative)."
    elif data:
        insight = f"{data[0]['count']} cancelled/not-delivered session(s) have no reason recorded yet."

    return {
        "chart_id": "cancellation_pareto",
        "title": "Cancellation and non-delivery causes",
        "purpose": "Identify which causes account for the majority of failed training across the formation.",
        "measure": "Cancelled and not-delivered sessions grouped by recorded reason, ranked by frequency, with cumulative percentage.",
        "assessment": insight or "No cancellations or non-delivered sessions in this period.",
        "action": "Concentrate command effort on the causes producing the greatest operational effect (the top of the Pareto ranking).",
        "question": "Which causes account for the majority of failed training?",
        "chart_type": "pareto",
        "x_axis": "Reason",
        "y_axis": "Sessions",
        "data": data,
        "insight": insight,
        "empty_state": "No cancellations or not-delivered sessions in this period.",
        "drill_down": {"route": "parade-nights", "filters": {"status": "not_delivered"}},
    }


# ── strategic chart builders ──────────────────────────────────────────────────

def _facilitator_capability_dependency(sessions: list) -> dict:
    """Pareto: top facilitators carrying the heaviest delivery load."""
    fac_cnt: dict[str, int] = defaultdict(int)
    for s in sessions:
        if s.status in _DELIVERED and s.facilitator_display_name_at_time:
            fac_cnt[s.facilitator_display_name_at_time] += 1

    total = sum(fac_cnt.values())
    ranked = sorted(fac_cnt.items(), key=lambda x: -x[1])[:10]
    cumulative = 0
    data = []
    for name, cnt in ranked:
        cumulative += cnt
        data.append({
            "label": name,
            "name": name,
            "count": cnt,
            "sessions": cnt,
            "pct": round(cnt / total * 100) if total else 0,
            "cumulative_pct": round(cumulative / total * 100) if total else 0,
        })

    insight = None
    if len(data) >= 2:
        top3_pct = sum(d["pct"] for d in data[:3])
        if top3_pct > 60:
            names = ", ".join(d["name"] for d in data[:3])
            insight = f"{names} account for {top3_pct}% of all delivered sessions — potential over-reliance."

    return {
        "chart_id": "capability_dependency",
        "title": "Facilitator capability dependency",
        "explanation": "Which facilitators are responsible for the most session deliveries.",
        "question": "Is our delivery capability concentrated on too few people?",
        "chart_type": "bar_horizontal",
        "x_axis": "Sessions delivered",
        "y_axis": "Facilitator",
        "data": data,
        "insight": insight,
        "empty_state": "No delivered sessions with assigned facilitators.",
        "drill_down": {"route": "facilitators"},
        "permission_scope": "squadron",
    }


def _subject_area_resilience(facs: list) -> dict:
    """Grouped bar: facilitators per subject area (active, backup, etc.)."""
    sa_map: dict[str, dict] = defaultdict(lambda: {"active": 0, "names": []})
    for f in facs:
        if not f.active_status:
            continue
        for sa in (f.subject_areas or []):
            sa_map[sa]["active"] += 1
            name = f"{f.current_rank or ''} {f.last_name}".strip()
            sa_map[sa]["names"].append(name)

    data = sorted(
        [{"label": sa, "count": v["active"],
          "risk": "critical" if v["active"] == 0 else "warn" if v["active"] == 1 else "ok",
          "names": v["names"]}
         for sa, v in sa_map.items()],
        key=lambda x: x["count"],
    )

    critical = [d for d in data if d["risk"] == "critical"]
    single = [d for d in data if d["risk"] == "warn"]
    insight = None
    if critical:
        insight = f"{len(critical)} subject area(s) have NO qualified facilitator: {', '.join(d['label'] for d in critical[:3])}."
    elif single:
        insight = f"{len(single)} subject area(s) rely on a single facilitator."

    return {
        "chart_id": "subject_area_resilience",
        "title": "Subject area staffing resilience",
        "explanation": "Number of active facilitators qualified in each subject area.",
        "question": "Which subject areas are at risk if a facilitator becomes unavailable?",
        "chart_type": "bar_horizontal",
        "x_axis": "Qualified facilitators",
        "y_axis": "Subject area",
        "data": data,
        "insight": insight,
        "empty_state": "No facilitator subject-area assignments recorded.",
        "drill_down": {"route": "facilitators"},
        "permission_scope": "squadron",
    }


def _facilitator_type_distribution(facs: list) -> dict:
    """Grouped bar: active facilitator counts per type (Officer/NCO/Senior
    Cadet/Civilian/etc). Sibling to _subject_area_resilience -- risk-register
    ask was "a second chart comparing facilitator counts per subject area AND
    type"; subject-area coverage already existed, type coverage did not."""
    type_counts: dict[str, int] = defaultdict(int)
    for f in facs:
        if not f.active_status:
            continue
        type_counts[f.type or "Unspecified"] += 1

    data = sorted(
        [{"label": t, "count": c} for t, c in type_counts.items()],
        key=lambda x: -x["count"],
    )

    return {
        "chart_id": "facilitator_type_distribution",
        "title": "Facilitators by type",
        "explanation": "Number of active facilitators of each type (Officer, NCO, Senior Cadet, Civilian, etc).",
        "question": "What mix of facilitator types is available to draw on?",
        "chart_type": "bar_horizontal",
        "x_axis": "Facilitators",
        "y_axis": "Type",
        "data": data,
        "insight": None,
        "empty_state": "No active facilitators recorded.",
        "drill_down": {"route": "facilitators"},
        "permission_scope": "squadron",
    }


def _term_comparison_ytd(all_sessions: list, all_pns: list) -> dict:
    """Stat card: YTD delivery rate + current-vs-prior term comparison."""
    today = date.today()
    today_iso = today.isoformat()
    year_prefix = str(today.year) + "-"

    pn_map = {pn.id: (pn.date, pn.term) for pn in all_pns}

    # Bucket terminal sessions by term; track latest PN date per term for ordering.
    term_buckets: dict[str, dict] = {}
    ytd_delivered = 0
    ytd_total = 0

    for s in all_sessions:
        if s.status not in _TERMINAL:
            continue
        info = pn_map.get(s.parade_night_id)
        if not info:
            continue
        pn_date, term = info
        if not pn_date:
            continue

        if pn_date.startswith(year_prefix) and pn_date <= today_iso:
            ytd_total += 1
            if s.status in _DELIVERED:
                ytd_delivered += 1

        if not term:
            continue
        if term not in term_buckets:
            term_buckets[term] = {"delivered": 0, "total": 0, "latest": "0000-00-00"}
        term_buckets[term]["total"] += 1
        if s.status in _DELIVERED:
            term_buckets[term]["delivered"] += 1
        if pn_date > term_buckets[term]["latest"]:
            term_buckets[term]["latest"] = pn_date

    sorted_terms = sorted(term_buckets.items(), key=lambda x: x[1]["latest"], reverse=True)

    def _pct(bucket: dict) -> int | None:
        return round(bucket["delivered"] / bucket["total"] * 100) if bucket["total"] else None

    ytd_pct = round(ytd_delivered / ytd_total * 100) if ytd_total else None
    cur_label = sorted_terms[0][0] if len(sorted_terms) >= 1 else None
    cur_pct = _pct(sorted_terms[0][1]) if len(sorted_terms) >= 1 else None
    prv_label = sorted_terms[1][0] if len(sorted_terms) >= 2 else None
    prv_pct = _pct(sorted_terms[1][1]) if len(sorted_terms) >= 2 else None
    delta = (cur_pct - prv_pct) if (cur_pct is not None and prv_pct is not None) else None

    insight_parts = []
    if ytd_pct is not None:
        insight_parts.append(
            f"Year-to-date delivery rate is {ytd_pct}% "
            f"({ytd_delivered} of {ytd_total} sessions delivered)."
        )
    if delta is not None:
        direction = "up" if delta > 0 else "down" if delta < 0 else "unchanged"
        insight_parts.append(
            f"Delivery is {direction} {abs(delta)} percentage point(s) "
            f"compared to {prv_label}."
        )

    return {
        "chart_id": "term_comparison_ytd",
        "chart_type": "term_comparison_ytd",
        "title": "Delivery — term comparison and year to date",
        "explanation": (
            "Year-to-date delivery reliability and a comparison between the "
            "current and previous training term."
        ),
        "question": "Is delivery improving between terms, and what is this year's overall rate?",
        "data": {
            "ytd_delivered": ytd_delivered,
            "ytd_total": ytd_total,
            "ytd_pct": ytd_pct,
            "current_term": cur_label,
            "current_term_pct": cur_pct,
            "prev_term": prv_label,
            "prev_term_pct": prv_pct,
            "delta_pct": delta,
        },
        "insight": " ".join(insight_parts) if insight_parts else None,
        "empty_state": "Not enough term data to compare. Record training term details on Parade Nights to enable this view.",
        "permission_scope": "squadron",
    }


def _delivery_forecast(all_sessions: list, all_pns: list) -> dict:
    """Stat card: deterministic end-of-year delivery forecast.

    Projects how many remaining planned sessions will be delivered based on
    the year-to-date delivery rate. Fully explainable — no AI or opaque
    scoring. Assumes future rate = historical rate (stated in insight).
    """
    today = date.today()
    today_iso = today.isoformat()
    year_prefix = str(today.year) + "-"
    year_end = f"{today.year}-12-31"

    pn_map = {pn.id: pn.date for pn in all_pns}

    ytd_delivered = 0
    ytd_nd = 0
    remaining_planned = 0

    for s in all_sessions:
        pn_date = pn_map.get(s.parade_night_id)
        if not pn_date:
            continue
        in_year = pn_date.startswith(year_prefix)
        in_past = in_year and pn_date <= today_iso
        in_future = in_year and pn_date > today_iso and pn_date <= year_end

        if in_past and s.status in _TERMINAL:
            if s.status in _DELIVERED:
                ytd_delivered += 1
            else:
                ytd_nd += 1
        elif in_future and s.status == "planned":
            remaining_planned += 1

    ytd_total = ytd_delivered + ytd_nd
    rate = ytd_delivered / ytd_total if ytd_total else None

    projected_delivered = round(remaining_planned * rate) if (rate is not None and remaining_planned > 0) else None
    projected_missed = (remaining_planned - projected_delivered) if projected_delivered is not None else None

    insight_parts = []
    if rate is not None:
        insight_parts.append(f"Year-to-date delivery rate: {round(rate * 100)}%.")
    if projected_delivered is not None:
        insight_parts.append(
            f"At this rate, {projected_delivered} of {remaining_planned} remaining planned sessions "
            f"are expected to be delivered by year end. "
            f"{projected_missed} are at risk of not being delivered."
        )
        insight_parts.append("Forecast assumes the historical rate continues — review if circumstances have changed.")
    elif remaining_planned > 0 and rate is None:
        insight_parts.append(
            f"{remaining_planned} sessions planned for the rest of the year. "
            "No historical delivery data available to forecast against."
        )

    return {
        "chart_id": "delivery_forecast",
        "chart_type": "delivery_forecast",
        "title": "Delivery forecast — end of year",
        "explanation": (
            "Projects remaining planned sessions against the year-to-date delivery rate. "
            "Deterministic: forecast = remaining planned × historical rate. No AI scoring."
        ),
        "question": "At our current rate, how many planned sessions are at risk of not being delivered by year end?",
        "data": {
            "ytd_delivered": ytd_delivered,
            "ytd_not_delivered": ytd_nd,
            "ytd_total_terminal": ytd_total,
            "delivery_rate_pct": round(rate * 100) if rate is not None else None,
            "remaining_planned": remaining_planned,
            "projected_delivered": projected_delivered,
            "projected_missed": projected_missed,
        },
        "insight": " ".join(insight_parts) if insight_parts else None,
        "empty_state": "Not enough data to forecast. Record outcomes on past Parade Nights to enable this view.",
        "permission_scope": "squadron",
    }


def _long_term_delivery_trend(sessions: list, pns: list, terms: int = 4) -> dict:
    """Line: delivery reliability per term (long-range strategic view)."""
    pn_map = {pn.id: (pn.date, pn.term) for pn in pns}
    term_buckets: dict[str, dict] = defaultdict(lambda: {"delivered": 0, "total": 0})
    for s in sessions:
        if s.status not in _TERMINAL:
            continue
        info = pn_map.get(s.parade_night_id)
        if not info:
            continue
        term = info[1] or "Unknown"
        term_buckets[term]["total"] += 1
        if s.status in _DELIVERED:
            term_buckets[term]["delivered"] += 1

    data = [
        {
            "label": term,
            "reliability_pct": round(v["delivered"] / v["total"] * 100) if v["total"] else None,
            "delivered": v["delivered"],
            "total": v["total"],
        }
        for term, v in sorted(term_buckets.items())
    ][-terms * 3:]  # last 3× terms to have some history

    return {
        "chart_id": "long_term_delivery_trend",
        "title": "Long-term delivery trend by term",
        "explanation": "Delivery reliability percentage per training term.",
        "question": "Is our training program becoming more or less reliable over time?",
        "chart_type": "line",
        "x_axis": "Term",
        "y_axis": "Reliability %",
        "thresholds": {"green": 80, "amber": 60, "red": 0},
        "data": data,
        "empty_state": "Not enough multi-term history to show a trend.",
        "drill_down": {"route": "parade-nights"},
        "permission_scope": "squadron",
    }


# ── squadron chart bundle (shared by scope=squadron and any wing/national
#    viewer who has selected a squadron via squadron_id — master transformation
#    plan Block 8: "a wing_admin's Dashboard should look like a squadron
#    Dashboard ... layered on", not a reduced subset) ──────────────────────────

def _full_squadron_charts(db: DBSession, sq_id: str, w_start: str, w_end: str) -> dict:
    pns = db.query(ParadeNight).filter(
        ParadeNight.squadron_id == sq_id,
        ParadeNight.date >= w_start,
        ParadeNight.date <= w_end,
        ParadeNight.is_archived == False,  # noqa: E712
    ).all()
    pn_ids = [pn.id for pn in pns]
    sessions = db.query(Session).filter(
        Session.parade_night_id.in_(pn_ids),
        Session.is_archived == False,  # noqa: E712
    ).all() if pn_ids else []
    facs = db.query(Facilitator).filter(
        Facilitator.squadron_id == sq_id,
        Facilitator.is_archived == False,  # noqa: E712
    ).all()
    rooms = db.query(TrainingArea).filter(
        TrainingArea.squadron_id == sq_id,
        TrainingArea.is_archived == False,  # noqa: E712
    ).all()
    curr_items = db.query(CurriculumItem).filter(
        CurriculumItem.is_archived == False,  # noqa: E712
    ).all()

    # Tactical: tonight + all PNs (not just window)
    all_pns = db.query(ParadeNight).filter(
        ParadeNight.squadron_id == sq_id,
        ParadeNight.is_archived == False,  # noqa: E712
    ).all()
    all_pn_ids = [pn.id for pn in all_pns]
    all_sessions = db.query(Session).filter(
        Session.parade_night_id.in_(all_pn_ids),
        Session.is_archived == False,  # noqa: E712
    ).all() if all_pn_ids else []

    charts: dict = {}
    charts["tonight"] = _safe_chart("tonight", _tonight_readiness, all_pns, all_sessions, facs, rooms)
    charts["upcoming_readiness"] = _safe_chart("upcoming_readiness", _upcoming_readiness, all_pns, all_sessions)
    charts["session_outcomes"] = _safe_chart("session_outcomes", _session_outcomes_distribution, sessions)
    charts["weekly_outcomes"] = _safe_chart("weekly_outcomes", _weekly_outcomes, sessions, pns)
    charts["delivery_trend"] = _safe_chart("delivery_trend", _delivery_trend, all_sessions, all_pns)
    charts["term_comparison_ytd"] = _safe_chart("term_comparison_ytd", _term_comparison_ytd, all_sessions, all_pns)
    charts["delivery_forecast"] = _safe_chart("delivery_forecast", _delivery_forecast, all_sessions, all_pns)
    # all_sessions (not the window-filtered `sessions`) — curriculum phase
    # progress is a cumulative measure like its sibling curriculum_backlog
    # (already all_sessions below), not a windowed one. Using the window-
    # filtered set here silently produced an all-zero chart whenever a
    # squadron's delivered history predates the window (e.g. "term" only
    # looks back 90 days), with no visible error — exactly the kind of
    # empty-looks-like-broken chart-trust problem this pass targets.
    charts["curriculum_progress"] = _safe_chart(
        "curriculum_progress", _curriculum_progress, all_sessions, curr_items, _phases_for_squadron(db, sq_id))
    charts["element_curriculum_progress"] = _safe_chart(
        "element_curriculum_progress", _element_curriculum_progress, all_sessions, curr_items,
        _elements_for_squadron(db, sq_id))
    charts["class_curriculum_progress"] = _safe_chart(
        "class_curriculum_progress", _class_curriculum_progress_summary, db, sq_id)
    charts["class_enrollment"] = _safe_chart("class_enrollment", _class_enrollment_distribution, db, sq_id)
    charts["curriculum_backlog"] = _safe_chart("curriculum_backlog", _curriculum_backlog, all_sessions, all_pns)
    charts["cancellation_reasons"] = _safe_chart("cancellation_reasons", _cancellation_reasons, sessions, pns)
    charts["facilitator_workload"] = _safe_chart("facilitator_workload", _facilitator_workload, sessions)
    charts["capability_dependency"] = _safe_chart(
        "capability_dependency", _facilitator_capability_dependency, all_sessions)
    charts["subject_area_resilience"] = _safe_chart("subject_area_resilience", _subject_area_resilience, facs)
    charts["facilitator_type_distribution"] = _safe_chart(
        "facilitator_type_distribution", _facilitator_type_distribution, facs)
    fac_leave = db.query(PlanningFacilitatorLeave).filter(
        PlanningFacilitatorLeave.facilitator_id.in_([f.id for f in facs]),
        PlanningFacilitatorLeave.is_archived == False,  # noqa: E712
    ).all() if facs else []
    charts["facilitator_status_distribution"] = _safe_chart(
        "facilitator_status_distribution", _facilitator_status_distribution, facs, fac_leave)
    all_pn_date_by_id = {pn.id: pn.date for pn in all_pns}
    charts["facilitator_repeated_gaps"] = _safe_chart(
        "facilitator_repeated_gaps", _facilitator_repeated_gaps, all_sessions, all_pn_date_by_id)
    return charts


def _view_squadron_id_for_dashboard(p: Principal, squadron_id: str, db: DBSession) -> str | None:
    """Validate a wing/national viewer's requested squadron_id the same way
    /api/facilitators, /api/curriculum etc. already do (_view_squadron_id in
    training.py) — view access only, no proxy/intervention required. Returns
    None (never raises) for a squadron outside the caller's view scope, so an
    unrelated bad id degrades to "no squadron charts" rather than a hard error
    on a read-heavy dashboard endpoint; a squadron that simply doesn't exist
    still 404s, matching training.py's behaviour for a broken link/typo."""
    sq = db.get(Squadron, squadron_id)
    if not sq:
        raise HTTPException(404, detail={"error": "squadron_not_found"})
    try:
        require_can_view_squadron(p, sq.id, sq.wing_id)
    except HTTPException:
        return None
    return sq.id


# ── main endpoints ────────────────────────────────────────────────────────────

def _wing_comparison_charts(
    db: DBSession, p: Principal, wing_id: str, squadron_id: str | None, w_start, w_end
) -> dict:
    """Wing-level comparison charts plus an optional drilled-in squadron's full
    chart set. Shared by the wing_admin/wing_viewer path (own wing_id) and the
    national-scope path (an explicit, view-permission-checked wing_id) so both
    render identically — see get_dashboard_charts."""
    charts: dict = {}
    # If a specific squadron is requested, viewing it needs no Proxy Mode
    # (view is broad by design) — same _view_squadron_id-style validation
    # used by /api/facilitators, /api/curriculum etc. (Block 8), and the
    # FULL squadron chart set (not a 4-chart subset) so a Wing/National
    # viewer's Dashboard genuinely looks like that squadron's own Dashboard
    # with comparison charts layered on, not a reduced page.
    if squadron_id:
        viewed_sq_id = _view_squadron_id_for_dashboard(p, squadron_id, db)
        if viewed_sq_id:
            charts.update(_full_squadron_charts(db, viewed_sq_id, w_start, w_end))

    charts["squadron_readiness"] = _safe_chart("squadron_readiness", _squadron_readiness, db, wing_id, w_start, w_end)
    charts["squadron_delivery_comparison"] = _safe_chart(
        "squadron_delivery_comparison", _squadron_delivery_comparison, db, wing_id, w_start, w_end)
    charts["wing_subject_area_gaps"] = _safe_chart("wing_subject_area_gaps", _wing_subject_area_gaps, db, wing_id)
    return charts


@router.get("/charts")
def get_dashboard_charts(
    window: str = Query("term", pattern="^(week|term|year)$"),
    squadron_id: str | None = Query(None, description="Wing/National: filter to specific squadron"),
    wing_id: str | None = Query(None, description="National-scope only: view a specific Wing's comparison charts (requires view access to that Wing)"),
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Return tactical and operational chart data for the requesting principal's scope.

    Wing and National users receive squad/wing-level comparison charts.
    Squadron users receive individual squadron charts.
    """
    scope = _scope(p)
    w_start, w_end = _date_window(window)

    charts: dict = {}

    if scope == "squadron":
        # Determine squadron
        sq_id = p.acting_squadron_id or p.squadron_id
        if not sq_id:
            return {"scope": scope, "window": window, "charts": {}, "error": "no_squadron_scope"}
        charts.update(_full_squadron_charts(db, sq_id, w_start, w_end))

    elif scope == "wing":
        w_id = p.acting_wing_id or p.wing_id
        if not w_id:
            return {"scope": scope, "window": window, "charts": {}, "error": "no_wing_scope"}
        charts.update(_wing_comparison_charts(db, p, w_id, squadron_id, w_start, w_end))

    elif wing_id:
        # National-scope principal (national_admin/national_viewer/system_admin/
        # auditor) browsing a specific Wing — view-only, no proxy/DI required,
        # mirrors the wing_admin/wing_viewer branch above exactly so a system
        # administrator's "Wing Dashboard" looks the same as a Wing Admin's.
        if not db.get(Wing, wing_id):
            raise HTTPException(404, detail={"error": "wing_not_found"})
        require_can_view_wing(p, wing_id)
        scope = "wing"
        charts.update(_wing_comparison_charts(db, p, wing_id, squadron_id, w_start, w_end))

    elif p.is_system_admin and squadron_id and not wing_id:
        # System Administrator's scope-selector, drilled into one Squadron
        # directly (no Wing selected) — return a genuine squadron-scoped
        # response matching native squadron view exactly (including the
        # "tonight" section, which only renders for scope=="squadron"),
        # rather than the national_admin/national_viewer/auditor contract
        # below of blending squadron detail into a "national"-scoped
        # response. Scoped to system_admin specifically so the existing
        # national-scope drill-down contract (see
        # test_wing_squadron_view_scope.py) is unchanged for other roles.
        viewed_sq_id = _view_squadron_id_for_dashboard(p, squadron_id, db)
        if not viewed_sq_id:
            raise HTTPException(404, detail={"error": "squadron_not_found"})
        scope = "squadron"
        charts.update(_full_squadron_charts(db, viewed_sq_id, w_start, w_end))

    else:  # national
        if squadron_id:
            viewed_sq_id = _view_squadron_id_for_dashboard(p, squadron_id, db)
            if viewed_sq_id:
                charts.update(_full_squadron_charts(db, viewed_sq_id, w_start, w_end))

        charts["wing_readiness"] = _safe_chart("wing_readiness", _wing_readiness_comparison, db, w_start, w_end)
        # Wing delivery comparison (re-use squadron_delivery_comparison per-wing)
        wings_data = _wing_ids_for_national(db)
        wing_delivery = []
        for winfo in wings_data:
            pns = db.query(ParadeNight).filter(
                ParadeNight.wing_id == winfo["id"],
                ParadeNight.date >= w_start,
                ParadeNight.date <= w_end,
                ParadeNight.is_archived == False,  # noqa: E712
            ).all()
            pn_ids = [pn.id for pn in pns]
            sessions = db.query(Session).filter(
                Session.parade_night_id.in_(pn_ids),
                Session.is_archived == False,  # noqa: E712
            ).all() if pn_ids else []
            delivered = sum(1 for s in sessions if s.status in _DELIVERED)
            not_del = sum(1 for s in sessions if s.status == "not_delivered")
            cancelled = sum(1 for s in sessions if s.status == "cancelled")
            wing_delivery.append({
                "label": winfo["code"], "name": winfo["name"],
                "delivered": delivered, "not_delivered": not_del, "cancelled": cancelled,
            })
        charts["wing_delivery_comparison"] = {
            "chart_id": "wing_delivery_comparison",
            "title": "Wing session outcomes comparison",
            "explanation": "Delivered, not delivered and cancelled sessions for each Wing.",
            "chart_type": "grouped_bar",
            "series": [
                {"key": "delivered", "label": "Delivered", "color": _STATUS_COLORS["delivered"]},
                {"key": "not_delivered", "label": "Not Delivered", "color": _STATUS_COLORS["not_delivered"]},
                {"key": "cancelled", "label": "Cancelled", "color": _STATUS_COLORS["cancelled"]},
            ],
            "data": wing_delivery,
            "empty_state": "No delivery data across Wings.",
            "permission_scope": "national",
        }

    return {
        "scope": scope,
        "window": window,
        "window_start": w_start,
        "window_end": w_end,
        "charts": charts,
    }


def _full_squadron_strategic_charts(db: DBSession, sq_id: str) -> dict:
    all_pns = db.query(ParadeNight).filter(
        ParadeNight.squadron_id == sq_id,
        ParadeNight.is_archived == False,  # noqa: E712
    ).all()
    all_sessions = db.query(Session).filter(
        Session.parade_night_id.in_([pn.id for pn in all_pns]),
        Session.is_archived == False,  # noqa: E712
    ).all() if all_pns else []
    facs = db.query(Facilitator).filter(
        Facilitator.squadron_id == sq_id,
        Facilitator.is_archived == False,  # noqa: E712
    ).all()
    charts: dict = {}
    charts["capability_dependency"] = _safe_chart(
        "capability_dependency", _facilitator_capability_dependency, all_sessions)
    charts["subject_area_resilience"] = _safe_chart("subject_area_resilience", _subject_area_resilience, facs)
    charts["facilitator_type_distribution"] = _safe_chart(
        "facilitator_type_distribution", _facilitator_type_distribution, facs)
    charts["long_term_delivery_trend"] = _safe_chart(
        "long_term_delivery_trend", _long_term_delivery_trend, all_sessions, all_pns)
    charts["term_comparison_ytd"] = _safe_chart("term_comparison_ytd", _term_comparison_ytd, all_sessions, all_pns)
    fac_leave = db.query(PlanningFacilitatorLeave).filter(
        PlanningFacilitatorLeave.facilitator_id.in_([f.id for f in facs]),
        PlanningFacilitatorLeave.is_archived == False,  # noqa: E712
    ).all() if facs else []
    charts["facilitator_status_distribution"] = _safe_chart(
        "facilitator_status_distribution", _facilitator_status_distribution, facs, fac_leave)
    all_pn_date_by_id = {pn.id: pn.date for pn in all_pns}
    charts["facilitator_repeated_gaps"] = _safe_chart(
        "facilitator_repeated_gaps", _facilitator_repeated_gaps, all_sessions, all_pn_date_by_id)
    charts["facilitator_leave_impact"] = _safe_chart(
        "facilitator_leave_impact", _facilitator_leave_impact, facs, fac_leave, all_pns, all_sessions)
    return charts


def _wing_strategic_charts(db: DBSession, wing_id: str) -> dict:
    charts: dict = {}
    facs = db.query(Facilitator).filter(
        Facilitator.wing_id == wing_id,
        Facilitator.is_archived == False,  # noqa: E712
    ).all()
    charts["subject_area_resilience"] = _safe_chart("subject_area_resilience", _subject_area_resilience, facs)
    charts["facilitator_type_distribution"] = _safe_chart(
        "facilitator_type_distribution", _facilitator_type_distribution, facs)
    # Long-term trend: aggregate all wing sessions
    sqn_ids = _sqn_ids_for_wing(db, wing_id)
    pns = db.query(ParadeNight).filter(
        ParadeNight.squadron_id.in_(sqn_ids),
        ParadeNight.is_archived == False,  # noqa: E712
    ).all()
    sessions = db.query(Session).filter(
        Session.parade_night_id.in_([pn.id for pn in pns]),
        Session.is_archived == False,  # noqa: E712
    ).all() if pns else []
    charts["long_term_delivery_trend"] = _safe_chart("long_term_delivery_trend", _long_term_delivery_trend, sessions, pns)
    charts["term_comparison_ytd"] = _safe_chart("term_comparison_ytd", _term_comparison_ytd, sessions, pns)
    return charts


def _national_strategic_charts(db: DBSession) -> dict:
    """REM-15 (original_instruction.md Section 13: "Wing, National and System
    dashboards aggregate and compare it"): the national-scope rollup, mirroring
    _wing_strategic_charts exactly but with no wing filter -- every active
    Facilitator/ParadeNight/Session nationally, instead of one Wing's."""
    charts: dict = {}
    facs = db.query(Facilitator).filter(Facilitator.is_archived == False).all()  # noqa: E712
    charts["subject_area_resilience"] = _safe_chart("subject_area_resilience", _subject_area_resilience, facs)
    charts["facilitator_type_distribution"] = _safe_chart(
        "facilitator_type_distribution", _facilitator_type_distribution, facs)
    pns = db.query(ParadeNight).filter(ParadeNight.is_archived == False).all()  # noqa: E712
    sessions = db.query(Session).filter(
        Session.parade_night_id.in_([pn.id for pn in pns]),
        Session.is_archived == False,  # noqa: E712
    ).all() if pns else []
    charts["long_term_delivery_trend"] = _safe_chart("long_term_delivery_trend", _long_term_delivery_trend, sessions, pns)
    charts["term_comparison_ytd"] = _safe_chart("term_comparison_ytd", _term_comparison_ytd, sessions, pns)
    return charts


@router.get("/charts/strategic")
def get_strategic_charts(
    window: str = Query("year", pattern="^(term|year)$"),
    wing_id: str | None = Query(None, description="National-scope only: view a specific Wing's strategic charts (requires view access to that Wing)"),
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Strategic / long-range charts — deferred load (lower priority than tactical).

    Deliberately does NOT accept squadron_id like the tactical /charts endpoint
    does (master transformation plan Block 8): several strategic chart_ids
    (subject_area_resilience, long_term_delivery_trend) are computed at BOTH
    squadron and wing scope under the same chart_id key, so naively merging a
    squadron_id-selected squadron's version into a wing viewer's response would
    silently overwrite the wing rollup — a real key collision, not a cosmetic
    one. The Facilitator Schedule Explorer's own endpoint
    (/api/dashboard/facilitator-schedule) is the squadron_id-aware path for
    facilitator_leave_impact instead.
    """
    scope = _scope(p)
    w_start, w_end = _date_window(window)
    charts: dict = {}

    if scope == "squadron":
        sq_id = p.acting_squadron_id or p.squadron_id
        if not sq_id:
            return {"scope": scope, "window": window, "charts": {}}
        charts.update(_full_squadron_strategic_charts(db, sq_id))

    elif scope == "wing":
        w_id = p.acting_wing_id or p.wing_id
        if w_id:
            charts.update(_wing_strategic_charts(db, w_id))

    elif wing_id:
        # National-scope principal browsing a specific Wing — view-only, no
        # proxy/DI required, mirrors the wing_admin/wing_viewer branch above.
        if not db.get(Wing, wing_id):
            raise HTTPException(404, detail={"error": "wing_not_found"})
        require_can_view_wing(p, wing_id)
        scope = "wing"
        charts.update(_wing_strategic_charts(db, wing_id))

    elif scope == "national":
        # REM-15: a national-scope principal (national_admin/national_viewer/
        # system_admin/auditor) with no wing_id selected previously fell
        # through every branch above and got an empty {} silently -- no
        # error, just a blank strategic dashboard. Aggregate across every
        # wing instead, matching the instruction's "Wing, National and
        # System dashboards aggregate and compare it" requirement.
        charts.update(_national_strategic_charts(db))

    return {"scope": scope, "window": window, "charts": charts}


@router.get("/facilitator-schedule")
def get_facilitator_schedule(
    window: str = Query("year", pattern="^(week|term|year)$"),
    squadron_id: str | None = Query(None, description="Wing/National: view a specific squadron's facilitator schedule"),
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Facilitator Schedule Explorer data (master transformation plan Block 9):
    one row per facilitator, items = their assigned sessions (dated via the
    parent ParadeNight — Session itself has no date column) plus recorded
    leave ranges, for a grouped timeline and its mandatory accessible list
    fallback.

    Squadron-scoped only, same as every other squadron page under Block 8: a
    Wing/National viewer must select a squadron via squadron_id (view access
    only, no proxy needed); nobody sees another squadron's facilitator
    schedule by default. Returns an empty result (not an error) when no
    squadron is resolved, matching the "select a squadron" empty-state
    convention already used across Calendar/Curriculum/Facilitators/Resources.
    """
    sq_id = _view_squadron_id(p, squadron_id, db)
    w_start, w_end = _date_window(window)
    if not sq_id:
        return {
            "squadron_id": None, "window": window, "window_start": w_start, "window_end": w_end,
            "facilitators": [], "items": [],
        }

    facs = db.query(Facilitator).filter(
        Facilitator.squadron_id == sq_id,
        Facilitator.is_archived == False,  # noqa: E712
    ).all()
    fac_ids = [f.id for f in facs]

    pns = db.query(ParadeNight).filter(
        ParadeNight.squadron_id == sq_id,
        ParadeNight.date >= w_start,
        ParadeNight.date <= w_end,
        ParadeNight.is_archived == False,  # noqa: E712
    ).all()
    pn_date_by_id = {pn.id: pn.date for pn in pns}
    sessions = db.query(Session).filter(
        Session.parade_night_id.in_(list(pn_date_by_id.keys())),
        Session.facilitator_id.isnot(None),
        Session.is_archived == False,  # noqa: E712
    ).all() if pn_date_by_id else []

    leave_rows = db.query(PlanningFacilitatorLeave).filter(
        PlanningFacilitatorLeave.facilitator_id.in_(fac_ids),
        PlanningFacilitatorLeave.is_archived == False,  # noqa: E712
        PlanningFacilitatorLeave.start_date <= w_end,
        PlanningFacilitatorLeave.end_date >= w_start,
    ).all() if fac_ids else []

    today_str = date.today().isoformat()
    on_leave_now = {lv.facilitator_id for lv in leave_rows if lv.start_date <= today_str <= lv.end_date}

    facilitators = [
        {
            "facilitator_id": f.id,
            "name": f"{(f.current_rank + ' ') if f.current_rank else ''}{f.first_name} {f.last_name}",
            "type": f.type,
            "subject_areas": f.subject_areas or [],
            "on_leave_now": f.id in on_leave_now,
        }
        for f in facs
    ]

    items = []
    for s in sessions:
        pd = pn_date_by_id.get(s.parade_night_id)
        if not pd:
            continue
        title = s.curriculum_title_at_time or s.custom_title or s.session_title or "Session"
        items.append({
            "id": f"session-{s.id}",
            "facilitator_id": s.facilitator_id,
            "kind": "session",
            "date": pd,
            "label": title,
            "status": s.status,
            "parade_night_id": s.parade_night_id,
            "session_id": s.id,
        })
    for lv in leave_rows:
        items.append({
            "id": f"leave-{lv.id}",
            "facilitator_id": lv.facilitator_id,
            "kind": "leave",
            "start_date": lv.start_date,
            "end_date": lv.end_date,
            "label": lv.reason or "Leave",
        })

    return {
        "squadron_id": sq_id,
        "window": window,
        "window_start": w_start,
        "window_end": w_end,
        "facilitators": facilitators,
        "items": items,
    }


@router.get("/command")
def get_command_dashboard(
    window: str = Query("term", pattern="^(week|term|semester|year)$"),
    wing_id: str | None = Query(None, description="National-scope only: view a specific Wing's command dashboard (requires view access to that Wing)"),
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Wing and National Training Dashboard — Sections A (Immediate Training
    Readiness) and B (Training Delivery Performance). Extends the Squadron
    dashboard upward: the Wing dashboard aggregates Squadron information, the
    National dashboard aggregates Wing information — the underlying counts
    are always aggregated first, never averaged as per-unit percentages.

    Not applicable to squadron-scope principals — /api/dashboard/charts
    remains the Squadron dashboard's own data source; this endpoint is
    Wing/National only, matching the brief's explicit two-scope requirement.

    View access requires no Proxy/Delegated Intervention Mode (can_view_wing/
    can_view_squadron already grant it) — this endpoint performs no writes.
    """
    scope = _scope(p)
    w_start, w_end = _date_window(window)

    if scope == "squadron":
        raise HTTPException(400, detail={
            "error": "not_applicable",
            "message": "The command dashboard is a Wing/National view. See /api/dashboard/charts for the Squadron dashboard.",
        })

    resolved_wing_id: str | None = None
    resolved_wing_name: str | None = None
    if scope == "wing":
        resolved_wing_id = p.acting_wing_id or p.wing_id
        if not resolved_wing_id:
            return {"scope": scope, "window": window, "error": "no_wing_scope", "sections": {}}
        w = db.get(Wing, resolved_wing_id)
        resolved_wing_name = w.name if w else None
    elif wing_id:
        # National-scope principal (national_admin/national_viewer/system_admin/
        # auditor) drilling into a specific Wing's command dashboard — view-only,
        # mirrors the same wing_id pattern already used by /charts and the
        # /reports/* endpoints.
        w = db.get(Wing, wing_id)
        if not w:
            raise HTTPException(404, detail={"error": "wing_not_found"})
        require_can_view_wing(p, wing_id)
        scope = "wing"
        resolved_wing_id = wing_id
        resolved_wing_name = w.name

    units = _command_child_units(db, scope, resolved_wing_id)

    # Section A — Immediate Training Readiness (not period-bound; "next" by definition)
    readiness_matrix = _readiness_matrix(db, scope, units)
    risk = _risk_forecast(db, scope, resolved_wing_id, units)
    immediate_issues = _immediate_issues(risk["data"], units, scope)

    # Section B — Training Delivery Performance (period-bound; aggregate counts first)
    all_pns: list = []
    all_sessions: list = []
    units_with_data = 0
    for u in units:
        pns, sessions = _unit_pns_and_sessions(db, u["kind"], u["id"], w_start, w_end)
        if pns:
            units_with_data += 1
        all_pns.extend(pns)
        all_sessions.extend(sessions)

    weekly_delivered = _command_weekly_delivered(all_sessions, all_pns)
    reliability_trend = _command_reliability_trend(all_sessions, all_pns)
    outcomes_by_unit = _outcomes_by_unit(db, scope, units, w_start, w_end)
    cancellation_pareto = _cancellation_pareto(all_sessions)

    return {
        "scope": scope,
        "wing_id": resolved_wing_id,
        "wing_name": resolved_wing_name,
        "window": window,
        "period": {"label": _WINDOW_LABELS.get(window, window), "start": w_start, "end": w_end},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "units_in_scope": len(units),
        "data_confidence": {
            "units_reporting": units_with_data, "units_expected": len(units),
            "completeness_pct": round(units_with_data / len(units) * 100) if units else None,
        },
        "sections": {
            "A": {
                "readiness_matrix": readiness_matrix,
                "risk_forecast": risk,
                "immediate_issues": immediate_issues,
            },
            "B": {
                "weekly_delivered": weekly_delivered,
                "reliability_trend": reliability_trend,
                "outcomes_by_unit": outcomes_by_unit,
                "cancellation_pareto": cancellation_pareto,
            },
        },
    }


# ── Adoption analytics ─────────────────────────────────────────────────────────

_MEANINGFUL_OBJECT_TYPES = {
    "session", "parade_night", "parade_night_bulk", "facilitator",
    "training_area", "training_class", "session_audience",
    "cadet_class_membership", "planning_year", "PlanningNotice",
}
_MEANINGFUL_ACTIONS = {
    "create", "edit", "update", "publish", "close", "status_change",
    "bulk_mark_remaining_delivered", "absorb", "set",
}


def _adoption_for_squadron(db: DBSession, squadron_id: str, since: datetime) -> dict:
    rows = (
        db.query(
            AuditLog.user_id,
            AuditLog.object_type,
            AuditLog.action,
            AuditLog.timestamp,
        )
        .filter(
            AuditLog.squadron_id == squadron_id,
            AuditLog.timestamp >= since,
            AuditLog.object_type.in_(_MEANINGFUL_OBJECT_TYPES),
            AuditLog.action.in_(_MEANINGFUL_ACTIONS),
        )
        .all()
    )

    active_user_ids: set[str] = set()
    sessions_scheduled = 0
    outcomes_recorded = 0
    programs_published = 0
    facilitators_maintained = 0
    last_ts: datetime | None = None

    for r in rows:
        if r.user_id:
            active_user_ids.add(r.user_id)
        if r.timestamp and (last_ts is None or r.timestamp > last_ts):
            last_ts = r.timestamp
        ot = r.object_type or ""
        ac = r.action or ""
        if ot == "session" and ac == "create":
            sessions_scheduled += 1
        elif ot == "session" and ac == "status_change":
            outcomes_recorded += 1
        elif ot == "parade_night_bulk" and ac == "bulk_mark_remaining_delivered":
            outcomes_recorded += 1
        elif ot == "parade_night" and ac == "publish":
            programs_published += 1
        elif ot == "facilitator" and ac in ("create", "update", "absorb"):
            facilitators_maintained += 1

    return {
        "active_users": len(active_user_ids),
        "total_meaningful_actions": len(rows),
        "sessions_scheduled": sessions_scheduled,
        "outcomes_recorded": outcomes_recorded,
        "programs_published": programs_published,
        "facilitators_maintained": facilitators_maintained,
        "last_activity": last_ts.isoformat() if last_ts else None,
    }


@router.get("/adoption")
def get_adoption_dashboard(
    period: str = Query("30d", pattern="^(7d|30d|term|year)$"),
    wing_id: str | None = Query(None),
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Adoption analytics — per-squadron meaningful-activity summary.

    Shows which squadrons are actively using the system based on audit log
    entries for meaningful actions (planning, scheduling, outcomes, publishing).
    Intended for Wing and National views only.

    Period options: 7d (7 days), 30d (30 days), term (90 days), year (365 days).

    Not a surveillance tool — reports squadron-level aggregates only,
    never individual user activity or personal data.
    """
    scope = _scope(p)
    if scope == "squadron":
        raise HTTPException(400, detail={
            "error": "not_applicable",
            "message": "Adoption analytics is a Wing/National view.",
        })

    today = datetime.now(timezone.utc).date()
    if period == "7d":
        since = datetime.combine(today - timedelta(days=7), datetime.min.time()).replace(tzinfo=timezone.utc)
    elif period == "30d":
        since = datetime.combine(today - timedelta(days=30), datetime.min.time()).replace(tzinfo=timezone.utc)
    elif period == "year":
        since = datetime.combine(today - timedelta(days=365), datetime.min.time()).replace(tzinfo=timezone.utc)
    else:
        since = datetime.combine(today - timedelta(days=90), datetime.min.time()).replace(tzinfo=timezone.utc)

    resolved_wing_id: str | None = None
    resolved_wing_name: str | None = None
    if scope == "wing":
        resolved_wing_id = p.acting_wing_id or p.wing_id
        if not resolved_wing_id:
            return {"scope": scope, "period": period, "units": []}
        w = db.get(Wing, resolved_wing_id)
        resolved_wing_name = w.name if w else None
    elif wing_id:
        w = db.get(Wing, wing_id)
        if not w:
            raise HTTPException(404, detail={"error": "wing_not_found"})
        require_can_view_wing(p, wing_id)
        resolved_wing_id = wing_id
        resolved_wing_name = w.name

    squadrons = _command_child_units(db, "wing" if resolved_wing_id else "national", resolved_wing_id)
    if not resolved_wing_id:
        all_sqn_rows = db.query(Squadron).filter(Squadron.is_archived == False).all()  # noqa: E712
        squadrons = [{"id": r.id, "code": r.code, "name": r.short_name or r.name, "kind": "squadron"} for r in all_sqn_rows]

    units = []
    for s in squadrons:
        metrics = _adoption_for_squadron(db, s["id"], since)
        units.append({
            "squadron_id": s["id"],
            "code": s["code"],
            "name": s["name"],
            **metrics,
        })

    units.sort(key=lambda u: -u["total_meaningful_actions"])

    return {
        "scope": scope,
        "wing_id": resolved_wing_id,
        "wing_name": resolved_wing_name,
        "period": period,
        "since": since.date().isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_units": len(units),
        "active_units": sum(1 for u in units if u["total_meaningful_actions"] > 0),
        "units": units,
    }
