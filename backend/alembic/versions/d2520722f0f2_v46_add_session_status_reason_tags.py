"""v46 add session_status_reason_tags reference data

Remediation program REM-23 continuation: governed reference data for
session-status-change reasons, mirroring facilitator_type_tags' exact
shape (v45). The Session/SessionStatusHistory reason field stays free-text
(no FK, no migration to existing rows) -- display_name here IS the stored
value, matching facilitator_type_tags' own convention. Seeded with the 8
real reason values already hardcoded as #or-reason's <option> list in
connected-frontend (not invented text) -- "Other" is deliberately NOT
seeded here since it's a genuine non-governed catch-all, not reference
data (same reasoning that kept Facilitator Type's seed to the actual
short codes already in use, not descriptive alternatives).

Revision ID: d2520722f0f2
Revises: ed6feec8b9cd
Create Date: 2026-08-10
"""
import uuid
from alembic import op
import sqlalchemy as sa

revision = 'd2520722f0f2'
down_revision = 'ed6feec8b9cd'
branch_labels = None
depends_on = None

_GLOBAL_SEED_REASONS = [
    "Facilitator unavailable",
    "Venue unavailable",
    "Equipment unavailable",
    "Weather",
    "Higher-priority activity",
    "Program changed",
    "Insufficient time",
    "Safety concern",
]


def upgrade():
    op.create_table(
        'session_status_reason_tags',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('squadron_id', sa.String(36), nullable=True),
        sa.Column('wing_id', sa.String(36), nullable=True),
        sa.Column('scope', sa.String(20), nullable=False, server_default='squadron'),
        sa.Column('display_name', sa.String(80), nullable=False),
        sa.Column('normalised_name', sa.String(80), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_session_status_reason_tags_squadron_id', 'session_status_reason_tags', ['squadron_id'])
    op.create_index('ix_session_status_reason_tags_normalised_name', 'session_status_reason_tags', ['normalised_name'])
    op.create_index('ix_session_status_reason_tags_wing_id', 'session_status_reason_tags', ['wing_id'])

    table = sa.table(
        'session_status_reason_tags',
        sa.column('id', sa.String),
        sa.column('scope', sa.String),
        sa.column('display_name', sa.String),
        sa.column('normalised_name', sa.String),
        sa.column('is_active', sa.Boolean),
    )
    op.bulk_insert(table, [
        {
            "id": str(uuid.uuid4()),
            "scope": "global",
            "display_name": name,
            "normalised_name": name.strip().lower(),
            "is_active": True,
        }
        for name in _GLOBAL_SEED_REASONS
    ])


def downgrade():
    op.drop_index('ix_session_status_reason_tags_wing_id', table_name='session_status_reason_tags')
    op.drop_index('ix_session_status_reason_tags_normalised_name', table_name='session_status_reason_tags')
    op.drop_index('ix_session_status_reason_tags_squadron_id', table_name='session_status_reason_tags')
    op.drop_table('session_status_reason_tags')
