"""v35 add updated_by to planning_notices

Revision ID: w8x9y0z1a2b3
Revises: v7w8x9y0z1a2
Create Date: 2026-07-12
"""
from alembic import op
import sqlalchemy as sa

revision = "w8x9y0z1a2b3"
down_revision = "v7w8x9y0z1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("planning_notices", sa.Column("updated_by", sa.String(36), nullable=True))


def downgrade() -> None:
    op.drop_column("planning_notices", "updated_by")
