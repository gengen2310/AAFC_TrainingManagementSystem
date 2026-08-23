"""REM-134: one ACTIVE planning year per (unit, year)

Nothing stopped a squadron accumulating duplicate years: the plain create
endpoint had no duplicate check, only /rollover returned 409. A dev database
reached 33 copies of a single year that way.

Scoped to ACTIVE rows deliberately. active_status=false is this system's archive
state for a planning year, and archiving is the normal operational action
(capability-preservation.md). A blanket unique index would make "archive the
badly set up 2026 year, then create a correct one" impossible, and would force
DELETEs against live production rows to deploy at all -- every duplicate found in
production on 2026-08-23 was active.

unit_id is NULL for wing and national years, and both SQLite and PostgreSQL treat
NULLs as distinct in a unique index, so those rows stay unconstrained. That is
correct: they are not squadron-scoped.

This migration refuses to run when duplicate ACTIVE rows exist rather than
choosing a survivor. Duplicate years own parade nights and sessions, so resolving
them is an operational decision. Archive the surplus -- archived rows do not
participate in this index -- rather than deleting anything.

Revision ID: b4c1f7d92e08
Revises: 0ae75ee5aed6
"""
from alembic import op
import sqlalchemy as sa

revision = "b4c1f7d92e08"
down_revision = "0ae75ee5aed6"
branch_labels = None
depends_on = None

INDEX = "uq_planning_years_unit_year_active"


def _refuse_if_duplicates(conn):
    dupes = conn.execute(sa.text(
        "SELECT unit_id, year, COUNT(*) AS n FROM planning_years "
        "WHERE unit_id IS NOT NULL AND active_status = :yes "
        "GROUP BY unit_id, year HAVING COUNT(*) > 1"
    ), {"yes": True}).fetchall()
    if not dupes:
        return
    detail = ", ".join(f"unit {r[0]} year {r[1]} x{r[2]}" for r in dupes[:10])
    more = f" (+{len(dupes) - 10} more)" if len(dupes) > 10 else ""
    raise RuntimeError(
        f"REM-134: {len(dupes)} duplicate ACTIVE (unit_id, year) group(s) block this "
        f"migration: {detail}{more}. Resolve them by ARCHIVING the surplus rows "
        "(active_status = false); deletion is neither required nor recommended, since "
        "archived rows do not participate in this index. Run "
        "`python tools/data-quality/planning_year_audit.py` to see which row in each "
        "group carries data, then re-run `alembic upgrade head`."
    )


def upgrade():
    conn = op.get_bind()
    _refuse_if_duplicates(conn)
    op.create_index(
        INDEX, "planning_years", ["unit_id", "year"],
        unique=True,
        sqlite_where=sa.text("active_status = 1"),
        postgresql_where=sa.text("active_status = true"),
    )


def downgrade():
    op.drop_index(INDEX, table_name="planning_years")
