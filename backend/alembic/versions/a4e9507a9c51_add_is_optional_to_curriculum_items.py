"""v64 — add is_optional to curriculum_items (K-007)

Revision ID: a4e9507a9c51
Revises: b7e3f9c24a81
Create Date: 2026-08-30

Per-item optional flag for CurriculumItem. Existing rows default to False
(mandatory) so no data backfill is required.

Uses batch_alter_table for SQLite compatibility.
"""
from alembic import op
import sqlalchemy as sa

revision = 'a4e9507a9c51'
down_revision = 'b7e3f9c24a81'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('curriculum_items') as batch_op:
        batch_op.add_column(
            sa.Column(
                'is_optional',
                sa.Boolean(),
                nullable=False,
                # sa.false(), not sa.text('0'). PostgreSQL rejects an integer
                # default on a boolean column outright -- "column is_optional is
                # of type boolean but default expression is of type integer" --
                # and the backend crash-looped on migrate against staging.
                # SQLite accepts 0, which is why the test suite never saw it:
                # the suite builds its schema with create_all on SQLite and does
                # not run this chain at all. sa.false() renders correctly on
                # both. Verified with scripts/rehearse_migrations.py, which
                # applies every migration to real PostgreSQL.
                server_default=sa.false(),
            )
        )


def downgrade():
    with op.batch_alter_table('curriculum_items') as batch_op:
        batch_op.drop_column('is_optional')
