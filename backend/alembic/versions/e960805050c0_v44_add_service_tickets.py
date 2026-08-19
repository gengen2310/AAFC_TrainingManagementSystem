"""v44 Add service_tickets table (Service Desk Sub-project E).

Revision ID: e960805050c0
Revises: b4c5d6e7f8a9
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa

revision = 'e960805050c0'
down_revision = 'b4c5d6e7f8a9'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "service_tickets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rank", sa.String(40), nullable=False),
        sa.Column("first_name", sa.String(80), nullable=False),
        sa.Column("last_name", sa.String(80), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("squadron_id", sa.String(36),
                  sa.ForeignKey("squadrons.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("admin_notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False,
                  server_default=sa.func.now()),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("resolved_at", sa.DateTime, nullable=True),
    )
    with op.batch_alter_table("service_tickets") as batch_op:
        batch_op.create_index("ix_service_tickets_status", ["status"])
        batch_op.create_index("ix_service_tickets_squadron_id", ["squadron_id"])
        batch_op.create_index("ix_service_tickets_created_at", ["created_at"])


def downgrade():
    op.drop_table("service_tickets")
