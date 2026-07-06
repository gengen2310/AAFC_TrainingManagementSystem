"""v23 Add location_type to curriculum_items.

Stores the recommended delivery location from the Learning Hub CSV
(e.g. INDOOR, OUTDOOR, INDOOR or OUTDOOR, INDOOR & OUTDOOR).

Revision ID: k6f7g8h9i0j1
Revises: j5e6f7g8h9i0
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa

revision = 'k6f7g8h9i0j1'
down_revision = 'j5e6f7g8h9i0'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'curriculum_items',
        sa.Column('location_type', sa.String(60), nullable=True),
    )


def downgrade():
    op.drop_column('curriculum_items', 'location_type')
