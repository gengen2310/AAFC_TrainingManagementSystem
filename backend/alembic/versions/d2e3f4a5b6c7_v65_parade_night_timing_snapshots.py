"""v65 parade_night_timing_snapshots

Materialised timing period data for each Parade Night. Written at creation
time so that master template changes do not retroactively alter existing nights.

Backfills existing nights that already have a timing_template_id.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-09-05
"""
import uuid
import sqlalchemy as sa
from alembic import op

revision = 'd2e3f4a5b6c7'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'parade_night_timing_snapshots',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('parade_night_id', sa.String(36),
                  sa.ForeignKey('parade_nights.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('period_number', sa.Integer, nullable=True),
        sa.Column('block_label', sa.String(120), nullable=False),
        sa.Column('start_time', sa.String(10), nullable=True),
        sa.Column('end_time', sa.String(10), nullable=True),
        sa.Column('is_instructional', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column('display_order', sa.Integer, nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index(
        'ix_pnts_night_period', 'parade_night_timing_snapshots',
        ['parade_night_id', 'period_number']
    )

    # Backfill: for each parade_night with a timing_template_id, write snapshot rows
    bind = op.get_bind()
    nights = bind.execute(sa.text(
        "SELECT id, timing_template_id FROM parade_nights "
        "WHERE timing_template_id IS NOT NULL AND is_archived = false"
    )).fetchall()

    for night_id, tmpl_id in nights:
        blocks = bind.execute(sa.text(
            "SELECT block_name, block_type, start_time, end_time, "
            "       is_instructional_period, display_order "
            "FROM timing_blocks "
            "WHERE timing_template_id = :tid AND is_archived = false "
            "ORDER BY display_order"
        ), {"tid": tmpl_id}).fetchall()

        period_counter = 0
        for display_idx, block in enumerate(blocks):
            block_name, block_type, start_t, end_t, is_instr, disp_ord = block
            if is_instr:
                period_counter += 1
                period_number = period_counter
            else:
                period_number = None

            bind.execute(sa.text(
                "INSERT INTO parade_night_timing_snapshots "
                "(id, parade_night_id, period_number, block_label, start_time, end_time, "
                " is_instructional, display_order, created_at) "
                "VALUES (:id, :night_id, :pnum, :label, :st, :et, :instr, :disp, CURRENT_TIMESTAMP)"
            ), {
                "id": str(uuid.uuid4()),
                "night_id": night_id,
                "pnum": period_number,
                "label": block_name,
                "st": start_t,
                "et": end_t,
                "instr": True if is_instr else False,
                "disp": display_idx,
            })


def downgrade():
    op.drop_index('ix_pnts_night_period', 'parade_night_timing_snapshots')
    op.drop_table('parade_night_timing_snapshots')
