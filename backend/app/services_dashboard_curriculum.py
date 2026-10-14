"""Curriculum metrics: progress and backlog, class enrollment and progress,
element progress, and the phases/elements that apply to a Squadron.

Moved verbatim from routers/dashboard.py (stabilisation, service extraction). Pure
read-side computation: no HTTP, no authorization -- callers resolve scope first.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from sqlalchemy.orm import Session as DBSession

from .models import CurriculumElement, CurriculumPhase, Squadron, TrainingClass
from .services_curriculum_progress import class_curriculum_progress
from .services_dashboard_common import _STATUS_COLORS


_PHASES = [
    "A. Orientation", "B. Initial", "C. Junior",
    "D. Intermediate", "E. Senior",
    "I. Bronze", "J. Silver", "K. Gold",
]


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
    ).order_by(TrainingClass.class_number, TrainingClass.display_name).all()

    stages: dict[str, dict] = {}
    for c in classes:
        prog = class_curriculum_progress(db, c)
        stage_id = prog["training_stage_id"]
        entry = stages.setdefault(stage_id, {
            "stage_name": prog["stage_name"] or "Unnamed stage",
            "classes": [],
            "total_delivered": 0,
            "total_applicable": 0,
        })
        delivered, total = prog["summary"]["delivered"], prog["summary"]["total"]
        entry["classes"].append({
            "training_class_id": c.id,
            "display_name": c.display_name,
            "class_number": c.class_number,
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
    ).order_by(TrainingClass.class_number, TrainingClass.display_name).all()

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
