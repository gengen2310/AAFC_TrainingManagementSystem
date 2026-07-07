"""v25 — per-account lockout columns + DB-backed IP rate-limiter table

Revision ID: m8h9i0j1k2l3
Revises: l7g8h9i0j1k2
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = 'm8h9i0j1k2l3'
down_revision = 'l7g8h9i0j1k2'
branch_labels = None
depends_on = None


def upgrade():
    # Per-account lockout columns on access_codes
    op.add_column('access_codes', sa.Column('failed_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('access_codes', sa.Column('locked_until', sa.DateTime(), nullable=True))

    # DB-backed IP rate-limiter table (replaces in-memory dicts, works across workers)
    op.create_table(
        'ip_login_attempts',
        sa.Column('ip', sa.String(45), primary_key=True),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('window_start', sa.DateTime(), nullable=False),
        sa.Column('locked_until', sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table('ip_login_attempts')
    op.drop_column('access_codes', 'locked_until')
    op.drop_column('access_codes', 'failed_attempts')
