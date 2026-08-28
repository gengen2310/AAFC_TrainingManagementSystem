"""v57 — wings.timezone (IANA zone for the wing-local calendar year)

Revision ID: a7c4e91b2f60
Revises: e2f3a4b5c6d7
Create Date: 2026-08-28
"""
import sqlalchemy as sa
from alembic import op

revision = "a7c4e91b2f60"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("wings") as b:
        b.add_column(sa.Column("timezone", sa.String(64), nullable=True))

    # Backfill EVERY existing wing, not just 7WG. A wing left NULL makes
    # wing_timezone raise, and that raise reaches every endpoint deriving the
    # current year -- setup status, the year listing, year-context, and every
    # year-scoped write -- as a 500 for all of that wing's squadrons. Staging
    # holds 15 wings, ten of them with 12 squadrons each; a 7WG-only backfill
    # would have taken most of it down on deploy.
    #
    # This is a one-time decision for rows that predate the column and have no
    # other source of truth, and the value is stored, visible and editable. It
    # is NOT the silent defaulting wing_timezone refuses: that refusal is about
    # date arithmetic at runtime, where a wrong zone is invisible. A wing that
    # is not actually in Perth must be corrected, and now can be.
    #
    # Deliberately no server_default: a NEW wing gets its zone explicitly from
    # timezone_for_new_wing at creation, not silently from the column.
    op.execute("UPDATE wings SET timezone = 'Australia/Perth' WHERE timezone IS NULL")

    left = op.get_bind().execute(
        sa.text("SELECT count(*) FROM wings WHERE timezone IS NULL")).scalar()
    if left:
        raise RuntimeError(
            f"{left} wing(s) still have no timezone after the backfill; refusing "
            f"to leave a deploy where those wings' squadrons cannot resolve a "
            f"training year.")


def downgrade() -> None:
    with op.batch_alter_table("wings") as b:
        b.drop_column("timezone")
