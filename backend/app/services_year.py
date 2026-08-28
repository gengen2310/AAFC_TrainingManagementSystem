"""Every decision about which training year something belongs to.

A Training Year is calendar context, not a workflow object. This module is the
only place that derives the current year, classifies a year as past/current/
future, or materialises a PlanningYear row.
"""
from __future__ import annotations

import datetime as _dt
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session as DBSession

from .models import PlanningYear, Squadron, Wing


class MissingTimezone(RuntimeError):
    """A wing has no IANA timezone. Never defaulted; always raised."""


def wing_timezone(db: DBSession, wing_id: str | None) -> ZoneInfo:
    wing = db.get(Wing, wing_id) if wing_id else None
    if wing is None or not wing.timezone:
        raise MissingTimezone(
            f"wing {wing_id} has no timezone set; refusing to assume UTC or "
            f"Australia/Perth"
        )
    return ZoneInfo(wing.timezone)


def squadron_timezone(db: DBSession, squadron_id: str) -> ZoneInfo:
    sqn = db.get(Squadron, squadron_id)
    if sqn is None:
        raise MissingTimezone(f"unknown squadron {squadron_id}")
    return wing_timezone(db, sqn.wing_id)


def wing_local_date(db: DBSession, squadron_id: str) -> _dt.date:
    """Today as the squadron's wing experiences it, not as the server does."""
    return _dt.datetime.now(squadron_timezone(db, squadron_id)).date()


FUTURE_YEARS_SELECTABLE = 2  # user decision 2026-08-28: current + 2


def current_year(db: DBSession, squadron_id: str) -> int:
    """The current training year. Derived, never stored, never written."""
    return wing_local_date(db, squadron_id).year


def year_state(db: DBSession, squadron_id: str, year: int) -> str:
    """"past" | "current" | "future" -- computed from the calendar, so no
    scheduled job and no 1 January write is required to keep it truthful."""
    now = current_year(db, squadron_id)
    if year < now:
        return "past"
    return "current" if year == now else "future"


def selectable_years(db: DBSession, squadron_id: str) -> list[int]:
    """Years offered in the selector: every past year that has a row, the
    current year, and FUTURE_YEARS_SELECTABLE ahead. Past is uncapped; future
    is capped by user decision.

    Past years are included whatever their active_status. Archiving is no
    longer a concept in the year UX, and a past year's data remains history
    that must stay reachable.
    """
    now = current_year(db, squadron_id)
    past = {
        year for (year,) in db.query(PlanningYear.year).filter(
            PlanningYear.unit_id == squadron_id,
            PlanningYear.year < now,
        ).all()
    }
    ahead = {now + n for n in range(FUTURE_YEARS_SELECTABLE + 1)}
    return sorted(past | ahead)
