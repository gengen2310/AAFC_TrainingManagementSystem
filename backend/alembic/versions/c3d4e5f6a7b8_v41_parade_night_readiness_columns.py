"""v41 — add ParadeNight.planning_status / data_quality (authoritative readiness model)

Adds the two new authoritative-readiness columns from services_readiness.py.
readiness_score (existing) becomes a legacy numeric projection derived from
planning_status, not independently computed. Nullable because this is schema-only:
no data backfill runs here. Every consumer this pass wires up (dashboard tonight/
upcoming-readiness cards, /api/reports/readiness, /api/reports/wing-overview) already
fetches each parade night's sessions per request and calls
services_readiness.parade_night_readiness() live, so a NULL stored value on an
untouched historical row never produces a wrong reading in any of those responses —
the stored columns exist for future consumers that want to filter/sort parade nights
by status without re-fetching sessions, not as the sole source of truth. They get
populated going forward by training.py's _recompute(), which already runs on every
session create/edit/status-change.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-24
"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('parade_nights') as batch_op:
        batch_op.add_column(sa.Column('planning_status', sa.String(20), nullable=True))
        batch_op.add_column(sa.Column('data_quality', sa.String(30), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('parade_nights') as batch_op:
        batch_op.drop_column('data_quality')
        batch_op.drop_column('planning_status')
