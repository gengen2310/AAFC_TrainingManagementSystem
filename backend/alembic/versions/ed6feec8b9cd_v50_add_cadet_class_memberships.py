"""v50 add cadet_class_memberships

Whole-system product/UX/data hardening program addendum, CLASS-09:
Foundation + Extension concurrent membership unsupported. Cadet.phase is a
single free-text string, unable to represent a Cadet concurrently
belonging to a Foundation-stage class (e.g. Senior 1) and an
Extension-stage class (e.g. Bronze CLP) at once.

Explicitly product-scope-confirmed by the user before this was built --
the addendum (§38/§39) makes individual cadet-class tracking conditional
on an explicit product decision, not an engineering default, per this
program's own data-minimisation principle. See
docs/product-review/parallel-class-impact-analysis.md's proposed target
shape and docs/remediation/master_gap_register.csv's CLASS-09 for the
gap record.

cadet_class_memberships is a lifecycle join between cadets and
training_classes (start_date/end_date/active_status, not a simple
idempotent current-set like session_audience -- a Cadet's membership
history has value, unlike a corrected Session/Class link). No unique
constraint on (cadet_id, training_class_id): a Cadet can legitimately hold
more than one historical membership in the same Class over time (left and
rejoined) -- "no duplicate currently-active membership" is enforced at the
API layer. Additive only: cadets.phase is untouched and remains a
free-text compatibility field per addendum §86-87.

Revision ID: ed6feec8b9cd
Revises: af4a8639bc3a
Create Date: 2026-08-10
"""
from alembic import op
import sqlalchemy as sa

revision = 'ed6feec8b9cd'
down_revision = 'af4a8639bc3a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'cadet_class_memberships',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('cadet_id', sa.String(36), nullable=False),
        sa.Column('training_class_id', sa.String(36), nullable=False),
        sa.Column('start_date', sa.String(10), nullable=True),
        sa.Column('end_date', sa.String(10), nullable=True),
        sa.Column('active_status', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('source', sa.String(20), nullable=False, server_default='manual'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
        sa.ForeignKeyConstraint(['cadet_id'], ['cadets.id']),
        sa.ForeignKeyConstraint(['training_class_id'], ['training_classes.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_cadet_class_memberships_cadet_id', 'cadet_class_memberships', ['cadet_id'])
    op.create_index('ix_cadet_class_memberships_training_class_id', 'cadet_class_memberships', ['training_class_id'])
    op.create_index('ix_cadet_class_memberships_is_archived', 'cadet_class_memberships', ['is_archived'])


def downgrade():
    op.drop_index('ix_cadet_class_memberships_is_archived', table_name='cadet_class_memberships')
    op.drop_index('ix_cadet_class_memberships_training_class_id', table_name='cadet_class_memberships')
    op.drop_index('ix_cadet_class_memberships_cadet_id', table_name='cadet_class_memberships')
    op.drop_table('cadet_class_memberships')
