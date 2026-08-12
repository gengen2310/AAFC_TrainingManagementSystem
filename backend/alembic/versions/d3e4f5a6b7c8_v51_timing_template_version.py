"""v51 add version column to timing_templates (optimistic locking)

Completes Phase 7 of the Level A program. All other priority models
(ParadeNight, Session, PlanningYear, AnchorEvent, ScheduledSession,
PlanningNotice) already have version columns from v37/v46.

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-08-12
"""
from alembic import op
import sqlalchemy as sa

revision = "d3e4f5a6b7c8"
down_revision = "c2d3e4f5a6b7"
branch_labels = None
depends_on = None

_TABLE = "timing_templates"
_COLUMN = "version"


def _existing_columns(table: str) -> list[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return [c["name"] for c in inspector.get_columns(table)]


def upgrade() -> None:
    if _COLUMN not in _existing_columns(_TABLE):
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.add_column(
                sa.Column(_COLUMN, sa.Integer(), nullable=False, server_default="0")
            )


def downgrade() -> None:
    with op.batch_alter_table(_TABLE) as batch_op:
        batch_op.drop_column(_COLUMN)
