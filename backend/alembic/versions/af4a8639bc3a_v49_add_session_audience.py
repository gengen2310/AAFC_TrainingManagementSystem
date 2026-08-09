"""v49 add session_audience

Whole-system product/UX/data hardening program addendum, CLASS-03: Session
audience is not class-specific. See
docs/product-review/parallel-class-impact-analysis.md Finding 2 for the
root cause (Session.cadet_group is a single free-text string, unable to
represent which specific Training Class(es) a Session was planned for) and
docs/remediation/master_gap_register.csv's CLASS-03 for the gap record.

session_audience is a many-to-many join between sessions and
training_classes, with an optional per-row outcome_override for addendum
§48 (a combined Session defaults every linked class to the parent Session's
own status; one class can be recorded as an exception without needing a
separate Session). Additive only: sessions.cadet_group is untouched and
remains a free-text compatibility field per addendum §86-87.

Revision ID: af4a8639bc3a
Revises: 4a34b5517bd3
Create Date: 2026-08-09
"""
from alembic import op
import sqlalchemy as sa

revision = 'af4a8639bc3a'
down_revision = '4a34b5517bd3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'session_audience',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('session_id', sa.String(36), nullable=False),
        sa.Column('training_class_id', sa.String(36), nullable=False),
        sa.Column('outcome_override', sa.String(30), nullable=True),
        sa.Column('outcome_override_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id']),
        sa.ForeignKeyConstraint(['training_class_id'], ['training_classes.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('session_id', 'training_class_id', name='uq_session_audience_session_class'),
    )
    op.create_index('ix_session_audience_session_id', 'session_audience', ['session_id'])
    op.create_index('ix_session_audience_training_class_id', 'session_audience', ['training_class_id'])


def downgrade():
    op.drop_index('ix_session_audience_training_class_id', table_name='session_audience')
    op.drop_index('ix_session_audience_session_id', table_name='session_audience')
    op.drop_table('session_audience')
