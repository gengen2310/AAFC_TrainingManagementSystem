"""v64 session_assistant_facilitators join table

Adds zero-to-many assistant facilitator relationship to Session.
Backfills existing assistant_facilitator_id values into the new table.
The old column is retained as deprecated — will be dropped in a later migration
once all consumers have been audited and migrated.

Revision ID: c1d2e3f4a5b6
Revises: b1c2d3e4f5a6
Create Date: 2026-09-05
"""
import uuid
import sqlalchemy as sa
from alembic import op

revision = 'c1d2e3f4a5b6'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'session_assistant_facilitators',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36),
                  sa.ForeignKey('sessions.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('user_id', sa.String(36), nullable=False, index=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint('session_id', 'user_id', name='uq_saf_session_user'),
    )
    # Backfill existing assistant_facilitator_id rows
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute(sa.text("""
            INSERT INTO session_assistant_facilitators (id, session_id, user_id, created_at)
            SELECT gen_random_uuid()::text, id, assistant_facilitator_id, NOW()
            FROM sessions
            WHERE assistant_facilitator_id IS NOT NULL
              AND is_archived = false
        """))
    else:
        # SQLite — used in test DB only; UUIDs generated in Python
        conn = op.get_bind()
        rows = conn.execute(sa.text(
            "SELECT id, assistant_facilitator_id FROM sessions "
            "WHERE assistant_facilitator_id IS NOT NULL AND is_archived = 0"
        )).fetchall()
        for row in rows:
            conn.execute(sa.text(
                "INSERT OR IGNORE INTO session_assistant_facilitators "
                "(id, session_id, user_id, created_at) VALUES (:id, :sid, :uid, CURRENT_TIMESTAMP)"
            ), {"id": str(uuid.uuid4()), "sid": row[0], "uid": row[1]})


def downgrade():
    op.drop_table('session_assistant_facilitators')
