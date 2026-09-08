"""v68: CadetSessionOutcome, rescheduled_to_session_id, CadetMemberImportBatch.

Adds:
  - sessions.rescheduled_to_session_id (nullable string, no DB FK for SQLite compat)
  - cadet_session_outcomes table (per-cadet per-session completion tracking)
  - cadet_member_import_batches table (CEA member upsert import with rollback delta)

Revision ID: f842d63a1d6c
Revises: d61e0844186f
Create Date: 2026-09-07
"""
from alembic import op
import sqlalchemy as sa

revision = "f842d63a1d6c"
down_revision = "d61e0844186f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── sessions.rescheduled_to_session_id ──────────────────────────────────
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.add_column(sa.Column(
            "rescheduled_to_session_id", sa.String(36), nullable=True, index=True
        ))

    # ── cadet_session_outcomes ───────────────────────────────────────────────
    op.create_table(
        "cadet_session_outcomes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.String(30), nullable=True),
        sa.Column("updated_at", sa.String(30), nullable=True),
        sa.Column("cadet_id", sa.String(36), nullable=False, index=True),
        sa.Column("session_id", sa.String(36), nullable=False, index=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("completion_date", sa.String(10), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="derived"),
        sa.Column("override_reason", sa.Text, nullable=True),
        sa.Column("changed_by", sa.String(36), nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.UniqueConstraint("cadet_id", "session_id", name="uq_cadet_session_outcome"),
    )

    # ── cadet_member_import_batches ──────────────────────────────────────────
    op.create_table(
        "cadet_member_import_batches",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.String(30), nullable=True),
        sa.Column("updated_at", sa.String(30), nullable=True),
        sa.Column("squadron_id", sa.String(36), nullable=False, index=True),
        sa.Column("imported_by", sa.String(36), nullable=False),
        sa.Column("source_file_name", sa.String(260), nullable=True),
        sa.Column("row_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("new_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("update_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("unchanged_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("committed", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("rollback_status", sa.String(20), nullable=True),
        sa.Column("import_delta", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("cadet_member_import_batches")
    op.drop_table("cadet_session_outcomes")
    with op.batch_alter_table("sessions") as batch_op:
        batch_op.drop_column("rescheduled_to_session_id")