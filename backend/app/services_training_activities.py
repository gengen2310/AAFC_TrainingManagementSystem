"""Unified Activities calendar sources: the national/wing/squadron
inheritance filter for Activity rows, the read-time CEA and holiday source
items merged into the calendar, and recurrence expansion for bulk-created
activities.

Moved verbatim from routers/training.py (stabilisation Phase 3, C5). Read-only
queries and pure date generation: no HTTP, no authorization -- callers resolve
the viewing scope first.
"""
from __future__ import annotations

from sqlalchemy.orm import Session as DBSession

from .models import Activity, Squadron


def _activities_visibility_filter(scope_type: str, scope_id: str | None, wing_id_of_scope: str | None):
    """OR-branched inheritance filter -- mirrors CurriculumItem's already-proven
    national/wing/squadron pattern (list_curriculum above) rather than a UNION.
    National activities are always visible; Wing activities are visible at Wing
    scope (that wing) and Squadron scope (that squadron's wing); Squadron
    activities are visible only at that Squadron's own scope -- never
    "inherited upward" and never copied into a sibling squadron's view."""
    from sqlalchemy import or_
    conditions = [Activity.owning_level == "national"]
    if scope_type in ("wing", "squadron") and wing_id_of_scope:
        conditions.append((Activity.owning_level == "wing") & (Activity.wing_id == wing_id_of_scope))
    if scope_type == "squadron" and scope_id:
        conditions.append((Activity.owning_level == "squadron") & (Activity.squadron_id == scope_id))
    return or_(*conditions)


def _cea_source_items(db: DBSession, wing_id: str | None, squadron_id: str | None,
                      date_from: str | None, date_end: str | None, viewer_squadron_id: str | None) -> list[dict]:
    """CEA activities are read-time merged, never copied into `Activity` --
    only classification_status=='classified' rows are shown (needs_review is
    an internal wing-admin review state), excluded if removed from the source
    import or locally hidden for the viewing squadron."""
    from .models.planning import CeaActivity, ActivityLocalHide
    q = db.query(CeaActivity).filter(
        CeaActivity.classification_status == "classified",
        CeaActivity.is_removed_from_cea == False,  # noqa: E712
        CeaActivity.is_archived == False,  # noqa: E712
    )
    if squadron_id:
        q = q.filter(CeaActivity.unit_id == squadron_id)
    elif wing_id:
        q = q.filter(CeaActivity.wing_id == wing_id)
    else:
        return []  # CEA import is wing-scoped only -- no meaningful "all-national" CEA view
    if date_from:
        q = q.filter((CeaActivity.activity_end_date == None) | (CeaActivity.activity_end_date >= date_from))  # noqa: E711
    if date_end:
        q = q.filter((CeaActivity.activity_start_date == None) | (CeaActivity.activity_start_date <= date_end))  # noqa: E711
    rows = q.order_by(CeaActivity.activity_start_date).limit(2000).all()
    hidden_ids: set[str] = set()
    if viewer_squadron_id:
        hides = db.query(ActivityLocalHide.cea_activity_id).filter(
            ActivityLocalHide.unit_id == viewer_squadron_id, ActivityLocalHide.is_hidden == True).all()  # noqa: E712
        hidden_ids = {h[0] for h in hides}
    out = []
    for c in rows:
        if c.id in hidden_ids:
            continue
        out.append({
            "activity_id": c.id, "source": "cea", "owning_level": None, "owning_scope_id": None,
            "owning_org_label": "CEA", "wing_id": c.wing_id, "squadron_id": c.unit_id,
            "activity_name": c.activity_name, "activity_type": c.activity_type,
            "date_start": c.activity_start_date, "date_end": c.activity_end_date,
            "time_start": c.start_time, "time_end": c.end_time,
            "location": c.location, "audience": [], "notes": c.notes,
            "workflow_status": c.status_name, "cea_seq_nr": c.cea_activity_id,
            "is_archived": False, "is_inherited": True, "read_only": True,
        })
    return out


def _holiday_source_items(db: DBSession, scope_type: str, wing_id: str | None, squadron_id: str | None,
                          date_from: str | None, date_end: str | None) -> list[dict]:
    """Holidays are year-scoped (via PlanningYear), not scope-tagged directly,
    so relevance is resolved by joining through this scope's own planning
    years -- Wing-level years for a Wing view, that Squadron's (and its
    Wing's) years for a Squadron view. National view shows none (no single
    "national planning year" concept exists) -- a deliberate, documented
    simplification, not an oversight."""
    from .models.planning import HolidayPeriod, PlanningYear
    year_ids: list[str] = []
    if scope_type == "wing" and wing_id:
        year_ids = [y.id for y in db.query(PlanningYear.id).filter(PlanningYear.wing_id == wing_id).all()]
    elif scope_type == "squadron" and squadron_id:
        sq = db.get(Squadron, squadron_id)
        yq = db.query(PlanningYear.id).filter(PlanningYear.unit_id == squadron_id)
        year_ids = [y.id for y in yq.all()]
        if sq and sq.wing_id:
            year_ids += [y.id for y in db.query(PlanningYear.id).filter(PlanningYear.wing_id == sq.wing_id).all()]
    if not year_ids:
        return []
    q = db.query(HolidayPeriod).filter(HolidayPeriod.planning_year_id.in_(year_ids))
    if date_from:
        q = q.filter(HolidayPeriod.end_date >= date_from)
    if date_end:
        q = q.filter(HolidayPeriod.start_date <= date_end)
    rows = q.order_by(HolidayPeriod.start_date).limit(500).all()
    return [{
        "activity_id": h.id, "source": "holiday", "owning_level": None, "owning_scope_id": None,
        "owning_org_label": "Holiday", "wing_id": wing_id, "squadron_id": squadron_id,
        "activity_name": h.name, "activity_type": h.holiday_type,
        "date_start": h.start_date, "date_end": h.end_date,
        "time_start": None, "time_end": None, "location": None, "audience": [],
        "notes": h.notes, "workflow_status": None, "cea_seq_nr": None,
        "is_archived": False, "is_inherited": True, "read_only": True,
    } for h in rows]


def _generate_dates(start: str, end: str, recurrence: str, weekday: int | None,
                    excluded: set[str], repeat_count: int | None):
    """Yield ISO date strings matching the recurrence rule within [start, end]."""
    from datetime import date, timedelta
    import calendar as _cal

    sd = date.fromisoformat(start)
    ed = date.fromisoformat(end)

    if recurrence == "daily":
        cur = sd
        count = 0
        while cur <= ed:
            ds = cur.isoformat()
            if ds not in excluded:
                yield ds
                count += 1
                if repeat_count and count >= repeat_count:
                    return
            cur += timedelta(days=1)

    elif recurrence in ("weekly", "fortnightly"):
        if weekday is None:
            weekday = sd.weekday()
        step = timedelta(days=7 if recurrence == "weekly" else 14)
        # Find first occurrence on or after start
        days_ahead = (weekday - sd.weekday()) % 7
        cur = sd + timedelta(days=days_ahead)
        count = 0
        while cur <= ed:
            ds = cur.isoformat()
            if ds not in excluded:
                yield ds
                count += 1
                if repeat_count and count >= repeat_count:
                    return
            cur += step

    elif recurrence == "monthly":
        from datetime import date as _date
        cur = sd.replace(day=1)
        target_day = sd.day
        count = 0
        while cur <= ed:
            last = _cal.monthrange(cur.year, cur.month)[1]
            day = min(target_day, last)
            candidate = _date(cur.year, cur.month, day)
            if sd <= candidate <= ed:
                ds = candidate.isoformat()
                if ds not in excluded:
                    yield ds
                    count += 1
                    if repeat_count and count >= repeat_count:
                        return
            if cur.month == 12:
                cur = cur.replace(year=cur.year + 1, month=1)
            else:
                cur = cur.replace(month=cur.month + 1)

    elif recurrence == "yearly":
        from datetime import date as _date
        import calendar as _cal
        cur_year = sd.year
        count = 0
        while True:
            try:
                candidate = _date(cur_year, sd.month, sd.day)
            except ValueError:
                last = _cal.monthrange(cur_year, sd.month)[1]
                candidate = _date(cur_year, sd.month, last)
            if candidate > ed:
                break
            if candidate >= sd:
                ds = candidate.isoformat()
                if ds not in excluded:
                    yield ds
                    count += 1
                    if repeat_count and count >= repeat_count:
                        return
            cur_year += 1
