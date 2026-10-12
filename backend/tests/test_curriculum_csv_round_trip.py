"""D17 (2026-10-11): curriculum CSV fields round-trip, and nothing is dropped silently.

Every documented column (Training Phase, Experiential Code, Title, Elements,
Foundation/Extension, Instructor Suitability, Timing, Location, Learning Hub
Link) must land in its field whatever the header case or column order. Two
gaps found reading import_curriculum_csv:
- the slash spelling "Foundation/Extension" (the field's name in the TRGO
  brief) was not mapped, so the column was ignored and every Foundation item
  was stored as Extension, with no warning;
- any unrecognised column was dropped without the result saying so.
The result now lists ignored_columns, and the slash spelling is mapped.
"""
from tests.conftest import login

HEADERS = ["LEARNING HUB LINK", "title", "Foundation/Extension", "Experiential Code",
           "Training Phase", "Elements", "Instructor Suitability", "Timing", "Location",
           "Squadron Notes"]
ROW = ["https://learninghub.example.org/module/rt-01", "Round Trip Module", "Foundation",
       "RT-CSV-01", "C. Intermediate", "Field Craft", "Qualified instructor only", "90 min",
       "Parade ground", "keep me"]


def _csv(headers, row):
    q = lambda v: '"' + v.replace('"', '""') + '"'
    return ",".join(map(q, headers)) + "\r\n" + ",".join(map(q, row)) + "\r\n"


def test_every_documented_column_lands_in_its_field_and_extras_are_reported(client):
    hdr = login(client, "SYSADMIN2026")
    files = {"file": ("curriculum.csv", _csv(HEADERS, ROW), "text/csv")}
    r = client.post("/api/curriculum/import-csv", headers=hdr, files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created"] + body.get("updated", 0) == 1, body
    assert body["ignored_columns"] == ["Squadron Notes"]
    item = next(i for i in client.get("/api/curriculum", headers=hdr).json()["items"]
                if i.get("code") == "RT-CSV-01")
    assert item["title"] == "Round Trip Module"
    assert item["phase"] == "C. Intermediate"
    assert item["element"] == "Field Craft"
    assert item["core_status"] == "core"                     # Foundation
    assert item["instructor_suitability"] == "Qualified instructor only"
    assert item["duration_minutes"] == 90
    assert item["location"] == "Parade ground"          # was dropped by the import model
    assert item["learning_hub_url"] == "https://learninghub.example.org/module/rt-01"


def test_a_file_with_only_known_columns_reports_none_ignored(client):
    hdr = login(client, "SYSADMIN2026")
    files = {"file": ("c.csv", _csv(["Code", "Title"], ["RT-CSV-02", "Known Columns Only"]), "text/csv")}
    r = client.post("/api/curriculum/import-csv?preview=true", headers=hdr, files=files)
    assert r.status_code == 200, r.text
    assert r.json()["ignored_columns"] == []


def test_an_over_long_location_is_reported_not_truncated(client):
    hdr = login(client, "SYSADMIN2026")
    files = {"file": ("c.csv", _csv(["Code", "Title", "Location"],
                                    ["RT-CSV-03", "Long Location", "x" * 61]), "text/csv")}
    r = client.post("/api/curriculum/import-csv?preview=true", headers=hdr, files=files)
    assert r.status_code == 400, r.text           # the only row was skipped -> no valid rows
    assert "Row 2: Location is longer than 60 characters" in r.json()["detail"]["message"]
