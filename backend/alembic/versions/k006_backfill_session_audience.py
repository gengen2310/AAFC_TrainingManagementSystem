"""K-006: backfill SessionAudience rows for legacy cadet_group sessions.

For every TrainingSession that has a cadet_group string but no SessionAudience
row, look up the matching TrainingClass by stage_code + squadron_id +
training_year_id (via the session's parade night). Creates a SessionAudience
row only when exactly one active TrainingClass matches — skips when zero or
multiple match so we never guess the wrong class.

Revision ID: b7f3c2e1d098
Revises: a4e9507a9c51
Create Date: 2026-08-31
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "b7f3c2e1d098"
down_revision = "a4e9507a9c51"
branch_labels = None
depends_on = None

_STAGE_CODE_MAP = {
    "orientation": "ORI",
    "initial": "INI",
    "junior": "JNR",
    "intermediate": "INT",
    "senior": "SNR",
}


def upgrade() -> None:
    conn = op.get_bind()

    # Fetch sessions with cadet_group set and no existing SessionAudience row.
    rows = conn.execute(text("""
        SELECT s.id AS session_id, s.cadet_group, s.squadron_id,
               pn.planning_year_id
        FROM sessions s
        JOIN parade_nights pn ON pn.id = s.parade_night_id
        WHERE s.cadet_group IS NOT NULL
          AND s.id NOT IN (
              SELECT DISTINCT session_id FROM session_audience
          )
    """)).fetchall()

    inserted = 0
    for row in rows:
        stage_code = _STAGE_CODE_MAP.get(row.cadet_group)
        if not stage_code:
            continue

        # Find exactly one active TrainingClass for this stage/squadron/year.
        tc_rows = conn.execute(text("""
            SELECT id FROM training_classes
            WHERE squadron_id  = :sqn
              AND training_year_id = :yr
              AND stage_code   = :sc
              AND is_archived  = 0
        """), {"sqn": row.squadron_id, "yr": row.planning_year_id, "sc": stage_code}).fetchall()

        if len(tc_rows) != 1:
            continue  # ambiguous or no class — skip

        # Guard against duplicate (unique constraint would catch it too, but let's be clean).
        exists = conn.execute(text("""
            SELECT 1 FROM session_audience
            WHERE session_id = :sid AND training_class_id = :tcid
            LIMIT 1
        """), {"sid": row.session_id, "tcid": tc_rows[0].id}).fetchone()
        if exists:
            continue

        import uuid as _uuid, datetime as _dt
        now = _dt.datetime.utcnow().isoformat()
        conn.execute(text("""
            INSERT INTO session_audience (id, session_id, training_class_id,
                                          outcome_override, outcome_override_reason,
                                          created_at, updated_at)
            VALUES (:id, :sid, :tcid, NULL, NULL, :now, :now)
        """), {"id": str(_uuid.uuid4()), "sid": row.session_id,
               "tcid": tc_rows[0].id, "now": now})
        inserted += 1

    print(f"K-006 backfill: created {inserted} SessionAudience rows "
          f"({len(rows) - inserted} skipped — no unique class match)")


def downgrade() -> None:
    # The backfilled rows cannot be safely distinguished from rows written by
    # application code after this migration runs, so downgrade is intentionally
    # a no-op. To roll back the data effect, restore from a pre-migration backup.
    pass
