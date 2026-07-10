"""v31: chain-link revision (superseded pre-merge)

planning_activity_imports, planning_activities, planning_activity_sqn_overrides
table creation removed before merge — superseded by v34 cea_import_batches,
cea_activities, and activity_local_hides which have the correct schema used
by current models.
Revision retained to preserve the linear chain v29→v30→v31→v32→v33→v34.

Revision ID: s4t5u6v7w8x9
Revises: r3s4t5u6v7w8
Create Date: 2026-07-10
"""
revision = "s4t5u6v7w8x9"
down_revision = "r3s4t5u6v7w8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
