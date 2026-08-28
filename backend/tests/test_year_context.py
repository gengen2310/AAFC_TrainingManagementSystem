"""Training Year as calendar context — timezone resolution (plan Task 1)."""
import pytest
from zoneinfo import ZoneInfo

from app.database import SessionLocal
from app.models import Squadron, Wing
from app.services_year import MissingTimezone, squadron_timezone


def test_squadron_timezone_comes_from_its_wing():
    db = SessionLocal()
    try:
        sqn = db.query(Squadron).filter(Squadron.code == "703").first()
        assert squadron_timezone(db, sqn.id) == ZoneInfo("Australia/Perth")
    finally:
        db.close()


def test_missing_timezone_raises_rather_than_defaulting():
    """A silent UTC or Perth default is invisible while 7WG is the only wing,
    and first bites when a second wing is created."""
    db = SessionLocal()
    try:
        sqn = db.query(Squadron).filter(Squadron.code == "703").first()
        wing = db.get(Wing, sqn.wing_id)
        original, wing.timezone = wing.timezone, None
        db.flush()
        with pytest.raises(MissingTimezone):
            squadron_timezone(db, sqn.id)
    finally:
        db.rollback()
        db.close()


# --- Task 2: derived year state -------------------------------------------
import datetime as dt
from unittest.mock import patch

from app.models import PlanningYear
from app.services_year import current_year, selectable_years, year_state


def _sqn_id(db):
    return db.query(Squadron).filter(Squadron.code == "703").first().id


def test_current_year_is_the_wing_local_calendar_year():
    db = SessionLocal()
    try:
        with patch("app.services_year.wing_local_date", return_value=dt.date(2026, 8, 28)):
            assert current_year(db, _sqn_id(db)) == 2026
    finally:
        db.close()


def test_new_years_eve_and_new_years_day_differ_with_no_database_write():
    """The whole point: 1 January performs no write. The default changes
    because the derived value changes."""
    db = SessionLocal()
    try:
        s = _sqn_id(db)
        before = db.query(PlanningYear).count()
        with patch("app.services_year.wing_local_date", return_value=dt.date(2026, 12, 31)):
            assert current_year(db, s) == 2026
        with patch("app.services_year.wing_local_date", return_value=dt.date(2027, 1, 1)):
            assert current_year(db, s) == 2027
        assert db.query(PlanningYear).count() == before, \
            "deriving the current year must not create rows"
    finally:
        db.close()


def test_year_state_is_derived_not_stored():
    db = SessionLocal()
    try:
        s = _sqn_id(db)
        with patch("app.services_year.wing_local_date", return_value=dt.date(2026, 8, 28)):
            assert year_state(db, s, 2025) == "past"
            assert year_state(db, s, 2026) == "current"
            assert year_state(db, s, 2027) == "future"
    finally:
        db.close()


def test_selectable_years_are_capped_at_current_plus_two():
    """User decision 2026-08-28, overriding the instruction's 'no cap'."""
    db = SessionLocal()
    try:
        with patch("app.services_year.wing_local_date", return_value=dt.date(2026, 8, 28)):
            years = selectable_years(db, _sqn_id(db))
        assert max(years) == 2028
        assert 2026 in years and 2027 in years
        assert 2029 not in years
    finally:
        db.close()
