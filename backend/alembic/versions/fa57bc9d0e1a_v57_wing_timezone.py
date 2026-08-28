"""v57 — wings.timezone (IANA string for rollover localisation)

Revision ID: fa57bc9d0e1a
Revises: e2f3a4b5c6d7
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa

revision = "fa57bc9d0e1a"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("wings") as batch_op:
        batch_op.add_column(sa.Column("timezone", sa.String(60), nullable=True))

    # Seed 7WG immediately — production has exactly one wing (7WG) and this
    # value is required for resolve_active_year() to function at all.
    bind = op.get_bind()
    bind.execute(sa.text("UPDATE wings SET timezone = 'Australia/Perth' WHERE code = '7WG'"))


def downgrade():
    with op.batch_alter_table("wings") as batch_op:
        batch_op.drop_column("timezone")
