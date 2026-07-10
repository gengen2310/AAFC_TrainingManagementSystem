"""v30: Parade Notices — parade_notices table

Revision ID: r3s4t5u6v7w8
Revises: q2r3s4t5u6v7
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa

revision = 'r3s4t5u6v7w8'
down_revision = 'q2r3s4t5u6v7'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "parade_notices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("planning_year_id", sa.String(36), sa.ForeignKey("planning_years.id"), nullable=True, index=True),
        sa.Column("parade_date_id", sa.String(36), sa.ForeignKey("parade_dates.id"), nullable=False, index=True),
        sa.Column("notice_text", sa.Text, nullable=False),
        sa.Column("audience", sa.String(50), nullable=True),
        sa.Column("priority", sa.String(20), nullable=False, server_default="normal"),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("is_archived", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )


def downgrade():
    op.drop_table("parade_notices")
