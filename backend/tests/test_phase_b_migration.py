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
                unit_id VARCHAR,
                planning_year_id VARCHAR,
                parade_date VARCHAR(10),
                parade_type VARCHAR,
                week_number INTEGER,
                is_active INTEGER NOT NULL DEFAULT 1,
                notes TEXT,
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

        # ── Seed pre-migration rows ──
        # SQLite does not enforce FK constraints (no PRAGMA foreign_keys=ON), so we
        # can insert minimal rows with fake FKs to avoid the full org hierarchy.
        # We DO need a real squadron row because migration step 3c queries it.
        conn.execute(text("""
            INSERT INTO wings
                (id, national_id, code, name, short_name, active_status, is_archived,
                 created_at, updated_at)
            VALUES ('wing-test-001', 'nat-test-001', 'TESTWG', 'Test Wing', 'TESTWG',
                    1, 0, datetime('now'), datetime('now'))
        """))
        conn.execute(text("""
            INSERT INTO squadrons
                (id, wing_id, code, name, short_name, unit_type, default_session_count,
                 active_status, is_archived, created_at, updated_at)
            VALUES ('sqn-test-001', 'wing-test-001', 'TEST001', 'Test Squadron', 'TST',
                    'standard_squadron', 3, 1, 0, datetime('now'), datetime('now'))
        """))
        conn.execute(text("""
            INSERT INTO planning_years
                (id, unit_id, year, name, active_status, version,
                 created_at, updated_at)
            VALUES ('py-test-001', 'sqn-test-001', 9001, 'Test Year 9001',
                    1, 0, datetime('now'), datetime('now'))
        """))

        # A parade_night that has a linked parade_date (normal case)
        conn.execute(text("""
            INSERT INTO parade_nights (id, squadron_id, wing_id, training_year, date,
                                       parade_type, version, is_archived)
            VALUES ('pn-linked-001', 'sqn-test-001', 'wing-test-001', 9001, '9001-09-05',
                    'normal', 0, 0)
        """))
        conn.execute(text("""
            INSERT INTO parade_dates (id, parade_night_id, unit_id, planning_year_id,
                                      parade_date, parade_type, week_number, is_active)
            VALUES ('pd-linked-001', 'pn-linked-001', 'sqn-test-001', 'py-test-001',
                    '9001-09-05', 'normal', 1, 1)
        """))

        # An orphan parade_date (parade_night_id IS NULL) — step 3c must create a night
        conn.execute(text("""
            INSERT INTO parade_dates (id, parade_night_id, unit_id, planning_year_id,
                                      parade_date, parade_type, week_number, is_active)
            VALUES ('pd-orphan-001', NULL, 'sqn-test-001', 'py-test-001',
                    '9001-09-12', 'normal', 2, 1)
        """))

        # A planning_notice referencing pd-linked-001 (so FK rename is exercised)
        conn.execute(text("""
            INSERT INTO planning_notices (id, parade_date_id, notice_text, is_archived, version)
            VALUES ('notice-001', 'pd-linked-001', 'Test notice', 0, 0)
        """))

    # Enable FK enforcement in SQLite so FK ordering bugs (like the PostgreSQL
    # parade_date_id → parade_night_id UPDATE ordering) are caught locally.
    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys = ON"))

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

    command.upgrade(cfg, "a1c68e84caf5")

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

    # ── Verify backfill results ──
    with engine.connect() as conn:
        # 1. Linked night got planning_year_id from its parade_date
        row = conn.execute(text(
            "SELECT planning_year_id FROM parade_nights WHERE id = 'pn-linked-001'"
        )).fetchone()
        assert row is not None, "pn-linked-001 must still exist"
        assert row[0] == "py-test-001", "linked night must have planning_year_id backfilled"

        # 2. Orphan parade_date got a new parade_night row created for it
        orphan_night = conn.execute(text("""
            SELECT pn.id, pn.planning_year_id, pn.date
            FROM parade_nights pn
            WHERE pn.date = '9001-09-12' AND pn.id != 'pn-linked-001'
        """)).fetchone()
        assert orphan_night is not None, (
            "A new parade_night must have been created for the orphan parade_date"
        )
        assert orphan_night[1] == "py-test-001", (
            "The new night must have planning_year_id from the orphan parade_date"
        )
        # The orphan parade_date must now point at the new night
        pd_link = conn.execute(text(
            "SELECT parade_night_id FROM _parade_dates_deprecated WHERE id = 'pd-orphan-001'"
        )).fetchone()
        assert pd_link is not None and pd_link[0] == orphan_night[0], (
            "orphan parade_date must now link to the newly created night"
        )

        # 3. PlanningNotice parade_night_id points to a parade_nights.id
        notice = conn.execute(text(
            "SELECT parade_night_id FROM planning_notices WHERE id = 'notice-001'"
        )).fetchone()
        assert notice is not None, "notice-001 must survive the migration"
        # The notice parade_night_id must point to the linked parade_night (pn-linked-001)
        assert notice[0] == "pn-linked-001", (
            "planning_notice parade_night_id must point to parade_nights.id after rename"
        )

        # 4. Verify planning_notices.parade_night_id value is a real parade_nights.id
        # (data-level FK integrity check — SQLite PRAGMA foreign_key_list may not
        # reflect named batch-mode FKs, so we validate referential integrity directly)
        ref_night = conn.execute(text(
            "SELECT id FROM parade_nights WHERE id = 'pn-linked-001'"
        )).fetchone()
        assert ref_night is not None, (
            "pn-linked-001 must exist in parade_nights so notice FK is satisfied"
        )
        # Verify the notice's parade_night_id matches an actual parade_nights row
        notice_ref = conn.execute(text("""
            SELECT pn.id FROM planning_notices n
            JOIN parade_nights pn ON pn.id = n.parade_night_id
            WHERE n.id = 'notice-001'
        """)).fetchone()
        assert notice_ref is not None, (
            "planning_notices.parade_night_id must join successfully to parade_nights"
        )


def test_phase_b_step2b_orphan_night_uses_existing_year(isolated_db):
    """Step 2b: an orphan parade night gets the planning_year_id of the existing year
    whose year field matches the night's calendar year (date '9001-xx-xx' → year 9001).

    The isolated_db fixture already contains py-test-001 for year 9001, so step 2b
    must find it and assign it — no new planning_year row should be created.
    """
    engine, cfg = isolated_db
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO parade_nights (id, squadron_id, wing_id, training_year, date,
                                       parade_type, version, is_archived)
            VALUES ('pn-orphan-existing', 'sqn-test-001', 'wing-test-001', 9001,
                    '9001-10-10', 'normal', 0, 0)
        """))

    command.upgrade(cfg, "a1c68e84caf5")

    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT planning_year_id FROM parade_nights WHERE id = 'pn-orphan-existing'"
        )).fetchone()
        assert row is not None, "pn-orphan-existing must survive the migration"
        assert row[0] == "py-test-001", (
            "orphan night dated in year 9001 must receive the existing py-test-001"
        )
        # The existing planning_year must not be duplicated
        count = conn.execute(text(
            "SELECT COUNT(*) FROM planning_years WHERE unit_id = 'sqn-test-001' AND year = 9001"
        )).scalar()
        assert count == 1, "step 2b must reuse the existing planning_year, not create a duplicate"


def test_phase_b_step2b_orphan_night_creates_missing_year(isolated_db):
    """Step 2b: an orphan parade night whose calendar year has no planning_year row
    triggers auto-creation of a new planning_year for that (squadron, year) pair.
    """
    engine, cfg = isolated_db
    # Year 8999 has no planning_year in the fixture
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO parade_nights (id, squadron_id, wing_id, training_year, date,
                                       parade_type, version, is_archived)
            VALUES ('pn-orphan-new-year', 'sqn-test-001', 'wing-test-001', 8999,
                    '8999-05-15', 'normal', 0, 0)
        """))

    command.upgrade(cfg, "a1c68e84caf5")

    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT planning_year_id FROM parade_nights WHERE id = 'pn-orphan-new-year'"
        )).fetchone()
        assert row is not None, "pn-orphan-new-year must survive the migration"
        assert row[0] is not None, "orphan night must have planning_year_id set after step 2b"
        # The auto-created year must exist and belong to the right squadron+year
        py = conn.execute(text(
            "SELECT unit_id, year, name FROM planning_years WHERE id = :pid"
        ), {"pid": row[0]}).fetchone()
        assert py is not None, "planning_year row must exist for the auto-assigned id"
        assert py[0] == "sqn-test-001", "auto-created year must belong to the correct squadron"
        assert py[1] == 8999, "auto-created year must have the correct calendar year"
        assert "8999" in py[2], "auto-created year name must include the year number"


def test_phase_b_aborts_on_null_year_in_linked_date(isolated_db):
    """_abort_if_blockers raises RuntimeError when a linked parade_date has NULL
    planning_year_id — this cannot be auto-resolved and requires manual intervention.
    """
    engine, cfg = isolated_db
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO parade_nights (id, squadron_id, wing_id, training_year, date,
                                       parade_type, version, is_archived)
            VALUES ('pn-null-year', 'sqn-test-001', 'wing-test-001', 9001,
                    '9001-11-01', 'normal', 0, 0)
        """))
        conn.execute(text("""
            INSERT INTO parade_dates (id, parade_night_id, unit_id, planning_year_id,
                                      parade_date, parade_type, week_number, is_active)
            VALUES ('pd-null-year', 'pn-null-year', 'sqn-test-001', NULL,
                    '9001-11-01', 'normal', 5, 1)
        """))
    import pytest as _pytest
    with _pytest.raises(RuntimeError, match="Phase B migration blocked"):
        command.upgrade(cfg, "a1c68e84caf5")
