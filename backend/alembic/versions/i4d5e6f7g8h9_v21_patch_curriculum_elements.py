"""v21 Patch — add missing updated_by column to curriculum_elements.

The v19 migration created curriculum_elements but omitted updated_by
that TimestampMixin expects.  This migration adds it without disturbing
any existing data or the seeded national elements.

Revision ID: i4d5e6f7g8h9
Revises: h3c4d5e6f7g8
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa

revision = 'i4d5e6f7g8h9'
down_revision = 'h3c4d5e6f7g8'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'curriculum_elements',
        sa.Column('updated_by', sa.String(36), nullable=True),
    )


def downgrade():
    op.drop_column('curriculum_elements', 'updated_by')
