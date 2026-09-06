"""v66 custom_phase_active_status

Adds active_status boolean to custom_training_phases.
Existing non-deleted phases default to active (True).

Revision ID: 62c57ff2e22f
Revises: d2e3f4a5b6c7
Create Date: 2026-09-06
"""
from alembic import op
import sqlalchemy as sa

revision = '62c57ff2e22f'
down_revision = 'd2e3f4a5b6c7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('custom_training_phases') as batch_op:
        batch_op.add_column(sa.Column('active_status', sa.Boolean(), nullable=False,
                                      server_default=sa.true()))


def downgrade():
    with op.batch_alter_table('custom_training_phases') as batch_op:
        batch_op.drop_column('active_status')
