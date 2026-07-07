"""v27 — Partial unique index on (squadron_id, date) for active parade nights.

Prevents duplicate parade nights on the same date for the same squadron
at the database level. The partial index covers only non-archived rows so
that archiving a parade night and creating a replacement on the same date
is permitted.

The application layer (training.py create_parade) returns a 409 before the
insert for the common case; this index is the safety net that catches the
concurrent-request race that the application check cannot.

Revision ID: o0j1k2l3m4n5
Revises: n9i0j1k2l3m4
Create Date: 2026-07-07
"""
from alembic import op

revision = 'o0j1k2l3m4n5'
down_revision = 'n9i0j1k2l3m4'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_parade_night_sqn_date_active
        ON parade_nights (squadron_id, date)
        WHERE is_archived = FALSE
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_parade_night_sqn_date_active")
