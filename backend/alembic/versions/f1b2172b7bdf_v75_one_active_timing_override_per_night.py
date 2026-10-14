"""v75: one ACTIVE timing override per parade night (fix v55/821e).

v8 created UNIQUE(parade_night_id) as uq_pnto_parade_night_id. v55 meant to
replace it with a partial unique index (active rows only) so "set or replace"
(archive the active override, insert the new one) works. Its PostgreSQL branch
dropped parade_night_timing_overrides_parade_night_id_key -- a name that never
existed -- so the FULL unique survived on PostgreSQL and every replacement
failed with a duplicate key. Migration 821e then dropped the partial index on
every dialect, leaving SQLite with no uniqueness at all.

This drops the stray full unique (PostgreSQL) and creates the intended
partial unique index on both dialects. Safe on existing data: the full unique
already allowed at most one row per night on PostgreSQL, so at most one is
active.

Revision ID: f1b2172b7bdf
Revises: 3391f31e0ba2
"""
from alembic import op
import sqlalchemy as sa

revision = "f1b2172b7bdf"
down_revision = "3391f31e0ba2"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("ALTER TABLE parade_night_timing_overrides "
                           "DROP CONSTRAINT IF EXISTS uq_pnto_parade_night_id"))
        op.execute(sa.text("DROP INDEX IF EXISTS uq_pnto_parade_night_id"))
    op.execute(sa.text("DROP INDEX IF EXISTS uq_pnto_active_per_night"))
    op.create_index("uq_pnto_active_per_night", "parade_night_timing_overrides", ["parade_night_id"],
                    unique=True,
                    postgresql_where=sa.text("NOT is_archived"),
                    sqlite_where=sa.text("NOT is_archived"))


def downgrade():
    op.drop_index("uq_pnto_active_per_night", table_name="parade_night_timing_overrides")
