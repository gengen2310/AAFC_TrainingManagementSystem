"""v30: chain-link revision (superseded pre-merge)

parade_notices table creation removed before merge — superseded by v33
planning_notices which has the correct schema used by current models.
Revision retained to preserve the linear chain v29→v30→v31→v32→v33→v34.

Revision ID: r3s4t5u6v7w8
Revises: q2r3s4t5u6v7
Create Date: 2026-07-09
"""
revision = 'r3s4t5u6v7w8'
down_revision = 'q2r3s4t5u6v7'
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
