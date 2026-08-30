"""v60 merge phase-b and account-recovery heads
Revision ID: 439ed68a5796
Revises: a1c68e84caf5, c3a7f2e91b48
Create Date: 2026-08-30 13:53:51.049031
"""
from alembic import op
import sqlalchemy as sa

revision = '439ed68a5796'
down_revision = ('a1c68e84caf5', 'c3a7f2e91b48')
branch_labels = None
depends_on = None

def upgrade():
    pass

def downgrade():
    pass
