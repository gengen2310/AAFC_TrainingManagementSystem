"""v70: authoritative Service Desk scope and assignment.

Adds service_tickets.wing_id so Wing-level submissions retain an authoritative
scope, and assigned_to_user_id so assignment is tied to an account rather than
free text alone. Existing squadron tickets are backfilled from squadrons.wing_id.

Revision ID: a8c1e4f6b2d9
Revises: 7f61608fa538
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa

revision = "a8c1e4f6b2d9"
down_revision = "7f61608fa538"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("service_tickets") as batch:
        batch.add_column(sa.Column("wing_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("assigned_to_user_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_service_tickets_wing_id_wings",
            "wings", ["wing_id"], ["id"], ondelete="SET NULL",
        )
        batch.create_foreign_key(
            "fk_service_tickets_assigned_to_user_id_users",
            "users", ["assigned_to_user_id"], ["id"], ondelete="SET NULL",
        )
        batch.create_index("ix_service_tickets_wing_id", ["wing_id"], unique=False)
        batch.create_index(
            "ix_service_tickets_assigned_to_user_id",
            ["assigned_to_user_id"], unique=False,
        )

    # Preserve existing tenancy before any future squadron archival can SET NULL
    # service_tickets.squadron_id.
    op.execute(sa.text(
        """
        UPDATE service_tickets
        SET wing_id = (
            SELECT squadrons.wing_id
            FROM squadrons
            WHERE squadrons.id = service_tickets.squadron_id
        )
        WHERE wing_id IS NULL AND squadron_id IS NOT NULL
        """
    ))


def downgrade():
    with op.batch_alter_table("service_tickets") as batch:
        batch.drop_index("ix_service_tickets_assigned_to_user_id")
        batch.drop_index("ix_service_tickets_wing_id")
        batch.drop_constraint(
            "fk_service_tickets_assigned_to_user_id_users", type_="foreignkey"
        )
        batch.drop_constraint("fk_service_tickets_wing_id_wings", type_="foreignkey")
        batch.drop_column("assigned_to_user_id")
        batch.drop_column("wing_id")
