"""v69: correct timestamp column types for cadet_session_outcomes and cadet_member_import_batches.

v68 created cadet_session_outcomes and cadet_member_import_batches with
created_at/updated_at as String(30) instead of DateTime. This migration
converts those four columns to DateTime so they are compatible with the
UTCDateTime TypeDecorator used by TimestampMixin.

PostgreSQL uses ALTER COLUMN ... USING for data-preserving conversion.
SQLite recreates the two v68 tables explicitly and copies timestamp values
without CAST.  This detail matters: SQLite's ``CAST(text AS DATETIME)`` applies
numeric affinity, so a value such as ``2026-09-08 01:02:03.123456`` becomes the
integer ``2026``.  Direct INSERT ... SELECT into a DATETIME-declared column
preserves the full ISO timestamp text while changing the declared schema type.
No database reset or schema-stamping shortcut is used.

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

_OUTCOME_COLUMNS = (
    "id",
    "created_at",
    "updated_at",
    "cadet_id",
    "session_id",
    "status",
    "completion_date",
    "source",
    "override_reason",
    "changed_by",
    "version",
    "created_by",
    "updated_by",
)

_IMPORT_BATCH_COLUMNS = (
    "id",
    "created_at",
    "updated_at",
    "squadron_id",
    "imported_by",
    "source_file_name",
    "row_count",
    "new_count",
    "update_count",
    "unchanged_count",
    "error_count",
    "committed",
    "rollback_status",
    "import_delta",
    "created_by",
    "updated_by",
)


def _timestamp_type(*, to_datetime: bool) -> sa.types.TypeEngine:
    return sa.DateTime() if to_datetime else sa.String(length=30)


def _create_sqlite_outcomes_table(name: str, *, to_datetime: bool) -> None:
    timestamp_type = _timestamp_type(to_datetime=to_datetime)
    op.create_table(
        name,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", timestamp_type, nullable=True),
        sa.Column("updated_at", _timestamp_type(to_datetime=to_datetime), nullable=True),
        sa.Column("cadet_id", sa.String(36), nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
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


def _create_sqlite_import_batches_table(name: str, *, to_datetime: bool) -> None:
    timestamp_type = _timestamp_type(to_datetime=to_datetime)
    op.create_table(
        name,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", timestamp_type, nullable=True),
        sa.Column("updated_at", _timestamp_type(to_datetime=to_datetime), nullable=True),
        sa.Column("squadron_id", sa.String(36), nullable=False),
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


def _copy_table_verbatim(source: str, target: str, columns: tuple[str, ...]) -> None:
    """Copy rows without type casts so SQLite retains timestamp text exactly."""
    bind = op.get_bind()
    column_sql = ", ".join(columns)
    bind.execute(sa.text(
        f"INSERT INTO {target} ({column_sql}) "
        f"SELECT {column_sql} FROM {source}"
    ))


def _sqlite_recreate_timestamp_tables(*, to_datetime: bool) -> None:
    """Recreate the two v68 tables without SQLite's lossy DATETIME CAST.

    Alembic batch ``alter_column(type_=DateTime)`` renders a CAST while copying
    rows.  On SQLite, CAST('2026-09-08 ...' AS DATETIME) yields integer 2026.
    Rebuilding explicitly lets SQLite keep the ISO timestamp as TEXT storage
    while the new column declaration becomes DATETIME, which is the representation
    expected by SQLAlchemy's DateTime/UTCDateTime handling.
    """
    outcome_tmp = "_alembic_v69_cadet_session_outcomes"
    import_tmp = "_alembic_v69_cadet_member_import_batches"

    _create_sqlite_outcomes_table(outcome_tmp, to_datetime=to_datetime)
    _copy_table_verbatim("cadet_session_outcomes", outcome_tmp, _OUTCOME_COLUMNS)
    op.drop_table("cadet_session_outcomes")
    op.rename_table(outcome_tmp, "cadet_session_outcomes")
    op.create_index(
        "ix_cadet_session_outcomes_cadet_id",
        "cadet_session_outcomes",
        ["cadet_id"],
        unique=False,
    )
    op.create_index(
        "ix_cadet_session_outcomes_session_id",
        "cadet_session_outcomes",
        ["session_id"],
        unique=False,
    )

    _create_sqlite_import_batches_table(import_tmp, to_datetime=to_datetime)
    _copy_table_verbatim(
        "cadet_member_import_batches",
        import_tmp,
        _IMPORT_BATCH_COLUMNS,
    )
    op.drop_table("cadet_member_import_batches")
    op.rename_table(import_tmp, "cadet_member_import_batches")
    op.create_index(
        "ix_cadet_member_import_batches_squadron_id",
        "cadet_member_import_batches",
        ["squadron_id"],
        unique=False,
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
        _sqlite_recreate_timestamp_tables(to_datetime=True)
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
        _sqlite_recreate_timestamp_tables(to_datetime=False)
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
