"""TRGO-01/02/03/05/08: deferred TRGO feature implementations (general-release
qualification continuation). See docs/release/qualification_gap_register.md.
"""
import io
from datetime import date, timedelta

import pytest
from tests.conftest import login


def _sqn_admin_hdr(client):
    return login(client, "ADMIN703")


def _wing_admin_hdr(client):
    return login(client, "ADMIN7WG")


def _general_hdr(client):
    return login(client, "703SQN2026")


def _make_year(client, hdr, year=2099, name="TRGO Feature Test Year"):
    r = client.post("/api/planning/years", json={"year": year, "name": name}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["planning_year_id"]


def _future_monday():
    """A Monday at least 14 days out, so week-shift math never crosses into the past."""
    d = date.today() + timedelta(days=14)
    return d - timedelta(days=d.weekday())


# ─────────────────────────────────────────────────────────────
# TRGO-01: Update Future Parade Nights
# ─────────────────────────────────────────────────────────────

def _seed_parade_dates(client, hdr, year_id, dates):
    ids = []
    for d in dates:
        r = client.post(f"/api/planning/years/{year_id}/parade-dates",
                        json={"parade_date": d, "parade_type": "standard"},
                        headers=hdr)
        assert r.status_code == 200, r.text
        ids.append(r.json()["parade_date_id"])
    return ids


def test_update_future_parade_day_preview_does_not_write(client):
    hdr = _sqn_admin_hdr(client)
    year_id = _make_year(client, hdr, year=2091)
    monday = _future_monday()
    tuesday_date = (monday + timedelta(days=1)).isoformat()
    _seed_parade_dates(client, hdr, year_id, [tuesday_date])

    r = client.post(f"/api/planning/years/{year_id}/update-future-parade-day",
                    json={"new_weekday": 4, "preview": True},  # move Tue -> Fri
                    headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["preview"] is True
    assert d["to_update"] == 1
    friday_date = (monday + timedelta(days=4)).isoformat()
    assert d["changes"][0]["new_date"] == friday_date
    assert d["changes"][0]["old_date"] == tuesday_date

    # Confirm nothing was actually written
    r2 = client.get(f"/api/planning/years/{year_id}/parade-dates", headers=hdr)
    dates = [row["parade_date"] for row in r2.json()]
    assert tuesday_date in dates
    assert friday_date not in dates


def test_update_future_parade_day_commit_requires_reason(client):
    hdr = _sqn_admin_hdr(client)
    year_id = _make_year(client, hdr, year=2092)
    monday = _future_monday()
    _seed_parade_dates(client, hdr, year_id, [(monday + timedelta(days=1)).isoformat()])

    r = client.post(f"/api/planning/years/{year_id}/update-future-parade-day",
                    json={"new_weekday": 4, "preview": False},
                    headers=hdr)
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "reason_required"


def test_update_future_parade_day_commit_moves_date_and_preserves_night(client):
    hdr = _sqn_admin_hdr(client)
    year_id = _make_year(client, hdr, year=2093)
    monday = _future_monday()
    tuesday_date = (monday + timedelta(days=1)).isoformat()
    ids = _seed_parade_dates(client, hdr, year_id, [tuesday_date])

    # Get the linked parade_night_id before the change
    before = client.get(f"/api/planning/years/{year_id}/parade-dates", headers=hdr).json()
    row = next(r for r in before if r["parade_date_id"] == ids[0])
    pn_id_before = row.get("parade_night_id")

    r = client.post(f"/api/planning/years/{year_id}/update-future-parade-day",
                    json={"new_weekday": 4, "preview": False, "reason": "Squadron changed parade night to Friday"},
                    headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["updated"] == 1
    assert d["skipped"] == 0

    after = client.get(f"/api/planning/years/{year_id}/parade-dates", headers=hdr).json()
    row_after = next(r for r in after if r["parade_date_id"] == ids[0])
    friday_date = (monday + timedelta(days=4)).isoformat()
    assert row_after["parade_date"] == friday_date
    # Same parade_night_id preserved -- sessions/facilitators/rooms untouched
    assert row_after.get("parade_night_id") == pn_id_before


def test_update_future_parade_day_historical_records_unchanged(client):
    """Records before from_date must never be touched."""
    hdr = _sqn_admin_hdr(client)
    year_id = _make_year(client, hdr, year=2094)
    monday = _future_monday()
    future_tuesday = (monday + timedelta(days=1)).isoformat()
    past_tuesday = "2020-01-07"  # a real past Tuesday, well before "today"
    _seed_parade_dates(client, hdr, year_id, [past_tuesday, future_tuesday])

    r = client.post(f"/api/planning/years/{year_id}/update-future-parade-day",
                    json={"new_weekday": 4, "preview": True},
                    headers=hdr)
    changed_old_dates = {c["old_date"] for c in r.json()["changes"]}
    assert past_tuesday not in changed_old_dates
    assert future_tuesday in changed_old_dates


def test_update_future_parade_day_exceptions_preserved_by_default(client):
    """A non-standard parade_type (e.g. a one-off special night) must not move."""
    hdr = _sqn_admin_hdr(client)
    year_id = _make_year(client, hdr, year=2095)
    monday = _future_monday()
    special_date = (monday + timedelta(days=1)).isoformat()
    r = client.post(f"/api/planning/years/{year_id}/parade-dates",
                    json={"parade_date": special_date, "parade_type": "special"},
                    headers=hdr)
    assert r.status_code == 200, r.text

    r2 = client.post(f"/api/planning/years/{year_id}/update-future-parade-day",
                     json={"new_weekday": 4, "preview": True},
                     headers=hdr)
    assert r2.json()["to_update"] == 0
    assert r2.json()["exceptions_preserved"] == 1


def test_update_future_parade_day_holiday_conflict_blocks(client):
    hdr = _sqn_admin_hdr(client)
    year_id = _make_year(client, hdr, year=2096)
    monday = _future_monday()
    tuesday_date = (monday + timedelta(days=1)).isoformat()
    friday_date = (monday + timedelta(days=4)).isoformat()
    _seed_parade_dates(client, hdr, year_id, [tuesday_date])
    r = client.post(f"/api/planning/years/{year_id}/holidays",
                    json={"name": "Test Holiday", "start_date": friday_date, "end_date": friday_date,
                          "affects_parade": True},
                    headers=hdr)
    assert r.status_code == 200, r.text

    r2 = client.post(f"/api/planning/years/{year_id}/update-future-parade-day",
                     json={"new_weekday": 4, "preview": True},
                     headers=hdr)
    d = r2.json()
    assert d["blocked"] == 1
    assert "holiday" in d["changes"][0]["conflicts"]


def test_update_future_parade_day_duplicate_date_blocks(client):
    hdr = _sqn_admin_hdr(client)
    year_id = _make_year(client, hdr, year=2097)
    monday = _future_monday()
    tuesday_date = (monday + timedelta(days=1)).isoformat()
    friday_date = (monday + timedelta(days=4)).isoformat()
    # A parade night already exists on the target Friday
    _seed_parade_dates(client, hdr, year_id, [tuesday_date, friday_date])

    r = client.post(f"/api/planning/years/{year_id}/update-future-parade-day",
                    json={"new_weekday": 4, "preview": True},
                    headers=hdr)
    d = r.json()
    tue_change = next(c for c in d["changes"] if c["old_date"] == tuesday_date)
    assert "duplicate_date" in tue_change["conflicts"]
    assert tue_change["blocked"] is True


def test_update_future_parade_day_writes_audit(client):
    hdr = _sqn_admin_hdr(client)
    year_id = _make_year(client, hdr, year=2098)
    monday = _future_monday()
    _seed_parade_dates(client, hdr, year_id, [(monday + timedelta(days=1)).isoformat()])

    client.post(f"/api/planning/years/{year_id}/update-future-parade-day",
               json={"new_weekday": 4, "preview": False, "reason": "Move to Friday nights"},
               headers=hdr)
    auditor_hdr = login(client, "AUDITOR2026")
    r = client.get("/api/system/audit-summary?action=update_future_parade_day_bulk&limit=10", headers=auditor_hdr)
    assert r.status_code == 200
    assert r.json()["count"] >= 1


def test_update_future_parade_day_sqn_general_cannot_commit(client):
    hdr_admin = _sqn_admin_hdr(client)
    hdr_general = _general_hdr(client)
    year_id = _make_year(client, hdr_admin, year=2081)
    monday = _future_monday()
    _seed_parade_dates(client, hdr_admin, year_id, [(monday + timedelta(days=1)).isoformat()])

    r = client.post(f"/api/planning/years/{year_id}/update-future-parade-day",
                    json={"new_weekday": 4, "preview": False, "reason": "test"},
                    headers=hdr_general)
    assert r.status_code == 403


def test_update_future_parade_day_rollback_on_conflict_does_not_partially_apply(client):
    """A blocked row must be reported as skipped, never partially written."""
    hdr = _sqn_admin_hdr(client)
    year_id = _make_year(client, hdr, year=2082)
    monday = _future_monday()
    tuesday_date = (monday + timedelta(days=1)).isoformat()
    friday_date = (monday + timedelta(days=4)).isoformat()
    ids = _seed_parade_dates(client, hdr, year_id, [tuesday_date, friday_date])

    r = client.post(f"/api/planning/years/{year_id}/update-future-parade-day",
                    json={"new_weekday": 4, "preview": False, "reason": "test"},
                    headers=hdr)
    d = r.json()
    assert d["skipped"] == 1
    # The blocked row's date must be unchanged
    after = client.get(f"/api/planning/years/{year_id}/parade-dates", headers=hdr).json()
    row = next(x for x in after if x["parade_date_id"] == ids[0])
    assert row["parade_date"] == tuesday_date


# ─────────────────────────────────────────────────────────────
# TRGO-02: unified Activities view -- local-hide state surfaced on read
# ─────────────────────────────────────────────────────────────

def test_cea_activities_list_includes_hide_state_defaults(client):
    hdr = _sqn_admin_hdr(client)
    year_id = _make_year(client, hdr, year=2083)
    r = client.post(f"/api/planning/years/{year_id}/cea/activities",
                    json={"activity_name": "Unhidden activity"}, headers=hdr)
    assert r.status_code == 200, r.text

    r2 = client.get(f"/api/planning/years/{year_id}/cea/activities", headers=hdr)
    assert r2.status_code == 200
    act = r2.json()["activities"][0]
    assert act["is_hidden_for_me"] is False
    assert act["local_note"] is None


def test_cea_activities_list_reflects_local_hide(client):
    hdr = _sqn_admin_hdr(client)
    year_id = _make_year(client, hdr, year=2084)
    r = client.post(f"/api/planning/years/{year_id}/cea/activities",
                    json={"activity_name": "To be hidden"}, headers=hdr)
    activity_id = r.json()["id"]

    r2 = client.post(f"/api/planning/cea/{activity_id}/local-hide",
                     json={"is_hidden": True, "local_note": "Not relevant to us"}, headers=hdr)
    assert r2.status_code == 200, r2.text

    r3 = client.get(f"/api/planning/years/{year_id}/cea/activities", headers=hdr)
    act = next(a for a in r3.json()["activities"] if a["id"] == activity_id)
    assert act["is_hidden_for_me"] is True
    assert act["local_note"] == "Not relevant to us"


def test_cea_local_hide_does_not_affect_other_squadron(client):
    """Local hide must be a per-squadron overlay, never visible to a sibling squadron."""
    hdr703 = _sqn_admin_hdr(client)
    hdr704 = login(client, "ADMIN704")
    year_id = _make_year(client, hdr703, year=2085)
    r = client.post(f"/api/planning/years/{year_id}/cea/activities",
                    json={"activity_name": "703-scoped activity"}, headers=hdr703)
    activity_id = r.json()["id"]
    client.post(f"/api/planning/cea/{activity_id}/local-hide",
               json={"is_hidden": True}, headers=hdr703)

    # 704 has no access to 703's year at all (different squadron), confirming
    # scope isolation independently of the hide-state field itself.
    r2 = client.get(f"/api/planning/years/{year_id}/cea/activities", headers=hdr704)
    assert r2.status_code == 403


# ─────────────────────────────────────────────────────────────
# TRGO-05: Facilitator CSV import
# ─────────────────────────────────────────────────────────────

def _csv_file(content: bytes, name="facilitators.csv"):
    return {"file": (name, io.BytesIO(content), "text/csv")}


def test_facilitator_import_template_downloadable(client):
    hdr = _sqn_admin_hdr(client)
    r = client.get("/api/facilitators/import/template.csv", headers=hdr)
    assert r.status_code == 200
    assert b"first_name" in r.content
    assert b"last_name" in r.content


def test_facilitator_import_preview_does_not_write(client):
    hdr = _sqn_admin_hdr(client)
    csv_content = b"rank,first_name,last_name,type,subject_areas\nFLTLT,Trgo05,Preview,Staff,Drill;Air_Space\n"
    r = client.post("/api/facilitators/import?preview=true", files=_csv_file(csv_content), headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["preview"] is True
    assert d["to_create"] == 1
    assert d["rows"][0]["action"] == "create"

    # Not actually created
    r2 = client.get("/api/facilitators", headers=hdr)
    names = [(f["first_name"], f["last_name"]) for f in r2.json()]
    assert ("Trgo05", "Preview") not in names


def test_facilitator_import_commit_creates_rows(client):
    hdr = _sqn_admin_hdr(client)
    csv_content = b"rank,first_name,last_name,type,subject_areas\nFLTLT,Trgo05,Commit,Staff,Drill\n"
    r = client.post("/api/facilitators/import?preview=false", files=_csv_file(csv_content), headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["created"] == 1
    assert d["skipped"] == 0
    assert len(d["created_ids"]) == 1

    r2 = client.get("/api/facilitators", headers=hdr)
    names = [(f["first_name"], f["last_name"]) for f in r2.json()]
    assert ("Trgo05", "Commit") in names


def test_facilitator_import_detects_duplicate_against_existing(client):
    hdr = _sqn_admin_hdr(client)
    client.post("/api/facilitators", json={"first_name": "Trgo05", "last_name": "Existing"}, headers=hdr)

    csv_content = b"first_name,last_name\nTrgo05,Existing\n"
    r = client.post("/api/facilitators/import?preview=true", files=_csv_file(csv_content), headers=hdr)
    d = r.json()
    assert d["rows"][0]["action"] == "duplicate"
    assert d["duplicates"] == 1


def test_facilitator_import_detects_duplicate_within_file(client):
    hdr = _sqn_admin_hdr(client)
    csv_content = b"first_name,last_name\nTrgo05,Dup\nTrgo05,Dup\n"
    r = client.post("/api/facilitators/import?preview=true", files=_csv_file(csv_content), headers=hdr)
    d = r.json()
    assert d["rows"][0]["action"] == "create"
    assert d["rows"][1]["action"] == "duplicate_in_file"


def test_facilitator_import_skips_duplicates_by_default_on_commit(client):
    hdr = _sqn_admin_hdr(client)
    client.post("/api/facilitators", json={"first_name": "Trgo05", "last_name": "SkipMe"}, headers=hdr)

    csv_content = b"first_name,last_name\nTrgo05,SkipMe\n"
    r = client.post("/api/facilitators/import?preview=false", files=_csv_file(csv_content), headers=hdr)
    d = r.json()
    assert d["created"] == 0
    assert d["skipped"] == 1


def test_facilitator_import_confirm_duplicate_rows_forces_create(client):
    hdr = _sqn_admin_hdr(client)
    client.post("/api/facilitators", json={"first_name": "Trgo05", "last_name": "ForceCreate"}, headers=hdr)

    csv_content = b"first_name,last_name\nTrgo05,ForceCreate\n"
    r = client.post("/api/facilitators/import?preview=false&confirm_duplicate_rows=0",
                    files=_csv_file(csv_content), headers=hdr)
    d = r.json()
    assert d["created"] == 1
    assert d["skipped"] == 0


def test_facilitator_import_malformed_row_reported_as_error(client):
    hdr = _sqn_admin_hdr(client)
    csv_content = b"first_name,last_name\nNoLastName,\n"
    r = client.post("/api/facilitators/import?preview=true", files=_csv_file(csv_content), headers=hdr)
    d = r.json()
    assert d["rows"][0]["action"] == "error"
    assert d["errors"] == 1


def test_facilitator_import_partial_invalid_file_still_creates_valid_rows(client):
    hdr = _sqn_admin_hdr(client)
    csv_content = b"first_name,last_name\nGood,Trgo05Row\n,\n"
    r = client.post("/api/facilitators/import?preview=false", files=_csv_file(csv_content), headers=hdr)
    d = r.json()
    assert d["created"] == 1
    assert d["errors"] == 1


def test_facilitator_import_neutralises_formula_injection(client):
    hdr = _sqn_admin_hdr(client)
    csv_content = b'first_name,last_name\n=HYPERLINK("evil"),Trgo05Formula\n'
    r = client.post("/api/facilitators/import?preview=false", files=_csv_file(csv_content), headers=hdr)
    d = r.json()
    assert d["created"] == 1
    r2 = client.get("/api/facilitators", headers=hdr)
    fac = next(f for f in r2.json() if f["last_name"] == "Trgo05Formula")
    assert not fac["first_name"].startswith("=")


def test_facilitator_import_requires_write_permission(client):
    hdr = _general_hdr(client)
    csv_content = b"first_name,last_name\nX,Y\n"
    r = client.post("/api/facilitators/import?preview=false", files=_csv_file(csv_content), headers=hdr)
    assert r.status_code == 403


def test_facilitator_import_writes_audit(client):
    hdr = _sqn_admin_hdr(client)
    csv_content = b"first_name,last_name\nTrgo05,AuditRow\n"
    client.post("/api/facilitators/import?preview=false", files=_csv_file(csv_content), headers=hdr)
    auditor_hdr = login(client, "AUDITOR2026")
    r = client.get("/api/system/audit-summary?action=csv_import&limit=10", headers=auditor_hdr)
    assert r.status_code == 200
    assert r.json()["count"] >= 1


def test_facilitator_import_handles_1000_row_file(client):
    hdr = _sqn_admin_hdr(client)
    lines = ["first_name,last_name"] + [f"Trgo05Bulk{i},Row{i}" for i in range(1000)]
    csv_content = ("\n".join(lines) + "\n").encode()
    r = client.post("/api/facilitators/import?preview=false", files=_csv_file(csv_content), headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["created"] == 1000
    assert d["errors"] == 0
