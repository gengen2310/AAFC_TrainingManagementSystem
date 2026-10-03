"""v72: make recovery email a unique credential-reset destination.

Revision ID: c0e3a6b8d4f2
Revises: b9d2f5a7c3e1
Create Date: 2026-09-29

Legacy databases may contain duplicate recovery addresses from before the
one-address/one-account rule existed. Choosing one account arbitrarily would be
unsafe, so every duplicated address is cleared and must be re-verified by its
account holder. Unique enforcement then closes the concurrent-create race that
application-level prechecks alone cannot prevent.
"""
from alembic import op
import sqlalchemy as sa

revision = "c0e3a6b8d4f2"
down_revision = "b9d2f5a7c3e1"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    duplicates = bind.execute(sa.text(
        "SELECT recovery_email FROM users "
        "WHERE recovery_email IS NOT NULL "
        "GROUP BY recovery_email HAVING COUNT(*) > 1"
    )).scalars().all()

    for address in duplicates:
        bind.execute(sa.text(
            "UPDATE users SET "
            "recovery_email = NULL, "
            "recovery_email_verified_at = NULL, "
            "recovery_email_updated_at = NULL, "
            "recovery_email_updated_by = NULL "
            "WHERE recovery_email = :address"
        ), {"address": address})

    # v59 created ix_users_recovery_email as a normal index. Recreate the same
    # stable name as UNIQUE so SQLite and PostgreSQL enforce the same invariant.
    op.drop_index("ix_users_recovery_email", table_name="users")
    op.create_index(
        "ix_users_recovery_email", "users", ["recovery_email"], unique=True
    )


def downgrade():
    op.drop_index("ix_users_recovery_email", table_name="users")
    op.create_index(
        "ix_users_recovery_email", "users", ["recovery_email"], unique=False
    )
