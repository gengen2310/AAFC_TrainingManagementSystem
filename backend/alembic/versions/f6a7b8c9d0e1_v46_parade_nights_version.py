"""v46 add version to parade_nights for optimistic locking

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-08-09

update_parade_night (PATCH /api/parade-nights/{id}) had no conflict detection at all --
confirmed live during the Final Remediation program that two concurrent PATCHes silently
last-write-win with zero warning, discarding one editor's change with no signal to either
user. Every other frequently-co-edited entity (PlanningYear, AnchorEvent, PlanningNotice,
Session/TrainingSession) already has this exact optimistic-locking pattern; ParadeNight was
the one significant gap, matching the governing instruction's own named example ("two users
edit one Parade Night").

Column-existence-checked, matching v44/v45's established defensive pattern for this
program, in case any environment's schema has already diverged from a pure migration-chain
build.
"""
from alembic import op
import sqlalchemy as sa

revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None

_TABLE = "parade_nights"
_COLUMN = "version"


def _existing_columns(table: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    if _COLUMN not in _existing_columns(_TABLE):
        op.add_column(_TABLE, sa.Column(_COLUMN, sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    # Deliberately a no-op, not a symmetric drop_column -- see v44/v45's downgrade for the
    # same reasoning: the model unconditionally requires this column now.
    pass
