"""v14 Training Planner — model extensions for annual program, mission scheduling, and rollover.

Adds:
- sessions.part_number (INT nullable)
- curriculum_items.part_count (INT default 1)
- curriculum_items.instructor_suitability (VARCHAR 120 nullable)
- anchor_events.cea_activity_id (INT nullable)
- anchor_events.nomination_end_date (VARCHAR 10 nullable)
- anchor_events.audience_staff_only (BOOL default 0)
- anchor_events.audience_proficient (BOOL default 0)
- anchor_events.audience_first_years (BOOL default 0)
- anchor_events.importance_level (INT nullable) — 1-5 numeric per spreadsheet
- anchor_events.unit_name (VARCHAR 200 nullable)
- holiday_periods.holiday_type (VARCHAR 40 default 'school_holiday')
- parade_dates.term (VARCHAR 10 nullable)
- parade_dates.week_number (INT nullable)
- parade_dates.cancellation_reason (TEXT nullable)

Revision ID: d1e3f5a7c9b0
Revises: a2c4e6f8b1d3
Create Date: 2026-06-29
"""
from alembic import op
import sqlalchemy as sa

revision = 'd1e3f5a7c9b0'
down_revision = 'a2c4e6f8b1d3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("sessions") as b:
        b.add_column(sa.Column("part_number", sa.Integer(), nullable=True))

    with op.batch_alter_table("curriculum_items") as b:
        b.add_column(sa.Column("part_count", sa.Integer(), nullable=False, server_default="1"))
        b.add_column(sa.Column("instructor_suitability", sa.String(120), nullable=True))

    with op.batch_alter_table("anchor_events") as b:
        b.add_column(sa.Column("cea_activity_id", sa.Integer(), nullable=True))
        b.add_column(sa.Column("nomination_end_date", sa.String(10), nullable=True))
        b.add_column(sa.Column("audience_staff_only", sa.Boolean(), nullable=False, server_default="0"))
        b.add_column(sa.Column("audience_proficient", sa.Boolean(), nullable=False, server_default="0"))
        b.add_column(sa.Column("audience_first_years", sa.Boolean(), nullable=False, server_default="0"))
        b.add_column(sa.Column("importance_level", sa.Integer(), nullable=True))
        b.add_column(sa.Column("unit_name", sa.String(200), nullable=True))

    with op.batch_alter_table("holiday_periods") as b:
        b.add_column(sa.Column("holiday_type", sa.String(40), nullable=False, server_default="school_holiday"))

    with op.batch_alter_table("parade_dates") as b:
        b.add_column(sa.Column("term", sa.String(10), nullable=True))
        b.add_column(sa.Column("week_number", sa.Integer(), nullable=True))
        b.add_column(sa.Column("cancellation_reason", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("parade_dates") as b:
        b.drop_column("cancellation_reason")
        b.drop_column("week_number")
        b.drop_column("term")

    with op.batch_alter_table("holiday_periods") as b:
        b.drop_column("holiday_type")

    with op.batch_alter_table("anchor_events") as b:
        b.drop_column("unit_name")
        b.drop_column("importance_level")
        b.drop_column("audience_first_years")
        b.drop_column("audience_proficient")
        b.drop_column("audience_staff_only")
        b.drop_column("nomination_end_date")
        b.drop_column("cea_activity_id")

    with op.batch_alter_table("curriculum_items") as b:
        b.drop_column("instructor_suitability")
        b.drop_column("part_count")

    with op.batch_alter_table("sessions") as b:
        b.drop_column("part_number")
