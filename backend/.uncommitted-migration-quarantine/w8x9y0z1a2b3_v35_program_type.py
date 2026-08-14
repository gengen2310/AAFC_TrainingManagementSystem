"""v35: Rename core_status values core→foundation, additional→extension

Revision ID: w8x9y0z1a2b3
Revises: v7w8x9y0z1a2
Create Date: 2026-07-14
"""
from alembic import op

revision = "w8x9y0z1a2b3"
down_revision = "v7w8x9y0z1a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rename existing values to the new canonical labels.
    # "optional" is a new value with no existing rows to migrate.
    op.execute(
        "UPDATE curriculum_items SET core_status = 'foundation' WHERE core_status = 'core'"
    )
    op.execute(
        "UPDATE curriculum_items SET core_status = 'extension' WHERE core_status = 'additional'"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE curriculum_items SET core_status = 'core' WHERE core_status = 'foundation'"
    )
    op.execute(
        "UPDATE curriculum_items SET core_status = 'additional' WHERE core_status = 'extension'"
    )
