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


# --- Task 3: canonical uniqueness -----------------------------------------
from sqlalchemy.exc import IntegrityError


def test_a_squadron_cannot_hold_two_live_containers_for_one_year():
    db = SessionLocal()
    try:
        s = _sqn_id(db)
        db.add(PlanningYear(unit_id=s, wing_id=None, year=2061, name="2061 Training Year"))
        db.commit()
        db.add(PlanningYear(unit_id=s, wing_id=None, year=2061, name="2061 again"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()


def test_a_retired_row_does_not_block_a_replacement():
    """Archiving a badly set-up year and creating a correct one must stay possible."""
    db = SessionLocal()
    try:
        s = _sqn_id(db)
        old = PlanningYear(unit_id=s, wing_id=None, year=2062, name="bad")
        old.active_status = False
        db.add(old); db.commit()
        db.add(PlanningYear(unit_id=s, wing_id=None, year=2062, name="2062 Training Year"))
        db.commit()      # must NOT raise
    finally:
        db.close()


def test_two_different_years_for_one_squadron_are_both_allowed():
    """Under the context model, planning 2027 while 2026 runs is normal --
    NOT the duplicate state the index exists to prevent."""
    db = SessionLocal()
    try:
        s = _sqn_id(db)
        db.add(PlanningYear(unit_id=s, wing_id=None, year=2063, name="2063"))
        db.add(PlanningYear(unit_id=s, wing_id=None, year=2064, name="2064"))
        db.commit()      # must NOT raise
    finally:
        db.close()


# --- Task 4: materialise on write, never on read --------------------------
from app.services_year import ensure_year_context, find_year_context


def test_find_does_not_create():
    db = SessionLocal()
    try:
        s = _sqn_id(db)
        before = db.query(PlanningYear).count()
        assert find_year_context(db, s, 2071) is None
        assert db.query(PlanningYear).count() == before, "a read must not write"
    finally:
        db.close()


def test_ensure_creates_once_and_is_idempotent():
    db = SessionLocal()
    try:
        s = _sqn_id(db)
        a = ensure_year_context(db, s, 2072)
        b = ensure_year_context(db, s, 2072)
        assert a.id == b.id
        assert db.query(PlanningYear).filter(
            PlanningYear.unit_id == s, PlanningYear.year == 2072,
            PlanningYear.active_status).count() == 1
    finally:
        db.close()


def test_ensure_derives_the_name_and_never_invents_one():
    db = SessionLocal()
    try:
        py = ensure_year_context(db, _sqn_id(db), 2073)
        assert py.name == "2073 Training Year"
        assert py.year == 2073
    finally:
        db.close()


def test_ensure_reuses_a_retired_year_number_by_creating_a_new_live_row():
    db = SessionLocal()
    try:
        s = _sqn_id(db)
        dead = PlanningYear(unit_id=s, wing_id=None, year=2074, name="old")
        dead.active_status = False
        db.add(dead); db.commit()
        live = ensure_year_context(db, s, 2074)
        assert live.id != dead.id and live.active_status is True
    finally:
        db.close()


def test_ensure_recovers_when_it_loses_the_insert_race():
    """The branch that makes ensure_year_context correct under concurrency.

    Simulates the interleaving directly: the first find returns None (as it
    would for a caller whose competitor has not committed yet), the insert
    then collides with the row that competitor committed, and the loser must
    re-read rather than raise.
    """
    import app.services_year as sy

    db = SessionLocal()
    try:
        s = _sqn_id(db)
        winner = sy.ensure_year_context(db, s, 2075)
        db.commit()

        real, calls = sy.find_year_context, {"n": 0}

        def blind_first_look(*a, **kw):
            calls["n"] += 1
            return None if calls["n"] == 1 else real(*a, **kw)

        with patch.object(sy, "find_year_context", blind_first_look):
            loser = sy.ensure_year_context(db, s, 2075)

        assert calls["n"] == 2, "the race branch was never entered"
        assert loser.id == winner.id, "the loser must return the winner's row"
        assert db.query(PlanningYear).filter(
            PlanningYear.unit_id == s, PlanningYear.year == 2075,
            PlanningYear.active_status).count() == 1
    finally:
        db.rollback()
        db.close()


# --- Task 5: listing and reading years that have no row --------------------
from tests.conftest import login, next_test_year


def _sqn_admin(client):
    hdr = login(client, "ADMIN703")
    sid = client.get("/api/auth/me", headers=hdr).json()["session"]["squadron_id"]
    return hdr, sid


def test_year_listing_includes_future_years_with_no_row(client):
    hdr, _ = _sqn_admin(client)
    rows = client.get("/api/planning/years?include_unmaterialised=true",
                      headers=hdr).json()
    unmaterialised = [r for r in rows if not r["materialised"]]
    assert unmaterialised, "future years with no row must still be listed"
    for r in unmaterialised:
        assert r["planning_year_id"] is None
        assert r["state"] in ("current", "future")


def test_every_listed_year_carries_a_derived_state(client):
    hdr, _ = _sqn_admin(client)
    rows = client.get("/api/planning/years", headers=hdr).json()
    assert rows, "the listing must not be empty"
    assert all(r["state"] in ("past", "current", "future") for r in rows), \
        [r for r in rows if r["state"] not in ("past", "current", "future")]


def test_year_context_read_does_not_create_a_row(client):
    # next_test_year() rather than a literal: the suite shares one database and
    # never resets it, so a hardcoded year is only unused until another test
    # claims it.
    year = next_test_year()
    hdr, sid = _sqn_admin(client)
    db = SessionLocal()
    before = db.query(PlanningYear).count()
    db.close()

    r = client.get(f"/api/planning/year-context?squadron_id={sid}&year={year}",
                   headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["year"] == year
    assert body["materialised"] is False
    assert body["planning_year_id"] is None
    assert body["name"] == f"{year} Training Year"

    db = SessionLocal()
    assert db.query(PlanningYear).count() == before, "a read must not write"
    db.close()


def test_year_context_rejects_another_squadrons_year(client):
    """The read is not a permission hole: 703's admin cannot read 704."""
    hdr, _ = _sqn_admin(client)
    db = SessionLocal()
    other = db.query(Squadron).filter(Squadron.code == "704").first().id
    db.close()
    r = client.get(f"/api/planning/year-context?squadron_id={other}&year=2026",
                   headers=hdr)
    assert r.status_code == 403, r.text


def test_the_default_listing_stays_materialised_only(client):
    """Contract preservation. Both frontends build /years/{id}/holidays style
    URLs straight from this list, so a planning_year_id of None would break
    them. Logical years must be opt-in, never default."""
    hdr, _ = _sqn_admin(client)
    rows = client.get("/api/planning/years", headers=hdr).json()
    assert rows, "the listing must not be empty"
    assert all(r["materialised"] for r in rows)
    assert all(r["planning_year_id"] is not None for r in rows)


# --- wing creation must store a zone, or every year derivation 500s ---------
def test_a_newly_created_wing_stores_a_timezone(client):
    """Regression: a wing created through the API had no timezone, so every
    endpoint deriving the current year raised MissingTimezone and returned 500.
    Caught by nine setup-status tests at once."""
    from tests.conftest import login as _login
    hdr = _login(client, "SYSADMIN2026")
    r = client.post("/api/wings", json={"code": "TZWG1", "name": "Timezone Test Wing"},
                    headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["timezone"], "a new wing must arrive with a stored zone"

    db = SessionLocal()
    try:
        w = db.query(Wing).filter(Wing.code == "TZWG1").first()
        assert w.timezone == "Australia/Perth"   # inherited from its sibling
    finally:
        db.close()


def test_an_explicit_timezone_is_honoured_and_a_bogus_one_rejected(client):
    from tests.conftest import login as _login
    hdr = _login(client, "SYSADMIN2026")
    ok = client.post("/api/wings", json={"code": "TZWG2", "name": "Eastern Test Wing",
                                         "timezone": "Australia/Sydney"}, headers=hdr)
    assert ok.status_code == 200, ok.text
    assert ok.json()["timezone"] == "Australia/Sydney"

    bad = client.post("/api/wings", json={"code": "TZWG3", "name": "Bogus Zone Wing",
                                          "timezone": "Mars/Olympus_Mons"}, headers=hdr)
    assert bad.status_code == 400, bad.text
