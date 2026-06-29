"""V12: Wire TRGO Planning to real parade nights and sessions.

Adds cadet_group to sessions (enables per-group grid rows in Night Builder).
Adds parade_night_id to parade_dates (links planning dates to real ParadeNight records).

Revision ID: a2c4e6f8b1d3
Revises: f3a1b5c9d7e2
Create Date: 2026-06-28
"""
from alembic import op
import sqlalchemy as sa

revision = 'a2c4e6f8b1d3'
down_revision = 'f3a1b5c9d7e2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('sessions') as batch_op:
        batch_op.add_column(sa.Column('cadet_group', sa.String(30), nullable=True))

    with op.batch_alter_table('parade_dates') as batch_op:
        batch_op.add_column(sa.Column('parade_night_id', sa.String(36), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('parade_dates') as batch_op:
        batch_op.drop_column('parade_night_id')

    with op.batch_alter_table('sessions') as batch_op:
        batch_op.drop_column('cadet_group')
