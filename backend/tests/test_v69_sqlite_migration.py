"""Regression coverage for the v68 -> v69 SQLite timestamp correction.

This test deliberately runs the real Alembic path against a file-backed SQLite
DB. It protects existing local/demo databases from being stamped at v69 while
retaining the v68 VARCHAR(30) timestamp declarations.
"""
from datetime import datetime, timezone

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session


V68 = "f842d63a1d6c"
V69 = "7f61608fa538"
TABLES = ("cadet_session_outcomes", "cadet_member_import_batches")
TIMESTAMP_COLUMNS = ("created_at", "updated_at")


def _declared_types(engine, table: str) -> dict[str, str]:
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).mappings().all()
    return {row["name"]: row["type"].upper() for row in rows}


def _timestamp_text(engine, table: str, row_id: str) -> tuple[str | None, str | None]:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                f"SELECT CAST(created_at AS TEXT), CAST(updated_at AS TEXT) "
                f"FROM {table} WHERE id = :row_id"
            ),
            {"row_id": row_id},
        ).one()
    return row[0], row[1]


def test_v69_sqlite_upgrade_downgrade_reupgrade_preserves_schema_and_data(tmp_path, monkeypatch):
    db_path = tmp_path / "v69.sqlite3"
    url = f"sqlite:///{db_path}"

    # alembic/env.py reads the application settings object rather than the URL
    # set on Config, so patch the authoritative setting before each command.
    from app import config as app_config

    monkeypatch.setattr(app_config.settings, "DATABASE_URL", url)
    cfg = Config("alembic.ini")
    engine = create_engine(url, future=True)

    # 1. Build an actual v68 database.
    command.upgrade(cfg, V68)

    # 2. Verify the defect exists at v68.
    for table in TABLES:
        types = _declared_types(engine, table)
        for column in TIMESTAMP_COLUMNS:
            assert types[column] == "VARCHAR(30)"

    created = "2026-09-08 01:02:03.123456"
    updated = "2026-09-08 04:05:06.654321"
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO cadet_session_outcomes
                (id, created_at, updated_at, cadet_id, session_id, status,
                 source, version)
            VALUES
                ('outcome-v69', :created, :updated, 'cadet-v69', 'session-v69',
                 'complete', 'derived', 0)
        """), {"created": created, "updated": updated})
        conn.execute(text("""
            INSERT INTO cadet_member_import_batches
                (id, created_at, updated_at, squadron_id, imported_by,
                 row_count, new_count, update_count, unchanged_count,
                 error_count, committed)
            VALUES
                ('batch-v69', :created, :updated, 'sqn-v69', 'user-v69',
                 1, 1, 0, 0, 0, 1)
        """), {"created": created, "updated": updated})

    before = {
        "cadet_session_outcomes": _timestamp_text(engine, "cadet_session_outcomes", "outcome-v69"),
        "cadet_member_import_batches": _timestamp_text(engine, "cadet_member_import_batches", "batch-v69"),
    }

    # 3. Upgrade to v69 and verify the declared schema now matches ORM metadata.
    command.upgrade(cfg, V69)
    for table in TABLES:
        types = _declared_types(engine, table)
        for column in TIMESTAMP_COLUMNS:
            assert types[column] == "DATETIME"

    # 4. Representative timestamp data must survive byte-for-byte as text.
    assert _timestamp_text(engine, "cadet_session_outcomes", "outcome-v69") == before["cadet_session_outcomes"]
    assert _timestamp_text(engine, "cadet_member_import_batches", "batch-v69") == before["cadet_member_import_batches"]

    # Exercise the real ORM contract on the migrated schema: existing String-era
    # rows read as aware UTC datetimes, and new aware datetimes round-trip.
    from app.models.training import CadetSessionOutcome

    with Session(engine) as session:
        existing = session.get(CadetSessionOutcome, "outcome-v69")
        assert existing is not None
        assert existing.created_at == datetime(2026, 9, 8, 1, 2, 3, 123456, tzinfo=timezone.utc)
        assert existing.updated_at == datetime(2026, 9, 8, 4, 5, 6, 654321, tzinfo=timezone.utc)

        written = CadetSessionOutcome(
            id="outcome-v69-write",
            cadet_id="cadet-v69-write",
            session_id="session-v69-write",
            status="complete",
            source="derived",
            version=0,
            created_at=datetime(2026, 9, 8, 7, 8, 9, tzinfo=timezone.utc),
            updated_at=datetime(2026, 9, 8, 10, 11, 12, tzinfo=timezone.utc),
        )
        session.add(written)
        session.commit()
        session.expire_all()
        reread = session.get(CadetSessionOutcome, "outcome-v69-write")
        assert reread is not None
        assert reread.created_at == datetime(2026, 9, 8, 7, 8, 9, tzinfo=timezone.utc)
        assert reread.updated_at == datetime(2026, 9, 8, 10, 11, 12, tzinfo=timezone.utc)

    # 5/6. Downgrade and re-upgrade must both remain valid and preserve rows.
    command.downgrade(cfg, V68)
    for table in TABLES:
        types = _declared_types(engine, table)
        for column in TIMESTAMP_COLUMNS:
            assert types[column] == "VARCHAR(30)"
    assert _timestamp_text(engine, "cadet_session_outcomes", "outcome-v69") == before["cadet_session_outcomes"]
    assert _timestamp_text(engine, "cadet_member_import_batches", "batch-v69") == before["cadet_member_import_batches"]

    command.upgrade(cfg, V69)
    for table in TABLES:
        types = _declared_types(engine, table)
        for column in TIMESTAMP_COLUMNS:
            assert types[column] == "DATETIME"
    assert _timestamp_text(engine, "cadet_session_outcomes", "outcome-v69") == before["cadet_session_outcomes"]
    assert _timestamp_text(engine, "cadet_member_import_batches", "batch-v69") == before["cadet_member_import_batches"]
