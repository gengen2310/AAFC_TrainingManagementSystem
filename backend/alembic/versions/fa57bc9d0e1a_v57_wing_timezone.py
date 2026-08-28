"""v57 — wings.timezone (IANA string for rollover localisation)

Revision ID: fa57bc9d0e1a
Revises: e2f3a4b5c6d7
Create Date: 2026-08-28
"""
from alembic import op
import sqlalchemy as sa

revision = "fa57bc9d0e1a"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("wings") as batch_op:
        batch_op.add_column(sa.Column("timezone", sa.String(60), nullable=True))

    # Backfill EVERY existing wing, not just 7WG.
    #
    # The original comment here said "production has exactly one wing (7WG)",
    # which is true of production and false of staging: staging holds 15 wings,
    # including ten LVW* load-test wings with 12 squadrons each. get_wing_timezone
    # raises on NULL by design -- correctly, since a wrong zone is invisible in
    # date arithmetic -- and that raise reaches every endpoint that resolves a
    # year. A 7WG-only backfill therefore 500s roughly 120 squadrons the moment
    # the deploy completes.
    #
    # Backfilling rows that predate the column is not the silent defaulting the
    # fail-loudly rule forbids: the value is written to the row, visible and
    # editable, and a wing that is not actually in Perth can be corrected. New
    # wings are unaffected -- there is deliberately no server_default.
    bind = op.get_bind()
    bind.execute(sa.text(
        "UPDATE wings SET timezone = 'Australia/Perth' WHERE timezone IS NULL"))

    left = bind.execute(
        sa.text("SELECT count(*) FROM wings WHERE timezone IS NULL")).scalar()
    if left:
        raise RuntimeError(
            f"{left} wing(s) still have no timezone after the backfill; refusing "
            f"to complete a deploy that leaves those wings' squadrons unable to "
            f"resolve a training year."
        )


def downgrade():
    with op.batch_alter_table("wings") as batch_op:
        batch_op.drop_column("timezone")
