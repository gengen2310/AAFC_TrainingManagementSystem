"""v62 — make the boolean flags NOT NULL, matching the model

The migrated schema and the ORM's own metadata disagreed on 68 columns, in one
direction: production was more permissive than the model. Most of that is
harmless -- a nullable created_at that every code path already guards.

Eight boolean flags are not harmless, because NULL changes query results rather
than merely permitting a bad value. SQL three-valued logic means a row with
is_archived = NULL matches neither `is_archived = false` nor `is_archived =
true`, so it disappears from every list that filters on it. The CEA activity
list does exactly that (routers/training.py: is_removed_from_cea == False AND
is_archived == False), so such a row would be silently invisible with no error
anywhere.

The model has always declared these non-optional with default False, and every
row is created through the ORM, so NULLs should not exist today -- this closes
the gap rather than repairing known damage. The backfill is there because
"should not exist" is not "cannot exist", and a server_default stops any future
raw-SQL path from reopening it.

Deliberately NOT included: the nullable created_at/updated_at columns and the
integer counters. Those diverge too, but NULL there yields a wrong display, not
a vanished row, and forcing NOT NULL on timestamps across a live database is a
much larger change than this one. They are tracked by
scripts/schema_parity.py's ratchet instead.

Revision ID: b7e3f9c24a81
Revises: f2c8e51d7a93
Create Date: 2026-08-30
"""
import sqlalchemy as sa
from alembic import op

revision = "b7e3f9c24a81"
down_revision = "f2c8e51d7a93"
branch_labels = None
depends_on = None

# (table, column) -- every one nullable in the migrated schema, NOT NULL with
# default False in the model, and filtered on somewhere with == False.
FLAGS = [
    ("activity_local_hides", "is_hidden"),
    ("activity_local_overrides", "is_hidden"),
    ("cea_activities", "audience_first_years"),
    ("cea_activities", "audience_proficient"),
    ("cea_activities", "audience_seniors"),
    ("cea_activities", "audience_staff_only"),
    ("cea_activities", "is_archived"),
    ("cea_activities", "is_removed_from_cea"),
]


def upgrade() -> None:
    conn = op.get_bind()
    for table, column in FLAGS:
        filled = conn.execute(sa.text(
            f"UPDATE {table} SET {column} = false WHERE {column} IS NULL"
        )).rowcount
        if filled:
            print(f"[v62] {table}.{column}: filled {filled} NULL(s) with false")
        with op.batch_alter_table(table) as b:
            b.alter_column(column, existing_type=sa.Boolean(),
                           server_default=sa.false(), nullable=False)

    for table, column in FLAGS:
        left = conn.execute(sa.text(
            f"SELECT COUNT(*) FROM {table} WHERE {column} IS NULL"
        )).scalar()
        if left:
            raise RuntimeError(f"v62 left {left} NULL(s) in {table}.{column}")


def downgrade() -> None:
    for table, column in FLAGS:
        with op.batch_alter_table(table) as b:
            b.alter_column(column, existing_type=sa.Boolean(),
                           server_default=None, nullable=True)
