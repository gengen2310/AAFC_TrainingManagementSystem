"""Facilitator metrics: workload, status and type distribution, capability
dependency, repeated gaps, leave impact, and subject-area resilience and gaps.

Moved verbatim from routers/dashboard.py (stabilisation, service extraction). Pure
read-side computation: no HTTP, no authorization -- callers resolve scope first.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from sqlalchemy.orm import Session as DBSession

from .models import Facilitator, Squadron
from .services_dashboard_common import _DELIVERED, _STATUS_COLORS


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
