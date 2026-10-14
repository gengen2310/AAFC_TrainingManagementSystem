"""v76: the last six timestamptz columns become naive UTC (PostgreSQL only).

The application stores every timestamp as naive UTC (UTCDateTime); 178 of 184
timestamp columns already match. These six were created as
"timestamp with time zone" -- the same drift v69 fixed for two other tables:

  activity_type_tags.created_at / updated_at
  training_area_capability_tags.created_at / updated_at
  parade_night_timing_snapshots.created_at
  session_assistant_facilitators.created_at

USING col AT TIME ZONE 'UTC' converts each stored instant to its exact UTC
wall-clock value, independent of the session TimeZone, so no instant changes
and reads return the same values as before. Whether HISTORICAL rows were
written under a non-UTC session (and are therefore already shifted) is a
separate question this migration neither causes nor hides -- see
docs/stabilisation/timestamp-runbook.md for the diagnostic query.

SQLite has no timestamptz, so this is a no-op there.

Revision ID: 63c110addb63
Revises: f1b2172b7bdf
"""
from alembic import op
import sqlalchemy as sa

revision = "63c110addb63"
down_revision = "f1b2172b7bdf"
branch_labels = None
depends_on = None

COLUMNS = (
    ("activity_type_tags", "created_at"),
    ("activity_type_tags", "updated_at"),
    ("training_area_capability_tags", "created_at"),
    ("training_area_capability_tags", "updated_at"),
    ("parade_night_timing_snapshots", "created_at"),
    ("session_assistant_facilitators", "created_at"),
)


def _is_timestamptz(bind, table, column):
    return bind.execute(sa.text(
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_schema = current_schema() AND table_name = :t AND column_name = :c"),
        {"t": table, "c": column}).scalar() == "timestamp with time zone"


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table, column in COLUMNS:
        if _is_timestamptz(bind, table, column):
            op.execute(sa.text(
                f'ALTER TABLE "{table}" ALTER COLUMN "{column}" '
                f'TYPE timestamp without time zone USING "{column}" AT TIME ZONE \'UTC\''))


def downgrade():
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    for table, column in COLUMNS:
        if not _is_timestamptz(bind, table, column):
            op.execute(sa.text(
                f'ALTER TABLE "{table}" ALTER COLUMN "{column}" '
                f'TYPE timestamp with time zone USING "{column}" AT TIME ZONE \'UTC\''))
