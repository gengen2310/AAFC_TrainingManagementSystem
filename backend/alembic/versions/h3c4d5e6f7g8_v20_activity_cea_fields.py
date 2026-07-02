"""v20: add CEA import fields to activities

Revision ID: h3c4d5e6f7g8
Revises: g2b3c4d5e6f7
Create Date: 2026-07-02
"""
from alembic import op
import sqlalchemy as sa

revision = 'h3c4d5e6f7g8'
down_revision = 'g2b3c4d5e6f7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('activities', sa.Column('time_start', sa.String(8), nullable=True))
    op.add_column('activities', sa.Column('time_end', sa.String(8), nullable=True))
    op.add_column('activities', sa.Column('cea_seq_nr', sa.String(30), nullable=True))
    op.create_index('ix_activities_cea_seq_nr', 'activities', ['cea_seq_nr'])


def downgrade() -> None:
    op.drop_index('ix_activities_cea_seq_nr', table_name='activities')
    op.drop_column('activities', 'cea_seq_nr')
    op.drop_column('activities', 'time_end')
    op.drop_column('activities', 'time_start')
