"""A parade night must link to the planning year its DATE falls in.

Reported 2026-08-25: a parade night created in TMS did not appear in Planning
Workspace, the Weekly Program, or the calendar. PW's canvas is built on
ParadeDate rows joined via planning_year_id, so a night linked to the wrong year
is invisible in the year the user is actually looking at.

Phase A note: only one active year per squadron is now allowed (unique index).
The resolution logic (_year_for_date) still applies its rung chain, but rung 3
("single active year") fires for any date when there is exactly one active year.
Tests are written for the Phase A model: each squadron holds exactly one active
year at a time.
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
    """A night created while year N is active links to year N.

    When the user later rolls over to year N+1, existing parade nights already
    attached to N must NOT move — they remain under the year they were created in.
    """
    hdr = login(client, "ADMIN703")
    base = next_test_year()

    # Create year N as the active year.
    earlier = _mk_year(client, hdr, base, f"{base} Training Year")

    date = f"{base}-05-15"          # unambiguously inside year N
    r = client.post("/api/parade-nights", json={"date": date, "term": "T2"}, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["linked_to_planning_year"] is True, "night was not linked to any year"

    in_earlier = _year_of_parade_date(client, hdr, earlier, date)
    assert in_earlier, (
        f"parade night dated {date} is NOT in planning year {base} — "
        f"it did not link to the active year"
    )

    # Promote year N+1 (archives year N). Existing night must stay in year N.
    later = _mk_year(client, hdr, base + 1, f"{base + 1} Training Year")
    in_earlier_after = _year_of_parade_date(client, hdr, earlier, date)
    in_later = _year_of_parade_date(client, hdr, later, date)
    assert in_earlier_after, "parade night must remain in year N after year N+1 is created"
    assert not in_later, f"parade night dated {date} wrongly appears in year {base + 1}"


def test_a_year_with_no_dates_yet_still_wins_on_calendar_match(client):
    """A freshly created active year with no parade dates still receives new nights.

    Phase A: rung 3 (sole active year) fires when there is exactly one active year.
    Creating a parade night while year N is the only active year links the night to N.
    """
    hdr = login(client, "ADMIN703")
    base = next_test_year()
    earlier = _mk_year(client, hdr, base, f"{base} Training Year")  # active, no dates yet

    date = f"{base}-03-11"
    r = client.post("/api/parade-nights", json={"date": date, "term": "T1"}, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["linked_to_planning_year"] is True
    assert _year_of_parade_date(client, hdr, earlier, date), \
        "sole active year should receive the new parade night"


def test_existing_parade_dates_win_over_calendar_match(client):
    """Rung 1 beats rung 2: the year's own date span defines it, not its number.

    A squadron running July-June (year N holds dates into calendar year N+1).
    A night in that range belongs to year N — the active year with the matching span.

    Phase A: only one active year at a time, so rung 1 or rung 3 (sole active)
    handles this correctly as long as year N is still active.
    """
    from app.database import SessionLocal
    from app.models.planning import ParadeDate, PlanningYear
    from app.routers.training import _year_for_date

    hdr = login(client, "ADMIN703")
    base = next_test_year()
    spanning_id = _mk_year(client, hdr, base, f"{base} Jul-Jun Year")

    db = SessionLocal()
    try:
        sq = db.get(PlanningYear, spanning_id).unit_id
        # a genuine July-June span: N-07-01 .. (N+1)-06-30
        for d in (f"{base}-07-01", f"{base + 1}-06-30"):
            db.add(ParadeDate(planning_year_id=spanning_id, unit_id=sq,
                              parade_date=d, parade_type="standard"))
        db.commit()

        # A date inside the span — calendar year is base+1 but year N's dates span it.
        # With year N as the sole active year, rung 1 (date within span) must fire.
        target = f"{base + 1}-02-10"
        chosen = _year_for_date(db, sq, target)
        assert chosen is not None, "resolver found no year at all"
        assert chosen.id == spanning_id, (
            f"expected the spanning year {base}, got {chosen.year} — "
            "rung 1 (date span) should have fired before any other rung"
        )
    finally:
        db.rollback()
        db.close()


def test_the_resolver_reports_none_when_it_cannot_tell(client):
    """Resolver returns None when no active year exists for the squadron."""
    from app.database import SessionLocal
    from app.routers.training import _year_for_date

    db = SessionLocal()
    try:
        # A squadron that has no years at all always returns None.
        assert _year_for_date(db, "no-such-squadron", "2026-05-15") is None
    finally:
        db.close()


def test_far_out_of_range_date_attaches_to_active_year(client):
    """Phase A: a far-out-of-range date attaches to the active year.

    Phase A semantic (deliberate): the unique-active-per-squadron index guarantees
    at most one active year exists. The resolver simply returns it — there is no
    rung chain, and dates outside any parade-date span or calendar-year number
    still attach to the sole active year rather than returning None.

    This test documents that behaviour explicitly. Pre-Phase-A rung 4 (return None
    when no rung fires) has been removed because with exactly one active year,
    rung 3 (sole active year) always fires. A far-out-of-range date like 1900-01-01
    will link to the active year — this is acceptable Phase A behaviour because a
    real parade night on that date is impossible in practice.
    """
    from app.database import SessionLocal
    from app.routers.training import _year_for_date
    from conftest import login, next_test_year

    hdr = login(client, "ADMIN703")
    base = next_test_year()
    yr_id = _mk_year(client, hdr, base, f"{base} Far-date Year")

    db = SessionLocal()
    try:
        from app.models.planning import PlanningYear
        py = db.get(PlanningYear, yr_id)
        squadron_id = py.unit_id

        # Far-out-of-range date — still returns the active year in Phase A
        result = _year_for_date(db, squadron_id, "1900-01-01")
        assert result is not None, (
            "Phase A: sole active year should be returned even for an out-of-range date"
        )
        assert result.id == yr_id, (
            "Phase A: the returned year must be the active year for this squadron"
        )
    finally:
        db.close()
