"""v32 facilitator leave table

Revision ID: t5u6v7w8x9y0
Revises: s4t5u6v7w8x9
Create Date: 2026-07-10

"""
from alembic import op
import sqlalchemy as sa

revision = 't5u6v7w8x9y0'
down_revision = 's4t5u6v7w8x9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'planning_facilitator_leave',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('facilitator_id', sa.String(36), nullable=False),
        sa.Column('planning_year_id', sa.String(36), nullable=True),
        sa.Column('start_date', sa.String(10), nullable=False),
        sa.Column('end_date', sa.String(10), nullable=False),
        sa.Column('reason', sa.String(200), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('is_archived', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime, nullable=True),
        sa.Column('updated_at', sa.DateTime, nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['facilitator_id'], ['facilitators.id']),
        sa.ForeignKeyConstraint(['planning_year_id'], ['planning_years.id']),
    )
    op.create_index('ix_planning_facilitator_leave_facilitator_id',
                    'planning_facilitator_leave', ['facilitator_id'])
    op.create_index('ix_planning_facilitator_leave_planning_year_id',
                    'planning_facilitator_leave', ['planning_year_id'])


def downgrade() -> None:
    op.drop_index('ix_planning_facilitator_leave_planning_year_id',
                  table_name='planning_facilitator_leave')
    op.drop_index('ix_planning_facilitator_leave_facilitator_id',
                  table_name='planning_facilitator_leave')
    op.drop_table('planning_facilitator_leave')
