"""v55 schema integrity: R5-M14 partial unique on timing overrides,
R5-L05 FK for planning_conflicts.scheduled_session_id, R5-L06 unique
constraint on session_audience (session_id, training_class_id).

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-08-16
"""
from alembic import op
import sqlalchemy as sa

revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None


def upgrade():
    # ── R5-M14: parade_night_timing_overrides ───────────────────────────────
    # The column had unique=True which blocks creating a replacement override
    # after the old one is archived (soft-deleted). Replace with a partial
    # unique index that only enforces uniqueness among non-archived rows.
    with op.batch_alter_table("parade_night_timing_overrides") as batch_op:
        # Drop the column-level unique constraint (created by SQLAlchemy as an
        # index named after the column).
        batch_op.drop_index("ix_parade_night_timing_overrides_parade_night_id")
        # Re-add a plain non-unique index so lookups stay fast.
        batch_op.create_index(
            "ix_pnto_parade_night_id",
            ["parade_night_id"],
            unique=False,
        )
    # Partial unique index must be created outside batch_alter_table because
    # batch mode rebuilds the whole table and loses dialect-specific WHERE.
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_pnto_active_per_night "
        "ON parade_night_timing_overrides (parade_night_id) "
        "WHERE is_archived = 0"
    )

    # ── R5-L06: session_audience — add unique constraint ────────────────────
    # The docstring states "A session/class pair may exist only once (unique
    # constraint)" but the constraint was missing from the schema.
    with op.batch_alter_table("session_audience") as batch_op:
        batch_op.create_unique_constraint(
            "uq_session_audience_pair",
            ["session_id", "training_class_id"],
        )

    # ── R5-L05: planning_conflicts — add FK for scheduled_session_id ────────
    # The column was String(36) with no FK. Sessions are soft-deleted (not
    # hard-deleted) so a FK won't break existing rows. ondelete=SET NULL
    # protects against any future hard-delete.
    with op.batch_alter_table("planning_conflicts") as batch_op:
        batch_op.create_foreign_key(
            "fk_planning_conflicts_session",
            "sessions",
            ["scheduled_session_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade():
    with op.batch_alter_table("planning_conflicts") as batch_op:
        batch_op.drop_constraint("fk_planning_conflicts_session", type_="foreignkey")

    with op.batch_alter_table("session_audience") as batch_op:
        batch_op.drop_constraint("uq_session_audience_pair", type_="unique")

    op.drop_index("uq_pnto_active_per_night", table_name="parade_night_timing_overrides")
    with op.batch_alter_table("parade_night_timing_overrides") as batch_op:
        batch_op.drop_index("ix_pnto_parade_night_id")
        batch_op.create_index(
            "ix_parade_night_timing_overrides_parade_night_id",
            ["parade_night_id"],
            unique=True,
        )
