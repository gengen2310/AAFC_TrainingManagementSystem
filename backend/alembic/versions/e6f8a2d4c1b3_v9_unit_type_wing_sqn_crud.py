"""v9 unit_type on Squadron and Wing/Squadron CRUD support

Adds:
  - squadrons.unit_type  — standard_squadron | specialist_squadron |
                           specialist_flight | support_unit
  - curriculum_items.owning_wing_id — explicit wing FK for wing-owned curriculum

Revision ID: e6f8a2d4c1b3
Revises: c4d8e1f3a0b2
Create Date: 2026-06-27
"""
from alembic import op
import sqlalchemy as sa

revision = 'e6f8a2d4c1b3'
down_revision = 'c4d8e1f3a0b2'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('squadrons',
                  sa.Column('unit_type', sa.String(40), nullable=False,
                            server_default='standard_squadron'))
    op.create_index('ix_squadrons_unit_type', 'squadrons', ['unit_type'])


def downgrade():
    op.drop_index('ix_squadrons_unit_type', table_name='squadrons')
    op.drop_column('squadrons', 'unit_type')
