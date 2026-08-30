"""v53 drop inert planning tables

Drop planning_locations and scheduled_sessions — both are fully superseded
(TrainingArea and TrainingSession are canonical) and have received no new writes
since the canonical-model decision (docs/next-stage/04_canonical_data_model.md).

Also converts planning_conflicts.scheduled_session_id from a FK to a plain
nullable string — the column was storing TrainingSession IDs but declared with
ForeignKey("scheduled_sessions.id"), a semantic bug that SQLite silently ignored.

Revision ID: a1b2c3d4e5f6
Revises: c3cb76ef2cf7
Create Date: 2026-08-14
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "9997f6527ef4"
down_revision = "c3cb76ef2cf7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Remove location_id FK from scheduled_sessions → planning_locations
    with op.batch_alter_table("scheduled_sessions", schema=None) as batch_op:
        batch_op.drop_column("location_id")

    # 2. Drop planning_locations (no remaining FKs)
    op.drop_table("planning_locations")

    # 3. Convert planning_conflicts.scheduled_session_id from FK to plain string.
    #    On SQLite: batch_alter_table recreates the table, dropping all FKs implicitly.
    #    On PostgreSQL: the FK constraint must be dropped explicitly; batch_alter_table
    #    only alters nullability and does NOT remove FK constraints in Postgres.
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(sa.text(
            "ALTER TABLE planning_conflicts "
            "DROP CONSTRAINT IF EXISTS planning_conflicts_scheduled_session_id_fkey"
        ))
    else:
        with op.batch_alter_table("planning_conflicts", schema=None) as batch_op:
            batch_op.alter_column(
                "scheduled_session_id",
                existing_type=sa.String(length=36),
                nullable=True,
            )

    # 4. Drop scheduled_sessions (fully inert; no live queries)
    op.drop_table("scheduled_sessions")


def downgrade() -> None:
    op.create_table(
        "planning_locations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("unit_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("location_type", sa.String(length=30), server_default="indoor", nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("active_status", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["unit_id"], ["squadrons.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_planning_locations_unit_id", "planning_locations", ["unit_id"])

    op.create_table(
        "scheduled_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("parade_date_id", sa.String(length=36), nullable=False),
        sa.Column("unit_id", sa.String(length=36), nullable=False),
        sa.Column("cadet_group", sa.String(length=30), nullable=False),
        sa.Column("session_number", sa.Integer(), nullable=False),
        sa.Column("curriculum_id", sa.String(length=36), nullable=True),
        sa.Column("activity_title", sa.String(length=200), nullable=True),
        sa.Column("facilitator_id", sa.String(length=36), nullable=True),
        sa.Column("location_id", sa.String(length=36), nullable=True),
        sa.Column("is_combined", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("combined_groups", sa.JSON(), nullable=True),
        sa.Column("override_conflict", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="draft", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=True),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
        sa.Column("version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_archived", sa.Boolean(), server_default=sa.false(), nullable=False),
        # v26 added archived_at to this table. A downgrade must restore the
        # shape the table had immediately before v53 ran, not the shape v11
        # created -- otherwise v26's own downgrade (DROP COLUMN archived_at)
        # fails against a table that never had the column.
        sa.Column("archived_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["location_id"], ["planning_locations.id"]),
        sa.ForeignKeyConstraint(["parade_date_id"], ["parade_dates.id"]),
        sa.ForeignKeyConstraint(["unit_id"], ["squadrons.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scheduled_sessions_parade_date_id", "scheduled_sessions", ["parade_date_id"])
    op.create_index("ix_scheduled_sessions_unit_id", "scheduled_sessions", ["unit_id"])
