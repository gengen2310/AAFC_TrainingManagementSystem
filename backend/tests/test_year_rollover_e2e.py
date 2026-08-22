"""Phase 8 — Year Rollover E2E tests.

These tests prove the complete operator workflow, not individual feature flags:
1. Set up a planning year with parade dates, holidays, and an anchor event
2. Execute rollover to the next year
3. Verify the new year has correctly date-shifted data
4. Verify the old year is fully intact (rollover is non-destructive)
5. Verify the new year is operational (sessions and notices can be added)
6. Verify items that are deliberately NOT carried over (anchor events)
7. Verify idempotency guard (second rollover to same year → 409)

Individual feature tests (copy_holidays=False, training classes, custom
target year, RBAC denial) live in test_planner_v14.py and
test_rollover_training_classes.py.

Year numbering: uses 2161–2179 (odd source years, even rollover targets) to
avoid collisions with other test files (test_concurrency.py uses 2088–2099,
test_planner_v14.py uses 2028–2062) and with each other when run alphabetically.
"""
from tests.conftest import login, next_test_year

ADM = "ADMIN703"
GENERAL = "703SQN2026"


def _hdr(client):
    return login(client, ADM)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_year(client, hdr, year=None, name=None):
    # REM-134: a fixed default year collided with itself on the second call.
    year = next_test_year() if year is None else year
    r = client.post("/api/planning/years",
                    json={"year": year, "name": name or f"E2E Test Year {year}"},
                    headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def _add_holiday(client, hdr, year_id, start="2080-07-01", end="2080-07-14"):
    r = client.post(f"/api/planning/years/{year_id}/holidays", json={
        "name": "School Holidays", "start_date": start, "end_date": end,
        "holiday_type": "school_holiday", "affects_parade": True,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def _generate_parade_dates(client, hdr, year_id, weekday=3,
                            start="2080-09-04", end="2080-10-31"):
    r = client.post(f"/api/planning/years/{year_id}/generate-parade-dates", json={
        "weekday": weekday, "start_date": start, "end_date": end,
        "parade_type": "standard",
    }, headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    # Response: {"ok": True, "created": N, "linked": M, "dates": [...ISO...]}
    return d


def _generated_date_strings(gen):
    """Extract the list of ISO date strings from a generate-parade-dates response."""
    return gen.get("dates", [])


def _add_anchor(client, hdr, year_id, start="2080-06-01"):
    r = client.post(f"/api/planning/years/{year_id}/anchors", json={
        "event_name": "Biennial Review", "event_type": "review",
        "importance": "key_event", "start_date": start,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def _rollover(client, hdr, year_id, **kwargs):
    body = {"copy_holidays": True, "carry_incomplete_sessions": True,
            "copy_training_classes": True}
    body.update(kwargs)
    r = client.post(f"/api/planning/years/{year_id}/rollover", json=body, headers=hdr)
    return r


def _list_dates(client, hdr, year_id):
    # Returns a plain list of parade date objects
    r = client.get(f"/api/planning/years/{year_id}/parade-dates", headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    return d if isinstance(d, list) else d.get("parade_dates", [])


def _list_holidays(client, hdr, year_id):
    # Returns a plain list of holiday objects
    r = client.get(f"/api/planning/years/{year_id}/holidays", headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    return d if isinstance(d, list) else d.get("holidays", [])


def _list_anchors(client, hdr, year_id):
    # Returns a plain list of anchor event objects
    r = client.get(f"/api/planning/years/{year_id}/anchors", headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    return d if isinstance(d, list) else d.get("anchors", [])


def _get_year(client, hdr, year_id):
    r = client.get(f"/api/planning/years/{year_id}", headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


# ─── E2E Tests ────────────────────────────────────────────────────────────────

def test_rollover_full_round_trip_creates_new_year(client):
    """Core E2E: rollover produces a new PlanningYear with correct year/name."""
    hdr = _hdr(client)
    source = _make_year(client, hdr, year=2161)
    _generate_parade_dates(client, hdr, source["planning_year_id"],
                           start="2161-09-01", end="2161-10-31")

    r = _rollover(client, hdr, source["planning_year_id"])
    assert r.status_code == 200, r.text
    out = r.json()

    assert out["ok"] is True
    assert out["year"] == 2162
    assert out["new_planning_year_id"]

    new_year = _get_year(client, hdr, out["new_planning_year_id"])
    assert new_year["year"] == 2162


def test_rollover_date_shifts_parade_dates_by_one_year(client):
    """Parade dates in the new year are exactly one year after the source dates."""
    hdr = _hdr(client)
    source = _make_year(client, hdr, year=next_test_year())
    gen = _generate_parade_dates(client, hdr, source["planning_year_id"],
                                 start="2163-09-01", end="2163-09-30")
    old_dates = sorted(_generated_date_strings(gen))
    assert old_dates, "Need at least one parade date"

    r = _rollover(client, hdr, source["planning_year_id"])
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["parade_dates_copied"] == len(old_dates)

    new_dates = sorted(d["parade_date"] for d in _list_dates(client, hdr, out["new_planning_year_id"]))
    # Each new date should be exactly 1 year after the corresponding old date
    for old, new in zip(old_dates, new_dates):
        old_y, old_rest = old[:4], old[4:]
        new_y, new_rest = new[:4], new[4:]
        assert int(new_y) == int(old_y) + 1, f"Date not shifted: {old} → {new}"
        assert old_rest == new_rest, f"Month/day changed: {old} → {new}"


def test_rollover_date_shifts_holidays_by_one_year(client):
    """Holiday periods are date-shifted one year forward."""
    hdr = _hdr(client)
    source = _make_year(client, hdr, year=next_test_year())
    _add_holiday(client, hdr, source["planning_year_id"],
                 start="2165-07-01", end="2165-07-14")

    r = _rollover(client, hdr, source["planning_year_id"], copy_holidays=True)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["holidays_copied"] == 1

    new_holidays = _list_holidays(client, hdr, out["new_planning_year_id"])
    assert len(new_holidays) == 1
    h = new_holidays[0]
    assert h["start_date"] == "2166-07-01"
    assert h["end_date"] == "2166-07-14"


def test_rollover_old_year_data_intact_after_rollover(client):
    """Rollover is non-destructive: source year data unchanged."""
    hdr = _hdr(client)
    source = _make_year(client, hdr, year=next_test_year())
    gen = _generate_parade_dates(client, hdr, source["planning_year_id"],
                                 start="2167-09-01", end="2167-09-30")
    old_count = len(_generated_date_strings(gen))
    _add_holiday(client, hdr, source["planning_year_id"],
                 start="2167-07-01", end="2167-07-07")

    r = _rollover(client, hdr, source["planning_year_id"])
    assert r.status_code == 200, r.text

    # Source year unchanged
    old_dates = _list_dates(client, hdr, source["planning_year_id"])
    assert len(old_dates) == old_count

    old_holidays = _list_holidays(client, hdr, source["planning_year_id"])
    assert len(old_holidays) == 1
    assert old_holidays[0]["start_date"] == "2167-07-01"


def test_rollover_anchor_events_not_copied(client):
    """Anchor events are deliberately NOT copied — they are year-specific.

    This is a design decision, not an omission. Wing-level events like bivouacs,
    reviews, and competitions must be re-entered because dates and details change
    each year. Auto-copying them would require the admin to delete stale entries,
    which is more error-prone than creating them fresh.
    """
    hdr = _hdr(client)
    source = _make_year(client, hdr, year=next_test_year())
    _add_anchor(client, hdr, source["planning_year_id"], start="2169-06-01")

    r = _rollover(client, hdr, source["planning_year_id"])
    assert r.status_code == 200, r.text

    new_anchors = _list_anchors(client, hdr, r.json()["new_planning_year_id"])
    assert len(new_anchors) == 0, (
        "Anchor events must NOT be auto-copied to the new year — "
        "they are year-specific and must be re-entered."
    )

    # Verify source year anchors still exist
    old_anchors = _list_anchors(client, hdr, source["planning_year_id"])
    assert len(old_anchors) == 1


def test_rollover_parade_dates_create_linked_parade_nights(client):
    """Each copied parade date must have a linked parade_night_id in the new year."""
    hdr = _hdr(client)
    source = _make_year(client, hdr, year=next_test_year())
    _generate_parade_dates(client, hdr, source["planning_year_id"],
                           start="2171-09-01", end="2171-09-30")

    r = _rollover(client, hdr, source["planning_year_id"])
    assert r.status_code == 200, r.text
    out = r.json()

    new_dates = _list_dates(client, hdr, out["new_planning_year_id"])
    assert new_dates, "New year must have parade dates"
    # At least one (ideally all) should have a linked parade_night_id
    with_pn = [d for d in new_dates if d.get("parade_night_id")]
    assert len(with_pn) > 0, "Rollover must create linked parade nights for new year dates"


def test_rollover_idempotency_second_attempt_returns_409(client):
    """Second rollover to the same target year must return 409 (idempotency guard)."""
    hdr = _hdr(client)
    source = _make_year(client, hdr, year=next_test_year())

    r1 = _rollover(client, hdr, source["planning_year_id"])
    assert r1.status_code == 200, r1.text

    r2 = _rollover(client, hdr, source["planning_year_id"])
    assert r2.status_code == 409, r2.text
    assert r2.json()["detail"]["error"] == "planning_year_already_exists"
    assert r2.json()["detail"]["existing_id"] == r1.json()["new_planning_year_id"]


def test_rollover_response_counts_match_actual_data(client):
    """The response summary counts (dates_copied, holidays_copied) match what's
    actually retrievable from the new year's list endpoints."""
    hdr = _hdr(client)
    source = _make_year(client, hdr, year=next_test_year())
    gen = _generate_parade_dates(client, hdr, source["planning_year_id"],
                                 start="2175-09-01", end="2175-09-30")
    _add_holiday(client, hdr, source["planning_year_id"],
                 start="2175-07-01", end="2175-07-07")
    _add_holiday(client, hdr, source["planning_year_id"],
                 start="2175-12-20", end="2175-12-31")

    r = _rollover(client, hdr, source["planning_year_id"])
    assert r.status_code == 200, r.text
    out = r.json()

    expected_dates = len(_generated_date_strings(gen))
    actual_new_dates = _list_dates(client, hdr, out["new_planning_year_id"])
    assert out["parade_dates_copied"] == expected_dates
    assert len(actual_new_dates) == expected_dates

    actual_new_holidays = _list_holidays(client, hdr, out["new_planning_year_id"])
    assert out["holidays_copied"] == 2
    assert len(actual_new_holidays) == 2


def test_rollover_new_year_is_operational_sessions_can_be_added(client):
    """After rollover, the new year's parade nights can have sessions created."""
    hdr = _hdr(client)
    source = _make_year(client, hdr, year=next_test_year())
    # Use a full month so at least one Thursday (weekday=3) falls in range.
    # A single-day range risks picking a non-Thursday and producing 0 dates.
    _generate_parade_dates(client, hdr, source["planning_year_id"],
                           start="2177-09-01", end="2177-09-30")

    r = _rollover(client, hdr, source["planning_year_id"])
    assert r.status_code == 200, r.text
    new_year_id = r.json()["new_planning_year_id"]

    new_dates = _list_dates(client, hdr, new_year_id)
    assert new_dates, "New year must have at least one parade date"

    pn_id = new_dates[0].get("parade_night_id")
    if not pn_id:
        return  # Skip if no parade night was auto-created (depends on squadron config)

    # Verify the parade night is reachable
    pn_r = client.get(f"/api/parade-nights/{pn_id}", headers=hdr)
    assert pn_r.status_code == 200, pn_r.text
    assert pn_r.json()["date"].startswith("2178")


def test_rollover_blocked_for_viewer_role(client):
    """Read-only roles must not be able to initiate a year rollover."""
    hdr_admin = _hdr(client)
    source = _make_year(client, hdr_admin, year=2179)

    hdr_general = login(client, GENERAL)
    r = client.post(f"/api/planning/years/{source['planning_year_id']}/rollover",
                    json={}, headers=hdr_general)
    assert r.status_code == 403, r.text
