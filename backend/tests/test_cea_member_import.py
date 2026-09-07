"""Tests for CEA member import (upsert on service_number): preview, commit, rollback."""
import pytest
from conftest import login


_CEA_CSV_HEADER = "Id,Rank,Name,Family name,Position,Unit,Scope,Gender,Access\n"

def _cea_csv(*rows):
    """Build a minimal CEA CSV string with the given (id, rank, first, last) tuples."""
    lines = _CEA_CSV_HEADER
    for id_, rank, first, last in rows:
        lines += f"{id_},{rank},{first},{last},Cadet,703 RCACS,Squadron,M,Active\n"
    return lines


# ── preview ──────────────────────────────────────────────────────────────────

def test_cea_preview_new_cadet(client):
    """A CEA Id not in the DB classifies as NEW."""
    h = login(client, "ADMIN703")
    csv = _cea_csv(("CEAPREVIEW001", "Cdt", "Alice", "TestPreview"))
    r = client.post("/api/import/cea-members/preview",
                    json={"csv_text": csv, "source_file_name": "test.csv"}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["new_count"] >= 1
    found = [row for row in body["rows"] if row["service_number"] == "CEAPREVIEW001"]
    assert found and found[0]["action"] == "NEW"


def test_cea_preview_update_existing(client):
    """After committing a cadet, a row with same CEA Id but different name classifies as UPDATE."""
    h = login(client, "ADMIN703")
    sn = "CEAUPD001"

    # Commit first
    csv1 = _cea_csv((sn, "Cdt", "Bob", "UpdateTest"))
    r1 = client.post("/api/import/cea-members/commit",
                     json={"csv_text": csv1, "source_file_name": "t.csv"}, headers=h)
    assert r1.status_code == 200

    # Preview with changed last name
    csv2 = _cea_csv((sn, "OCdt", "Bob", "UpdateTestChanged"))
    r2 = client.post("/api/import/cea-members/preview",
                     json={"csv_text": csv2, "source_file_name": "t.csv"}, headers=h)
    assert r2.status_code == 200
    body = r2.json()
    found = [row for row in body["rows"] if row["service_number"] == sn]
    assert found and found[0]["action"] == "UPDATE"


def test_cea_preview_unchanged(client):
    """Same row twice classifies second as UNCHANGED."""
    h = login(client, "ADMIN703")
    sn = "CEAUNCHG001"

    csv = _cea_csv((sn, "Cdt", "Charlie", "UnchangedTest"))
    r1 = client.post("/api/import/cea-members/commit",
                     json={"csv_text": csv, "source_file_name": "t.csv"}, headers=h)
    assert r1.status_code == 200

    r2 = client.post("/api/import/cea-members/preview",
                     json={"csv_text": csv, "source_file_name": "t.csv"}, headers=h)
    assert r2.status_code == 200
    body = r2.json()
    found = [row for row in body["rows"] if row["service_number"] == sn]
    assert found and found[0]["action"] == "UNCHANGED"


def test_cea_preview_error_missing_id(client):
    """Row missing CEA Id classifies as ERROR."""
    h = login(client, "ADMIN703")
    csv = _CEA_CSV_HEADER + ",Cdt,Dave,ErrorTest,Cadet,703,Squadron,M,Active\n"
    r = client.post("/api/import/cea-members/preview",
                    json={"csv_text": csv, "source_file_name": "t.csv"}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["error_count"] >= 1


def test_cea_preview_empty_csv(client):
    h = login(client, "ADMIN703")
    r = client.post("/api/import/cea-members/preview",
                    json={"csv_text": _CEA_CSV_HEADER, "source_file_name": "t.csv"}, headers=h)
    assert r.status_code == 400


def test_cea_preview_unauthenticated(client):
    r = client.post("/api/import/cea-members/preview", json={"csv_text": "x"})
    assert r.status_code == 401


# ── commit ───────────────────────────────────────────────────────────────────

def test_cea_commit_creates_cadet(client):
    """Commit with a new CEA Id creates a Cadet with service_number set."""
    from app.database import SessionLocal
    from app.models.training import Cadet

    h = login(client, "ADMIN703")
    sn = "CEACREATE001"
    csv = _cea_csv((sn, "Cdt", "Eve", "CommitTest"))
    r = client.post("/api/import/cea-members/commit",
                    json={"csv_text": csv, "source_file_name": "t.csv"}, headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["new_count"] >= 1
    assert "batch_id" in body

    db = SessionLocal()
    try:
        cadet = db.query(Cadet).filter(Cadet.service_number == sn).first()
        assert cadet is not None
        assert cadet.last_name == "CommitTest"
    finally:
        db.close()


def test_cea_commit_updates_existing_no_duplicate(client):
    """Commit with existing CEA Id updates rank/name — no duplicate Cadet created."""
    from app.database import SessionLocal
    from app.models.training import Cadet

    h = login(client, "ADMIN703")
    sn = "CEAUPSERT001"

    # Initial create
    csv1 = _cea_csv((sn, "Cdt", "Frank", "UpsertTestA"))
    r1 = client.post("/api/import/cea-members/commit",
                     json={"csv_text": csv1, "source_file_name": "t.csv"}, headers=h)
    assert r1.status_code == 200

    # Update rank + last name
    csv2 = _cea_csv((sn, "OCdt", "Frank", "UpsertTestB"))
    r2 = client.post("/api/import/cea-members/commit",
                     json={"csv_text": csv2, "source_file_name": "t.csv"}, headers=h)
    assert r2.status_code == 200
    body = r2.json()
    assert body["update_count"] >= 1

    db = SessionLocal()
    try:
        cadets = db.query(Cadet).filter(
            Cadet.service_number == sn,
            Cadet.is_archived == False,  # noqa: E712
        ).all()
        # Only one active cadet, not two
        assert len(cadets) == 1
        assert cadets[0].rank == "OCdt"
        assert cadets[0].last_name == "UpsertTestB"
    finally:
        db.close()


def test_cea_commit_unauthenticated(client):
    r = client.post("/api/import/cea-members/commit", json={"csv_text": "x"})
    assert r.status_code == 401


# ── rollback ─────────────────────────────────────────────────────────────────

def test_cea_rollback_archives_new_cadet(client):
    """Rollback of a batch that created a Cadet soft-archives that Cadet."""
    from app.database import SessionLocal
    from app.models.training import Cadet

    h = login(client, "ADMIN703")
    sn = "CEARB001"

    csv = _cea_csv((sn, "Cdt", "Grace", "RollbackTest"))
    r = client.post("/api/import/cea-members/commit",
                    json={"csv_text": csv, "source_file_name": "t.csv"}, headers=h)
    assert r.status_code == 200
    batch_id = r.json()["batch_id"]

    # Verify it exists
    db = SessionLocal()
    try:
        cadet = db.query(Cadet).filter(Cadet.service_number == sn, Cadet.is_archived == False).first()  # noqa: E712
        assert cadet is not None
    finally:
        db.close()

    # Rollback
    r2 = client.post(f"/api/import/cea-members/rollback?batch_id={batch_id}", headers=h)
    assert r2.status_code == 200
    body = r2.json()
    assert body["ok"] is True
    assert body["new_archived"] >= 1

    # Verify cadet is now archived
    db2 = SessionLocal()
    try:
        cadet = db2.query(Cadet).filter(Cadet.service_number == sn, Cadet.is_archived == False).first()  # noqa: E712
        assert cadet is None
    finally:
        db2.close()


def test_cea_rollback_restores_update(client):
    """Rollback of an update batch restores previous rank/name."""
    from app.database import SessionLocal
    from app.models.training import Cadet

    h = login(client, "ADMIN703")
    sn = "CEARBRESTORE001"

    # Create the cadet
    csv1 = _cea_csv((sn, "Cdt", "Henry", "OriginalName"))
    r1 = client.post("/api/import/cea-members/commit",
                     json={"csv_text": csv1, "source_file_name": "t.csv"}, headers=h)
    assert r1.status_code == 200

    # Update it
    csv2 = _cea_csv((sn, "OCdt", "Henry", "ChangedName"))
    r2 = client.post("/api/import/cea-members/commit",
                     json={"csv_text": csv2, "source_file_name": "t.csv"}, headers=h)
    assert r2.status_code == 200
    update_batch_id = r2.json()["batch_id"]

    # Rollback the update
    r3 = client.post(f"/api/import/cea-members/rollback?batch_id={update_batch_id}", headers=h)
    assert r3.status_code == 200
    assert r3.json()["updated_restored"] >= 1

    # Verify restored
    db = SessionLocal()
    try:
        cadet = db.query(Cadet).filter(Cadet.service_number == sn, Cadet.is_archived == False).first()  # noqa: E712
        assert cadet is not None
        assert cadet.rank == "Cdt"
        assert cadet.last_name == "OriginalName"
    finally:
        db.close()


def test_cea_rollback_double_rollback_rejected(client):
    """Rolling back an already-rolled-back batch returns 409."""
    h = login(client, "ADMIN703")
    sn = "CEADBL001"

    csv = _cea_csv((sn, "Cdt", "Iris", "DoubleRBTest"))
    r = client.post("/api/import/cea-members/commit",
                    json={"csv_text": csv, "source_file_name": "t.csv"}, headers=h)
    assert r.status_code == 200
    batch_id = r.json()["batch_id"]

    r2 = client.post(f"/api/import/cea-members/rollback?batch_id={batch_id}", headers=h)
    assert r2.status_code == 200

    r3 = client.post(f"/api/import/cea-members/rollback?batch_id={batch_id}", headers=h)
    assert r3.status_code == 409


def test_cea_rollback_unauthenticated(client):
    r = client.post("/api/import/cea-members/rollback?batch_id=fake-id")
    assert r.status_code == 401


# ── SECURITY: no plaintext access codes in responses ─────────────────────────

def test_cea_import_no_access_code_exposure(client):
    """Import responses must not contain access_code, code_hash, or plain_code."""
    h = login(client, "ADMIN703")
    sn = "CEASEC001"
    csv = _cea_csv((sn, "Cdt", "Jay", "SecTest"))
    r = client.post("/api/import/cea-members/commit",
                    json={"csv_text": csv, "source_file_name": "t.csv"}, headers=h)
    assert r.status_code == 200
    text = r.text
    assert "access_code" not in text
    assert "code_hash" not in text
    assert "plain_code" not in text
