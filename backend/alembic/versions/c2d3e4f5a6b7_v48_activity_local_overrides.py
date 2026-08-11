"""v48 activity_local_overrides table (REM-103)

Squadron-local adjustments to a Wing/National-owned inherited Activity --
date/time/notes overrides plus a hide/relevance flag, one row per
(activity_id, squadron_id). Mirrors activity_local_hides' established
pattern (per-squadron annotation row, source record never modified) but
for the general Activity model instead of CEA-only.

Revision ID: c2d3e4f5a6b7
Revises: b3f7a1c9d4e2
Create Date: 2026-08-11
"""
from alembic import op
import sqlalchemy as sa

revision = 'c2d3e4f5a6b7'
down_revision = 'b3f7a1c9d4e2'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "activity_local_overrides",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("activity_id", sa.String(36), sa.ForeignKey("activities.id"), nullable=False, index=True),
        sa.Column("squadron_id", sa.String(36), sa.ForeignKey("squadrons.id"), nullable=False, index=True),
        sa.Column("local_date_start", sa.String(10), nullable=True),
        sa.Column("local_date_end", sa.String(10), nullable=True),
        sa.Column("local_time_start", sa.String(8), nullable=True),
        sa.Column("local_time_end", sa.String(8), nullable=True),
        sa.Column("local_notes", sa.Text, nullable=True),
        sa.Column("is_hidden", sa.Boolean, default=False),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.UniqueConstraint("activity_id", "squadron_id", name="uq_activity_local_override_activity_squadron"),
    )


def downgrade():
    op.drop_table("activity_local_overrides")
