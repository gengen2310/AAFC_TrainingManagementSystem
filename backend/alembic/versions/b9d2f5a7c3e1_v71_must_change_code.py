"""v71: enforce first-login access-code rotation.

Revision ID: b9d2f5a7c3e1
Revises: a8c1e4f6b2d9
Create Date: 2026-09-29
"""
from alembic import op
import sqlalchemy as sa

revision = "b9d2f5a7c3e1"
down_revision = "a8c1e4f6b2d9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column(
            "must_change_code", sa.Boolean(), nullable=False,
            server_default=sa.false(),
        ))


def downgrade():
    with op.batch_alter_table("users") as batch:
        batch.drop_column("must_change_code")
