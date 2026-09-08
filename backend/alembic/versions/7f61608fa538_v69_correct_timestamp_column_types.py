"""v69: correct timestamp column types for cadet_session_outcomes and cadet_member_import_batches.

v68 created cadet_session_outcomes and cadet_member_import_batches with
created_at/updated_at as String(30) instead of DateTime. This migration
converts those four columns to DateTime so they are compatible with the
UTCDateTime TypeDecorator used by TimestampMixin.

PostgreSQL uses ALTER COLUMN ... USING for data-preserving conversion.
SQLite uses Alembic batch recreation because SQLite cannot alter an existing
column declaration in place. Existing rows are copied into the recreated
tables; no database reset or schema stamping shortcut is used.

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
_TIMESTAMP_COLUMNS = ("created_at", "updated_at")


def _sqlite_change_timestamp_type(*, to_datetime: bool) -> None:
    """Recreate the v68 tables with the requested timestamp declaration.

    ``recreate="always"`` is deliberate: SQLite has no supported in-place
    ALTER COLUMN type operation. Alembic reflects the full table, creates a
    temporary replacement, copies data verbatim, then swaps it into place.
    This preserves rows, indexes, and constraints while changing only the
    declared type of the four timestamp columns.
    """
    source_type = sa.String(length=30) if to_datetime else sa.DateTime()
    target_type = sa.DateTime() if to_datetime else sa.String(length=30)

    for table in _TABLES:
        with op.batch_alter_table(table, recreate="always") as batch_op:
            for col in _TIMESTAMP_COLUMNS:
                batch_op.alter_column(
                    col,
                    existing_type=source_type,
                    type_=target_type,
                    existing_nullable=True,
                )


def _postgresql_change_timestamp_type(*, to_datetime: bool) -> None:
    bind = op.get_bind()
    target_sql = "TIMESTAMP" if to_datetime else "VARCHAR(30)"
    using_sql = "{col}::TIMESTAMP" if to_datetime else "{col}::TEXT"

    tables = _TABLES if to_datetime else reversed(_TABLES)
    for table in tables:
        for col in _TIMESTAMP_COLUMNS:
            bind.execute(sa.text(
                f"ALTER TABLE {table} "
                f"ALTER COLUMN {col} TYPE {target_sql} "
                f"USING {using_sql.format(col=col)}"
            ))


def upgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        _sqlite_change_timestamp_type(to_datetime=True)
        return
    if dialect == "postgresql":
        _postgresql_change_timestamp_type(to_datetime=True)
        return

    for table in _TABLES:
        for col in _TIMESTAMP_COLUMNS:
            op.alter_column(
                table,
                col,
                existing_type=sa.String(length=30),
                type_=sa.DateTime(),
                existing_nullable=True,
            )


def downgrade() -> None:
    dialect = op.get_bind().dialect.name
    if dialect == "sqlite":
        _sqlite_change_timestamp_type(to_datetime=False)
        return
    if dialect == "postgresql":
        _postgresql_change_timestamp_type(to_datetime=False)
        return

    for table in reversed(_TABLES):
        for col in _TIMESTAMP_COLUMNS:
            op.alter_column(
                table,
                col,
                existing_type=sa.DateTime(),
                type_=sa.String(length=30),
                existing_nullable=True,
            )
