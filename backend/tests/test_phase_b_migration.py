# backend/tests/test_phase_b_migration.py
"""
Forward migration test for phase B: merging parade_dates into parade_nights.

Strategy: use metadata.create_all() to set up all tables from current models
(which are at the post-migration/post-T3 schema), then patch the four affected
tables and the parade_dates table back to their pre-migration state using raw DDL.
This avoids running the full migration chain (legacy bare-ALTER ops fail on SQLite)
while producing a faithful pre-migration DB state.
"""
import pytest
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect, text


@pytest.fixture
def isolated_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_phase_b.db"
    url = f"sqlite:///{db_file}"
    engine = create_engine(url)

    from app import config as app_config
    monkeypatch.setattr(app_config.settings, "DATABASE_URL", url)

    from app.database import Base
    from app import models  # noqa: F401 — registers all models into Base.metadata
    Base.metadata.create_all(engine)

    # Patch the four tables that this migration changes + parade_dates (removed from models
    # in T3) back to their pre-migration state so command.upgrade() sees the right input.
    with engine.begin() as conn:
        # parade_nights: replace planning_year_id + new cols with training_year
        conn.execute(text("DROP TABLE IF EXISTS parade_nights"))
        conn.execute(text("""
            CREATE TABLE parade_nights (
                id VARCHAR NOT NULL PRIMARY KEY,
                created_at DATETIME,
                updated_at DATETIME,
                created_by VARCHAR,
                updated_by VARCHAR,
                squadron_id VARCHAR NOT NULL,
                wing_id VARCHAR NOT NULL,
                training_year INTEGER,
                date VARCHAR(10) NOT NULL,
                term VARCHAR,
                start_time VARCHAR,
                end_time VARCHAR,
                session_count INTEGER,
                parade_type VARCHAR,
                notes TEXT,
                published_status VARCHAR,
                readiness_score REAL,
                planning_status VARCHAR,
                data_quality VARCHAR,
                closeout_status VARCHAR,
                published_by VARCHAR,
                closed_by VARCHAR,
                published_at DATETIME,
                closed_at DATETIME,
                timing_template_id VARCHAR,
                version INTEGER NOT NULL DEFAULT 0,
                is_archived INTEGER NOT NULL DEFAULT 0,
                archived_at DATETIME
            )
        """))
        conn.execute(text(
            "CREATE INDEX ix_parade_nights_training_year ON parade_nights (training_year)"
        ))

        # parade_dates: not in models post-T3; the migration renames it → deprecated
        conn.execute(text("""
            CREATE TABLE parade_dates (
                id VARCHAR NOT NULL PRIMARY KEY,
                created_at DATETIME,
                updated_at DATETIME,
                created_by VARCHAR,
                updated_by VARCHAR,
                parade_night_id VARCHAR,
                planning_year_id VARCHAR,
                week_number INTEGER,
                is_active INTEGER NOT NULL DEFAULT 1,
                cancellation_reason TEXT,
                is_archived INTEGER NOT NULL DEFAULT 0
            )
        """))

        # planning_notices: parade_date_id + planning_year_id (pre-migration names)
        conn.execute(text("DROP TABLE IF EXISTS planning_notices"))
        conn.execute(text("""
            CREATE TABLE planning_notices (
                id VARCHAR NOT NULL PRIMARY KEY,
                created_at DATETIME,
                updated_at DATETIME,
                created_by VARCHAR,
                updated_by VARCHAR,
                parade_date_id VARCHAR NOT NULL,
                planning_year_id VARCHAR,
                notice_text TEXT,
                audience VARCHAR,
                priority VARCHAR,
                is_archived INTEGER NOT NULL DEFAULT 0,
                version INTEGER NOT NULL DEFAULT 0
            )
        """))
        conn.execute(text(
            "CREATE INDEX ix_planning_notices_planning_year_id "
            "ON planning_notices (planning_year_id)"
        ))

        # planning_conflicts: parade_date_id (pre-migration name)
        conn.execute(text("DROP TABLE IF EXISTS planning_conflicts"))
        conn.execute(text("""
            CREATE TABLE planning_conflicts (
                id VARCHAR NOT NULL PRIMARY KEY,
                created_at DATETIME,
                updated_at DATETIME,
                created_by VARCHAR,
                updated_by VARCHAR,
                planning_year_id VARCHAR,
                parade_date_id VARCHAR,
                scheduled_session_id VARCHAR,
                conflict_type VARCHAR,
                severity VARCHAR,
                message TEXT,
                is_resolved INTEGER NOT NULL DEFAULT 0,
                override_reason TEXT,
                resolved_by VARCHAR
            )
        """))

        # anchor_prep_plans: planned_parade_date_id (pre-migration name)
        conn.execute(text("DROP TABLE IF EXISTS anchor_prep_plans"))
        conn.execute(text("""
            CREATE TABLE anchor_prep_plans (
                id VARCHAR NOT NULL PRIMARY KEY,
                created_at DATETIME,
                updated_at DATETIME,
                created_by VARCHAR,
                updated_by VARCHAR,
                anchor_event_id VARCHAR,
                curriculum_id VARCHAR,
                planned_parade_date_id VARCHAR,
                planned_session_number INTEGER,
                cadet_group VARCHAR,
                status VARCHAR,
                notes TEXT
            )
        """))

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", url)
    command.stamp(alembic_cfg, "d5f81a3c9e27")

    return engine, alembic_cfg


def test_phase_b_forward(isolated_db):
    engine, cfg = isolated_db
    inspector = inspect(engine)

    # Verify pre-state
    cols_before = {c["name"] for c in inspector.get_columns("parade_nights")}
    assert "planning_year_id" not in cols_before
    assert "training_year" in cols_before
    assert "parade_dates" in inspector.get_table_names()

    command.upgrade(cfg, "head")

    inspector2 = inspect(engine)
    cols = {c["name"] for c in inspector2.get_columns("parade_nights")}
    assert "planning_year_id" in cols
    assert "training_year" not in cols
    assert "week_number" in cols
    assert "is_active" in cols
    assert "cancellation_reason" in cols

    # parade_dates renamed
    tables = inspector2.get_table_names()
    assert "parade_dates" not in tables
    assert "_parade_dates_deprecated" in tables

    # PlanningNotice has parade_night_id, not parade_date_id
    notice_cols = {c["name"] for c in inspector2.get_columns("planning_notices")}
    assert "parade_night_id" in notice_cols
    assert "parade_date_id" not in notice_cols
    assert "planning_year_id" not in notice_cols

    # PlanningConflict
    conflict_cols = {c["name"] for c in inspector2.get_columns("planning_conflicts")}
    assert "parade_night_id" in conflict_cols
    assert "parade_date_id" not in conflict_cols

    # AnchorPrepPlan
    anchor_cols = {c["name"] for c in inspector2.get_columns("anchor_prep_plans")}
    assert "planned_parade_night_id" in anchor_cols
    assert "planned_parade_date_id" not in anchor_cols
