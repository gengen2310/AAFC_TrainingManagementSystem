"""A parade night must link to the planning year its DATE falls in.

Reported 2026-08-25: a parade night created in TMS did not appear in Planning
Workspace, the Weekly Program, or the calendar. PW's canvas is built on
ParadeDate rows joined via planning_year_id, so a night linked to the wrong year
is invisible in the year the user is actually looking at.
"""
from conftest import login, next_test_year


def _mk_year(client, hdr, year, name):
    r = client.post("/api/planning/years", json={"year": year, "name": name}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["planning_year_id"]


def _year_of_parade_date(client, hdr, year_id, date):
    """Is there a ParadeDate for `date` under this planning year?"""
    r = client.get(f"/api/planning/years/{year_id}/parade-dates", headers=hdr)
    if r.status_code != 200:
        return None
    rows = r.json() if isinstance(r.json(), list) else r.json().get("parade_dates", [])
    return [d for d in rows if d.get("parade_date") == date]


def test_parade_night_links_to_the_year_containing_its_date(client):
    """The bug: linkage picks the highest-numbered active year, ignoring the date.

    A squadron mid-rollover legitimately has two active years. A night dated in
    the earlier one gets attached to the later one, and then does not appear in
    Planning Workspace when the user opens the year they scheduled it in.
    """
    hdr = login(client, "ADMIN703")
    base = next_test_year()

    earlier = _mk_year(client, hdr, base, f"{base} Training Year")
    later = _mk_year(client, hdr, base + 1, f"{base + 1} Training Year")

    date = f"{base}-05-15"          # unambiguously inside `earlier`
    r = client.post("/api/parade-nights", json={"date": date, "term": "T2"}, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["linked_to_planning_year"] is True, "night was not linked to any year"

    in_earlier = _year_of_parade_date(client, hdr, earlier, date)
    in_later = _year_of_parade_date(client, hdr, later, date)

    assert in_earlier, (
        f"parade night dated {date} is NOT in planning year {base} — "
        f"it landed in {base + 1} instead, so Planning Workspace cannot see it "
        f"when the user opens {base}"
    )
    assert not in_later, f"parade night dated {date} wrongly appears in year {base + 1}"


def test_a_year_with_no_dates_yet_still_wins_on_calendar_match(client):
    """The reported case: a year created moments ago has no parade dates to span.

    Rung 2 of the chain. Without it, a brand-new year could never receive its
    first parade night, which is precisely when the user is creating them.
    """
    hdr = login(client, "ADMIN703")
    base = next_test_year()
    earlier = _mk_year(client, hdr, base, f"{base} Training Year")
    _mk_year(client, hdr, base + 1, f"{base + 1} Training Year")   # newer, empty, higher number

    date = f"{base}-03-11"
    r = client.post("/api/parade-nights", json={"date": date, "term": "T1"}, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["linked_to_planning_year"] is True
    assert _year_of_parade_date(client, hdr, earlier, date), \
        "calendar-year match should have chosen the earlier year"


def test_existing_parade_dates_win_over_calendar_match(client):
    """Rung 1 beats rung 2: the user's own dates define the year, not its number.

    A squadron running July-June has a year numbered N holding dates that run into
    calendar year N+1. A night in that range belongs to it, even though a year
    numbered N+1 also exists and would win on calendar match.

    Driven directly rather than through the API: seeding the span via the API is
    circular, because each seeding night is itself routed by the rule under test.
    An earlier version of this test gave the year a SINGLE date and expected it to
    span a later one, which it cannot.
    """
    from app.database import SessionLocal
    from app.models import Squadron
    from app.models.planning import ParadeDate, PlanningYear
    from app.routers.training import _year_for_date

    hdr = login(client, "ADMIN703")
    base = next_test_year()
    spanning_id = _mk_year(client, hdr, base, f"{base} Jul-Jun Year")
    _mk_year(client, hdr, base + 1, f"{base + 1} Training Year")

    db = SessionLocal()
    try:
        sq = db.get(PlanningYear, spanning_id).unit_id
        # a genuine July-June span: N-07-01 .. (N+1)-06-30
        for d in (f"{base}-07-01", f"{base + 1}-06-30"):
            db.add(ParadeDate(planning_year_id=spanning_id, unit_id=sq,
                              parade_date=d, parade_type="standard"))
        db.commit()

        target = f"{base + 1}-02-10"     # inside the span; calendar year is base+1
        chosen = _year_for_date(db, sq, target)
        assert chosen is not None, "resolver found no year at all"
        assert chosen.id == spanning_id, (
            f"expected the spanning year {base}, got {chosen.year} — "
            "calendar match beat the year's own date range"
        )
    finally:
        db.rollback()
        db.close()


def test_the_resolver_reports_none_when_it_cannot_tell(client):
    """Rung 4. Better an honest unlinked night than a silently wrong year."""
    from app.database import SessionLocal
    from app.routers.training import _year_for_date
    from app.models import Squadron

    db = SessionLocal()
    try:
        sq = db.query(Squadron).filter(Squadron.code.like("703%")).first()
        assert sq is not None
        # a date no active year spans and no active year is numbered for
        assert _year_for_date(db, sq.id, "1900-01-01") is None
        # and a squadron with no years at all
        assert _year_for_date(db, "no-such-squadron", "2026-05-15") is None
    finally:
        db.close()
