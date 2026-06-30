"""v18 Curriculum identifier — adds identifier and part_number to curriculum_items.

Identifier is the globally unique lesson/mission key (e.g. "ORI-M01-01(2)").
Multiple rows can share the same code (Module_Code) for different parts;
uniqueness is enforced at application level on identifier, not on code.

Revision ID: f1a2b3c4d5e6
Revises: e7a9c2f4b8d1
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa

revision = 'f1a2b3c4d5e6'
down_revision = 'e7a9c2f4b8d1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('curriculum_items',
                  sa.Column('identifier', sa.String(80), nullable=True))
    op.add_column('curriculum_items',
                  sa.Column('part_number', sa.Integer, nullable=True, server_default='1'))
    op.create_index('ix_curriculum_items_identifier', 'curriculum_items', ['identifier'])


def downgrade():
    op.drop_index('ix_curriculum_items_identifier', table_name='curriculum_items')
    op.drop_column('curriculum_items', 'identifier')
    op.drop_column('curriculum_items', 'part_number')
