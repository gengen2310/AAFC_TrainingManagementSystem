"""Year model services: timezone resolution and active-year rollover.

Two hard rules from the spec (2026-08-27):
  - Wing.timezone must be set; fail loudly if unset — never fall back to UTC.
  - resolve_active_year() promotes a draft year on the first read on/after
    1 January of the draft year's own `year` number, in wing-local time.
"""
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy.orm import Session


def get_wing_timezone(wing_id: str, db: Session) -> ZoneInfo:
    """Return the ZoneInfo for a Wing. Raises RuntimeError if unset or invalid.

    This must never silently fall back to UTC or Perth. The fail-loudly rule
    is more important in a single-wing deployment than a multi-wing one:
    with one wing, a missing timezone is invisible until wing two is added —
    exactly when nobody is watching for it.
    """
    from .models.organisations import Wing
    wing = db.get(Wing, wing_id)
    if not wing:
        raise RuntimeError(f"Wing {wing_id!r} not found")
    if not wing.timezone:
        raise RuntimeError(
            f"Wing {wing_id!r} has no timezone configured. "
            "Set Wing.timezone to a valid IANA string (e.g. 'Australia/Perth') "
            "before using year rollover."
        )
    try:
        return ZoneInfo(wing.timezone)
    except ZoneInfoNotFoundError:
        raise RuntimeError(
            f"Wing {wing_id!r} has invalid IANA timezone {wing.timezone!r}. "
            "Use a value from the IANA Time Zone Database (e.g. 'Australia/Perth')."
        )
