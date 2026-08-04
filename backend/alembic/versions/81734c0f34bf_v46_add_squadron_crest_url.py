"""v46 add squadron crest_url

Remediation program Section 7, Stage 4. External URL only -- Railway's
filesystem is ephemeral and this codebase has no object storage
configured; a binary-upload crest feature would need a new
infrastructure dependency this migration deliberately avoids. Nullable,
additive, no backfill needed (existing squadrons simply have no crest
set, matching "default crest when none is uploaded" in the source
instruction).

Revision ID: 81734c0f34bf
Revises: abc97c354bbb
Create Date: 2026-08-05 00:51:11.985476
"""
from alembic import op
import sqlalchemy as sa

revision = '81734c0f34bf'
down_revision = 'abc97c354bbb'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('squadrons', sa.Column('crest_url', sa.String(500), nullable=True))


def downgrade():
    op.drop_column('squadrons', 'crest_url')
