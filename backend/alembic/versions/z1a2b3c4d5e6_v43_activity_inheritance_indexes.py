"""v43 Activity inheritance indexes + AuditLog.batch_id (NATHQ/Wing Activities,
bulk account archive — Phase 2). Additive only: three composite indexes on
the existing activities table (owning_level/wing_id/squadron_id already
exist as columns, just never indexed for the inheritance query's access
pattern) and one nullable, indexed batch-correlation column on audit_logs.
No backfill needed — existing Activity rows already default
owning_level="squadron", and existing AuditLog rows simply carry a NULL
batch_id.

Revision ID: z1a2b3c4d5e6
Revises: y8z9a0b1c2d3
Create Date: 2026-08-01
"""
from alembic import op
import sqlalchemy as sa

revision = 'z1a2b3c4d5e6'
down_revision = 'y8z9a0b1c2d3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_activities_owning_level_archived', 'activities',
                     ['owning_level', 'is_archived'])
    op.create_index('ix_activities_wing_archived_date', 'activities',
                     ['wing_id', 'is_archived', 'date_start'])
    op.create_index('ix_activities_squadron_archived_date', 'activities',
                     ['squadron_id', 'is_archived', 'date_start'])
    with op.batch_alter_table('audit_logs') as batch_op:
        batch_op.add_column(sa.Column('batch_id', sa.String(36), nullable=True))
    op.create_index('ix_audit_logs_batch_id', 'audit_logs', ['batch_id'])


def downgrade():
    op.drop_index('ix_audit_logs_batch_id', table_name='audit_logs')
    with op.batch_alter_table('audit_logs') as batch_op:
        batch_op.drop_column('batch_id')
    op.drop_index('ix_activities_squadron_archived_date', table_name='activities')
    op.drop_index('ix_activities_wing_archived_date', table_name='activities')
    op.drop_index('ix_activities_owning_level_archived', table_name='activities')
