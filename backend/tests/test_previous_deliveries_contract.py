"""Contract regression for the Planning Workspace previous-delivery warning."""

import pytest

from tests.conftest import login


def _session_with_curriculum(client, headers):
    response = client.get("/api/parade-nights", headers=headers)
    assert response.status_code == 200, response.text
    for night in response.json():
        night_id = night["parade_night_id"]
        builder = client.get(f"/api/parade-nights/{night_id}/builder", headers=headers)
        if builder.status_code != 200:
            continue
        for session in builder.json().get("sessions", []):
            curriculum_id = session.get("curriculum_item_id") or session.get("curriculum_id")
            session_id = session.get("id") or session.get("session_id")
            if curriculum_id and session_id:
                return session_id, curriculum_id
    pytest.skip("No seeded Session with a Curriculum Item")


def test_previous_deliveries_contract_includes_note_and_training_classes(client):
    """The endpoint consumed by PW is a list of delivery records with lesson notes."""
    headers = login(client, "ADMIN703")
    session_id, curriculum_id = _session_with_curriculum(client, headers)

    delivered = client.post(
        f"/api/sessions/{session_id}/deliver",
        json={"delivery_note": "Contract regression delivery note."},
        headers=headers,
    )
    assert delivered.status_code in (200, 409), delivered.text

    response = client.get(
        f"/api/curriculum-items/{curriculum_id}/previous-deliveries",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    records = response.json()
    assert isinstance(records, list)
    assert records, "A delivered seeded lesson must appear in previous-deliveries"

    record = next((r for r in records if r.get("session_id") == session_id), records[0])
    assert isinstance(record.get("parade_night_date"), str)
    assert "delivery_note" in record
    assert isinstance(record.get("training_classes"), list)
