"""v34: CEA import batches, activities, and local hides

Revision ID: v7w8x9y0z1a2
Revises: u6v7w8x9y0z1
Create Date: 2026-07-10
"""
from alembic import op
import sqlalchemy as sa

revision = "v7w8x9y0z1a2"
down_revision = "u6v7w8x9y0z1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cea_import_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("planning_year_id", sa.String(36), sa.ForeignKey("planning_years.id"), nullable=True, index=True),
        sa.Column("wing_id", sa.String(36), nullable=True, index=True),
        sa.Column("imported_by", sa.String(36), nullable=False),
        sa.Column("source_file_name", sa.String(260), nullable=True),
        sa.Column("row_count", sa.Integer, default=0),
        sa.Column("created_count", sa.Integer, default=0),
        sa.Column("updated_count", sa.Integer, default=0),
        sa.Column("duplicate_count", sa.Integer, default=0),
        sa.Column("skipped_count", sa.Integer, default=0),
        sa.Column("error_count", sa.Integer, default=0),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    op.create_table(
        "cea_activities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("import_batch_id", sa.String(36), sa.ForeignKey("cea_import_batches.id"), nullable=True, index=True),
        sa.Column("planning_year_id", sa.String(36), sa.ForeignKey("planning_years.id"), nullable=True, index=True),
        sa.Column("wing_id", sa.String(36), nullable=True, index=True),
        sa.Column("unit_id", sa.String(36), sa.ForeignKey("squadrons.id"), nullable=True, index=True),
        sa.Column("cea_activity_id", sa.String(60), nullable=True, index=True),
        sa.Column("activity_type", sa.String(80), nullable=True),
        sa.Column("status_name", sa.String(60), nullable=True),
        sa.Column("parent_unit", sa.String(200), nullable=True),
        sa.Column("host_unit", sa.String(200), nullable=True),
        sa.Column("activity_name", sa.String(300), nullable=False),
        sa.Column("nomination_start_date", sa.String(10), nullable=True),
        sa.Column("nomination_end_date", sa.String(10), nullable=True),
        sa.Column("activity_start_date", sa.String(10), nullable=True),
        sa.Column("activity_end_date", sa.String(10), nullable=True),
        sa.Column("start_time", sa.String(8), nullable=True),
        sa.Column("end_time", sa.String(8), nullable=True),
        sa.Column("location", sa.String(300), nullable=True),
        sa.Column("activity_poc", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("source_type", sa.String(20), default="cea"),
        sa.Column("classification_status", sa.String(20), default="needs_review"),
        sa.Column("importance", sa.String(30), nullable=True),
        sa.Column("audience_staff_only", sa.Boolean, default=False),
        sa.Column("audience_seniors", sa.Boolean, default=False),
        sa.Column("audience_proficient", sa.Boolean, default=False),
        sa.Column("audience_first_years", sa.Boolean, default=False),
        sa.Column("classified_by", sa.String(36), nullable=True),
        sa.Column("classified_at", sa.String(26), nullable=True),
        sa.Column("is_removed_from_cea", sa.Boolean, default=False),
        sa.Column("is_archived", sa.Boolean, default=False),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    op.create_table(
        "activity_local_hides",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("cea_activity_id", sa.String(36), sa.ForeignKey("cea_activities.id"), nullable=False, index=True),
        sa.Column("unit_id", sa.String(36), sa.ForeignKey("squadrons.id"), nullable=False, index=True),
        sa.Column("is_hidden", sa.Boolean, default=True),
        sa.Column("local_note", sa.Text, nullable=True),
        sa.Column("hidden_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("activity_local_hides")
    op.drop_table("cea_activities")
    op.drop_table("cea_import_batches")
