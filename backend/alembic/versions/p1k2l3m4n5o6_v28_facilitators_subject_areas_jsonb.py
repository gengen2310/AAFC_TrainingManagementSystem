"""v28: convert facilitators.subject_areas from TEXT to JSONB

Revision ID: p1k2l3m4n5o6
Revises: o0j1k2l3m4n5
Create Date: 2026-07-07
"""
from alembic import op

revision = 'p1k2l3m4n5o6'
down_revision = 'o0j1k2l3m4n5'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE facilitators
        ALTER COLUMN subject_areas TYPE JSONB
        USING CASE
            WHEN subject_areas IS NULL THEN NULL
            ELSE subject_areas::jsonb
        END
    """)


def downgrade():
    op.execute("""
        ALTER TABLE facilitators
        ALTER COLUMN subject_areas TYPE TEXT
        USING subject_areas::text
    """)
