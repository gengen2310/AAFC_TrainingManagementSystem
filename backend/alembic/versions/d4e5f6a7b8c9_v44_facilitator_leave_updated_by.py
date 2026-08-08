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
"""
from alembic import op
import sqlalchemy as sa

revision = "d4e5f6a7b8c9"
down_revision = "5a195a98148a"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("planning_facilitator_leave", sa.Column("updated_by", sa.String(36), nullable=True))


def downgrade() -> None:
    op.drop_column("planning_facilitator_leave", "updated_by")
