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
from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession

from ..database import get_db
from ..dependencies import get_principal
from ..models import (
    CurriculumItem,
    Facilitator,
    ParadeNight,
    PlanningFacilitatorLeave,
    Session,
    Squadron,
    TrainingArea,
    Wing,
)
from ..permissions import (
    Principal,
    require_can_view_squadron,
    require_can_view_wing,
    resolve_view_squadron_id,
)
from ..services_dashboard_adoption import _adoption_for_squadron
from ..services_dashboard_common import (
    _DELIVERED,
    _STATUS_COLORS,
    _command_child_units,
    _date_window,
    _sqn_ids_for_wing,
    _unit_pns_and_sessions,
    _wing_ids_for_national,
)
from ..services_dashboard_curriculum import (
    _class_curriculum_progress_summary,
    _class_enrollment_distribution,
    _curriculum_backlog,
    _curriculum_progress,
    _element_curriculum_progress,
    _elements_for_squadron,
    _phases_for_squadron,
)
from ..services_dashboard_delivery import (
    _cancellation_pareto,
    _cancellation_reasons,
    _command_reliability_trend,
    _command_weekly_delivered,
    _delivery_forecast,
    _delivery_trend,
    _long_term_delivery_trend,
    _outcomes_by_unit,
    _session_outcomes_distribution,
    _squadron_delivery_comparison,
    _term_comparison_ytd,
    _weekly_outcomes,
)
from ..services_dashboard_facilitators import (
    _facilitator_capability_dependency,
    _facilitator_leave_impact,
    _facilitator_repeated_gaps,
    _facilitator_status_distribution,
    _facilitator_type_distribution,
    _facilitator_workload,
    _subject_area_resilience,
    _wing_subject_area_gaps,
)
from ..services_dashboard_readiness import (
    _immediate_issues,
    _readiness_matrix,
    _risk_forecast,
    _squadron_readiness,
    _tonight_readiness,
    _upcoming_readiness,
    _wing_readiness_comparison,
)
from ..services_data_quality import data_freshness

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# ── constants ─────────────────────────────────────────────────────────────────


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



_WINDOW_LABELS = {
    "week": "This Week", "term": "This Term", "semester": "Semester",
    "year": "Training Year",
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
    /api/facilitators, /api/curriculum etc. already do (resolve_view_squadron_id in
    permissions.py) — view access only, no proxy/intervention required. Returns
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
    _freshness_sq_id: str | None = None
    _freshness_wing_id: str | None = None

    if scope == "squadron":
        # Determine squadron
        sq_id = p.acting_squadron_id or p.squadron_id
        if not sq_id:
            return {"scope": scope, "window": window, "charts": {}, "error": "no_squadron_scope"}
        _freshness_sq_id = sq_id
        charts.update(_full_squadron_charts(db, sq_id, w_start, w_end))

    elif scope == "wing":
        w_id = p.acting_wing_id or p.wing_id
        if not w_id:
            return {"scope": scope, "window": window, "charts": {}, "error": "no_wing_scope"}
        _freshness_wing_id = w_id
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
        _freshness_wing_id = wing_id
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
        _freshness_sq_id = viewed_sq_id
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
        "data_freshness": data_freshness(db, scope, _freshness_sq_id, _freshness_wing_id),
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
    sq_id = resolve_view_squadron_id(p, squadron_id, db)
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


# ── command dashboard: Wing / National (Sections A + B) ────────────────────────
# Extends the existing Squadron dashboard upward — the Wing dashboard aggregates
# Squadron information, the National dashboard aggregates Wing information.
# Every chart aggregates the underlying counts first and never averages
# per-unit percentages. Every chart carries the operational metadata (purpose/
# measure/action/data_confidence) the command dashboard design requires, not
# just a title and a number — see docs/release/qualification_gap_register.md
# for the requirement this implements.
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
