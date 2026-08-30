"""v61 — national scope for the five user-creatable reference-data tag tables

Adds national_id to subject_area_tags, facilitator_type_tags,
session_status_reason_tags, activity_type_tags and
training_area_capability_tags.

"global" on these tables meant global across the whole installation. With more
than one NationalEntity that is a cross-tenant leak, so scope "global" now
means "global within one national entity" and national_id records which.

Backfill derives the national through the org tree (squadron -> wing ->
national, or wing -> national) for wing- and squadron-scoped rows. Global rows
are deliberately left NULL: there is no way to recover which national created
one, and a NULL reads as "visible to every national", which is exactly the
pre-v60 behaviour. Narrowing them by guessing would silently hide reference
data that squadrons are using today.

Revision ID: e9b2d47a1c05
Revises: c3a7f2e91b48
Create Date: 2026-08-30
"""
import sqlalchemy as sa
from alembic import op

revision = "e9b2d47a1c05"
# Re-parented 2026-08-30 onto 439ed68a5796, the migration that merges the
# Phase B and account-recovery heads. This chain was written against
# c3a7f2e91b48 (v59) before Phase B landed on main; leaving it there would
# leave the versions directory with two heads and "alembic upgrade head"
# would refuse to run. Safe to re-parent because no environment has ever
# applied this revision.
down_revision = "439ed68a5796"
branch_labels = None
depends_on = None

TAG_TABLES = (
    "subject_area_tags",
    "facilitator_type_tags",
    "session_status_reason_tags",
    "activity_type_tags",
    "training_area_capability_tags",
)


def upgrade() -> None:
    conn = op.get_bind()
    for table in TAG_TABLES:
        with op.batch_alter_table(table) as b:
            b.add_column(sa.Column("national_id", sa.String(36), nullable=True))
        op.create_index(f"ix_{table}_national_id", table, ["national_id"])

        # squadron-scoped rows: squadron -> wing -> national
        conn.execute(sa.text(f"""
            UPDATE {table} SET national_id = (
                SELECT w.national_id FROM squadrons s
                JOIN wings w ON w.id = s.wing_id
                WHERE s.id = {table}.squadron_id
            )
            WHERE national_id IS NULL AND squadron_id IS NOT NULL
        """))
        # wing-scoped rows: wing -> national
        conn.execute(sa.text(f"""
            UPDATE {table} SET national_id = (
                SELECT w.national_id FROM wings w WHERE w.id = {table}.wing_id
            )
            WHERE national_id IS NULL AND wing_id IS NOT NULL
        """))

    # Self-verify: no wing- or squadron-scoped row may be left unattributed
    # while its org row exists. A miss here means the backfill silently failed
    # and the scope filter would then treat the row as national-agnostic.
    for table in TAG_TABLES:
        orphans = conn.execute(sa.text(f"""
            SELECT COUNT(*) FROM {table} t
            WHERE t.national_id IS NULL
              AND (
                (t.squadron_id IS NOT NULL
                 AND EXISTS (SELECT 1 FROM squadrons s
                             JOIN wings w ON w.id = s.wing_id
                             WHERE s.id = t.squadron_id))
                OR
                (t.squadron_id IS NULL AND t.wing_id IS NOT NULL
                 AND EXISTS (SELECT 1 FROM wings w WHERE w.id = t.wing_id))
              )
        """)).scalar()
        if orphans:
            raise RuntimeError(
                f"v60 backfill left {orphans} row(s) in {table} without a "
                f"national_id despite a resolvable org chain"
            )


def downgrade() -> None:
    for table in TAG_TABLES:
        op.drop_index(f"ix_{table}_national_id", table_name=table)
        with op.batch_alter_table(table) as b:
            b.drop_column("national_id")
