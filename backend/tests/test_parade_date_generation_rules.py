"""Parade-date generation: one rule for preview and write, a fixed fortnightly
cadence, and bounded work per request.

Defects pinned here (found 2026-10-04):
  1. Fortnightly cadence shifted after any skipped night: excluding 17 Feb from
     a fortnightly Wednesday series produced 24 Feb, 10 Mar ... instead of
     3 Mar, 17 Mar ... (a holiday-skipped night did the same). "Skip dates" and
     holiday handling remove an occurrence; they do not restart the cadence.
  2. Unbounded work: an out-of-range weekday, or an end date far in the future,
     walked day by day to year 9999 (1-4 s of CPU) and then raised
     OverflowError (HTTP 500); an end date just below that limit would have
     created millions of parade nights in one request.
  3. Preview and write each carried their own copy of the loop.
"""
from types import SimpleNamespace

import pytest

from app.services_parade_dates import (
    MAX_DATES_PER_REQUEST, ParadeDateRuleError, classify_parade_dates,
)
from tests.conftest import login, next_test_year


def _rows(holidays=(), **kw):
    kw.setdefault("excluded_dates", [])
    kw.setdefault("exclude_holidays", True)
    kw.setdefault("frequency", "weekly")
    kw.setdefault("end_date", None)
    kw.setdefault("max_repeats", None)
    hol = [SimpleNamespace(start_date=a, end_date=b) for a, b in holidays]
    return [(r["date"], r["status"][0]) for r in classify_parade_dates(holidays=hol, **kw)]


HOLIDAY = [("2027-04-05", "2027-04-16")]

# Captured from the pre-change implementation; every valid non-fortnightly
# pattern must be unchanged (characterisation).
UNCHANGED = {
    "weekly_end": (dict(weekday=3, start_date="2027-02-01", end_date="2027-03-31"),
        [("2027-02-04","w"),("2027-02-11","w"),("2027-02-18","w"),("2027-02-25","w"),("2027-03-04","w"),("2027-03-11","w"),("2027-03-18","w"),("2027-03-25","w")]),
    "weekly_repeats": (dict(weekday=3, start_date="2027-02-01", max_repeats=5),
        [("2027-02-04","w"),("2027-02-11","w"),("2027-02-18","w"),("2027-02-25","w"),("2027-03-04","w")]),
    "monthly": (dict(weekday=1, start_date="2027-01-15", end_date="2027-07-31", frequency="monthly"),
        [("2027-02-02","w"),("2027-03-02","w"),("2027-04-06","h"),("2027-05-04","w"),("2027-06-01","w"),("2027-07-06","w")]),
    "daily_skip": (dict(weekday=0, start_date="2027-03-01", end_date="2027-03-08", frequency="daily", excluded_dates=["2027-03-03"]),
        [("2027-03-01","w"),("2027-03-02","w"),("2027-03-03","e"),("2027-03-04","w"),("2027-03-05","w"),("2027-03-06","w"),("2027-03-07","w"),("2027-03-08","w")]),
    "yearly": (dict(weekday=0, start_date="2027-03-10", end_date="2030-12-31", frequency="yearly"),
        [("2027-03-10","w"),("2028-03-10","w"),("2029-03-10","w"),("2030-03-10","w")]),
    "weekly_holiday": (dict(weekday=3, start_date="2027-03-25", end_date="2027-04-30"),
        [("2027-03-25","w"),("2027-04-01","w"),("2027-04-08","h"),("2027-04-15","h"),("2027-04-22","w"),("2027-04-29","w")]),
    "unknown_freq_falls_back_to_weekly": (dict(weekday=4, start_date="2027-02-01", end_date="2027-02-28", frequency="bogus"),
        [("2027-02-05","w"),("2027-02-12","w"),("2027-02-19","w"),("2027-02-26","w")]),
}


@pytest.mark.parametrize("name", sorted(UNCHANGED))
def test_valid_patterns_are_unchanged(name):
    kw, expected = UNCHANGED[name]
    assert _rows(HOLIDAY, **kw) == expected


def test_fortnightly_without_skips_is_unchanged():
    assert _rows(weekday=2, start_date="2027-02-01", end_date="2027-04-30", frequency="fortnightly") == [
        ("2027-02-03","w"),("2027-02-17","w"),("2027-03-03","w"),("2027-03-17","w"),
        ("2027-03-31","w"),("2027-04-14","w"),("2027-04-28","w")]


def test_fortnightly_skip_keeps_the_cadence():
    assert _rows(weekday=2, start_date="2027-02-01", end_date="2027-04-30", frequency="fortnightly",
                 excluded_dates=["2027-02-17"]) == [
        ("2027-02-03","w"),("2027-02-17","e"),("2027-03-03","w"),("2027-03-17","w"),
        ("2027-03-31","w"),("2027-04-14","w"),("2027-04-28","w")]


def test_fortnightly_holiday_keeps_the_cadence():
    assert _rows(HOLIDAY, weekday=2, start_date="2027-02-01", end_date="2027-04-30", frequency="fortnightly") == [
        ("2027-02-03","w"),("2027-02-17","w"),("2027-03-03","w"),("2027-03-17","w"),
        ("2027-03-31","w"),("2027-04-14","h"),("2027-04-28","w")]


def test_fortnightly_max_repeats_counts_created_nights_on_cadence():
    assert _rows(weekday=2, start_date="2027-02-01", frequency="fortnightly", max_repeats=3,
                 excluded_dates=["2027-02-03"]) == [
        ("2027-02-03","e"),("2027-02-17","w"),("2027-03-03","w"),("2027-03-17","w")]


@pytest.mark.parametrize("weekday", [-1, 7, 99])
def test_weekday_outside_monday_to_sunday_is_rejected(weekday):
    with pytest.raises(ParadeDateRuleError) as e:
        _rows(weekday=weekday, start_date="2027-02-01", max_repeats=3)
    assert e.value.code == "invalid_weekday"


def test_end_date_beyond_the_scan_horizon_is_rejected_not_walked():
    with pytest.raises(ParadeDateRuleError) as e:
        _rows(weekday=2, start_date="2027-02-01", end_date="9999-12-31", frequency="daily")
    assert e.value.code == "date_range_too_long"


def test_more_dates_than_the_per_request_limit_is_rejected():
    with pytest.raises(ParadeDateRuleError) as e:
        _rows(weekday=2, start_date="2027-01-01", end_date="2030-12-31", frequency="daily")
    assert e.value.code == "too_many_dates"
    with pytest.raises(ParadeDateRuleError):
        _rows(weekday=2, start_date="2027-01-01", frequency="weekly", max_repeats=MAX_DATES_PER_REQUEST + 1)


def test_a_full_year_of_daily_nights_is_still_allowed():
    rows = _rows(weekday=0, start_date="2028-01-01", end_date="2028-12-31", frequency="daily", exclude_holidays=False)
    assert len(rows) == 366


def test_start_near_the_end_of_the_calendar_does_not_overflow():
    rows = _rows(weekday=4, start_date="9999-12-01", max_repeats=3)   # 9999-12-31 is a Friday
    assert rows == [("9999-12-03","w"),("9999-12-10","w"),("9999-12-17","w")]


@pytest.mark.parametrize("bad", [dict(start_date="2027-13-01"), dict(end_date="2027-02-30")])
def test_invalid_dates_keep_their_existing_error_code(bad):
    kw = dict(weekday=2, start_date="2027-02-01", end_date="2027-03-01") | bad
    with pytest.raises(ParadeDateRuleError) as e:
        _rows(**kw)
    assert e.value.code == "invalid_date_format"


def test_missing_end_and_repeats_keeps_its_existing_error_code():
    with pytest.raises(ParadeDateRuleError) as e:
        _rows(weekday=2, start_date="2027-02-01")
    assert e.value.code == "end_date_or_max_repeats_required"


# ── API: preview and write agree; errors keep the 400 + detail.error shape ──

def _year(client, hdr):
    year = next_test_year()
    r = client.post("/api/planning/years", json={"year": year, "name": f"{year} Gen Rules"}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["planning_year_id"]


def test_api_preview_and_generate_create_the_same_fortnightly_dates(client):
    # 2092: no other test creates parade nights in that year, so this cannot
    # collide with fixed-date tests (an earlier 2027 version clashed with
    # test_template_compulsory's 2027-04-14 night depending on test order).
    hdr = login(client, "ADMIN703")
    yid = _year(client, hdr)
    body = {"weekday": 2, "start_date": "2092-02-01", "end_date": "2092-04-30", "frequency": "fortnightly",
            "excluded_dates": ["2092-02-20"], "exclude_holidays": False}
    try:
        pv = client.post(f"/api/planning/years/{yid}/preview-parade-dates", json=body, headers=hdr)
        assert pv.status_code == 200, pv.text
        will = [r["date"] for r in pv.json()["dates"] if r["new"]]
        gen = client.post(f"/api/planning/years/{yid}/generate-parade-dates", json=body, headers=hdr)
        assert gen.status_code == 200, gen.text
        assert gen.json()["dates"] == will == [
            "2092-02-06", "2092-03-05", "2092-03-19", "2092-04-02", "2092-04-16", "2092-04-30"]
    finally:
        for n in client.get(f"/api/planning/years/{yid}/parade-dates", headers=hdr).json():
            pnid = n.get("parade_night_id") or n.get("id")
            assert client.delete(f"/api/parade-nights/{pnid}", headers=hdr).status_code == 200


@pytest.mark.parametrize("path", ["preview-parade-dates", "generate-parade-dates"])
def test_api_rejects_unbounded_requests_with_400_and_creates_nothing(client, path):
    hdr = login(client, "ADMIN703")
    yid = _year(client, hdr)
    for body, code in [
        ({"weekday": 7, "start_date": "2027-02-01", "max_repeats": 3}, "invalid_weekday"),
        ({"weekday": 2, "start_date": "2027-02-01", "end_date": "9999-12-31", "frequency": "daily"}, "date_range_too_long"),
        ({"weekday": 2, "start_date": "2027-01-01", "end_date": "2030-12-31", "frequency": "daily"}, "too_many_dates"),
    ]:
        r = client.post(f"/api/planning/years/{yid}/{path}", json=body, headers=hdr)
        assert r.status_code == 400, (body, r.status_code, r.text)
        assert r.json()["detail"]["error"] == code
        assert r.json()["detail"].get("message"), "the UI shows detail.message to the user"
    assert client.get(f"/api/planning/years/{yid}/parade-dates", headers=hdr).json() == []


# Codex review on #71 (services_parade_dates.py:76-82), pinned 2026-10-09.

def test_max_repeats_bounds_the_scan_even_when_the_end_date_is_far():
    # The generator modal sends both bounds; whichever comes first wins, so a
    # far end date must not be rejected when the count stops the walk early.
    rows = _rows(weekday=2, start_date="2027-01-01", end_date="2099-12-31",
                 frequency="daily", max_repeats=3)
    assert [d for d, _ in rows] == ["2027-01-01", "2027-01-02", "2027-01-03"]


def test_max_repeats_the_horizon_cannot_reach_is_rejected_not_truncated():
    # yearly x200 from 2027 needs 200 years; returning the ~30 the horizon
    # allows would silently create fewer nights than asked for.
    with pytest.raises(ParadeDateRuleError) as e:
        _rows(weekday=0, start_date="2027-03-01", frequency="yearly", max_repeats=200)
    assert e.value.code == "max_repeats_beyond_horizon"


def test_both_bounds_unreachable_count_within_horizon_is_rejected():
    with pytest.raises(ParadeDateRuleError) as e:
        _rows(weekday=0, start_date="2027-03-01", end_date="2199-01-01",
              frequency="yearly", max_repeats=200)
    assert e.value.code == "max_repeats_beyond_horizon"


def test_end_date_reached_before_max_repeats_is_still_a_normal_stop():
    rows = _rows(weekday=3, start_date="2027-02-01", end_date="2027-02-28", max_repeats=50)
    assert len(rows) == 4                                   # four Thursdays in Feb 2027


@pytest.mark.parametrize("frequency", ["daily", "weekly", "fortnightly", "monthly", "yearly"])
def test_a_start_on_the_last_calendar_day_never_overflows(frequency):
    # 9999-12-31 is a Friday (4). Any frequency, any weekday: a result or a
    # rule error, never OverflowError (HTTP 500).
    for weekday in range(7):
        try:
            _rows(weekday=weekday, start_date="9999-12-31", frequency=frequency, max_repeats=1)
        except ParadeDateRuleError:
            pass
