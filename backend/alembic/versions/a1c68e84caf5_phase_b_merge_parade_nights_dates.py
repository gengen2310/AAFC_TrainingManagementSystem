"""phase_b_merge_parade_nights_dates

Revision ID: a1c68e84caf5
Revises: d5f81a3c9e27
Create Date: 2026-08-29

Collapse parade_dates into parade_nights.
PRECONDITION: run scripts/phase_b_audit.py first and confirm exit 0.
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = 'a1c68e84caf5'
down_revision = 'd5f81a3c9e27'
branch_labels = None
depends_on = None


def _abort_if_blockers(conn):
    """Raise only if linked parade_dates have NULL planning_year_id (cannot be auto-resolved).

    Orphan nights (no linked parade_date) are handled by step 2b — they get a
    planning_year assigned by calendar year, with auto-creation if none exists.
    """
    null_year = conn.execute(sa.text("""
        SELECT COUNT(*) FROM parade_nights pn
        JOIN parade_dates pd ON pd.parade_night_id = pn.id
        WHERE pd.planning_year_id IS NULL
    """)).scalar()
    if null_year:
        raise RuntimeError(
            f"Phase B migration blocked: {null_year} linked parade_date row(s) have NULL "
            f"planning_year_id. Run scripts/phase_b_audit.py and resolve all blockers first."
        )


def upgrade():
    import uuid as _uuid_mod

    conn = op.get_bind()
    _abort_if_blockers(conn)

    # ── 1. Add new columns to parade_nights (nullable first for backfill) ──
    with op.batch_alter_table("parade_nights") as batch:
        batch.add_column(sa.Column("planning_year_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("week_number", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("is_active", sa.Boolean(), nullable=True, server_default="1"))
        batch.add_column(sa.Column("cancellation_reason", sa.String(), nullable=True))

    # ── 2. Backfill from linked parade_dates ──
    conn.execute(sa.text("""
        UPDATE parade_nights
        SET planning_year_id = (
            SELECT pd.planning_year_id FROM parade_dates pd
            WHERE pd.parade_night_id = parade_nights.id LIMIT 1
        ),
        week_number = (
            SELECT pd.week_number FROM parade_dates pd
            WHERE pd.parade_night_id = parade_nights.id LIMIT 1
        ),
        is_active = COALESCE((
            SELECT pd.is_active FROM parade_dates pd
            WHERE pd.parade_night_id = parade_nights.id LIMIT 1
        ), TRUE),
        cancellation_reason = (
            SELECT pd.cancellation_reason FROM parade_dates pd
            WHERE pd.parade_night_id = parade_nights.id LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1 FROM parade_dates pd WHERE pd.parade_night_id = parade_nights.id
        )
    """))

    # ── 2b. Assign planning_year_id to orphan nights (no linked parade_date) ──
    # TMS-only parade nights (created before Planning Workspace or never opened there)
    # have no parade_date link. Assign planning_year_id by calendar year, creating
    # a planning_year row if none exists for that squadron+year combination.
    # SUBSTR(CAST(date AS TEXT), 1, 4) extracts the 4-digit year from both SQLite
    # TEXT dates and PostgreSQL DATE types (both format as 'YYYY-MM-DD' when cast).
    orphan_groups = conn.execute(sa.text("""
        SELECT DISTINCT pn.squadron_id, pn.wing_id,
               CAST(SUBSTR(CAST(pn.date AS TEXT), 1, 4) AS INTEGER) AS parade_year
        FROM parade_nights pn
        WHERE NOT EXISTS (SELECT 1 FROM parade_dates pd WHERE pd.parade_night_id = pn.id)
          AND pn.planning_year_id IS NULL
    """)).fetchall()

    for grp in orphan_groups:
        sq_id, wg_id, yr = grp.squadron_id, grp.wing_id, grp.parade_year
        # Prefer the active planning year; fall back to any year for this (unit, year) pair.
        py_row = conn.execute(sa.text("""
            SELECT id FROM planning_years
            WHERE unit_id = :uid AND year = :yr
            ORDER BY active_status DESC, created_at DESC
            LIMIT 1
        """), {"uid": sq_id, "yr": yr}).fetchone()
        if py_row is None:
            py_id = str(_uuid_mod.uuid4())
            conn.execute(sa.text("""
                INSERT INTO planning_years
                    (id, unit_id, wing_id, year, name, active_status, version,
                     created_at, updated_at)
                VALUES (:id, :uid, :wid, :yr, :name, TRUE, 0,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """), {
                "id": py_id, "uid": sq_id, "wid": wg_id,
                "yr": yr, "name": f"{yr} Training Year",
            })
        else:
            py_id = py_row.id
        conn.execute(sa.text("""
            UPDATE parade_nights
            SET planning_year_id = :py_id
            WHERE squadron_id = :sq_id
              AND CAST(SUBSTR(CAST(date AS TEXT), 1, 4) AS INTEGER) = :yr
              AND NOT EXISTS (
                  SELECT 1 FROM parade_dates pd WHERE pd.parade_night_id = parade_nights.id
              )
              AND planning_year_id IS NULL
        """), {"py_id": py_id, "sq_id": sq_id, "yr": yr})

    # ── 3. Drop training_year; make planning_year_id NOT NULL ──
    with op.batch_alter_table("parade_nights") as batch:
        batch.drop_index("ix_parade_nights_training_year")
        batch.drop_column("training_year")
        batch.alter_column("planning_year_id", nullable=False)
        batch.alter_column("is_active", nullable=False, server_default=None)
        batch.create_foreign_key(
            "fk_parade_nights_planning_year_id",
            "planning_years", ["planning_year_id"], ["id"]
        )

    # ── 3b. Normalize parade_type: 'standard' → 'normal' for pre-existing nights ──
    conn.execute(sa.text(
        "UPDATE parade_nights SET parade_type = 'normal' WHERE parade_type = 'standard'"
    ))

    # ── 3c. Create ParadeNight rows for parade_dates with no linked parade night ──
    # The parade_dates.parade_date column holds the ISO date string.
    orphan_dates = conn.execute(sa.text("""
        SELECT pd.id, pd.parade_date, pd.unit_id, pd.planning_year_id, pd.parade_type,
               pd.week_number, pd.is_active, pd.notes
        FROM parade_dates pd
        WHERE pd.parade_night_id IS NULL
    """)).fetchall()

    for row in orphan_dates:
        # Only create a night if unit_id matches a squadron (wing/national years skipped).
        sq_check = conn.execute(sa.text(
            "SELECT id, wing_id FROM squadrons WHERE id = :uid"
        ), {"uid": row.unit_id}).fetchone()
        if sq_check is None:
            print(
                f"[WARN] phase_b migration: orphan parade_date {row.id} has unit_id "
                f"{row.unit_id} not found in squadrons — skipping (wing/national year edge case)"
            )
            continue
        night_id = str(_uuid_mod.uuid4())
        conn.execute(sa.text("""
            INSERT INTO parade_nights
                (id, date, squadron_id, wing_id, planning_year_id, parade_type,
                 week_number, is_active, notes, is_archived, created_at, updated_at)
            VALUES (:nid, :date, :sqn_id, :wing_id, :py_id,
                    COALESCE(:ptype, 'normal'),
                    :wknum, COALESCE(:active, TRUE), :notes, FALSE,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """), {
            "nid": night_id, "date": row.parade_date,
            "sqn_id": sq_check.id, "wing_id": sq_check.wing_id,
            "py_id": row.planning_year_id,
            "ptype": row.parade_type, "wknum": row.week_number,
            "active": row.is_active, "notes": row.notes,
        })
        conn.execute(sa.text(
            "UPDATE parade_dates SET parade_night_id = :nid WHERE id = :did"
        ), {"nid": night_id, "did": row.id})

    # ── 4. planning_notices: rename parade_date_id → parade_night_id; drop planning_year_id ──
    conn.execute(sa.text("""
        UPDATE planning_notices
        SET parade_date_id = (
            SELECT pd.parade_night_id FROM parade_dates pd
            WHERE pd.id = planning_notices.parade_date_id LIMIT 1
        )
        WHERE parade_date_id IS NOT NULL
    """))
    # Drop index on column being removed before batch rebuild (SQLite batch mode
    # does not always reliably skip recreating indexes on dropped columns).
    op.drop_index("ix_planning_notices_planning_year_id", table_name="planning_notices")
    # C1: On PostgreSQL, unnamed FKs created inline get auto-generated names. Drop them
    # before the batch rename so they are not left pointing at _parade_dates_deprecated.
    if conn.dialect.name == "postgresql":
        conn.execute(sa.text(
            "ALTER TABLE planning_notices DROP CONSTRAINT IF EXISTS "
            "planning_notices_parade_date_id_fkey"
        ))
        conn.execute(sa.text(
            "ALTER TABLE planning_conflicts DROP CONSTRAINT IF EXISTS "
            "planning_conflicts_parade_date_id_fkey"
        ))
        conn.execute(sa.text(
            "ALTER TABLE anchor_prep_plans DROP CONSTRAINT IF EXISTS "
            "anchor_prep_plans_planned_parade_date_id_fkey"
        ))
    with op.batch_alter_table("planning_notices") as batch:
        batch.alter_column("parade_date_id", new_column_name="parade_night_id", nullable=False)
        batch.drop_column("planning_year_id")
        batch.create_foreign_key(
            "fk_planning_notices_parade_night_id",
            "parade_nights", ["parade_night_id"], ["id"]
        )

    # ── 5. planning_conflicts: rename parade_date_id → parade_night_id ──
    conn.execute(sa.text("""
        UPDATE planning_conflicts
        SET parade_date_id = (
            SELECT pd.parade_night_id FROM parade_dates pd
            WHERE pd.id = planning_conflicts.parade_date_id LIMIT 1
        )
        WHERE parade_date_id IS NOT NULL
    """))
    with op.batch_alter_table("planning_conflicts") as batch:
        batch.alter_column("parade_date_id", new_column_name="parade_night_id")
        batch.create_foreign_key(
            "fk_planning_conflicts_parade_night_id",
            "parade_nights", ["parade_night_id"], ["id"]
        )

    # ── 6. anchor_prep_plans: rename planned_parade_date_id → planned_parade_night_id ──
    conn.execute(sa.text("""
        UPDATE anchor_prep_plans
        SET planned_parade_date_id = (
            SELECT pd.parade_night_id FROM parade_dates pd
            WHERE pd.id = anchor_prep_plans.planned_parade_date_id LIMIT 1
        )
        WHERE planned_parade_date_id IS NOT NULL
    """))
    with op.batch_alter_table("anchor_prep_plans") as batch:
        batch.alter_column("planned_parade_date_id", new_column_name="planned_parade_night_id")
        batch.create_foreign_key(
            "fk_anchor_prep_plans_planned_parade_night_id",
            "parade_nights", ["planned_parade_night_id"], ["id"]
        )

    # ── 7. Rename parade_dates → _parade_dates_deprecated ──
    op.rename_table("parade_dates", "_parade_dates_deprecated")


def downgrade():
    # NOTE: downgrade is a development-only escape hatch — schema structure is restored
    # but FK data in planning_notices/planning_conflicts/anchor_prep_plans will point to
    # parade_night IDs, not parade_date IDs. Data integrity is not recovered.
    op.rename_table("_parade_dates_deprecated", "parade_dates")

    # Restore anchor_prep_plans (drop new FK, rename column back)
    with op.batch_alter_table("anchor_prep_plans") as batch:
        batch.drop_constraint("fk_anchor_prep_plans_planned_parade_night_id", type_="foreignkey")
        batch.alter_column("planned_parade_night_id", new_column_name="planned_parade_date_id")

    # Restore planning_conflicts (drop new FK, rename column back)
    with op.batch_alter_table("planning_conflicts") as batch:
        batch.drop_constraint("fk_planning_conflicts_parade_night_id", type_="foreignkey")
        batch.alter_column("parade_night_id", new_column_name="parade_date_id")

    # Restore planning_notices (drop new FK, rename column back, re-add planning_year_id)
    with op.batch_alter_table("planning_notices") as batch:
        batch.drop_constraint("fk_planning_notices_parade_night_id", type_="foreignkey")
        batch.alter_column("parade_night_id", new_column_name="parade_date_id")
        batch.add_column(sa.Column("planning_year_id", sa.String(), nullable=True))

    # Restore parade_nights (add back training_year, drop new columns)
    with op.batch_alter_table("parade_nights") as batch:
        batch.drop_constraint("fk_parade_nights_planning_year_id", type_="foreignkey")
        batch.add_column(sa.Column("training_year", sa.Integer(), nullable=True))
        batch.drop_column("planning_year_id")
        batch.drop_column("week_number")
        batch.drop_column("is_active")
        batch.drop_column("cancellation_reason")
