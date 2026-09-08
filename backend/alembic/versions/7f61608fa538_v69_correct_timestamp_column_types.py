"""v69: correct timestamp column types for cadet_session_outcomes and cadet_member_import_batches.

v68 created cadet_session_outcomes and cadet_member_import_batches with
created_at/updated_at as String(30) instead of DateTime. This migration
converts those four columns to DateTime so they are compatible with the
UTCDateTime TypeDecorator used by TimestampMixin.

PostgreSQL: ALTER COLUMN with a USING clause to cast existing ISO-8601
string values to TIMESTAMP. SQLite: no-op (SQLite is dynamically typed
so the ORM reads String(30)-stored values correctly via UTCDateTime, and
the local test database is always rebuilt from ORM metadata, never from
this migration path).

Revision ID: 7f61608fa538
Revises: f842d63a1d6c
Create Date: 2026-09-08
"""
from alembic import op
import sqlalchemy as sa

revision = "7f61608fa538"
down_revision = "f842d63a1d6c"
branch_labels = None
depends_on = None

_TABLES = ("cadet_session_outcomes", "cadet_member_import_batches")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return  # SQLite is dynamically typed; no column change needed

    for table in _TABLES:
        for col in ("created_at", "updated_at"):
            bind.execute(sa.text(
                f"ALTER TABLE {table} "
                f"ALTER COLUMN {col} TYPE TIMESTAMP "
                f"USING {col}::TIMESTAMP"
            ))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    for table in reversed(_TABLES):
        for col in ("created_at", "updated_at"):
            bind.execute(sa.text(
                f"ALTER TABLE {table} "
                f"ALTER COLUMN {col} TYPE VARCHAR(30) "
                f"USING {col}::TEXT"
            ))
