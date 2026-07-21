"""v39 — canonical subject_area_tags table for user-creatable facilitator tags

Revision ID: e7a9c2f4b8d1
Revises: d5e6f7a8b9c0
Create Date: 2026-07-21
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'd5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'subject_area_tags',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('squadron_id', sa.String(36), nullable=True),
        sa.Column('wing_id', sa.String(36), nullable=True),
        sa.Column('scope', sa.String(20), nullable=False, server_default='squadron'),
        sa.Column('display_name', sa.String(80), nullable=False),
        sa.Column('normalised_name', sa.String(80), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_subject_area_tags_squadron_id', 'subject_area_tags', ['squadron_id'])
    op.create_index('ix_subject_area_tags_normalised_name', 'subject_area_tags', ['normalised_name'])
    op.create_index('ix_subject_area_tags_wing_id', 'subject_area_tags', ['wing_id'])


def downgrade():
    op.drop_index('ix_subject_area_tags_wing_id', table_name='subject_area_tags')
    op.drop_index('ix_subject_area_tags_normalised_name', table_name='subject_area_tags')
    op.drop_index('ix_subject_area_tags_squadron_id', table_name='subject_area_tags')
    op.drop_table('subject_area_tags')
