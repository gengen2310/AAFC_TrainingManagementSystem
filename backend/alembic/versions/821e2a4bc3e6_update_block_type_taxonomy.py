"""update_block_type_taxonomy
Revision ID: 821e2a4bc3e6
Revises: 3197cd57cd98
Create Date: 2026-08-21 19:41:18.753568
"""
from alembic import op
import sqlalchemy as sa

revision = '821e2a4bc3e6'
down_revision = '3197cd57cd98'
branch_labels = None
depends_on = None

# Map old → new block type values
_TYPE_MAP = {
    "administration": "admin",
    "roll_call": "admin",
    "flight_period": "training_period",
    "instructional_period": "training_period",
    "break": "drinks_break",
    "fatigues": "fatigue",
    "debrief": "briefing",
    "custom": "other",
    # unchanged: arrival, parade, dismissal (keep as-is)
}
_SCHEDULABLE = {"training_period"}


def upgrade():
    # ── Data migration: update block type taxonomy ────────────────────────────
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT id, block_type, is_instructional_period FROM timing_blocks"
    )).fetchall()
    for row_id, block_type, is_ip in rows:
        new_type = _TYPE_MAP.get(block_type, block_type)
        new_ip = new_type in _SCHEDULABLE
        conn.execute(sa.text(
            "UPDATE timing_blocks SET block_type=:bt, is_instructional_period=:ip WHERE id=:id"
        ), {"bt": new_type, "ip": new_ip, "id": row_id})

    # ── Schema changes auto-detected by alembic autogenerate ─────────────────
    op.drop_index(op.f('ix_pnto_parade_night_id'), table_name='parade_night_timing_overrides')
    op.drop_index(op.f('uq_pnto_active_per_night'), table_name='parade_night_timing_overrides',
                  sqlite_where=sa.text('NOT is_archived'))
    op.create_index(op.f('ix_parade_night_timing_overrides_parade_night_id'),
                    'parade_night_timing_overrides', ['parade_night_id'], unique=False)
    op.add_column('service_desk_email_configs',
                  sa.Column('created_by', sa.String(length=36), nullable=True))
    op.add_column('service_desk_email_configs',
                  sa.Column('updated_by', sa.String(length=36), nullable=True))
    with op.batch_alter_table('service_desk_email_configs') as batch_op:
        batch_op.alter_column('created_at', existing_type=sa.DATETIME(), nullable=False)
        batch_op.alter_column('updated_at', existing_type=sa.DATETIME(), nullable=False)
    op.drop_index(op.f('ix_sd_email_configs_wing_id'), table_name='service_desk_email_configs')
    op.create_index(op.f('ix_service_desk_email_configs_wing_id'),
                    'service_desk_email_configs', ['wing_id'], unique=False)
    op.drop_index(op.f('ix_service_tickets_created_at'), table_name='service_tickets')
    op.drop_index(op.f('ix_service_tickets_squadron_id'), table_name='service_tickets')
    op.drop_index(op.f('ix_service_tickets_status'), table_name='service_tickets')


def downgrade():
    # Schema: restore dropped indexes
    op.create_index(op.f('ix_service_tickets_status'), 'service_tickets', ['status'], unique=False)
    op.create_index(op.f('ix_service_tickets_squadron_id'), 'service_tickets',
                    ['squadron_id'], unique=False)
    op.create_index(op.f('ix_service_tickets_created_at'), 'service_tickets',
                    ['created_at'], unique=False)
    op.drop_index(op.f('ix_service_desk_email_configs_wing_id'),
                  table_name='service_desk_email_configs')
    op.create_index(op.f('ix_sd_email_configs_wing_id'),
                    'service_desk_email_configs', ['wing_id'], unique=False)
    with op.batch_alter_table('service_desk_email_configs') as batch_op:
        batch_op.alter_column('updated_at', existing_type=sa.DATETIME(), nullable=True)
        batch_op.alter_column('created_at', existing_type=sa.DATETIME(), nullable=True)
    op.drop_column('service_desk_email_configs', 'updated_by')
    op.drop_column('service_desk_email_configs', 'created_by')
    op.drop_index(op.f('ix_parade_night_timing_overrides_parade_night_id'),
                  table_name='parade_night_timing_overrides')
    op.create_index(op.f('uq_pnto_active_per_night'), 'parade_night_timing_overrides',
                    ['parade_night_id'], unique=1, sqlite_where=sa.text('NOT is_archived'))
    op.create_index(op.f('ix_pnto_parade_night_id'), 'parade_night_timing_overrides',
                    ['parade_night_id'], unique=False)
    # No reverse map for block types — downgrade is best-effort only
