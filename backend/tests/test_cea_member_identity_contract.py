"""CEA member-import identity/integrity contracts.

CEA Id/service_number is the stable identity. Import must upsert that identity,
never create a second live Cadet for the same CEA number, and ambiguous/malformed
rows must not be partially applied.
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest

from tests.conftest import login


HEADER = "Id,Rank,Name,Family name,Position,Unit,Scope,Gender,Access\n"


def _row(cea_id: str, rank: str, first: str, last: str) -> str:
    return f"{cea_id},{rank},{first},{last},Cadet,Ignored Unit,Squadron,F,Active\n"


def _db():
    from app.database import SessionLocal

    return SessionLocal()


def _sq(db, code: str):
    from app.models import Squadron

    return db.query(Squadron).filter(Squadron.code == code).first()


def _cadet(db, squadron_id: str, cea_id: str, *, rank="Cdt", first="Original", last="Cadet"):
    from app.models.training import Cadet

    c = Cadet(
        squadron_id=squadron_id,
        service_number=cea_id,
        rank=rank,
        first_name=first,
        last_name=last,
        created_by="test",
        updated_by="test",
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def test_duplicate_cea_id_in_file_is_not_first_row_wins(client):
    """Every occurrence of a duplicated stable ID is ambiguous; none may be committed."""
    headers = login(client, "ADMIN703")
    cea_id = f"CEADUP{uuid.uuid4().hex[:10]}"
    csv_text = HEADER + _row(cea_id, "Cdt", "First", "Version") + _row(
        cea_id, "CCPL", "Second", "Version"
    )

    preview = client.post(
        "/api/import/cea-members/preview",
        json={"csv_text": csv_text, "file_name": "duplicate.csv"},
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    occurrences = [r for r in preview.json()["rows"] if r.get("service_number") == cea_id]
    assert len(occurrences) == 2
    assert all(r.get("action") == "ERROR" for r in occurrences), (
        "Duplicate CEA IDs must not use an arbitrary first-row-wins policy"
    )

    commit = client.post(
        "/api/import/cea-members/commit",
        json={"csv_text": csv_text, "file_name": "duplicate.csv"},
        headers=headers,
    )
    assert commit.status_code in (200, 400, 409, 422), commit.text

    db = _db()
    try:
        from app.models.training import Cadet

        live = db.query(Cadet).filter(
            Cadet.service_number == cea_id,
            Cadet.is_archived == False,  # noqa: E712
        ).all()
        assert live == [], "A duplicated stable ID in one file must not create/update a Cadet"
    finally:
        db.close()


def test_missing_family_name_is_malformed_and_not_committed(client):
    """The CEA member shape used by TMS requires Id/Rank/Name/Family name identity fields."""
    headers = login(client, "ADMIN703")
    cea_id = f"CEAMAL{uuid.uuid4().hex[:10]}"
    csv_text = HEADER + _row(cea_id, "Cdt", "NoFamily", "")

    preview = client.post(
        "/api/import/cea-members/preview",
        json={"csv_text": csv_text, "file_name": "malformed.csv"},
        headers=headers,
    )
    assert preview.status_code == 200, preview.text
    row = next(r for r in preview.json()["rows"] if r.get("service_number") == cea_id)
    assert row["action"] == "ERROR", "Malformed required CEA row must be classified ERROR"

    commit = client.post(
        "/api/import/cea-members/commit",
        json={"csv_text": csv_text, "file_name": "malformed.csv"},
        headers=headers,
    )
    assert commit.status_code in (200, 400, 409, 422), commit.text

    db = _db()
    try:
        from app.models.training import Cadet

        assert db.query(Cadet).filter(
            Cadet.service_number == cea_id,
            Cadet.is_archived == False,  # noqa: E712
        ).first() is None
    finally:
        db.close()


def test_existing_cea_id_in_another_squadron_never_creates_duplicate_identity(client):
    """Cross-squadron ownership may require a transfer/conflict workflow, but duplicate identity is never valid."""
    db = _db()
    try:
        sq704 = _sq(db, "704")
        if sq704 is None:
            pytest.skip("704 squadron is not seeded")
        cea_id = f"CEAXSQ{uuid.uuid4().hex[:10]}"
        original = _cadet(db, sq704.id, cea_id, first="Before", last="TransferGuard")
        original_id = original.id
    finally:
        db.close()

    headers = login(client, "ADMIN703")
    csv_text = HEADER + _row(cea_id, "CCPL", "After", "TransferGuard")
    response = client.post(
        "/api/import/cea-members/commit",
        json={"csv_text": csv_text, "file_name": "cross-squadron.csv"},
        headers=headers,
    )
    assert response.status_code in (200, 403, 409, 422), response.text

    db = _db()
    try:
        from app.models.training import Cadet

        live = db.query(Cadet).filter(
            Cadet.service_number == cea_id,
            Cadet.is_archived == False,  # noqa: E712
        ).all()
        assert len(live) == 1, (
            "CEA Id is the stable identity: importing it from another squadron must "
            "use a sanctioned transfer/conflict path, never create a second live Cadet"
        )
        assert live[0].id == original_id, "Stable identity must remain the existing Cadet row"
    finally:
        db.close()


def test_partial_import_does_not_archive_members_missing_from_file(client):
    """A later CEA file is an upsert set, not an authoritative deletion snapshot."""
    db = _db()
    try:
        sq703 = _sq(db, "703")
        if sq703 is None:
            pytest.skip("703 squadron is not seeded")
        keep_id = f"CEAKEEP{uuid.uuid4().hex[:10]}"
        update_id = f"CEAUP{uuid.uuid4().hex[:10]}"
        keep = _cadet(db, sq703.id, keep_id, first="Keep", last="Present")
        update = _cadet(db, sq703.id, update_id, first="Before", last="Update")
        keep_db_id, update_db_id = keep.id, update.id
    finally:
        db.close()

    response = client.post(
        "/api/import/cea-members/commit",
        json={
            "csv_text": HEADER + _row(update_id, "CCPL", "After", "Update"),
            "file_name": "partial.csv",
        },
        headers=login(client, "ADMIN703"),
    )
    assert response.status_code == 200, response.text

    db = _db()
    try:
        from app.models.training import Cadet

        keep = db.get(Cadet, keep_db_id)
        update = db.get(Cadet, update_db_id)
        assert keep is not None and not keep.is_archived
        assert update is not None and not update.is_archived
        assert update.first_name == "After"
    finally:
        db.close()


def test_cea_upsert_preserves_existing_class_membership(client):
    """Rank/name refresh updates the Cadet row in place and preserves memberships/history links."""
    from app.models import CadetClassMembership
    from app.models.training import TrainingClass

    db = _db()
    try:
        sq703 = _sq(db, "703")
        if sq703 is None:
            pytest.skip("703 squadron is not seeded")
        tc = db.query(TrainingClass).filter(
            TrainingClass.squadron_id == sq703.id,
            TrainingClass.is_archived == False,  # noqa: E712
        ).first()
        if tc is None:
            pytest.skip("703 has no training class")
        cea_id = f"CEAMEM{uuid.uuid4().hex[:10]}"
        cadet = _cadet(db, sq703.id, cea_id, rank="Cdt", first="Before", last="Membership")
        membership = CadetClassMembership(
            cadet_id=cadet.id,
            training_class_id=tc.id,
            start_date=str(date.today()),
            active_status=True,
            source="manual",
            created_by="test",
            updated_by="test",
        )
        db.add(membership)
        db.commit()
        cadet_id, membership_id = cadet.id, membership.id
    finally:
        db.close()

    response = client.post(
        "/api/import/cea-members/commit",
        json={
            "csv_text": HEADER + _row(cea_id, "CCPL", "After", "Membership"),
            "file_name": "refresh.csv",
        },
        headers=login(client, "ADMIN703"),
    )
    assert response.status_code == 200, response.text

    db = _db()
    try:
        from app.models.training import Cadet

        cadet = db.get(Cadet, cadet_id)
        membership = db.get(CadetClassMembership, membership_id)
        assert cadet is not None and cadet.first_name == "After" and cadet.rank == "CCPL"
        assert membership is not None and membership.active_status and not membership.is_archived
    finally:
        db.close()
