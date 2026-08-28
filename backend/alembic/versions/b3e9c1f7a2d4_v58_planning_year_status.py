"""v58 — planning_years.status (draft|active|archived) + backfill from active_status

Revision ID: b3e9c1f7a2d4
Revises: fa57bc9d0e1a
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa

revision = "b3e9c1f7a2d4"
down_revision = "fa57bc9d0e1a"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("planning_years") as batch_op:
        batch_op.add_column(
            sa.Column("status", sa.String(20), nullable=False,
                      server_default="active")
        )

    # Backfill: active_status=True → 'active', False → 'archived'.
    # Draft is a new concept — no existing row is a draft; they're all
    # either active or archived based on the old boolean.
    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE planning_years SET status = CASE "
        "  WHEN active_status THEN 'active' "
        "  ELSE 'archived' "
        "END"
    ))


def downgrade():
    with op.batch_alter_table("planning_years") as batch_op:
        batch_op.drop_column("status")
