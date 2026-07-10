"""v31: planning_activity_imports, planning_activities, planning_activity_sqn_overrides

Revision ID: s4t5u6v7w8x9
Revises: r3s4t5u6v7w8
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa

revision = "s4t5u6v7w8x9"
down_revision = "r3s4t5u6v7w8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "planning_activity_imports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("planning_year_id", sa.String(36), sa.ForeignKey("planning_years.id"), nullable=True),
        sa.Column("squadron_id", sa.String(36), nullable=True),
        sa.Column("source_type", sa.String(30), nullable=False, server_default="cea"),
        sa.Column("source_file", sa.String(300), nullable=True),
        sa.Column("imported_by", sa.String(36), nullable=True),
        sa.Column("row_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_pai_year", "planning_activity_imports", ["planning_year_id"])
    op.create_index("ix_pai_sqn", "planning_activity_imports", ["squadron_id"])

    op.create_table(
        "planning_activities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("planning_year_id", sa.String(36), sa.ForeignKey("planning_years.id"), nullable=True),
        sa.Column("import_batch_id", sa.String(36), sa.ForeignKey("planning_activity_imports.id"), nullable=True),
        sa.Column("owning_squadron_id", sa.String(36), nullable=True),
        sa.Column("source_type", sa.String(30), nullable=False, server_default="cea"),
        # CEA source fields
        sa.Column("activity_id", sa.String(100), nullable=True),
        sa.Column("activity_type", sa.String(100), nullable=True),
        sa.Column("parent_unit", sa.String(200), nullable=True),
        sa.Column("host_unit", sa.String(200), nullable=True),
        sa.Column("activity_name", sa.String(500), nullable=False),
        sa.Column("nomination_start_date", sa.String(10), nullable=True),
        sa.Column("nomination_end_date", sa.String(10), nullable=True),
        sa.Column("activity_start_date", sa.String(10), nullable=True),
        sa.Column("activity_end_date", sa.String(10), nullable=True),
        sa.Column("location", sa.String(300), nullable=True),
        sa.Column("activity_poc", sa.String(200), nullable=True),
        # Classification
        sa.Column("staff_only", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("seniors", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("proficient", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("first_years", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("activity_importance", sa.String(30), nullable=True),
        # Review
        sa.Column("is_reviewed", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("reviewed_by", sa.String(36), nullable=True),
        sa.Column("reviewed_at", sa.String(30), nullable=True),
        # Lifecycle
        sa.Column("status", sa.String(30), nullable=False, server_default="imported"),
        sa.Column("is_archived", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("raw_source_data", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_pa_year", "planning_activities", ["planning_year_id"])
    op.create_index("ix_pa_batch", "planning_activities", ["import_batch_id"])
    op.create_index("ix_pa_sqn", "planning_activities", ["owning_squadron_id"])
    op.create_index("ix_pa_activity_id", "planning_activities", ["activity_id"])
    op.create_index("ix_pa_start", "planning_activities", ["activity_start_date"])

    op.create_table(
        "planning_activity_sqn_overrides",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("activity_id", sa.String(36), sa.ForeignKey("planning_activities.id"), nullable=False),
        sa.Column("squadron_id", sa.String(36), nullable=False),
        sa.Column("is_hidden", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("local_notes", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_paso_activity", "planning_activity_sqn_overrides", ["activity_id"])
    op.create_index("ix_paso_sqn", "planning_activity_sqn_overrides", ["squadron_id"])


def downgrade() -> None:
    op.drop_table("planning_activity_sqn_overrides")
    op.drop_table("planning_activities")
    op.drop_table("planning_activity_imports")
