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
