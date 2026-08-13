"""v40 drop dead custom_phases table

Revision ID: 5cf6d7e8f9a0
Revises: 4be5c6d7e8f9
Create Date: 2026-08-13

custom_phases was created in v9 (migration 175e1c6e12f7) as an early
attempt at a squadron-scoped phase-name override table.  It was never
wired to any API endpoint, any frontend call, or any foreign-key reference
from another table.  CurriculumPhase (curriculum_phases, migration v35)
is the governed replacement, with the scope/visibility model this table
lacks.

The comment in training.py at the CurriculumPhase block explicitly
documents: "CustomPhase (the pre-existing, fully-unwired dead table) is
deliberately left alone, not built on."  This migration completes that
decision by removing the table and its sole index so it no longer clutters
the schema or the SQLAlchemy metadata.

Safe preconditions (verified 2026-08-13):
  - No FK from any other table references custom_phases
  - No router endpoint reads or writes custom_phases
  - No frontend code calls a custom_phases API path
  - Production custom_phases table expected to be empty (no write path exists)
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "5cf6d7e8f9a0"
down_revision = "4be5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("custom_phases") as batch_op:
        batch_op.drop_index("ix_custom_phases_squadron_id")
    op.drop_table("custom_phases")


def downgrade() -> None:
    # Recreate the table structure only — no data was ever written to it,
    # so there is nothing to restore.
    op.create_table(
        "custom_phases",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("squadron_id", sa.String(36), sa.ForeignKey("squadrons.id"), nullable=False),
        sa.Column("phase_key", sa.String(40), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("abbr", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_custom_phases_squadron_id", "custom_phases", ["squadron_id"])
