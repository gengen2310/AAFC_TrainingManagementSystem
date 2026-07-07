"""v26 — Add missing archived_at column to anchor_events and scheduled_sessions.

Both tables use SoftDeleteMixin which defines archived_at, but they were created
in v11 before archived_at was added to the mixin, and no migration patched them.
Without this column SQLAlchemy raises ProgrammingError on every query to these
tables, breaking anchors, long-range, annual-program, and term-planner endpoints.

Revision ID: n9i0j1k2l3m4
Revises: m8h9i0j1k2l3
Create Date: 2026-07-07
"""
import sqlalchemy as sa
from alembic import op

revision = 'n9i0j1k2l3m4'
down_revision = 'm8h9i0j1k2l3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("anchor_events") as b:
        b.add_column(sa.Column("archived_at", sa.DateTime(), nullable=True))

    with op.batch_alter_table("scheduled_sessions") as b:
        b.add_column(sa.Column("archived_at", sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table("scheduled_sessions") as b:
        b.drop_column("archived_at")

    with op.batch_alter_table("anchor_events") as b:
        b.drop_column("archived_at")
