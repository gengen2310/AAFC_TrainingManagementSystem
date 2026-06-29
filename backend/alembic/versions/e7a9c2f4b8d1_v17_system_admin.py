"""v17 System Admin Console — adds system_settings table for maintenance mode and platform state.

Revision ID: e7a9c2f4b8d1
Revises: d1e3f5a7c9b0
Create Date: 2026-06-29
"""
from alembic import op
import sqlalchemy as sa

revision = 'e7a9c2f4b8d1'
down_revision = 'd1e3f5a7c9b0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(80), primary_key=True),
        sa.Column("value", sa.Text, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
    )


def downgrade():
    op.drop_table("system_settings")
