"""v8 flexible parade-night timing templates

Adds:
  - timing_templates       (squadron, effective date range, named blocks)
  - timing_blocks          (ordered blocks per template, instructional-period flag)
  - parade_night_timing_overrides  (per-parade-night template override)
  - parade_nights.timing_template_id  (point-in-time recording)

Revision ID: c4d8e1f3a0b2
Revises: b3e9f4c2a0d1
Create Date: 2026-06-27
"""
from alembic import op
import sqlalchemy as sa

revision = 'c4d8e1f3a0b2'
down_revision = 'b3e9f4c2a0d1'
branch_labels = None
depends_on = None


def upgrade():
    # ── timing_templates ──────────────────────────────────────────────────────
    op.create_table(
        'timing_templates',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('squadron_id', sa.String(36), nullable=False),
        sa.Column('name', sa.String(120), nullable=False),
        sa.Column('effective_from', sa.String(10), nullable=False),
        sa.Column('effective_to', sa.String(10), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('active_status', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
        sa.ForeignKeyConstraint(['squadron_id'], ['squadrons.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_timing_templates_squadron_id', 'timing_templates', ['squadron_id'])
    op.create_index('ix_timing_templates_effective_from', 'timing_templates', ['effective_from'])
    op.create_index('ix_timing_templates_is_archived', 'timing_templates', ['is_archived'])

    # ── timing_blocks ─────────────────────────────────────────────────────────
    op.create_table(
        'timing_blocks',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('timing_template_id', sa.String(36), nullable=False),
        sa.Column('display_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('block_name', sa.String(80), nullable=False),
        sa.Column('block_type', sa.String(40), nullable=False, server_default='custom'),
        sa.Column('start_time', sa.String(10), nullable=True),
        sa.Column('end_time', sa.String(10), nullable=True),
        sa.Column('duration_minutes', sa.Integer(), nullable=True),
        sa.Column('is_instructional_period', sa.Boolean(), nullable=False,
                  server_default=sa.text('false')),
        sa.Column('period_number', sa.Integer(), nullable=True),
        sa.Column('is_optional', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
        sa.ForeignKeyConstraint(['timing_template_id'], ['timing_templates.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_timing_blocks_template_id', 'timing_blocks', ['timing_template_id'])

    # ── parade_night_timing_overrides ─────────────────────────────────────────
    op.create_table(
        'parade_night_timing_overrides',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('parade_night_id', sa.String(36), nullable=False),
        sa.Column('timing_template_id', sa.String(36), nullable=True),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
        sa.ForeignKeyConstraint(['parade_night_id'], ['parade_nights.id']),
        sa.ForeignKeyConstraint(['timing_template_id'], ['timing_templates.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('parade_night_id', name='uq_pnto_parade_night_id'),
    )
    op.create_index('ix_pnto_parade_night_id', 'parade_night_timing_overrides',
                    ['parade_night_id'])

    # ── parade_nights: point-in-time template recording ───────────────────────
    op.add_column('parade_nights',
                  sa.Column('timing_template_id', sa.String(36), nullable=True))


def downgrade():
    op.drop_column('parade_nights', 'timing_template_id')
    op.drop_index('ix_pnto_parade_night_id', table_name='parade_night_timing_overrides')
    op.drop_table('parade_night_timing_overrides')
    op.drop_index('ix_timing_blocks_template_id', table_name='timing_blocks')
    op.drop_table('timing_blocks')
    op.drop_index('ix_timing_templates_is_archived', table_name='timing_templates')
    op.drop_index('ix_timing_templates_effective_from', table_name='timing_templates')
    op.drop_index('ix_timing_templates_squadron_id', table_name='timing_templates')
    op.drop_table('timing_templates')
