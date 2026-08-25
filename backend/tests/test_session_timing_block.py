"""A session's program period must survive create and edit.

The printed Weekly Program lays sessions out by timing block: the block is the
row. A session with no timing_block_id falls through to the "Unlinked periods"
footnote and never appears in the grid. Two ways to lose it were found on
2026-08-26 while consolidating three divergent copies of the session payload.
"""
from conftest import login, next_test_year


def _night_with_blocks(client, hdr):
    """A parade night with a template of its own, effective for its own date.

    Deliberately does not lean on the seeded 703 template: the suite seeds once
    and never resets, and other tests archive templates, expire them and rewrite
    block_type values. Depending on that shared state made these tests pass alone
    and fail in the full run, with blocks coming back empty.
    """
    year = next_test_year()
    y = client.post("/api/planning/years",
                    json={"year": year, "name": "timing block"}, headers=hdr).json()
    date = f"{year}-08-14"

    r = client.post("/api/timing-templates", json={
        "name": f"Timing-block test {year}",
        "effective_from": f"{year}-01-01",
        "is_default": True,
        "blocks": [
            {"display_order": 0, "block_name": "Period 1", "block_type": "training_period",
             "is_instructional_period": True, "period_number": 1,
             "start_time": "19:00", "end_time": "19:45"},
            {"display_order": 1, "block_name": "Period 2", "block_type": "training_period",
             "is_instructional_period": True, "period_number": 2,
             "start_time": "19:50", "end_time": "20:35"},
        ],
    }, headers=hdr)
    assert r.status_code == 200, r.text

    pnid = client.post("/api/parade-nights",
                       json={"date": date, "term": "T3"}, headers=hdr).json()["parade_night_id"]
    night = [n for n in client.get("/api/parade-nights", headers=hdr).json() if n["date"] == date][0]
    tpl = [t for t in client.get("/api/timing-templates", headers=hdr).json()
           if t["timing_template_id"] == night.get("timing_template_id")]
    assert tpl, "the night did not pick up a timing template"
    blocks = [b for b in tpl[0]["blocks"] if b["is_instructional_period"]]
    assert blocks, "the template this test created must offer instructional periods"
    return date, pnid, blocks[0]["timing_block_id"]


def _block_of(client, hdr, date, session_id):
    night = [n for n in client.get("/api/parade-nights", headers=hdr).json() if n["date"] == date][0]
    return [s for s in night["sessions"] if s["session_id"] == session_id][0].get("timing_block_id")


def test_creating_a_session_keeps_the_program_period(client):
    """SessionIn declares timing_block_id and create_session never wrote it.

    The field was accepted and silently dropped, so a session created with a
    period had none — including every session created from the Add Parade Night
    form, which was only just wired up to send them.
    """
    hdr = login(client, "ADMIN703")
    date, pnid, bid = _night_with_blocks(client, hdr)

    r = client.post("/api/sessions",
                    json={"parade_night_id": pnid, "period_number": 1, "timing_block_id": bid},
                    headers=hdr)
    assert r.status_code == 200, r.text
    assert _block_of(client, hdr, date, r.json()["session_id"]) == bid, \
        "the period given at create time was dropped"


def test_editing_a_session_without_naming_the_period_keeps_it(client):
    """PUT replaces the whole session, so an omitted field is a cleared field.

    saveSessEdit (the per-session edit button) omitted timing_block_id, so every
    quick edit silently removed the session from the printed grid.
    """
    hdr = login(client, "ADMIN703")
    date, pnid, bid = _night_with_blocks(client, hdr)
    sid = client.post("/api/sessions",
                      json={"parade_night_id": pnid, "period_number": 1, "timing_block_id": bid},
                      headers=hdr).json()["session_id"]
    assert _block_of(client, hdr, date, sid) == bid

    # an edit that changes something else entirely
    r = client.put(f"/api/sessions/{sid}",
                   json={"parade_night_id": pnid, "period_number": 1,
                         "phase_at_time": "C. Junior", "timing_block_id": bid},
                   headers=hdr)
    assert r.status_code == 200, r.text
    assert _block_of(client, hdr, date, sid) == bid, \
        "editing an unrelated field must not clear the period"
