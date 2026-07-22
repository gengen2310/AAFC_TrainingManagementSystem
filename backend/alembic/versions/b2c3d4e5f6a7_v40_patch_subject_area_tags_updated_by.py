"""v40 — Patch missing updated_by column on subject_area_tags

The v39 migration created subject_area_tags without the updated_by column
that TimestampMixin now includes.  Every authenticated query against
/api/subject-area-tags crashes with:

  psycopg2.errors.UndefinedColumn: column subject_area_tags.updated_by does not exist

This is the same class of defect fixed by v24 for planning tables created
before updated_by was added to TimestampMixin.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-22
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('subject_area_tags') as batch_op:
        batch_op.add_column(sa.Column('updated_by', sa.String(36), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('subject_area_tags') as batch_op:
        batch_op.drop_column('updated_by')
