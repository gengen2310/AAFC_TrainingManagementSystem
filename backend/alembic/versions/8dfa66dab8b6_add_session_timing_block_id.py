"""add_session_timing_block_id
Revision ID: 8dfa66dab8b6
Revises: e9c422baf945
Create Date: 2026-08-21 20:13:50.107182
"""
from alembic import op
import sqlalchemy as sa

revision = '8dfa66dab8b6'
down_revision = 'e9c422baf945'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(sa.Column("timing_block_id", sa.String(36), nullable=True))
    op.create_index("ix_sessions_timing_block_id", "sessions", ["timing_block_id"], unique=False)


def downgrade():
    op.drop_index("ix_sessions_timing_block_id", table_name="sessions")
    with op.batch_alter_table("sessions") as batch:
        batch.drop_column("timing_block_id")
