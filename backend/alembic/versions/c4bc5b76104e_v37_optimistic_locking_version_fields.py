"""v37_optimistic_locking_version_fields
Revision ID: c4bc5b76104e
Revises: x9y0z1a2b3c4
Create Date: 2026-07-16 18:05:12.349809
"""
from alembic import op
import sqlalchemy as sa

revision = 'c4bc5b76104e'
down_revision = 'x9y0z1a2b3c4'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('planning_years') as batch_op:
        batch_op.add_column(sa.Column('version', sa.Integer(), server_default='0', nullable=False))
    with op.batch_alter_table('anchor_events') as batch_op:
        batch_op.add_column(sa.Column('version', sa.Integer(), server_default='0', nullable=False))
    with op.batch_alter_table('scheduled_sessions') as batch_op:
        batch_op.add_column(sa.Column('version', sa.Integer(), server_default='0', nullable=False))
    with op.batch_alter_table('planning_notices') as batch_op:
        batch_op.add_column(sa.Column('version', sa.Integer(), server_default='0', nullable=False))
    with op.batch_alter_table('sessions') as batch_op:
        batch_op.add_column(sa.Column('version', sa.Integer(), server_default='0', nullable=False))


def downgrade():
    with op.batch_alter_table('sessions') as batch_op:
        batch_op.drop_column('version')
    with op.batch_alter_table('planning_notices') as batch_op:
        batch_op.drop_column('version')
    with op.batch_alter_table('scheduled_sessions') as batch_op:
        batch_op.drop_column('version')
    with op.batch_alter_table('anchor_events') as batch_op:
        batch_op.drop_column('version')
    with op.batch_alter_table('planning_years') as batch_op:
        batch_op.drop_column('version')
