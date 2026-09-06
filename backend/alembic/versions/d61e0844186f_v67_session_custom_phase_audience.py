"""v67 session_custom_phase_audience

Creates session_custom_phase_audiences join table for relational
custom training phase targeting on Sessions.

Revision ID: d61e0844186f
Revises: 62c57ff2e22f
Create Date: 2026-09-06
"""
from alembic import op
import sqlalchemy as sa

revision = 'd61e0844186f'
down_revision = '62c57ff2e22f'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'session_custom_phase_audiences',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36),
                  sa.ForeignKey('sessions.id', ondelete='CASCADE'),
                  nullable=False),
        sa.Column('custom_phase_id', sa.String(36),
                  sa.ForeignKey('custom_training_phases.id', ondelete='CASCADE'),
                  nullable=False),
        sa.UniqueConstraint('session_id', 'custom_phase_id', name='uq_scpa_session_custom_phase'),
    )
    op.create_index('ix_scpa_session', 'session_custom_phase_audiences', ['session_id'])
    op.create_index('ix_scpa_custom_phase', 'session_custom_phase_audiences', ['custom_phase_id'])


def downgrade():
    op.drop_index('ix_scpa_custom_phase', 'session_custom_phase_audiences')
    op.drop_index('ix_scpa_session', 'session_custom_phase_audiences')
    op.drop_table('session_custom_phase_audiences')
