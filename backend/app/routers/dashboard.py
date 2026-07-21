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

from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DBSession

from ..database import get_db
from ..dependencies import get_principal
from ..models import (
    ParadeNight, Session, Facilitator, Squadron, Wing,
    CurriculumItem, Equipment, TrainingArea,
)
from ..permissions import Principal, require_role

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


def _date_window(window: str) -> tuple[str, str]:
    """Return (start_date_iso, end_date_iso) for the given window label."""
    today = date.today()
    if window == "week":
        return (today - timedelta(days=7)).isoformat(), (today + timedelta(days=7)).isoformat()
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
        pct = round(b["delivered"] / b["total"] * 100) if b["total"] else None
        data.append({"label": wk, "reliability_pct": pct, "delivered": b["delivered"], "total": b["total"]})

    # Insight: trend direction
    insight = None
    valid = [d for d in data if d["reliability_pct"] is not None]
    if len(valid) >= 4:
        last4 = [v["reliability_pct"] for v in valid[-4:]]
        first4 = [v["reliability_pct"] for v in valid[:4]]
        if sum(last4) / 4 > sum(first4) / 4 + 5:
            insight = "Delivery reliability has improved over the past four weeks."
        elif sum(last4) / 4 < sum(first4) / 4 - 5:
            insight = "Delivery reliability has declined recently — review causes."

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


def _curriculum_progress(sessions: list, curr_items: list) -> dict:
    """Horizontal stacked bar: delivered vs not-delivered vs planned per phase."""
    # Count from sessions
    phase_data: dict[str, dict] = {
        ph: {"phase": ph, "delivered": 0, "delivered_with_issue": 0,
             "not_delivered": 0, "cancelled": 0, "planned": 0, "total_items": 0}
        for ph in _PHASES
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

    data = [phase_data[ph] for ph in _PHASES]
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


def _curriculum_backlog(sessions: list, pns: list) -> dict:
    """Ranked bar: phases with most undelivered sessions relative to historical parade nights."""
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
        ph = s.phase_at_time or "Unknown"
        phase_cnt[ph] += 1

    data = sorted(
        [{"label": ph, "count": cnt, "color": "#e51937"} for ph, cnt in phase_cnt.items()],
        key=lambda x: -x["count"],
    )

    return {
        "chart_id": "curriculum_backlog",
        "title": "Curriculum backlog by phase",
        "explanation": "Sessions not delivered or cancelled on past parade nights, ranked by phase.",
        "question": "Where is the training backlog accumulating?",
        "chart_type": "bar_horizontal",
        "x_axis": "Missed sessions",
        "y_axis": "Phase",
        "data": data,
        "insight": (f"The largest backlog is in {data[0]['label']} ({data[0]['count']} sessions)."
                    if data else None),
        "empty_state": "No backlog — all past sessions were delivered.",
        "drill_down": {"route": "parade-nights", "filters": {"status": "not_delivered"}},
        "permission_scope": "squadron",
    }


def _cancellation_reasons(sessions: list, pns: list) -> dict:
    """Ranked bar: most common cancellation / not-delivered reasons."""
    today_str = date.today().isoformat()
    pn_map = {pn.id: pn.date for pn in pns}
    reason_cnt: dict[str, int] = defaultdict(int)

    for s in sessions:
        pn_date = pn_map.get(s.parade_night_id, "")
        if pn_date >= today_str:
            continue
        reason = None
        if s.status == "cancelled":
            reason = (s.cancelled_reason or "").strip() or "Reason not recorded"
        elif s.status == "not_delivered":
            reason = (s.not_delivered_reason or "").strip() or "Reason not recorded"
        if reason:
            # Truncate long free-text to first sentence / 60 chars
            reason = reason[:60] + ("…" if len(reason) > 60 else "")
            reason_cnt[reason] += 1

    data = sorted(
        [{"label": r, "count": c} for r, c in reason_cnt.items()],
        key=lambda x: -x["count"],
    )[:12]  # top 12

    insight = None
    if data:
        top = data[0]
        insight = f"Most common cause: \"{top['label']}\" ({top['count']} sessions)."

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


def _tonight_readiness(pns: list, sessions: list, facs: list, rooms: list) -> dict:
    """Tonight's / next parade night readiness card."""
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
    fac_ids = {f.id for f in facs}
    room_ids = {r.id for r in rooms}

    # Compute readiness measures
    total_sess = len(pn_sessions)
    sessions_ready = sum(1 for s in pn_sessions if s.facilitator_id and (not s.training_area_id or s.training_area_id in room_ids))
    fac_filled = sum(1 for s in pn_sessions if s.facilitator_id)
    fac_total = total_sess
    room_filled = sum(1 for s in pn_sessions if s.training_area_id)
    room_total = total_sess

    # Issues
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

    overall_pct = round(sessions_ready / total_sess * 100) if total_sess else 0

    plain = (
        "Tonight's program is ready to run."
        if not issues else
        f"Tonight's program can run, but {len(issues)} item(s) need attention."
    )

    return {
        "chart_id": "tonight",
        "title": "Tonight's readiness",
        "explanation": plain,
        "question": "Is tonight's parade night ready to run?",
        "chart_type": "readiness_card",
        "data": {
            "date": next_pn.date,
            "term": next_pn.term,
            "overall_pct": overall_pct,
            "sessions_total": total_sess,
            "sessions_ready": sessions_ready,
            "fac_filled": fac_filled,
            "fac_total": fac_total,
            "room_filled": room_filled,
            "room_total": room_total,
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
    """Card grid: next 8 parade nights with readiness score."""
    today_str = date.today().isoformat()
    upcoming = sorted([pn for pn in pns if pn.date >= today_str], key=lambda p: p.date)[:8]
    pn_sessions: dict[str, list] = defaultdict(list)
    for s in sessions:
        pn_sessions[s.parade_night_id].append(s)

    data = []
    for pn in upcoming:
        sess = pn_sessions.get(pn.id, [])
        total = len(sess)
        unstaffed = sum(1 for s in sess if not s.facilitator_id)
        ready = sum(1 for s in sess if s.facilitator_id)
        pct = round(ready / total * 100) if total else 0
        data.append({
            "date": pn.date,
            "term": pn.term,
            "sessions_total": total,
            "sessions_ready": ready,
            "unstaffed": unstaffed,
            "readiness_pct": pct,
            "published": pn.published_status,
        })

    return {
        "chart_id": "upcoming_readiness",
        "title": "Upcoming parade night readiness",
        "explanation": "Staffing readiness for the next eight parade nights.",
        "question": "Are upcoming parade nights fully staffed?",
        "chart_type": "readiness_grid",
        "data": data,
        "insight": (f"{sum(1 for d in data if d['unstaffed'] > 0)} upcoming nights have unstaffed sessions."
                    if any(d["unstaffed"] > 0 for d in data) else
                    "All upcoming parade nights are fully staffed." if data else None),
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
            cells.append({"subject_area": sa, "count": count, "risk": risk})
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
            "name": name,
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


# ── main endpoints ────────────────────────────────────────────────────────────

@router.get("/charts")
def get_dashboard_charts(
    window: str = Query("term", pattern="^(week|term|year)$"),
    squadron_id: str | None = Query(None, description="Wing/National: filter to specific squadron"),
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

        charts["tonight"] = _tonight_readiness(all_pns, all_sessions, facs, rooms)
        charts["upcoming_readiness"] = _upcoming_readiness(all_pns, all_sessions)
        charts["session_outcomes"] = _session_outcomes_distribution(sessions)
        charts["weekly_outcomes"] = _weekly_outcomes(sessions, pns)
        charts["delivery_trend"] = _delivery_trend(all_sessions, all_pns)
        charts["curriculum_progress"] = _curriculum_progress(sessions, curr_items)
        charts["curriculum_backlog"] = _curriculum_backlog(all_sessions, all_pns)
        charts["cancellation_reasons"] = _cancellation_reasons(sessions, pns)
        charts["facilitator_workload"] = _facilitator_workload(sessions)

    elif scope == "wing":
        wing_id = p.acting_wing_id or p.wing_id
        if not wing_id:
            return {"scope": scope, "window": window, "charts": {}, "error": "no_wing_scope"}

        # If a specific squadron is requested (proxy mode)
        if squadron_id:
            sq = db.get(Squadron, squadron_id)
            if sq and sq.wing_id == wing_id:
                pns = db.query(ParadeNight).filter(
                    ParadeNight.squadron_id == squadron_id,
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
                    Facilitator.squadron_id == squadron_id,
                    Facilitator.is_archived == False,  # noqa: E712
                ).all()
                rooms = db.query(TrainingArea).filter(
                    TrainingArea.squadron_id == squadron_id,
                    TrainingArea.is_archived == False,  # noqa: E712
                ).all()
                all_pns = db.query(ParadeNight).filter(
                    ParadeNight.squadron_id == squadron_id,
                    ParadeNight.is_archived == False,  # noqa: E712
                ).all()
                all_pn_ids = [pn.id for pn in all_pns]
                all_sessions = db.query(Session).filter(
                    Session.parade_night_id.in_(all_pn_ids),
                    Session.is_archived == False,  # noqa: E712
                ).all() if all_pn_ids else []
                charts["tonight"] = _tonight_readiness(all_pns, all_sessions, facs, rooms)
                charts["session_outcomes"] = _session_outcomes_distribution(sessions)
                charts["weekly_outcomes"] = _weekly_outcomes(sessions, pns)
                charts["facilitator_workload"] = _facilitator_workload(sessions)
                charts["curriculum_progress"] = _curriculum_progress(sessions, [])

        # Wing-level comparison charts
        charts["squadron_readiness"] = _squadron_readiness(db, wing_id, w_start, w_end)
        charts["squadron_delivery_comparison"] = _squadron_delivery_comparison(db, wing_id, w_start, w_end)
        charts["wing_subject_area_gaps"] = _wing_subject_area_gaps(db, wing_id)

    else:  # national
        charts["wing_readiness"] = _wing_readiness_comparison(db, w_start, w_end)
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


@router.get("/charts/strategic")
def get_strategic_charts(
    window: str = Query("year", pattern="^(term|year)$"),
    db: DBSession = Depends(get_db),
    p: Principal = Depends(get_principal),
):
    """Strategic / long-range charts — deferred load (lower priority than tactical)."""
    scope = _scope(p)
    w_start, w_end = _date_window(window)
    charts: dict = {}

    if scope == "squadron":
        sq_id = p.acting_squadron_id or p.squadron_id
        if not sq_id:
            return {"scope": scope, "window": window, "charts": {}}
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
        charts["capability_dependency"] = _facilitator_capability_dependency(all_sessions)
        charts["subject_area_resilience"] = _subject_area_resilience(facs)
        charts["long_term_delivery_trend"] = _long_term_delivery_trend(all_sessions, all_pns)

    elif scope == "wing":
        wing_id = p.acting_wing_id or p.wing_id
        if wing_id:
            facs = db.query(Facilitator).filter(
                Facilitator.wing_id == wing_id,
                Facilitator.is_archived == False,  # noqa: E712
            ).all()
            charts["subject_area_resilience"] = _subject_area_resilience(facs)
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
            charts["long_term_delivery_trend"] = _long_term_delivery_trend(sessions, pns)

    return {"scope": scope, "window": window, "charts": charts}
