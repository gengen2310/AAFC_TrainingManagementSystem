"""v33 planning notices

Revision ID: u6v7w8x9y0z1
Revises: t5u6v7w8x9y0
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa

revision = "u6v7w8x9y0z1"
down_revision = "t5u6v7w8x9y0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "planning_notices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("planning_year_id", sa.String(36), sa.ForeignKey("planning_years.id"), nullable=True, index=True),
        sa.Column("parade_date_id", sa.String(36), sa.ForeignKey("parade_dates.id"), nullable=False, index=True),
        sa.Column("notice_text", sa.Text, nullable=False),
        sa.Column("audience", sa.String(60), nullable=True),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("is_archived", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("planning_notices")
