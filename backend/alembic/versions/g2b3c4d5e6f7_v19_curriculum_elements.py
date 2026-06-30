"""v19 Curriculum Elements — managed subject/category groupings for curriculum items.

Scope levels: system (built-in defaults), national, wing, squadron.
Users see elements at or above their own scope level.

Revision ID: g2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-06-30
"""
from alembic import op
import sqlalchemy as sa

revision = 'g2b3c4d5e6f7'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None

_DEFAULT_ELEMENTS = [
    ('Air_Space',          'Air & Space',               'national'),
    ('Drill',              'Drill',                     'national'),
    ('Field',              'Field Skills',              'national'),
    ('Personal_Dev',       'Personal Development (PDL)', 'national'),
    ('Service_Community',  'Service & Community',       'national'),
    ('SQN_Affairs',        'Squadron Affairs',          'national'),
    ('CDT_Skills',         'Cadet Skills',              'national'),
    ('Bronze_CLP',         'Bronze CLP',                'national'),
    ('Silver_CLP',         'Silver CLP',                'national'),
    ('Gold_CLP',           'Gold CLP',                  'national'),
]


def upgrade():
    op.create_table(
        'curriculum_elements',
        sa.Column('id',            sa.String(36),  nullable=False, primary_key=True),
        sa.Column('name',          sa.String(60),  nullable=False),
        sa.Column('display_name',  sa.String(120), nullable=False),
        sa.Column('scope_level',   sa.String(20),  nullable=False),
        sa.Column('wing_id',       sa.String(36),  nullable=True),
        sa.Column('squadron_id',   sa.String(36),  nullable=True),
        sa.Column('active_status', sa.Boolean(),   nullable=False, server_default='true'),
        sa.Column('created_by',    sa.String(36),  nullable=True),
        sa.Column('is_archived',   sa.Boolean(),   nullable=False, server_default='false'),
        sa.Column('archived_at',   sa.DateTime(),  nullable=True),
        sa.Column('created_at',    sa.DateTime(),  nullable=True),
        sa.Column('updated_at',    sa.DateTime(),  nullable=True),
    )
    op.create_index('ix_curriculum_elements_name',        'curriculum_elements', ['name'])
    op.create_index('ix_curriculum_elements_scope_level', 'curriculum_elements', ['scope_level'])
    op.create_index('ix_curriculum_elements_wing_id',     'curriculum_elements', ['wing_id'])
    op.create_index('ix_curriculum_elements_squadron_id', 'curriculum_elements', ['squadron_id'])

    # Seed built-in national elements
    import uuid
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    conn = op.get_bind()
    for name, display_name, scope in _DEFAULT_ELEMENTS:
        existing = conn.execute(
            sa.text("SELECT id FROM curriculum_elements WHERE name=:n AND scope_level=:s"),
            {"n": name, "s": scope}
        ).fetchone()
        if not existing:
            conn.execute(
                sa.text(
                    "INSERT INTO curriculum_elements "
                    "(id, name, display_name, scope_level, active_status, is_archived, created_at, updated_at) "
                    "VALUES (:id, :name, :display_name, :scope_level, true, false, :now, :now)"
                ),
                {"id": str(uuid.uuid4()), "name": name, "display_name": display_name,
                 "scope_level": scope, "now": now},
            )


def downgrade():
    op.drop_index('ix_curriculum_elements_squadron_id', table_name='curriculum_elements')
    op.drop_index('ix_curriculum_elements_wing_id',     table_name='curriculum_elements')
    op.drop_index('ix_curriculum_elements_scope_level', table_name='curriculum_elements')
    op.drop_index('ix_curriculum_elements_name',        table_name='curriculum_elements')
    op.drop_table('curriculum_elements')
