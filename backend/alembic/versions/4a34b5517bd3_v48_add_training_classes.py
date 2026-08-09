"""v48 add training_classes

Whole-system product/UX/data hardening program addendum, CLASS-01: the
Training Stage vs Training Class domain model. See
docs/product-review/parallel-class-impact-analysis.md for the full design
rationale and docs/remediation/master_gap_register.csv's CLASS-01..14 for
the dependent work this unblocks.

A TrainingClass is a Squadron-specific local group undertaking a Training
Stage (CurriculumPhase) during a Training Year (PlanningYear) -- e.g.
"Senior 1"/"Senior 2" both undertaking the same Senior CurriculumPhase.
Additive only: Session.cadet_group and Cadet.phase are untouched by this
migration and remain in place as free-text compatibility fields until every
consumer (Mission Backlog, Weekly Program, dashboards, both frontends) has
migrated to the new model, per addendum sections 86-87. No existing table is
altered; no existing data is touched.

Revision ID: 4a34b5517bd3
Revises: f6a7b8c9d0e1
Create Date: 2026-08-09
"""
from alembic import op
import sqlalchemy as sa

revision = '4a34b5517bd3'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'training_classes',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('squadron_id', sa.String(36), nullable=False),
        sa.Column('training_year_id', sa.String(36), nullable=False),
        sa.Column('training_stage_id', sa.String(36), nullable=False),
        sa.Column('display_name', sa.String(80), nullable=False),
        sa.Column('sequence', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('start_date', sa.String(10), nullable=True),
        sa.Column('end_date', sa.String(10), nullable=True),
        sa.Column('expected_count', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('version', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('created_by', sa.String(36), nullable=True),
        sa.Column('updated_by', sa.String(36), nullable=True),
        sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['squadron_id'], ['squadrons.id']),
        sa.ForeignKeyConstraint(['training_year_id'], ['planning_years.id']),
        sa.ForeignKeyConstraint(['training_stage_id'], ['curriculum_phases.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_training_classes_squadron_id', 'training_classes', ['squadron_id'])
    op.create_index('ix_training_classes_training_year_id', 'training_classes', ['training_year_id'])
    op.create_index('ix_training_classes_training_stage_id', 'training_classes', ['training_stage_id'])
    op.create_index('ix_training_classes_is_archived', 'training_classes', ['is_archived'])


def downgrade():
    op.drop_index('ix_training_classes_is_archived', table_name='training_classes')
    op.drop_index('ix_training_classes_training_stage_id', table_name='training_classes')
    op.drop_index('ix_training_classes_training_year_id', table_name='training_classes')
    op.drop_index('ix_training_classes_squadron_id', table_name='training_classes')
    op.drop_table('training_classes')
