"""v54 parade_dates.parade_night_id: add FK constraint and index

parade_dates.parade_night_id was declared as a bare String(36) with only a
comment documenting the intended FK to parade_nights.id.  Without a proper
ForeignKey() declaration SQLAlchemy's fk_dependents() helper never finds
ParadeDate rows as children of a ParadeNight, so deleting a ParadeNight
template (or any future cascade-delete logic) silently leaves dangling
string values in parade_night_id.

This migration:
  1. Nullifies any existing parade_date rows whose parade_night_id no longer
     points to a real parade_night (cleanup before constraint is applied).
  2. Adds an index on parade_dates.parade_night_id.
  3. Adds the FK constraint with ON DELETE SET NULL.

Revision ID: a3b4c5d6e7f8
Revises: 9997f6527ef4
Create Date: 2026-08-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a3b4c5d6e7f8"
down_revision = "9997f6527ef4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Nullify dangling references before adding the FK constraint.
    conn.execute(sa.text("""
        UPDATE parade_dates
        SET parade_night_id = NULL
        WHERE parade_night_id IS NOT NULL
          AND parade_night_id NOT IN (SELECT id FROM parade_nights)
    """))

    if conn.dialect.name == "postgresql":
        # PostgreSQL: add index and FK constraint directly.
        op.create_index("ix_parade_dates_parade_night_id",
                        "parade_dates", ["parade_night_id"], unique=False)
        op.create_foreign_key(
            "fk_parade_dates_parade_night_id",
            "parade_dates", "parade_nights",
            ["parade_night_id"], ["id"],
            ondelete="SET NULL",
        )
    else:
        # SQLite: batch_alter_table recreates the table with the FK declared.
        with op.batch_alter_table("parade_dates", schema=None) as batch_op:
            batch_op.create_index("ix_parade_dates_parade_night_id",
                                  ["parade_night_id"], unique=False)
            batch_op.create_foreign_key(
                "fk_parade_dates_parade_night_id",
                "parade_nights", ["parade_night_id"], ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.drop_constraint("fk_parade_dates_parade_night_id", "parade_dates",
                           type_="foreignkey")
        op.drop_index("ix_parade_dates_parade_night_id", table_name="parade_dates")
    else:
        with op.batch_alter_table("parade_dates", schema=None) as batch_op:
            batch_op.drop_constraint("fk_parade_dates_parade_night_id",
                                     type_="foreignkey")
            batch_op.drop_index("ix_parade_dates_parade_night_id")
