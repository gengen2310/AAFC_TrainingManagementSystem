"""D18 (2026-10-11): CEA bulk import stores invalid dates/times and never says why.

_parse_cea_date falls back to the raw text when no format matches, so
'31/02/2026' or 'next Tuesday' was stored as an activity's date;
_parse_cea_time kept the first five characters of anything with a colon
('25:99' stored) and dropped '9:30' entirely. Rows without a name were
skipped silently, and any other per-row exception only bumped 'errors'.
The response now lists row_errors (row number, field, value, what to fix);
an invalid row is not written; valid rows in the same file still import
(the import's existing partial semantics are kept).
"""
import io

from tests.conftest import login
from tests.test_cea_consolidation import _wing_admin_year_for_squadron

HEADER = "ActivityID,Name,StartDate,EndDate,StartTime,EndTime,Location\n"


def _import(client, hdr, year_id, body: str):
    return client.post(f"/api/planning/years/{year_id}/cea/import", headers=hdr,
                       files={"file": ("cea.csv", io.BytesIO((HEADER + body).encode()), "text/csv")})


def _activities(client, hdr, year_id):
    r = client.get(f"/api/planning/years/{year_id}/cea/activities", headers=hdr)
    assert r.status_code == 200, r.text
    return {a["cea_activity_id"]: a for a in r.json()["activities"]}


def test_invalid_rows_are_reported_and_not_written_while_valid_rows_import(client):
    sqn = login(client, "ADMIN703")
    wing = login(client, "ADMIN7WG")
    year_id = _wing_admin_year_for_squadron(client, sqn)
    r = _import(client, wing, year_id,
                "D18-OK,Good Camp,05/03/2099,07/03/2099,9:30,16:00,Range A\n"
                "D18-BADDATE,Bad Date,31/02/2099,,,,\n"
                "D18-WORDS,Wordy Date,next Tuesday,,,,\n"
                "D18-BADTIME,Bad Time,2099-03-10,,25:99,,\n"
                ",,2099-03-11,,,,\n")
    assert r.status_code == 200, r.text
    body = r.json()
    errs = body["row_errors"]
    by_row = {e["row"]: e for e in errs}
    assert set(by_row) == {3, 4, 5, 6}, errs
    assert by_row[3]["field"] == "StartDate" and "31/02/2099" in by_row[3]["message"]
    assert by_row[4]["field"] == "StartDate"
    assert by_row[5]["field"] == "StartTime" and "25:99" in by_row[5]["message"]
    assert by_row[6]["field"] == "Name"
    acts = _activities(client, sqn, year_id)
    assert "D18-OK" in acts
    assert acts["D18-OK"]["activity_start_date"] == "2099-03-05"
    assert acts["D18-OK"]["start_time"] == "09:30"              # was dropped (len 4)
    for bad in ("D18-BADDATE", "D18-WORDS", "D18-BADTIME"):
        assert bad not in acts, bad


def test_a_bad_reimport_row_leaves_the_existing_activity_untouched(client):
    sqn = login(client, "ADMIN703")
    wing = login(client, "ADMIN7WG")
    year_id = _wing_admin_year_for_squadron(client, sqn)
    assert _import(client, wing, year_id, "D18-KEEP,Keep Me,2099-04-01,,,,Hangar\n").status_code == 200
    r = _import(client, wing, year_id, "D18-KEEP,Keep Me Renamed,2099-04-99,,,,Elsewhere\n")
    assert r.status_code == 200, r.text
    assert r.json()["row_errors"], r.json()
    a = _activities(client, sqn, year_id)["D18-KEEP"]
    assert (a["activity_name"], a["activity_start_date"], a["location"]) == ("Keep Me", "2099-04-01", "Hangar")


def test_all_empty_lines_are_skipped_without_errors(client):
    sqn = login(client, "ADMIN703")
    wing = login(client, "ADMIN7WG")
    year_id = _wing_admin_year_for_squadron(client, sqn)
    r = _import(client, wing, year_id, "D18-PAD,Padded File,2099-05-01,,,,\n,,,,,,\n,,,,,,\n")
    assert r.status_code == 200, r.text
    assert r.json()["row_errors"] == []
    assert "D18-PAD" in _activities(client, sqn, year_id)
