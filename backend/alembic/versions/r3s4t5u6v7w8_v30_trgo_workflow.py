"""v30: TRGO Workflow — add planning_importance + importance_level to activities; add local_lessons table

Revision ID: r3s4t5u6v7w8
Revises: q2r3s4t5u6v7
Create Date: 2026-07-07
"""
from alembic import op
import sqlalchemy as sa

revision = 'r3s4t5u6v7w8'
down_revision = 'q2r3s4t5u6v7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("activities", sa.Column("planning_importance", sa.String(30), nullable=True))
    op.add_column("activities", sa.Column("importance_level", sa.Integer, nullable=True))

    op.create_table(
        "local_lessons",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("squadron_id", sa.String(36), sa.ForeignKey("squadrons.id"), nullable=True, index=True),
        sa.Column("lesson_code", sa.String(20), nullable=False),
        sa.Column("lesson_name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("subject_area", sa.String(80), nullable=True),
        sa.Column("default_duration_mins", sa.Integer, nullable=True),
        sa.Column("is_template", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("is_archived", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("archived_at", sa.DateTime, nullable=True),
    )


def downgrade():
    op.drop_table("local_lessons")
    op.drop_column("activities", "importance_level")
    op.drop_column("activities", "planning_importance")
