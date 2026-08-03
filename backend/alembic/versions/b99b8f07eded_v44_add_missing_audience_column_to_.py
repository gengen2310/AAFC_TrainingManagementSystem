"""v44 add missing audience column to activities

The Activity model (app/models/training.py) has carried an `audience` JSON
column since commit 78a5e21, but no migration was ever written for it.
SQLite dev/test DBs never showed the gap because seed_all()'s reset_db()
rebuilds the schema straight from current model metadata, bypassing
Alembic. Environments migrated incrementally via `alembic upgrade head`
(production) are missing the column outright; environments rebuilt
wholesale via reset_db() + `alembic stamp head` (e.g. staging after a full
seed_all() run) already have it physically despite never running this
migration. Existence-checked so it's a safe no-op wherever the column is
already present, and a real additive fix where it's not.

Revision ID: b99b8f07eded
Revises: z1a2b3c4d5e6
Create Date: 2026-08-03 18:16:04.361120
"""
from alembic import op
import sqlalchemy as sa

revision = 'b99b8f07eded'
down_revision = 'z1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    cols = [c["name"] for c in sa.inspect(bind).get_columns("activities")]
    if "audience" not in cols:
        op.add_column("activities", sa.Column("audience", sa.JSON(), nullable=True))


def downgrade():
    bind = op.get_bind()
    cols = [c["name"] for c in sa.inspect(bind).get_columns("activities")]
    if "audience" in cols:
        op.drop_column("activities", "audience")
