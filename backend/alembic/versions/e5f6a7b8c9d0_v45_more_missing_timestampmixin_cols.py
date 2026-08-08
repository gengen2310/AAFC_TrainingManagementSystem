"""v45 add missing created_by/updated_by to three more TimestampMixin tables

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-08

Found via a static sweep of every TimestampMixin model against its creation
migration, prompted by the same class of bug already hit four times now
(planning_notices v35, curriculum_phases+facilitator_type_tags v47, and
planning_facilitator_leave in the immediately-preceding v44 migration).
Three more tables were created without the created_by/updated_by columns
TimestampMixin requires, and no later migration ever added them:

  - squadron_event_status (v29, q2r3s4t5u6v7)
  - wing_event_curriculum_links (v29, q2r3s4t5u6v7)
  - activity_local_hides (v34, v7w8x9y0z1a2)

None of these have been reported broken yet, but the same drift class already
caused four production incidents against tables built purely through the
migration chain (invisible locally/in CI because seed_all()/init_db() build
schema from SQLAlchemy metadata directly, bypassing Alembic) -- fixing
proactively rather than waiting for the next incident report.
"""
from alembic import op
import sqlalchemy as sa

revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None

_TABLES = ["squadron_event_status", "wing_event_curriculum_links", "activity_local_hides"]


def upgrade() -> None:
    for table in _TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("created_by", sa.String(36), nullable=True))
            batch_op.add_column(sa.Column("updated_by", sa.String(36), nullable=True))


def downgrade() -> None:
    for table in reversed(_TABLES):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_column("updated_by")
            batch_op.drop_column("created_by")
