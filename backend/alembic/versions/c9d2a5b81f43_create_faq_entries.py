"""FAQ entries for Help & Reference

A system_admin-authored question and answer list, grouped by category and shown
to every signed-in user. answer_html holds allowlist-sanitised HTML (app.richtext),
never raw author input.

Revision ID: c9d2a5b81f43
Revises: b4c1f7d92e08
"""
from alembic import op
import sqlalchemy as sa

revision = "c9d2a5b81f43"
down_revision = "b4c1f7d92e08"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "faq_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("category", sa.String(80), nullable=False, server_default="General"),
        sa.Column("question", sa.String(300), nullable=False),
        sa.Column("answer_html", sa.Text(), nullable=False, server_default=""),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_faq_entries_category", "faq_entries", ["category"])


def downgrade():
    op.drop_index("ix_faq_entries_category", table_name="faq_entries")
    op.drop_table("faq_entries")
