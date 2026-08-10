"""v47 complete session_status_reason_tags preset list

REM-14 (original_instruction.md Section 12): the instruction's preset
reason list is facilitator unavailable / weather / venue unavailable /
equipment unavailable / insufficient numbers / higher-priority activity /
time lost / safety / administrative requirement / other. v46's seed
(d2520722f0f2) was missing "insufficient numbers" and "administrative
requirement", and used "Insufficient time" instead of "time lost". This
migration adds the two missing global reasons and renames the existing
"Insufficient time" row -- safe because display_name is a free-text
snapshot copied onto Session/SessionStatusHistory.reason at write time
(no FK), so renaming the reference row does not alter any historical
session's stored reason text.

Revision ID: b3f7a1c9d4e2
Revises: d2520722f0f2
Create Date: 2026-08-10
"""
import uuid
from alembic import op
import sqlalchemy as sa

revision = 'b3f7a1c9d4e2'
down_revision = 'd2520722f0f2'
branch_labels = None
depends_on = None

_NEW_GLOBAL_REASONS = [
    "Insufficient numbers",
    "Administrative requirement",
]


def upgrade():
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
        for name in _NEW_GLOBAL_REASONS
    ])
    op.execute(
        sa.text(
            "UPDATE session_status_reason_tags "
            "SET display_name = 'Time lost', normalised_name = 'time lost' "
            "WHERE scope = 'global' AND normalised_name = 'insufficient time'"
        )
    )


def downgrade():
    op.execute(
        sa.text(
            "UPDATE session_status_reason_tags "
            "SET display_name = 'Insufficient time', normalised_name = 'insufficient time' "
            "WHERE scope = 'global' AND normalised_name = 'time lost'"
        )
    )
    op.execute(
        sa.text(
            "DELETE FROM session_status_reason_tags "
            "WHERE scope = 'global' AND normalised_name IN ('insufficient numbers', 'administrative requirement')"
        )
    )
