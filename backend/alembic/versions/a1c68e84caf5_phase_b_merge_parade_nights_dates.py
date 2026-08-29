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
    """Raise if any orphan or unresolvable nights exist."""
    orphans = conn.execute(sa.text("""
        SELECT COUNT(*) FROM parade_nights pn
        LEFT JOIN parade_dates pd ON pd.parade_night_id = pn.id
        WHERE pd.id IS NULL AND pn.is_archived = 0
    """)).scalar()
    if orphans:
        raise RuntimeError(
            f"Phase B migration blocked: {orphans} active parade_night row(s) have no linked "
            f"parade_date. Run scripts/phase_b_audit.py and resolve all blockers first."
        )
    null_year = conn.execute(sa.text("""
        SELECT COUNT(*) FROM parade_nights pn
        JOIN parade_dates pd ON pd.parade_night_id = pn.id
        WHERE pd.planning_year_id IS NULL AND pn.is_archived = 0
    """)).scalar()
    if null_year:
        raise RuntimeError(
            f"Phase B migration blocked: {null_year} linked parade_date row(s) have NULL "
            f"planning_year_id. Run scripts/phase_b_audit.py and resolve all blockers first."
        )


def upgrade():
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
        ), 1),
        cancellation_reason = (
            SELECT pd.cancellation_reason FROM parade_dates pd
            WHERE pd.parade_night_id = parade_nights.id LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1 FROM parade_dates pd WHERE pd.parade_night_id = parade_nights.id
        )
    """))

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
    with op.batch_alter_table("planning_notices") as batch:
        batch.alter_column("parade_date_id", new_column_name="parade_night_id")
        batch.drop_column("planning_year_id")

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

    # ── 7. Rename parade_dates → _parade_dates_deprecated ──
    op.rename_table("parade_dates", "_parade_dates_deprecated")


def downgrade():
    # Restore table name
    op.rename_table("_parade_dates_deprecated", "parade_dates")

    # Restore anchor_prep_plans
    with op.batch_alter_table("anchor_prep_plans") as batch:
        batch.alter_column("planned_parade_night_id", new_column_name="planned_parade_date_id")

    # Restore planning_conflicts
    with op.batch_alter_table("planning_conflicts") as batch:
        batch.alter_column("parade_night_id", new_column_name="parade_date_id")

    # Restore planning_notices (re-add planning_year_id)
    with op.batch_alter_table("planning_notices") as batch:
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
