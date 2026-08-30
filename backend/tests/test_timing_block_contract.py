"""The timing-block payload contract, pinned per endpoint.

Part 14 recorded "the Planning Workspace does not display Timing Template
blocks" as the programme's one confirmed missing capability. It does not
reproduce: /weekly-program serialises blocks with exactly the keys the PW's
TimingBlock type reads, and the grid renders them.

What is real is that three endpoints serialise the same object two different
ways, and nothing enforces which is which:

  /planning/parade-dates/{id}/weekly-program  sequence / name / is_instructional
  /planning/parade-dates/{id}/builder         display_order / block_name /
  /parade-nights/{id}/builder                 is_instructional_period

Each side is internally consistent today -- the React PW reads the first shape,
the connected-frontend reads the second. But the divergence is invisible: point
either consumer at the other endpoint and it fails silently rather than loudly.
Blank column headers, duplicate React keys, and -- worst -- `!is_instructional`
evaluating true for every block, so the grid would render every cell as a break
and never show a session.

These tests pin both shapes so neither can drift, and so a future unification
has to change the tests deliberately rather than break a consumer quietly.
"""
from conftest import login, next_test_year

# The PW reads these off WeeklyProgramData.timing_blocks (frontend/src/api/types.ts).
PW_BLOCK_KEYS = {
    "sequence", "name", "block_type", "start_time", "end_time",
    "duration_minutes", "is_instructional", "period_number",
}
# The connected-frontend reads these off both /builder endpoints.
TMS_BLOCK_KEYS = {
    "display_order", "block_name", "block_type", "start_time", "end_time",
    "duration_minutes", "is_instructional_period", "period_number",
}


def _setup(client):
    """A planning year with one parade date, for 703 Squadron.

    Idempotent by design. The suite seeds once per session and never resets, so
    a year number handed out by next_test_year() can already exist by the time
    this runs -- POST /planning/years then 409s with the existing id. Taking
    that id, and reusing an existing parade date when there is one, keeps these
    tests independent of what ran before them.
    """
    hdr = login(client, "ADMIN703")
    year = next_test_year()
    r = client.post("/api/planning/years",
                    json={"year": year, "name": f"{year} Year"}, headers=hdr)
    if r.status_code == 200:
        yr_id = r.json()["planning_year_id"]
    elif r.status_code == 409:
        yr_id = r.json()["detail"]["existing_id"]
    else:
        raise AssertionError(f"could not obtain a planning year: {r.status_code} {r.text}")

    existing = client.get(f"/api/planning/years/{yr_id}/parade-dates", headers=hdr)
    assert existing.status_code == 200, existing.text
    dates = existing.json()
    if dates:
        return hdr, yr_id, dates[0]["parade_date_id"]

    rp = client.post(f"/api/planning/years/{yr_id}/parade-dates",
                     json={"parade_date": f"{year}-09-04"}, headers=hdr)
    assert rp.status_code == 200, rp.text
    return hdr, yr_id, rp.json()["parade_date_id"]


def test_weekly_program_blocks_use_the_pw_key_names(client):
    """Part 14 re-tested: the PW's own type must match what it is sent."""
    hdr, _, pd_id = _setup(client)
    r = client.get(f"/api/planning/parade-dates/{pd_id}/weekly-program", headers=hdr)
    assert r.status_code == 200, r.text
    blocks = r.json()["timing_blocks"]
    assert blocks, (
        "no timing blocks returned -- 703 has no effective template, so this "
        "test proves nothing about the key names"
    )
    for b in blocks:
        assert set(b) == PW_BLOCK_KEYS, (
            f"weekly-program block keys drifted from the PW's TimingBlock type: "
            f"missing={PW_BLOCK_KEYS - set(b)} unexpected={set(b) - PW_BLOCK_KEYS}"
        )


def test_weekly_program_marks_instructional_blocks(client):
    """`is_instructional` must be a real boolean, not absent.

    The PW grid branches on `!b.is_instructional`. An absent key is falsy, so
    every cell would render as a break and no session would ever appear.
    """
    hdr, _, pd_id = _setup(client)
    r = client.get(f"/api/planning/parade-dates/{pd_id}/weekly-program", headers=hdr)
    blocks = r.json()["timing_blocks"]
    assert blocks
    assert all(isinstance(b["is_instructional"], bool) for b in blocks)
    assert any(b["is_instructional"] for b in blocks), (
        "no block is instructional, so the PW grid has no cell to schedule into"
    )


def test_planning_builder_blocks_use_the_tms_key_names(client):
    hdr, _, pd_id = _setup(client)
    r = client.get(f"/api/planning/parade-dates/{pd_id}/builder", headers=hdr)
    assert r.status_code == 200, r.text
    blocks = r.json()["timing_blocks"]
    assert blocks
    for b in blocks:
        assert set(b) == TMS_BLOCK_KEYS, (
            f"builder block keys drifted from what connected-frontend reads: "
            f"missing={TMS_BLOCK_KEYS - set(b)} unexpected={set(b) - TMS_BLOCK_KEYS}"
        )


def test_the_two_shapes_carry_the_same_blocks(client):
    """Different key names, same underlying rows -- not different data."""
    hdr, _, pd_id = _setup(client)
    wp = client.get(f"/api/planning/parade-dates/{pd_id}/weekly-program",
                    headers=hdr).json()["timing_blocks"]
    bl = client.get(f"/api/planning/parade-dates/{pd_id}/builder",
                    headers=hdr).json()["timing_blocks"]
    assert len(wp) == len(bl)
    assert [b["name"] for b in wp] == [b["block_name"] for b in bl]
    assert [b["sequence"] for b in wp] == [b["display_order"] for b in bl]
    assert ([b["is_instructional"] for b in wp]
            == [b["is_instructional_period"] for b in bl])
