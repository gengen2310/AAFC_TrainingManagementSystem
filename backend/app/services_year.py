"""Every decision about which training year something belongs to.

A Training Year is calendar context, not a workflow object. This module is the
only place that derives the current year, classifies a year as past/current/
future, or materialises a PlanningYear row.
"""
from __future__ import annotations

import datetime as _dt
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session as DBSession

from .models import Squadron, Wing


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
