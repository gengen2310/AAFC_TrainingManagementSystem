"""Tests for Training Records endpoints: matrix, individual cadet, CSV export, roster, bulk membership."""
import csv
import io

import pytest
from conftest import login


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_training_class_id(client, headers):
    """Return the first training class id visible to this user."""
    r = client.get("/api/training-classes", headers=headers)
    if r.status_code == 200:
        data = r.json()
        items = data if isinstance(data, list) else data.get("training_classes", [])
        if items:
            return items[0].get("training_class_id") or items[0].get("id")
    return None


def _get_cadet_id(client, headers):
    r = client.get("/api/cadets", headers=headers)
    if r.status_code == 200:
        data = r.json()
        items = data if isinstance(data, list) else data.get("cadets", [])
        if items:
            return items[0].get("cadet_id") or items[0].get("id")
    return None


# ── Training Records matrix ───────────────────────────────────────────────────

def test_training_records_matrix_ok(client):
    h = login(client, "ADMIN703")
    class_id = _get_training_class_id(client, h)
    if not class_id:
        pytest.skip("no training class in seed")
    r = client.get(f"/api/training-records?class_id={class_id}", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert "training_class_id" in body
    assert "curriculum_items" in body
    assert "rows" in body


def test_training_records_matrix_missing_class_id(client):
    h = login(client, "ADMIN703")
    r = client.get("/api/training-records", headers=h)
    assert r.status_code in (400, 422)


def test_training_records_matrix_unauthenticated(client):
    r = client.get("/api/training-records?class_id=x")
    assert r.status_code == 401


def test_training_records_matrix_forbidden_sqn_general(client):
    """sqn_general must not access training records."""
    h = login(client, "703SQN2026")  # sqn_general seed code
    r = client.get("/api/training-records?class_id=fake", headers=h)
    assert r.status_code in (403, 404)  # 403 if forbidden before lookup, 404 if class not found


# ── CSV export ────────────────────────────────────────────────────────────────

def test_training_records_export_ok(client):
    h = login(client, "ADMIN703")
    class_id = _get_training_class_id(client, h)
    if not class_id:
        pytest.skip("no training class in seed")
    r = client.get(f"/api/training-records/export?class_id={class_id}", headers=h)
    assert r.status_code == 200
    assert "text/csv" in r.headers.get("content-type", "")

    # Even when there are no completion rows, the export must retain the
    # operational columns Training Officers depend on for CEA entry.
    rows = list(csv.reader(io.StringIO(r.text)))
    assert rows, "CSV export must contain a header row"
    headers = rows[0]
    assert "CEA Number" in headers
    assert "Completion Date" in headers


def test_training_records_export_unauthenticated(client):
    r = client.get("/api/training-records/export?class_id=x")
    assert r.status_code == 401


# ── Individual cadet training record ─────────────────────────────────────────

def test_cadet_training_record_ok(client):
    h = login(client, "ADMIN703")
    cadet_id = _get_cadet_id(client, h)
    if not cadet_id:
        pytest.skip("no cadet in seed")
    r = client.get(f"/api/cadets/{cadet_id}/training-record", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert "cadet_id" in body
    assert "phases" in body


def test_cadet_training_record_not_found(client):
    h = login(client, "ADMIN703")
    r = client.get("/api/cadets/nonexistent-id-xyz/training-record", headers=h)
    assert r.status_code == 404


def test_cadet_training_record_unauthenticated(client):
    r = client.get("/api/cadets/x/training-record", headers=h)
    assert r.status_code == 401


# ── Training class roster ─────────────────────────────────────────────────────

def test_training_class_roster_ok(client):
    h = login(client, "ADMIN703")
    class_id = _get_training_class_id(client, h)
    if not class_id:
        pytest.skip("no training class in seed")
    r = client.get(f"/api/training-classes/{class_id}/roster", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert "training_class_id" in body
    assert "cadets" in body
    assert isinstance(body["cadets"], list)


def test_training_class_roster_not_found(client):
    h = login(client, "ADMIN703")
    r = client.get("/api/training-classes/nonexistent-xyz/roster", headers=h)
    assert r.status_code == 404


def test_training_class_roster_unauthenticated(client):
    r = client.get("/api/training-classes/x/roster")
    assert r.status_code == 401


# ── Bulk membership ───────────────────────────────────────────────────────────

def _make_cadet(db, sq_id, service_number):
    from app.models.training import Cadet
    existing = db.query(Cadet).filter(Cadet.service_number == service_number).first()
    if existing:
        return existing.id
    c = Cadet(squadron_id=sq_id, service_number=service_number,
              first_name="Test", last_name="BulkMember", created_by="test")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c.id


def test_bulk_membership_add(client):
    from app.database import SessionLocal
    from app.models.training import TrainingClass
    from app.models import Squadron

    h = login(client, "ADMIN703")
    db = SessionLocal()
    try:
        sq = db.query(Squadron).filter(Squadron.code == "703").first()
        if not sq:
            pytest.skip("no squadron 703 in seed")
        tc = db.query(TrainingClass).filter(TrainingClass.squadron_id == sq.id, TrainingClass.is_archived == False).first()  # noqa: E712
        if not tc:
            pytest.skip("no training class in seed")
        class_id = tc.id
        cadet_id = _make_cadet(db, sq.id, "CEABULK001")
    finally:
        db.close()

    r = client.post(
        f"/api/training-classes/{class_id}/bulk-membership",
        json={"action": "add", "cadet_ids": [cadet_id]},
        headers=h,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["processed"] >= 0  # may be 0 if already a member


def test_bulk_membership_remove(client):
    from app.database import SessionLocal
    from app.models.training import TrainingClass
    from app.models import Squadron, CadetClassMembership

    h = login(client, "ADMIN703")
    db = SessionLocal()
    try:
        sq = db.query(Squadron).filter(Squadron.code == "703").first()
        if not sq:
            pytest.skip("no squadron 703 in seed")
        tc = db.query(TrainingClass).filter(TrainingClass.squadron_id == sq.id, TrainingClass.is_archived == False).first()  # noqa: E712
        if not tc:
            pytest.skip("no training class in seed")
        class_id = tc.id
        cadet_id = _make_cadet(db, sq.id, "CEABULKRM001")
        # Ensure they are a member
        existing = db.query(CadetClassMembership).filter(
            CadetClassMembership.cadet_id == cadet_id,
            CadetClassMembership.training_class_id == class_id,
            CadetClassMembership.is_archived == False,  # noqa: E712
            CadetClassMembership.active_status == True,  # noqa: E712
        ).first()
        if not existing:
            from datetime import date
            m = CadetClassMembership(
                cadet_id=cadet_id, training_class_id=class_id,
                start_date=str(date.today()), source="manual",
                created_by="test", updated_by="test",
            )
            db.add(m)
            db.commit()
    finally:
        db.close()

    r = client.post(
        f"/api/training-classes/{class_id}/bulk-membership",
        json={"action": "remove", "cadet_ids": [cadet_id]},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_bulk_membership_invalid_action(client):
    h = login(client, "ADMIN703")
    r = client.post(
        "/api/training-classes/fake-id/bulk-membership",
        json={"action": "delete_all", "cadet_ids": []},
        headers=h,
    )
    assert r.status_code == 422


def test_bulk_membership_unauthenticated(client):
    r = client.post(
        "/api/training-classes/x/bulk-membership",
        json={"action": "add", "cadet_ids": []},
    )
    assert r.status_code == 401


# ── SECURITY: training records responses must not leak access codes ───────────

def test_training_records_no_access_code_in_response(client):
    h = login(client, "ADMIN703")
    class_id = _get_training_class_id(client, h)
    if not class_id:
        pytest.skip("no training class in seed")
    r = client.get(f"/api/training-records?class_id={class_id}", headers=h)
    assert r.status_code == 200
    text = r.text
    assert "access_code" not in text
    assert "plain_code" not in text
    assert "code_hash" not in text
