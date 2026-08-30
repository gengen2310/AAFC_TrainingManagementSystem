"""v59 — account recovery: User.recovery_email* + recovery_tokens

Spec: docs/superpowers/specs/2026-08-29-account-recovery-design.md

No backfill. Existing System Administrators are deliberately NOT given an
address -- there is none to invent, and a fabricated one would be worse than
none. The gap is surfaced instead, via GET /api/setup/status.

Revision ID: c3a7f2e91b48
Revises: d5f81a3c9e27
Create Date: 2026-08-29
"""
import sqlalchemy as sa
from alembic import op

revision = "c3a7f2e91b48"
down_revision = "d5f81a3c9e27"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("recovery_email", sa.String(254), nullable=True))
        b.add_column(sa.Column("recovery_email_verified_at", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("recovery_email_updated_at", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("recovery_email_updated_by", sa.String(36), nullable=True))
    op.create_index("ix_users_recovery_email", "users", ["recovery_email"])

    op.create_table(
        "recovery_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        # SHA-256 hex. The raw token is never stored.
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(), nullable=True),
        sa.Column("created_ip", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        # TimestampMixin also carries created_by / updated_by. The repo's
        # schema-drift guards check every TimestampMixin table for them, and
        # caught their absence here.
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
    )
    op.create_index("ix_recovery_tokens_user_id", "recovery_tokens", ["user_id"])
    op.create_index("ix_recovery_tokens_token_hash", "recovery_tokens", ["token_hash"])
    op.create_index("ix_recovery_tokens_purpose", "recovery_tokens", ["purpose"])


def downgrade() -> None:
    op.drop_table("recovery_tokens")
    op.drop_index("ix_users_recovery_email", table_name="users")
    with op.batch_alter_table("users") as b:
        b.drop_column("recovery_email_updated_by")
        b.drop_column("recovery_email_updated_at")
        b.drop_column("recovery_email_verified_at")
        b.drop_column("recovery_email")
