"""add_training_class_stage_code
Revision ID: e9c422baf945
Revises: 821e2a4bc3e6
Create Date: 2026-08-21 19:58:38.048230
"""
from alembic import op
import sqlalchemy as sa

revision = 'e9c422baf945'
down_revision = '821e2a4bc3e6'
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("training_classes") as batch:
        batch.add_column(sa.Column("stage_code", sa.String(10), nullable=True))
        # Also make training_stage_id nullable so auto-created classes (Task 5)
        # don't require a phase link at creation time.
        batch.alter_column("training_stage_id", existing_type=sa.String(36), nullable=True)
    op.create_index(op.f('ix_training_classes_stage_code'), 'training_classes', ['stage_code'], unique=False)

def downgrade():
    op.drop_index(op.f('ix_training_classes_stage_code'), table_name='training_classes')
    with op.batch_alter_table("training_classes") as batch:
        batch.drop_column("stage_code")
        batch.alter_column("training_stage_id", existing_type=sa.String(36), nullable=False)
