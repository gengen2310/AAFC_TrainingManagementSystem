"""Training-record completion-date provenance contracts.

Test-only. A successful completion date is the Parade Night date on which the
successful Session occurred. CadetSessionOutcome persistence metadata must never
become a second date authority. Repeated successful attempts keep full history and
the summary uses the most recent successful Parade Night date.
"""

from __future__ import annotations

import csv
import io
import uuid

import pytest
from sqlalchemy import func

from tests.conftest import login


ADM703 = "ADMIN703"


def _db():
    from app.database import SessionLocal
    return SessionLocal()


def _setup_record_fixture(client):
    from app.models import CadetClassMembership, CurriculumItem, SessionAudience, Squadron
    from app.models.planning import PlanningYear
    from app.models.training import (
        Cadet,
        CadetSessionOutcome,
        ParadeNight,
        Session,
        TrainingClass,
    )

    headers = login(client, ADM703)
    phase_name = f"TR-DATE-{uuid.uuid4().hex[:10]}"
    phase_response = client.post(
        "/api/curriculum/phases",
        json={"name": phase_name, "display_name": phase_name, "scope_level": "squadron"},
        headers=headers,
    )
    assert phase_response.status_code == 200, phase_response.text
    phase_id = phase_response.json()["phase_id"]

    db = _db()
    sq = db.query(Squadron).filter(Squadron.code == "703").first()
    if sq is None:
        db.close()
        pytest.skip("703 squadron is not seeded")

    py = db.query(PlanningYear).filter(PlanningYear.unit_id == sq.id).first()
    if py is None:
        py = PlanningYear(
            unit_id=sq.id,
            year=2096,
            name="Training Record Date Guard",
            created_by="test",
            updated_by="test",
        )
        db.add(py)
        db.flush()

    max_number = db.query(func.max(TrainingClass.class_number)).filter(
        TrainingClass.squadron_id == sq.id,
        TrainingClass.training_year_id == py.id,
    ).scalar()
    tc = TrainingClass(
        squadron_id=sq.id,
        training_year_id=py.id,
        training_stage_id=phase_id,
        display_name=f"Date Guard {uuid.uuid4().hex[:6]}",
        class_number=(max_number or 0) + 1,
        created_by="test",
        updated_by="test",
    )
    db.add(tc)
    db.flush()

    cadet = Cadet(
        squadron_id=sq.id,
        service_number=f"TRDATE{uuid.uuid4().hex[:8]}",
        rank="CDT",
        first_name="Date",
        last_name="Guard",
        created_by="test",
        updated_by="test",
    )
    db.add(cadet)
    db.flush()
    db.add(CadetClassMembership(
        cadet_id=cadet.id,
        training_class_id=tc.id,
        start_date="2026-01-01",
        active_status=True,
        source="manual",
        created_by="test",
        updated_by="test",
    ))

    item = CurriculumItem(
        identifier=f"TRDATE-{uuid.uuid4().hex[:8]}",
        code=f"TRDATE-{uuid.uuid4().hex[:6]}",
        title="Completion date provenance guard",
        phase=phase_name,
        part_number=1,
        recommended_sequence=1,
        active_status=True,
    )
    db.add(item)
    db.flush()

    attempts = []
    for idx, parade_date in enumerate(("2026-03-04", "2026-04-01"), start=1):
        pn = ParadeNight(
            squadron_id=sq.id,
            wing_id=sq.wing_id,
            planning_year_id=py.id,
            date=parade_date,
            term="T1",
        )
        db.add(pn)
        db.flush()
        sess = Session(
            squadron_id=sq.id,
            parade_night_id=pn.id,
            period_number=idx,
            curriculum_item_id=item.id,
            status="delivered",
            delivery_notes=f"Delivered attempt {idx}",
            created_by="test",
            updated_by="test",
        )
        db.add(sess)
        db.flush()
        db.add(SessionAudience(session_id=sess.id, training_class_id=tc.id))
        # Deliberately poison the persisted outcome date. The Parade Night is the
        # authoritative operational completion date, not this denormalised field.
        db.add(CadetSessionOutcome(
            cadet_id=cadet.id,
            session_id=sess.id,
            status="completed",
            completion_date=f"2099-12-0{idx}",
            source="derived",
            changed_by="test",
        ))
        attempts.append((sess.id, parade_date))

    db.commit()
    fixture = {
        "headers": headers,
        "class_id": tc.id,
        "cadet_id": cadet.id,
        "item_id": item.id,
        "service_number": cadet.service_number,
        "latest_parade_date": "2026-04-01",
        "attempts": attempts,
    }
    db.close()
    return fixture


def test_class_matrix_completion_date_is_actual_parade_night_date_and_latest_success(client):
    f = _setup_record_fixture(client)
    response = client.get(f"/api/training-records?class_id={f['class_id']}", headers=f["headers"])
    assert response.status_code == 200, response.text
    row = next(r for r in response.json()["rows"] if r["cadet_id"] == f["cadet_id"])
    cell = row["cells"][f["item_id"]]
    assert cell["status"] == "completed"
    assert cell["completion_date"] == f["latest_parade_date"], (
        "Training Records summary must show the most recent successful Parade Night date; "
        "CadetSessionOutcome.completion_date is not an independent date authority"
    )


def test_individual_record_preserves_attempts_and_uses_parade_dates_for_summary(client):
    f = _setup_record_fixture(client)
    response = client.get(f"/api/cadets/{f['cadet_id']}/training-record", headers=f["headers"])
    assert response.status_code == 200, response.text
    item = next(
        item
        for phase in response.json()["phases"]
        for item in phase.get("items", [])
        if item["curriculum_item_id"] == f["item_id"]
    )
    assert item["summary_status"] == "completed"
    assert item["summary_completion_date"] == f["latest_parade_date"]
    assert [a["parade_night_date"] for a in item["attempts"]] == ["2026-03-04", "2026-04-01"]
    assert len(item["attempts"]) == 2, "Repeated successful deliveries must remain separately inspectable"


def test_training_records_export_completion_date_is_actual_parade_night_date(client):
    f = _setup_record_fixture(client)
    response = client.get(f"/api/training-records/export?class_id={f['class_id']}", headers=f["headers"])
    assert response.status_code == 200, response.text
    rows = list(csv.DictReader(io.StringIO(response.text)))
    matching = [r for r in rows if r.get("CEA Number") == f["service_number"]]
    assert matching, "Expected the completed curriculum item in Training Records export"
    assert any(r.get("Completion Date") == f["latest_parade_date"] for r in matching), (
        "Export Completion Date must be the actual successful Parade Night date"
    )
    assert all(not (r.get("Completion Date") or "").startswith("2099-") for r in matching)
