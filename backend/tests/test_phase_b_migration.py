# backend/tests/test_phase_b_migration.py
"""
Forward migration test for phase B: merging parade_dates into parade_nights.

Strategy: use metadata.create_all() to set up the current schema (identical to
running migrations up to d5f81a3c9e27 but avoids legacy bare-ALTER ops that
SQLite doesn't support), then stamp the revision, then run our new migration.
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

    # env.py reads settings.DATABASE_URL and overrides the alembic config URL,
    # so we must patch the settings singleton to point at our temp DB.
    from app import config as app_config
    monkeypatch.setattr(app_config.settings, "DATABASE_URL", url)

    # Create the schema using SQLAlchemy metadata (same approach as seed_all/reset_db).
    # This avoids running the full migration chain, which contains legacy bare-ALTER
    # operations that are not supported by SQLite outside batch mode.
    from app.database import Base
    from app import models  # noqa: F401 — registers all models into Base.metadata
    Base.metadata.create_all(engine)

    # Stamp the DB at d5f81a3c9e27 so Alembic tracks us as being at that revision.
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", url)
    command.stamp(alembic_cfg, "d5f81a3c9e27")

    return engine, alembic_cfg


def test_phase_b_forward(isolated_db):
    engine, cfg = isolated_db
    inspector = inspect(engine)

    # Verify pre-state: parade_nights lacks planning_year_id and has training_year
    cols_before = {c["name"] for c in inspector.get_columns("parade_nights")}
    assert "planning_year_id" not in cols_before
    assert "training_year" in cols_before

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
