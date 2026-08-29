"""v58 — renumber 708's container from 2027 to 2026 (user decision 2026-08-28)

708's only live container is numbered 2027 and holds all 15 of its parade dates
in 2026. The dates are authoritative, so the container is renumbered. This is
the one case where a year integer is changed, and it happens because a human
decided it -- never by inference.

The guard is not decoration. If the row is not in exactly the state that
decision was made about, this refuses rather than renumbering something else.

Revision ID: d5f81a3c9e27
Revises: a7c4e91b2f60
Create Date: 2026-08-28
"""
import sqlalchemy as sa
from alembic import op

revision = "d5f81a3c9e27"
down_revision = "a7c4e91b2f60"
branch_labels = None
depends_on = None

TARGET = "b482b6ed-6e45-4158-b8fb-b169782dd72a"


def upgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(sa.text(
        "SELECT year, "
        "(SELECT count(*) FROM parade_dates WHERE planning_year_id = :i), "
        "(SELECT count(*) FROM parade_dates WHERE planning_year_id = :i "
        "   AND parade_date NOT LIKE '2026-%') "
        "FROM planning_years WHERE id = :i"), {"i": TARGET}).first()
    if row is None:
        return          # not this database (dev, test, a fresh deploy)
    year, dates, non_2026 = row
    if (year, dates, non_2026) != (2027, 15, 0):
        raise RuntimeError(
            f"708's container is not in the state the decision was made about "
            f"(year={year}, dates={dates}, non-2026 dates={non_2026}). "
            f"Refusing to renumber. Run tools/data-quality/year_container_audit.py."
        )
    # conn.execute, NOT op.execute: Alembic's op.execute() takes no parameter
    # dict, so op.execute(text, params) raises TypeError at runtime. The unit
    # tests missed it because their op.execute double accepted params -- a
    # double that is more permissive than the real API hides exactly this.
    conn.execute(sa.text(
        "UPDATE planning_years SET year = 2026, name = '2026 Training Year' "
        "WHERE id = :i"), {"i": TARGET})


def downgrade() -> None:
    op.get_bind().execute(sa.text(
        "UPDATE planning_years SET year = 2027, "
        "name = '2026 Training Year → 2027' WHERE id = :i"), {"i": TARGET})
