"""Year model services: timezone resolution and active-year rollover.

Two hard rules from the spec (2026-08-27):
  - Wing.timezone must be set; fail loudly if unset — never fall back to UTC.
  - resolve_active_year() promotes a draft year on the first read on/after
    1 January of the draft year's own `year` number, in wing-local time.
"""
from datetime import datetime, date as date_type
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


def resolve_active_year(
    squadron_id: str,
    wing_id: str,
    db: Session,
    *,
    _today: "date_type | None" = None,
):
    """Return the active PlanningYear for this squadron; run rollover if due.

    If there is a draft year and today >= 1 January of the draft year's own
    `year` number (in wing-local time), promote the draft to active and archive
    the outgoing active year — all in one transaction. The unique index on
    (unit_id, year) WHERE active_status=true makes concurrent promotions safe:
    the loser gets an IntegrityError and retries after reading the winner.

    The `_today` parameter is for test injection only — never pass it in
    production code.
    """
    from .models.planning import PlanningYear
    from sqlalchemy import exc

    tz = get_wing_timezone(wing_id, db)
    today_local = _today or datetime.now(tz).date()

    active = (
        db.query(PlanningYear)
        .filter(PlanningYear.unit_id == squadron_id,
                PlanningYear.status == "active")
        .first()
    )
    draft = (
        db.query(PlanningYear)
        .filter(PlanningYear.unit_id == squadron_id,
                PlanningYear.status == "draft")
        .first()
    )

    if draft:
        rollover_date = date_type(draft.year, 1, 1)
        if today_local >= rollover_date:
            try:
                if active:
                    active.status = "archived"
                    active.active_status = False   # dual-write compat
                draft.status = "active"
                draft.active_status = True         # dual-write compat
                db.commit()
                db.refresh(draft)
                return draft
            except exc.IntegrityError:
                db.rollback()
                # Another request won the promotion race — re-read the winner.
                return (
                    db.query(PlanningYear)
                    .filter(PlanningYear.unit_id == squadron_id,
                            PlanningYear.status == "active")
                    .first()
                )

    return active
