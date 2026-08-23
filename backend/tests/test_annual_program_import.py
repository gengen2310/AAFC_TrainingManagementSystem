"""Regression tests for POST /api/planning/years/{id}/import-program's per-row squadron
scope enforcement (REM-45 residual / security review candidate 3).

Confirmed live during the Final Remediation program: a wing_admin, never entering
Proxy/Delegated Intervention Mode, could import a CADET.Net CSV into a wing-scoped plan
year whose Unit column routed a row to a specific squadron -- creating real squadron-scoped
data (an Activity record) with no proxy check at all. Every other squadron-scoped write path
in this app requires Proxy Mode; this endpoint's row-resolution logic bypassed that entirely
for wing/national-scoped plan years.
"""
from conftest import login
from tests.conftest import next_test_year


def _sqn_id(client, headers, code):
    r = client.get("/api/squadrons", headers=headers)
    assert r.status_code == 200
    for s in r.json():
        if s["code"] == code:
            return s["squadron_id"]
    return None


def _make_csv(unit_code="703", seq="IDOR-TEST-01"):
    return (
        "SeqNr,Name,Start date,Start time,End date,End time,Unit,Owner,Status,Last Updated\r\n"
        f"{seq},IDOR Regression Activity,15/03/2031,09:00,15/03/2031,10:00,{unit_code},Wing HQ,Confirmed,\r\n"
    )


def test_wing_admin_without_proxy_cannot_import_rows_into_a_squadron(client):
    """The confirmed live exploit: create a wing-scoped plan year, import a row whose Unit
    column routes to a real squadron, while never entering Proxy Mode -- must be skipped,
    not written."""
    h = login(client, "ADMIN7WG")
    proxy_before = client.get("/api/proxy/current", headers=h).json()
    assert proxy_before["active"] is False

    yr = client.post("/api/planning/years", headers=h, json={"year": next_test_year(), "name": "Scope Test Year A"})
    assert yr.status_code == 200, yr.text
    year_id = yr.json()["planning_year_id"]

    files = {"file": ("program.csv", _make_csv(seq="IDOR-TEST-A"), "text/csv")}
    r = client.post(f"/api/planning/years/{year_id}/import-program", headers=h, files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created_activities"] == 0, "row must not be written without write authority"
    assert body["skipped"] == 1
    assert any("write authority" in e for e in body["parse_errors"])

    # Proxy Mode was never entered at any point -- confirms this wasn't silently auto-granted.
    proxy_after = client.get("/api/proxy/current", headers=h).json()
    assert proxy_after["active"] is False

    sqn_id = _sqn_id(client, h, "703")
    acts = client.get(f"/api/activities?squadron_id={sqn_id}", headers=login(client, "ADMIN703")).json()
    assert not any(a.get("cea_seq_nr") == "IDOR-TEST-A" for a in acts), \
        "activity must not have been created for the target squadron"


def test_wing_admin_preview_flags_scope_denied_rows_without_writing(client):
    """Preview mode must surface the same scope check (so a user sees which rows would be
    blocked before committing) without ever writing to the database."""
    h = login(client, "ADMIN7WG")
    yr = client.post("/api/planning/years", headers=h, json={"year": next_test_year(), "name": "Scope Test Year B"})
    year_id = yr.json()["planning_year_id"]

    files = {"file": ("program.csv", _make_csv(seq="IDOR-TEST-B"), "text/csv")}
    r = client.post(f"/api/planning/years/{year_id}/import-program?preview=true", headers=h, files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["preview"] is True
    assert len(body["rows"]) == 1
    assert body["rows"][0]["status"] == "blocked_scope"

    sqn_id = _sqn_id(client, h, "703")
    acts = client.get(f"/api/activities?squadron_id={sqn_id}", headers=login(client, "ADMIN703")).json()
    assert not any(a.get("cea_seq_nr") == "IDOR-TEST-B" for a in acts)


def test_wing_admin_with_active_proxy_can_import_rows_into_that_squadron(client):
    """The legitimate path must keep working exactly as before: a wing_admin who has
    properly entered Proxy Mode for the target squadron can still import rows for it."""
    h = login(client, "ADMIN7WG")
    sqn_id = _sqn_id(client, h, "703")

    yr = client.post("/api/planning/years", headers=h, json={"year": next_test_year(), "name": "Scope Test Year C"})
    year_id = yr.json()["planning_year_id"]

    enter = client.post(f"/api/proxy/enter/{sqn_id}", headers=h, json={"reason": "Legitimate import"})
    assert enter.status_code == 200, enter.text

    files = {"file": ("program.csv", _make_csv(seq="IDOR-TEST-C"), "text/csv")}
    r = client.post(f"/api/planning/years/{year_id}/import-program", headers=h, files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created_activities"] == 1, "legitimate proxied import must still succeed"
    assert body["skipped"] == 0

    client.post("/api/proxy/exit", headers=h)

    acts = client.get(f"/api/activities?squadron_id={sqn_id}", headers=login(client, "ADMIN703")).json()
    assert any(a.get("cea_seq_nr") == "IDOR-TEST-C" for a in acts), \
        "activity must have been created for the target squadron"


def test_wing_admin_proxied_into_a_different_squadron_still_blocked_for_this_one(client):
    """Being in Proxy Mode for squadron A must not grant write authority into squadron B via
    this import path -- the scope check is per-row against the row's own resolved squadron,
    not a blanket 'is in some proxy session' check."""
    h = login(client, "ADMIN7WG")
    sqn_703 = _sqn_id(client, h, "703")
    sqn_704 = _sqn_id(client, h, "704")
    assert sqn_703 and sqn_704 and sqn_703 != sqn_704

    yr = client.post("/api/planning/years", headers=h, json={"year": next_test_year(), "name": "Scope Test Year D"})
    year_id = yr.json()["planning_year_id"]

    enter = client.post(f"/api/proxy/enter/{sqn_704}", headers=h, json={"reason": "Proxied into 704 only"})
    assert enter.status_code == 200, enter.text

    files = {"file": ("program.csv", _make_csv(unit_code="703", seq="IDOR-TEST-D"), "text/csv")}
    r = client.post(f"/api/planning/years/{year_id}/import-program", headers=h, files=files)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["created_activities"] == 0, "proxy into a different squadron must not grant write here"
    assert body["skipped"] == 1

    client.post("/api/proxy/exit", headers=h)
