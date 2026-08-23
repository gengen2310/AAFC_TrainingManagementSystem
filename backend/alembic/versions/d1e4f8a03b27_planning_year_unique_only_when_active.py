"""REM-134 reconciliation: retire the blanket index some databases already have

An earlier version of b4c1f7d92e08 created a BLANKET unique index on
(unit_id, year), named uq_planning_years_unit_year. Rehearsing the production
upgrade on 2026-08-23 showed that chain could not be traversed: staging and
production both sit BELOW b4c1f7d92e08, so they had to pass through the blanket
check, and it counts archived rows. Archiving the duplicates -- the whole point
of scoping to active rows -- did not unblock them. b4c1f7d92e08 was corrected in
place, which is safe because no deployed environment had applied it.

Development databases that applied the earlier version still carry the blanket
index. This migration retires it and makes sure the partial one exists, so both
histories converge. On a database that took the corrected b4c1f7d92e08 it is a
no-op.

Revision ID: d1e4f8a03b27
Revises: c9d2a5b81f43
"""
from alembic import op
import sqlalchemy as sa

revision = "d1e4f8a03b27"
down_revision = "c9d2a5b81f43"
branch_labels = None
depends_on = None

OLD = "uq_planning_years_unit_year"
NEW = "uq_planning_years_unit_year_active"


def upgrade():
    conn = op.get_bind()
    existing = {ix["name"] for ix in sa.inspect(conn).get_indexes("planning_years")}

    if OLD in existing:
        op.drop_index(OLD, table_name="planning_years")

    if NEW not in existing:
        dupes = conn.execute(sa.text(
            "SELECT unit_id, year, COUNT(*) FROM planning_years "
            "WHERE unit_id IS NOT NULL AND active_status = :yes "
            "GROUP BY unit_id, year HAVING COUNT(*) > 1"
        ), {"yes": True}).fetchall()
        if dupes:
            detail = ", ".join(f"unit {r[0]} year {r[1]} x{r[2]}" for r in dupes[:10])
            raise RuntimeError(
                f"REM-134: {len(dupes)} duplicate ACTIVE (unit_id, year) group(s) block "
                f"this migration: {detail}. Archive the surplus rows and re-run."
            )
        op.create_index(
            NEW, "planning_years", ["unit_id", "year"],
            unique=True,
            sqlite_where=sa.text("active_status = 1"),
            postgresql_where=sa.text("active_status = true"),
        )


def downgrade():
    # Nothing to undo: the partial index belongs to b4c1f7d92e08, and the blanket
    # index this retires is not something to restore.
    pass
