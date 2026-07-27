"""v42 Curriculum Phases — governed training-phase catalogue (master
transformation plan Block 10). Mirrors curriculum_elements exactly (same
scope model: system > national > wing > squadron), plus a sort_order column
since phases have a natural training-progression order that plain subject
elements don't.

Revision ID: y8z9a0b1c2d3
Revises: c3d4e5f6a7b8
Create Date: 2026-07-25
"""
from alembic import op
import sqlalchemy as sa

revision = 'y8z9a0b1c2d3'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None

# Matches dashboard.py's existing _PHASES constant — the phase names already
# in live use across charts/badges/curriculum grouping today.
_DEFAULT_PHASES = [
    ('A. Orientation',   'A. Orientation',   'national', 10),
    ('B. Initial',       'B. Initial',       'national', 20),
    ('C. Junior',        'C. Junior',        'national', 30),
    ('D. Intermediate',  'D. Intermediate',  'national', 40),
    ('E. Senior',        'E. Senior',        'national', 50),
    ('I. Bronze',        'I. Bronze',        'national', 60),
    ('J. Silver',        'J. Silver',        'national', 70),
    ('K. Gold',          'K. Gold',          'national', 80),
]


def upgrade():
    op.create_table(
        'curriculum_phases',
        sa.Column('id',            sa.String(36),  nullable=False, primary_key=True),
        sa.Column('name',          sa.String(60),  nullable=False),
        sa.Column('display_name',  sa.String(120), nullable=False),
        sa.Column('scope_level',   sa.String(20),  nullable=False),
        sa.Column('wing_id',       sa.String(36),  nullable=True),
        sa.Column('squadron_id',   sa.String(36),  nullable=True),
        sa.Column('sort_order',    sa.Integer(),   nullable=False, server_default='0'),
        sa.Column('active_status', sa.Boolean(),   nullable=False, server_default='true'),
        sa.Column('created_by',    sa.String(36),  nullable=True),
        sa.Column('is_archived',   sa.Boolean(),   nullable=False, server_default='false'),
        sa.Column('archived_at',   sa.DateTime(),  nullable=True),
        sa.Column('created_at',    sa.DateTime(),  nullable=True),
        sa.Column('updated_at',    sa.DateTime(),  nullable=True),
    )
    op.create_index('ix_curriculum_phases_name',        'curriculum_phases', ['name'])
    op.create_index('ix_curriculum_phases_scope_level', 'curriculum_phases', ['scope_level'])
    op.create_index('ix_curriculum_phases_wing_id',     'curriculum_phases', ['wing_id'])
    op.create_index('ix_curriculum_phases_squadron_id', 'curriculum_phases', ['squadron_id'])

    # Seed built-in national phases
    import uuid
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    conn = op.get_bind()
    for name, display_name, scope, sort_order in _DEFAULT_PHASES:
        existing = conn.execute(
            sa.text("SELECT id FROM curriculum_phases WHERE name=:n AND scope_level=:s"),
            {"n": name, "s": scope}
        ).fetchone()
        if not existing:
            conn.execute(
                sa.text(
                    "INSERT INTO curriculum_phases "
                    "(id, name, display_name, scope_level, sort_order, active_status, is_archived, created_at, updated_at) "
                    "VALUES (:id, :name, :display_name, :scope_level, :sort_order, true, false, :now, :now)"
                ),
                {"id": str(uuid.uuid4()), "name": name, "display_name": display_name,
                 "scope_level": scope, "sort_order": sort_order, "now": now},
            )


def downgrade():
    op.drop_index('ix_curriculum_phases_squadron_id', table_name='curriculum_phases')
    op.drop_index('ix_curriculum_phases_wing_id',     table_name='curriculum_phases')
    op.drop_index('ix_curriculum_phases_scope_level', table_name='curriculum_phases')
    op.drop_index('ix_curriculum_phases_name',        table_name='curriculum_phases')
    op.drop_table('curriculum_phases')
