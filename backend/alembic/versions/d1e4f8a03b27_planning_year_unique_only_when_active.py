"""REM-134 correction: the uniqueness rule applies to ACTIVE planning years only

b4c1f7d92e08 created a blanket unique index on (unit_id, year). Auditing the
deployed databases on 2026-08-23 showed why that was wrong:

  * active_status=false is this system's ARCHIVE state for a planning year, and
    archiving is the normal operational action (capability-preservation.md).
    A blanket constraint makes "archive the badly set up 2026 year, then create
    a correct one" impossible -- a real workflow, broken by the fix meant to
    protect it.
  * Every duplicate found in production was ACTIVE, across four squadrons. Under
    a blanket constraint the only way to deploy would have been to DELETE live
    rows. Scoped to active rows, the same duplicates can be resolved by
    archiving the empty ones, which is reversible.

The protection is unchanged for the case that motivated REM-134: a unit still
cannot hold two active years with the same number, so e2e runs cannot stack 33
copies of year 2064.

Revision ID: d1e4f8a03b27
Revises: c9d2a5b81f43
"""
from alembic import op
import sqlalchemy as sa

revision = "d1e4f8a03b27"
down_revision = "c9d2a5b81f43"
branch_labels = None
depends_on = None

_OLD = "uq_planning_years_unit_year"
_NEW = "uq_planning_years_unit_year_active"


def _partial_where(bind) -> str:
    # SQLite has no native boolean; it stores 0/1.
    return "active_status = true" if bind.dialect.name == "postgresql" else "active_status = 1"


def upgrade():
    conn = op.get_bind()

    # b4c1f7d92e08 may not have run yet in a given environment -- both staging
    # and production were behind it on 2026-08-23 -- so dropping is conditional.
    insp = sa.inspect(conn)
    existing = {ix["name"] for ix in insp.get_indexes("planning_years")}
    if _OLD in existing:
        op.drop_index(_OLD, table_name="planning_years")

    dupes = conn.execute(sa.text(
        "SELECT unit_id, year, COUNT(*) AS n FROM planning_years "
        "WHERE unit_id IS NOT NULL AND active_status = :true_val "
        "GROUP BY unit_id, year HAVING COUNT(*) > 1"
    ), {"true_val": True}).fetchall()
    if dupes:
        detail = ", ".join(f"unit {r[0]} year {r[1]} x{r[2]}" for r in dupes[:10])
        more = f" (+{len(dupes) - 10} more)" if len(dupes) > 10 else ""
        raise RuntimeError(
            f"REM-134: {len(dupes)} duplicate ACTIVE (unit_id, year) group(s) block this "
            f"migration: {detail}{more}. Resolve them by ARCHIVING the surplus rows "
            "(active_status = false) -- deletion is not required and not recommended, "
            "since archived rows no longer participate in this index. Run "
            "`python tools/data-quality/planning_year_audit.py` to see which row in each "
            "group carries parade dates, then re-run `alembic upgrade head`."
        )

    op.create_index(
        _NEW, "planning_years", ["unit_id", "year"],
        unique=True,
        sqlite_where=sa.text("active_status = 1"),
        postgresql_where=sa.text("active_status = true"),
    )


def downgrade():
    """Restore the blanket unique index b4c1f7d92e08 created.

    Checked BEFORE dropping anything. The blanket index cannot coexist with an
    archived-plus-active pair for the same year, which the partial index
    deliberately allows, so a naive drop-then-create leaves the table with
    neither index when it fails.
    """
    conn = op.get_bind()
    dupes = conn.execute(sa.text(
        "SELECT unit_id, year, COUNT(*) AS n FROM planning_years "
        "WHERE unit_id IS NOT NULL GROUP BY unit_id, year HAVING COUNT(*) > 1"
    )).fetchall()
    if dupes:
        detail = ", ".join(f"unit {r[0]} year {r[1]} x{r[2]}" for r in dupes[:10])
        raise RuntimeError(
            f"REM-134: cannot downgrade. {len(dupes)} (unit_id, year) group(s) have more "
            f"than one row once archived rows are counted: {detail}. The blanket index this "
            "downgrade restores does not permit that, and these rows are legitimate under "
            "the partial index. Resolve them first if you genuinely need the old index back."
        )

    insp = sa.inspect(conn)
    if _NEW in {ix["name"] for ix in insp.get_indexes("planning_years")}:
        op.drop_index(_NEW, table_name="planning_years")
    op.create_index(_OLD, "planning_years", ["unit_id", "year"], unique=True)
