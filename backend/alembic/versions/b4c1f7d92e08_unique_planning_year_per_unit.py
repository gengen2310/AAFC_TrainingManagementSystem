"""REM-134: one planning year per (unit, year)

Nothing stopped a squadron accumulating duplicate planning years: the plain
create endpoint had no duplicate check (only /rollover returned 409). Local
dev databases reached 33 copies of a single year that way.

unit_id is NULL for wing/national years. SQLite and PostgreSQL both treat NULLs
as distinct in a unique index, so those rows stay unconstrained -- deliberately,
since they are not squadron-scoped.

This migration refuses to run against data it would have to destroy. Duplicate
planning years own parade nights, sessions and long-range entries, so picking a
survivor is an operational decision, not a schema one. Run
`python tools/data-quality/planning_year_audit.py` to see the groups and their
referencing rows, resolve them, then re-run the upgrade.

Revision ID: b4c1f7d92e08
Revises: 0ae75ee5aed6
"""
from alembic import op
import sqlalchemy as sa

revision = "b4c1f7d92e08"
down_revision = "0ae75ee5aed6"
branch_labels = None
depends_on = None

_INDEX = "uq_planning_years_unit_year"


def upgrade():
    conn = op.get_bind()
    dupes = conn.execute(sa.text(
        "SELECT unit_id, year, COUNT(*) AS n FROM planning_years "
        "WHERE unit_id IS NOT NULL GROUP BY unit_id, year HAVING COUNT(*) > 1"
    )).fetchall()
    if dupes:
        detail = ", ".join(f"unit {r[0]} year {r[1]} x{r[2]}" for r in dupes[:10])
        more = f" (+{len(dupes) - 10} more)" if len(dupes) > 10 else ""
        raise RuntimeError(
            f"REM-134: {len(dupes)} duplicate (unit_id, year) group(s) block this "
            f"migration: {detail}{more}. These rows own parade nights and sessions, "
            "so this migration will not choose which to keep. Run "
            "`python tools/data-quality/planning_year_audit.py` to review them, "
            "resolve the duplicates, then re-run `alembic upgrade head`."
        )
    op.create_index(_INDEX, "planning_years", ["unit_id", "year"], unique=True)


def downgrade():
    op.drop_index(_INDEX, table_name="planning_years")
