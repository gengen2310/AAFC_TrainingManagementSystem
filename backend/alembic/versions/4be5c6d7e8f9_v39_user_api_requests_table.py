"""v39 user_api_requests table (DEF-11 per-account API rate limiting)

Revision ID: 4be5c6d7e8f9
Revises: 3adfd5f63190
Create Date: 2026-08-13

"""
from alembic import op
import sqlalchemy as sa

revision = '4be5c6d7e8f9'
down_revision = '3adfd5f63190'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_api_requests',
        sa.Column('user_id', sa.String(36), primary_key=True),
        sa.Column('request_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('window_start', sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('user_api_requests')
