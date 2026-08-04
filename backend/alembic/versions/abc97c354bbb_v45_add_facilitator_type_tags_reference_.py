"""v45 add facilitator_type_tags reference data

Remediation program Section 6, Stage 3: governed reference data for
Facilitator Type, mirroring subject_area_tags' exact shape (v39).
Facilitator.type stays free-text (no FK, no migration to existing rows) --
display_name here IS the stored value, matching subject_area_tags'
own convention (no separate code/label split). Seeded with the exact
short codes connected-frontend's #fac-type <select> already uses as its
option VALUES (not its display text, which is more descriptive) --
"Officer"/"NCO"/"Senior Cadet"/"Civilian" -- plus "Staff", the
Facilitator.type column's actual default and the value already used by
most seeded/demo facilitator records (confirmed: "Officer"/"NCO" are
essentially unused in real data; "Staff" is the common case). Seeding
the descriptive long-form text instead would have silently orphaned
every existing "Staff" facilitator from the new reference list.

Revision ID: abc97c354bbb
Revises: b99b8f07eded
Create Date: 2026-08-05 00:20:54.306280
"""
import uuid
from alembic import op
import sqlalchemy as sa

revision = 'abc97c354bbb'
down_revision = 'b99b8f07eded'
branch_labels = None
depends_on = None

_GLOBAL_SEED_TYPES = [
    "Staff",
    "Officer",
    "NCO",
    "Senior Cadet",
    "Civilian",
]


def upgrade():
    op.create_table(
        'facilitator_type_tags',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('squadron_id', sa.String(36), nullable=True),
        sa.Column('wing_id', sa.String(36), nullable=True),
        sa.Column('scope', sa.String(20), nullable=False, server_default='squadron'),
        sa.Column('display_name', sa.String(80), nullable=False),
        sa.Column('normalised_name', sa.String(80), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_facilitator_type_tags_squadron_id', 'facilitator_type_tags', ['squadron_id'])
    op.create_index('ix_facilitator_type_tags_normalised_name', 'facilitator_type_tags', ['normalised_name'])
    op.create_index('ix_facilitator_type_tags_wing_id', 'facilitator_type_tags', ['wing_id'])

    table = sa.table(
        'facilitator_type_tags',
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
        for name in _GLOBAL_SEED_TYPES
    ])


def downgrade():
    op.drop_index('ix_facilitator_type_tags_wing_id', table_name='facilitator_type_tags')
    op.drop_index('ix_facilitator_type_tags_normalised_name', table_name='facilitator_type_tags')
    op.drop_index('ix_facilitator_type_tags_squadron_id', table_name='facilitator_type_tags')
    op.drop_table('facilitator_type_tags')
