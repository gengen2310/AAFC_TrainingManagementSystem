"""Parade-date recurrence: the single rule behind both the preview and the
generate endpoints (planning router), so what the preview shows is by
construction what generation creates.

Pure domain logic: no HTTP, no database. Callers pass the holiday periods
(objects with ISO `start_date` / `end_date`) and map ParadeDateRuleError to
their transport's error shape.

Rules:
- daily / weekly / fortnightly / monthly (first given weekday of the month) /
  yearly (same month and day as the start); an unknown frequency falls back to
  weekly (existing behaviour, kept).
- Fortnightly is anchored to the first matching weekday on or after the start
  date. A skipped night (explicit skip or holiday) removes that occurrence; it
  does not restart the cadence.
- max_repeats counts nights that will be created, not skipped ones.
- Work is bounded: weekday must be 0-6; the scan never runs more than
  SCAN_HORIZON_DAYS past the start; at most MAX_DATES_PER_REQUEST dates are
  touched. A year of daily nights (366) is far inside both limits.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

# 30 years: beyond any plausible planning, small enough that walking it is
# trivial (~11k iterations) and never reaches date.max from a normal start.
SCAN_HORIZON_DAYS = 30 * 366
MAX_DATES_PER_REQUEST = 1000


class ParadeDateRuleError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _parse(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ParadeDateRuleError("invalid_date_format", "Dates must be valid ISO dates (YYYY-MM-DD).")


def classify_parade_dates(
    *,
    weekday: int,
    start_date: str,
    end_date: str | None,
    frequency: str | None,
    excluded_dates: Iterable[str],
    exclude_holidays: bool,
    max_repeats: int | None,
    holidays: Iterable,
) -> list[dict]:
    """Every date the pattern touches, each with status will_create,
    explicitly_skipped or holiday_conflict, in date order."""
    start = _parse(start_date)
    end = _parse(end_date) if end_date else None
    if end is None and max_repeats is None:
        raise ParadeDateRuleError("end_date_or_max_repeats_required", "Provide either end_date or max_repeats.")
    if not 0 <= weekday <= 6:
        raise ParadeDateRuleError("invalid_weekday", "Parade day must be Monday to Sunday (0-6).")
    if max_repeats is not None and max_repeats > MAX_DATES_PER_REQUEST:
        raise ParadeDateRuleError(
            "too_many_dates",
            f"At most {MAX_DATES_PER_REQUEST} parade dates can be generated at once.")
    try:
        horizon = start + timedelta(days=SCAN_HORIZON_DAYS)
    except OverflowError:
        horizon = date.max
    # With max_repeats the count bounds the walk, so a far end date is allowed;
    # the scan itself still never passes the horizon.
    if end is not None and end > horizon and max_repeats is None:
        raise ParadeDateRuleError(
            "date_range_too_long",
            f"The end date must be within {SCAN_HORIZON_DAYS // 366} years of the start date.")
    limit = min(end, horizon) if end is not None else horizon

    excluded = set(excluded_dates or [])
    holiday_ranges = [(h.start_date, h.end_date) for h in holidays] if exclude_holidays else []
    freq = (frequency or "weekly").lower()
    try:
        fortnight_anchor = start + timedelta(days=(weekday - start.weekday()) % 7)
    except OverflowError:
        fortnight_anchor = None     # that weekday never occurs before the calendar ends

    rows: list[dict] = []
    created = 0
    d = start
    while d <= limit:
        if max_repeats is not None and created >= max_repeats:
            break
        if freq == "daily":
            include = True
        elif freq == "fortnightly":
            include = (fortnight_anchor is not None and d.weekday() == weekday
                       and (d - fortnight_anchor).days % 14 == 0)
        elif freq == "monthly":
            include = d.weekday() == weekday and d.day <= 7
        elif freq == "yearly":
            include = d.month == start.month and d.day == start.day
        else:                                   # weekly, and unknown -> weekly
            include = d.weekday() == weekday
        if include:
            ds = d.isoformat()
            if ds in excluded:
                rows.append({"date": ds, "status": "explicitly_skipped"})
            elif any(a <= ds <= b for a, b in holiday_ranges):
                rows.append({"date": ds, "status": "holiday_conflict"})
            else:
                rows.append({"date": ds, "status": "will_create"})
                created += 1
            if len(rows) > MAX_DATES_PER_REQUEST:
                raise ParadeDateRuleError(
                    "too_many_dates",
                    f"At most {MAX_DATES_PER_REQUEST} parade dates can be generated at once. "
                    "Shorten the date range.")
        if d == date.max:
            break
        d += timedelta(days=1)
    # The walk stopped at the horizon (not at the caller's end date) before the
    # requested count: refuse rather than silently create fewer nights.
    if max_repeats is not None and created < max_repeats and (end is None or end > horizon):
        raise ParadeDateRuleError(
            "max_repeats_beyond_horizon",
            f"{max_repeats} parade nights do not fit within {SCAN_HORIZON_DAYS // 366} years of "
            "the start date. Lower the number of repeats or set an end date.")
    return rows
