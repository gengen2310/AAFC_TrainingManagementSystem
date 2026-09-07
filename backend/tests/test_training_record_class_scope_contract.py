"""Class-level Training Records must show the selected Training Class's phase curriculum only."""

from __future__ import annotations

import uuid

import pytest

from tests.conftest import login
from tests.test_training_record_visibility_contract import (
    ADM703,
    _cadet_member,
    _curriculum_item,
    _db,
    _squadron,
    _training_class,
)


def _squadron_phase(client, label: str) -> tuple[str, str]:
    name = f"TR-CLASS-{label}-{uuid.uuid4().hex[:8]}"
    response = client.post(
        "/api/curriculum/phases",
        json={"name": name, "display_name": name, "scope_level": "squadron"},
        headers=login(client, ADM703),
    )
    assert response.status_code == 200, response.text
    return response.json()["phase_id"], name


def test_class_training_record_excludes_unrelated_phase_curriculum(client):
    """A Foundation-class matrix must not acquire columns from an unrelated local phase/class."""
    target_phase_id, target_phase_name = _squadron_phase(client, "TARGET")
    _, unrelated_phase_name = _squadron_phase(client, "UNRELATED")
    headers = login(client, ADM703)

    db = _db()
    try:
        sq = _squadron(db)
        if sq is None:
            pytest.skip("703 squadron is not seeded")
        target_item = _curriculum_item(db, target_phase_name, title="Target phase lesson")
        unrelated_item = _curriculum_item(db, unrelated_phase_name, title="Unrelated phase lesson")
        tc = _training_class(db, sq.id, target_phase_id)
        _cadet_member(db, sq.id, tc.id)
        class_id = tc.id
        target_id, unrelated_id = target_item.id, unrelated_item.id
    finally:
        db.close()

    response = client.get(f"/api/training-records?class_id={class_id}", headers=headers)
    assert response.status_code == 200, response.text
    returned_ids = {item["curriculum_item_id"] for item in response.json()["curriculum_items"]}
    assert target_id in returned_ids, "Selected Training Class phase curriculum is missing"
    assert unrelated_id not in returned_ids, (
        "Class-level Training Records must be scoped to the selected Training Class's "
        "training phase; unrelated phase curriculum must not become matrix columns"
    )
