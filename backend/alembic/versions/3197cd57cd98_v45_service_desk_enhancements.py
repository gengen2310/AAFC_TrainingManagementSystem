"""v45 service desk enhancements: category, assigned_to, unit_name, email config table

Revision ID: 3197cd57cd98
Revises: e960805050c0
Create Date: 2026-08-21
"""
from alembic import op
import sqlalchemy as sa

revision = '3197cd57cd98'
down_revision = 'e960805050c0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to service_tickets (nullable for backwards compat with existing rows)
    with op.batch_alter_table("service_tickets", schema=None) as batch_op:
        batch_op.add_column(sa.Column("category", sa.String(40), nullable=True, server_default="other"))
        batch_op.add_column(sa.Column("unit_name", sa.String(200), nullable=True))
        batch_op.add_column(sa.Column("assigned_to_name", sa.String(120), nullable=True))

    # Create email config table
    op.create_table(
        "service_desk_email_configs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("wing_id", sa.String(36), sa.ForeignKey("wings.id", ondelete="CASCADE"), nullable=True),
        sa.Column("notification_email", sa.String(200), nullable=False),
        sa.Column("updated_by_user_id", sa.String(36), nullable=True),
    )
    op.create_index("ix_sd_email_configs_wing_id", "service_desk_email_configs", ["wing_id"])


def downgrade() -> None:
    op.drop_index("ix_sd_email_configs_wing_id", table_name="service_desk_email_configs")
    op.drop_table("service_desk_email_configs")
    with op.batch_alter_table("service_tickets", schema=None) as batch_op:
        batch_op.drop_column("assigned_to_name")
        batch_op.drop_column("unit_name")
        batch_op.drop_column("category")
