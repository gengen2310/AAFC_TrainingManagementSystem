"""Every decision about which training year something belongs to.

A Training Year is calendar context, not a workflow object. This module is the
only place that derives the current year, classifies a year as past/current/
future, or materialises a PlanningYear row.
"""
from __future__ import annotations

import datetime as _dt
import uuid as _uuid
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
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


def year_display_name(year: int) -> str:
    """The only place a year's name is produced. Derived, never user-entered."""
    return f"{year} Training Year"


def find_year_context(db: DBSession, squadron_id: str, year: int) -> PlanningYear | None:
    """Resolve the canonical container, or None. NEVER creates."""
    return (db.query(PlanningYear)
              .filter(PlanningYear.unit_id == squadron_id,
                      PlanningYear.year == year,
                      PlanningYear.active_status)
              .first())


def ensure_year_context(db: DBSession, squadron_id: str, year: int,
                        user_id: str | None = None) -> PlanningYear:
    """Resolve the canonical container, creating it if absent.

    Write paths only. Idempotent under concurrency: two callers may both see
    None, so the loser of the insert race is caught and re-read rather than
    guarded by a check-then-write, which has no lock between the check and
    the write and so cannot be correct.
    """
    existing = find_year_context(db, squadron_id, year)
    if existing is not None:
        return existing

    sqn = db.get(Squadron, squadron_id)
    py = PlanningYear(
        id=str(_uuid.uuid4()), unit_id=squadron_id,
        wing_id=sqn.wing_id if sqn else None,
        year=year, name=year_display_name(year),
        created_by=user_id, updated_by=user_id,
    )
    db.add(py)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raced = find_year_context(db, squadron_id, year)
        if raced is None:
            raise
        return raced
    return py


DEFAULT_WING_TIMEZONE = "Australia/Perth"


def timezone_for_new_wing(db: DBSession, national_id: str,
                          requested: str | None = None) -> str:
    """The IANA zone to STORE on a wing at creation.

    Resolving here, once, is not the silent defaulting wing_timezone refuses.
    That refusal is about date arithmetic: a wrong zone used to derive "today"
    is invisible and corrupts every year boundary. This value is written to the
    row, shown in the UI, and editable -- an admin who creates an eastern-states
    wing can see it is wrong and change it.

    Preference order: what the caller asked for, then a sibling wing's zone,
    then the national default.
    """
    if requested:
        ZoneInfo(requested)          # validate; raises for an unknown zone
        return requested
    sibling = (db.query(Wing)
                 .filter(Wing.national_id == national_id,
                         Wing.timezone.isnot(None))
                 .first())
    return sibling.timezone if sibling else DEFAULT_WING_TIMEZONE
