"""Readiness metrics: tonight / upcoming / per-unit readiness, the readiness
matrix and trend, risk forecast and immediate issues.

Moved verbatim from routers/dashboard.py (stabilisation, service extraction). Pure
read-side computation: no HTTP, no authorization -- callers resolve scope first.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from sqlalchemy.orm import Session as DBSession

from .models import ParadeNight, Session, Squadron, Wing
from .services_dashboard_common import (
    _DELIVERED,
    _TERMINAL,
    _iso_week,
    _unit_pns_and_sessions,
    _unit_session_filter,
)
from .services_readiness import parade_night_readiness, session_requirements


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
    from .models import Activity, HolidayPeriod, PlanningYear

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
