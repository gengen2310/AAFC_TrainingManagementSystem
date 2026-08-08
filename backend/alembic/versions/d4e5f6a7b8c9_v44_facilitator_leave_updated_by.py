"""v44 add updated_by to planning_facilitator_leave

Revision ID: d4e5f6a7b8c9
Revises: 5a195a98148a
Create Date: 2026-08-08

PlanningFacilitatorLeave (app/models/planning.py) inherits TimestampMixin, which
requires an updated_by column -- but the table's creation migration (t5u6v7w8x9y0,
v32) never included it, same class of gap already fixed once for planning_notices
(w8x9y0z1a2b3, v35) and once for curriculum_phases/facilitator_type_tags. Every ORM
query touching this table (including GET /api/facilitators, which loads
upcoming_leave) fails with UndefinedColumn against a database built purely through
this migration chain -- confirmed live on production, 2026-08-08.

Column-existence-checked rather than a bare add_column: staging's database was at
some point rebuilt via seed_all()'s metadata-based reset_db() (which reads the
correct model schema directly, bypassing Alembic) and then alembic-stamped, so it
already has this column even though it never actually ran this migration -- a bare
add_column crashed staging's deploy with DuplicateColumn on first attempt. Every
environment's real state must be handled, not just production's.
"""
from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "5a195a98148a"
branch_labels = None
depends_on = None

_TABLE = "planning_facilitator_leave"
_COLUMN = "updated_by"


def _existing_columns(table: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    if _COLUMN not in _existing_columns(_TABLE):
        op.add_column(_TABLE, sa.Column(_COLUMN, sa.String(36), nullable=True))


def downgrade() -> None:
    # Deliberately a no-op, not a symmetric drop_column: the model (TimestampMixin)
    # unconditionally requires this column, so dropping it would immediately
    # re-break every environment's ORM queries against this table -- reintroducing
    # the exact SEV1 this migration exists to fix, not "reverting" anything safely.
    pass
