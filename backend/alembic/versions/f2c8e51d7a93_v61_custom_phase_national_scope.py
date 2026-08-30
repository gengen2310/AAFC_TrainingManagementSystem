"""v61 — attribute national-scoped custom training phases to their national

No schema change. custom_training_phases already carries the polymorphic scope
pair (scope_type, scope_id); the router simply discarded scope_id for
scope_type = 'national', so every national saw every other national's phases.

This backfills scope_id for those rows, but ONLY when the attribution is
unambiguous -- that is, when exactly one NationalEntity exists, in which case
every existing national-scoped row provably belongs to it.

With two or more nationals the row itself records nothing about who created it.
The migration then leaves scope_id NULL and prints a warning rather than
guessing: a NULL reads as "visible to every national", which is exactly the
pre-v61 behaviour, so nothing changes for those rows and nothing is silently
misfiled. They need a human decision, not a heuristic.

scope_type = 'system' is deliberately untouched. It means installation-wide,
above any one national, and carries no scope_id by design.

Revision ID: f2c8e51d7a93
Revises: e9b2d47a1c05
Create Date: 2026-08-30
"""
import sqlalchemy as sa
from alembic import op

revision = "f2c8e51d7a93"
down_revision = "e9b2d47a1c05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    unattributed = conn.execute(sa.text(
        "SELECT COUNT(*) FROM custom_training_phases "
        "WHERE scope_type = 'national' AND scope_id IS NULL"
    )).scalar() or 0
    if not unattributed:
        return

    nationals = conn.execute(sa.text(
        "SELECT id FROM national_entities ORDER BY id"
    )).fetchall()

    if len(nationals) == 1:
        conn.execute(sa.text(
            "UPDATE custom_training_phases SET scope_id = :nid "
            "WHERE scope_type = 'national' AND scope_id IS NULL"
        ), {"nid": nationals[0][0]})

        remaining = conn.execute(sa.text(
            "SELECT COUNT(*) FROM custom_training_phases "
            "WHERE scope_type = 'national' AND scope_id IS NULL"
        )).scalar() or 0
        if remaining:
            raise RuntimeError(
                f"v61 backfill left {remaining} national-scoped phase(s) "
                f"unattributed despite exactly one national entity existing"
            )
        print(f"[v61] attributed {unattributed} national-scoped phase(s) "
              f"to {nationals[0][0]}")
    else:
        print(
            f"[v61] WARNING: {unattributed} national-scoped custom training "
            f"phase(s) have no scope_id, and {len(nationals)} national "
            f"entities exist. Their owner cannot be derived from the row, so "
            f"they are left NULL and remain visible to every national -- "
            f"unchanged from before this migration. Assign each one a "
            f"national by hand, then re-check: "
            f"SELECT id, name FROM custom_training_phases "
            f"WHERE scope_type = 'national' AND scope_id IS NULL;"
        )


def downgrade() -> None:
    # Restore the pre-v61 shape: national scope carried no scope_id.
    op.get_bind().execute(sa.text(
        "UPDATE custom_training_phases SET scope_id = NULL "
        "WHERE scope_type = 'national'"
    ))
