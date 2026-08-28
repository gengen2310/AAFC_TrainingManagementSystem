"""v59 — replace planning_years per-year-number unique index with per-squadron index

OLD index: unique (unit_id, year) WHERE active_status — prevents two active 2026 rows
           but permits active-2026 + active-2027, which is how 6 squadrons accumulated
           duplicate active years (resolved via REM-156 before this migration runs).

NEW index: unique (unit_id) WHERE status='active' — at most one active year per squadron,
           regardless of year number.

Pre-flight: refuses to run if any squadron holds >1 active year.

Revision ID: e3693a06b1bd
Revises: b3e9c1f7a2d4
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa

revision = "e3693a06b1bd"
down_revision = "b3e9c1f7a2d4"
branch_labels = None
depends_on = None

_PREFLIGHT_SQL = """
    SELECT unit_id, COUNT(*) AS cnt
    FROM planning_years
    WHERE status = 'active' AND unit_id IS NOT NULL
    GROUP BY unit_id
    HAVING COUNT(*) > 1
"""


def upgrade():
    bind = op.get_bind()

    # Pre-flight: refuse if any squadron has >1 active year.
    conflicts = bind.execute(sa.text(_PREFLIGHT_SQL)).fetchall()
    if conflicts:
        unit_ids = [r[0] for r in conflicts]
        raise RuntimeError(
            f"Migration v59 aborted: the following squadrons hold more than one "
            f"active planning year: {unit_ids}. "
            "Resolve via the /archive or /promote endpoints before re-running."
        )

    # Drop the old per-(unit_id, year) index and replace with per-squadron index.
    # batch_alter_table handles SQLite's limited ALTER TABLE support.
    with op.batch_alter_table("planning_years") as batch_op:
        batch_op.drop_index("uq_planning_years_unit_year_active")
        batch_op.create_index(
            "uq_planning_years_unit_active",
            ["unit_id"],
            unique=True,
            postgresql_where=sa.text("status = 'active'"),
            sqlite_where=sa.text("status = 'active'"),
        )


def downgrade():
    with op.batch_alter_table("planning_years") as batch_op:
        batch_op.drop_index("uq_planning_years_unit_active")
        batch_op.create_index(
            "uq_planning_years_unit_year_active",
            ["unit_id", "year"],
            unique=True,
            postgresql_where=sa.text("active_status = true"),
            sqlite_where=sa.text("active_status = 1"),
        )
