"""v29: Wing HQ Calendar — wing_hq_events, squadron_event_status, wing_event_curriculum_links

Revision ID: q2r3s4t5u6v7
Revises: p1k2l3m4n5o6
Create Date: 2026-07-07
"""
from alembic import op
import sqlalchemy as sa

revision = 'q2r3s4t5u6v7'
down_revision = 'p1k2l3m4n5o6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "wing_hq_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("wing_id", sa.String(36), nullable=False, index=True),
        sa.Column("year", sa.Integer, nullable=False, index=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("event_type", sa.String(40), nullable=False, server_default="wing_event"),
        sa.Column("start_date", sa.String(10), nullable=False, index=True),
        sa.Column("end_date", sa.String(10), nullable=True),
        sa.Column("start_time", sa.String(8), nullable=True),
        sa.Column("end_time", sa.String(8), nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("source_system", sa.String(60), nullable=True),
        sa.Column("source_reference", sa.String(200), nullable=True, index=True),
        sa.Column("source_event_code", sa.String(80), nullable=True),
        sa.Column("planning_importance", sa.String(30), nullable=False, server_default="key_event"),
        sa.Column("audience", sa.JSON, nullable=True),
        sa.Column("visibility", sa.String(20), nullable=False, server_default="wing_only"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("requires_squadron_action", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_planning_anchor", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("is_archived", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("archived_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "squadron_event_status",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("wing_event_id", sa.String(36), sa.ForeignKey("wing_hq_events.id"), nullable=False, index=True),
        sa.Column("squadron_id", sa.String(36), sa.ForeignKey("squadrons.id"), nullable=False, index=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="not_reviewed"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("reviewed_by", sa.String(36), nullable=True),
        sa.Column("reviewed_at", sa.DateTime, nullable=True),
        sa.Column("local_activity_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.UniqueConstraint("wing_event_id", "squadron_id", name="uq_sqn_event_status"),
    )

    op.create_table(
        "wing_event_curriculum_links",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("wing_event_id", sa.String(36), sa.ForeignKey("wing_hq_events.id"), nullable=False, index=True),
        sa.Column("curriculum_item_id", sa.String(36), sa.ForeignKey("curriculum_items.id"), nullable=False, index=True),
        sa.Column("link_type", sa.String(30), nullable=False, server_default="covers"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.UniqueConstraint("wing_event_id", "curriculum_item_id", name="uq_wing_event_curriculum"),
    )


def downgrade():
    op.drop_table("wing_event_curriculum_links")
    op.drop_table("squadron_event_status")
    op.drop_table("wing_hq_events")
