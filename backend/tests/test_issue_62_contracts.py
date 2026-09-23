"""Regression contracts for the issue #62 workflow remediation."""

from conftest import login


def test_post_cadets_creates_scoped_record_and_audits(client):
    headers = login(client, "ADMIN703")
    payload = {
        "service_number": "I62-CADET-001",
        "rank": "CDT",
        "first_name": "Taylor",
        "last_name": "Example",
        "phase": "Junior",
    }
    response = client.post("/api/cadets", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    cadet_id = response.json()["cadet_id"]
    rows = client.get("/api/cadets", headers=headers).json()
    assert any(row["cadet_id"] == cadet_id for row in rows)

    audit = client.get("/api/audit", headers=headers)
    assert audit.status_code == 200
    assert any(
        row.get("object_id") == cadet_id and row.get("action") == "create"
        for row in audit.json()
    )


def test_post_cadets_rejects_unauthenticated_and_read_only(client):
    payload = {"service_number": "I62-DENIED", "last_name": "Denied"}
    assert client.post("/api/cadets", json=payload).status_code == 401
    headers = login(client, "703SQN2026")
    assert client.post("/api/cadets", json=payload, headers=headers).status_code == 403


def test_cea_realistic_excel_export_bom_and_header_aliases(client):
    headers = login(client, "ADMIN703")
    csv_text = (
        "\ufeffService Number;Rank;First Name;Surname;Position;Unit;Scope;Gender;Access\r\n"
        "I62-CEA-001;CDT;Alex;Nguyen;Cadet;703 SQN;Squadron;X;Active\r\n"
    )
    response = client.post(
        "/api/import/cea-members/preview",
        json={"csv_text": csv_text, "file_name": "CEA Members.csv"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    row = response.json()["rows"][0]
    assert row["action"] == "NEW"
    assert row["service_number"] == "I62-CEA-001"
    assert row["first_name"] == "Alex"
    assert row["last_name"] == "Nguyen"


def test_cea_missing_columns_explains_the_required_fix(client):
    headers = login(client, "ADMIN703")
    response = client.post(
        "/api/import/cea-members/preview",
        json={"csv_text": "Rank,Name\nCDT,Alex\n"},
        headers=headers,
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "missing_required_columns"
    assert "Service Number" in detail["message"]
    assert "Surname" in detail["message"]
