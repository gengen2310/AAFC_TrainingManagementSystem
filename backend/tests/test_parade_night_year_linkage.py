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
    assert "parade_night_id" in r.json(), "create_parade must return parade_night_id"

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
    assert "parade_night_id" in r.json(), "create_parade must return parade_night_id"
    assert _year_of_parade_date(client, hdr, earlier, date), \
        "calendar-year match should have chosen the earlier year"


def test_existing_parade_dates_win_over_calendar_match(client):
    """Phase B: ParadeDate and _year_for_date were removed. The year linkage is
    now set directly via planning_year_id on ParadeNight at creation time via
    ensure_year_context (calendar-year match). This test verifies the API-level
    behaviour: a night dated inside a calendar year is linked to the planning
    year whose `year` field matches that calendar year, not to a higher-numbered
    year that also exists.
    """
    hdr = login(client, "ADMIN703")
    base = next_test_year()
    spanning_id = _mk_year(client, hdr, base, f"{base} Jul-Jun Year")
    _mk_year(client, hdr, base + 1, f"{base + 1} Training Year")

    # A night dated in `base` must land in the year numbered `base`.
    target = f"{base}-11-15"
    r = client.post("/api/parade-nights", json={"date": target, "term": "T2"}, headers=hdr)
    assert r.status_code == 200, r.text
    pn_id = r.json()["parade_night_id"]

    from app.database import SessionLocal
    from app.models import ParadeNight
    db = SessionLocal()
    try:
        pn = db.get(ParadeNight, pn_id)
        assert pn is not None
        assert pn.planning_year_id == spanning_id, (
            f"Night dated {target} should link to planning year {base} ({spanning_id!r}), "
            f"but got planning_year_id={pn.planning_year_id!r}"
        )
    finally:
        db.close()


def test_the_resolver_reports_none_when_it_cannot_tell(client):
    """Phase B: _year_for_date was removed; planning_year_id is now set via
    ensure_year_context which creates a year when none exists rather than
    returning None. This test verifies that a parade night can always be created
    (ensure_year_context is idempotent) and receives a non-null planning_year_id.

    Uses year 4999 — NOT in the next_test_year() counter range (which starts at
    5000 and steps by 3, allocating values ≡ 2 mod 3; 4999 ≡ 1 mod 3) — so the
    planning year implicitly created by ensure_year_context here does not consume
    a counter slot and cannot collide with any test that calls next_test_year().
    """
    hdr = login(client, "ADMIN703")
    # No planning year pre-created — ensure_year_context must create one.
    date = "4999-06-01"
    r = client.post("/api/parade-nights", json={"date": date, "term": "T2"}, headers=hdr)
    assert r.status_code == 200, r.text
    pn_id = r.json()["parade_night_id"]

    from app.database import SessionLocal
    from app.models import ParadeNight
    db = SessionLocal()
    try:
        pn = db.get(ParadeNight, pn_id)
        assert pn is not None
        assert pn.planning_year_id is not None, (
            "ensure_year_context must always assign a planning_year_id"
        )
    finally:
        db.close()
