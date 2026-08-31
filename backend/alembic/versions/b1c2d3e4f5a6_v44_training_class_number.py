"""v44 TrainingClass.sequence → class_number: canonical 1-based numbering with
UNIQUE(squadron_id, training_year_id, class_number).

Renames the existing sequence column (default 0) to class_number (default 1),
backfills 1-based numbers per (squadron_id, training_year_id) group ordered by
the prior sequence value then display_name, then adds the uniqueness constraint.

The backfill uses Python-level row iteration so it is identical on SQLite and
PostgreSQL — no CTE or ROW_NUMBER() that would fail on SQLite.

Revision ID: b1c2d3e4f5a6
Revises: z1a2b3c4d5e6
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from collections import defaultdict

revision = "b1c2d3e4f5a6"
down_revision = "b7f3c2e1d098"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # Step 1: rename sequence → class_number using batch_alter_table
    # (batch_alter_table is required for SQLite ALTER TABLE operations)
    with op.batch_alter_table("training_classes", recreate="auto") as batch_op:
        batch_op.alter_column(
            "sequence",
            new_column_name="class_number",
            existing_type=sa.Integer(),
            existing_nullable=False,
            existing_server_default="0",
            server_default="1",
        )

    # Step 2: backfill — assign 1-based canonical numbers per
    # (squadron_id, training_year_id) group, ordered by prior value then
    # display_name.  Rows already having a sensible positive value get
    # re-sequenced to close gaps; rows at 0 (the old default) sort last
    # within their group so they receive the highest numbers.
    rows = conn.execute(text(
        "SELECT id, squadron_id, training_year_id, class_number, display_name "
        "FROM training_classes ORDER BY squadron_id, training_year_id, class_number, display_name"
    )).fetchall()

    groups: dict[tuple, list] = defaultdict(list)
    for row in rows:
        key = (row.squadron_id, row.training_year_id)
        groups[key].append(row)

    for group_rows in groups.values():
        for idx, row in enumerate(group_rows, start=1):
            conn.execute(
                text("UPDATE training_classes SET class_number = :n WHERE id = :id"),
                {"n": idx, "id": row.id},
            )

    # Step 3: add the uniqueness constraint (batch_alter_table again)
    with op.batch_alter_table("training_classes", recreate="auto") as batch_op:
        batch_op.create_unique_constraint(
            "uq_training_class_number_per_year",
            ["squadron_id", "training_year_id", "class_number"],
        )


def downgrade() -> None:
    with op.batch_alter_table("training_classes", recreate="auto") as batch_op:
        batch_op.drop_constraint("uq_training_class_number_per_year", type_="unique")
        batch_op.alter_column(
            "class_number",
            new_column_name="sequence",
            existing_type=sa.Integer(),
            existing_nullable=False,
            existing_server_default="1",
            server_default="0",
        )
