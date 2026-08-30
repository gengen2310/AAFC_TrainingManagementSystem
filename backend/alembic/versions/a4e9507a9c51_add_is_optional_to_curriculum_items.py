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
                server_default=sa.text('0'),
            )
        )


def downgrade():
    with op.batch_alter_table('curriculum_items') as batch_op:
        batch_op.drop_column('is_optional')
