"""v57 — wings.timezone (IANA zone for the wing-local calendar year)

Revision ID: a7c4e91b2f60
Revises: e2f3a4b5c6d7
Create Date: 2026-08-28
"""
import sqlalchemy as sa
from alembic import op

revision = "a7c4e91b2f60"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("wings") as b:
        b.add_column(sa.Column("timezone", sa.String(64), nullable=True))
    # Backfilled by code, not by a column default, so a NEW wing still arrives
    # NULL and trips MissingTimezone rather than silently inheriting Perth.
    op.execute("UPDATE wings SET timezone = 'Australia/Perth' WHERE code = '7WG'")


def downgrade() -> None:
    with op.batch_alter_table("wings") as b:
        b.drop_column("timezone")
