"""v47 — Patch missing updated_by column on curriculum_phases and facilitator_type_tags

Both tables were created without the updated_by column that TimestampMixin
declares (v42 for curriculum_phases, v45 for facilitator_type_tags), the
same class of defect v40 already patched once for subject_area_tags, and
v24 patched before that for the original planning tables. Found live on
staging via GET /api/curriculum/phases and GET /api/facilitator-type-tags,
both crashing with:

  psycopg2.errors.UndefinedColumn: column curriculum_phases.updated_by does not exist
  psycopg2.errors.UndefinedColumn: column facilitator_type_tags.updated_by does not exist

Invisible to every local/CI test because local SQLite's schema is created
directly from the SQLAlchemy models (bypassing Alembic entirely), so
`updated_by` always "exists" there regardless of what any migration
actually does -- only a real Postgres environment running the full
migration chain surfaces this class of drift. Confirmed via a full
information_schema audit against staging Postgres that no other table has
the same drift (v24 and v40 already closed the other two instances).

Revision ID: 5a195a98148a
Revises: 81734c0f34bf
Create Date: 2026-08-05
"""
from alembic import op
import sqlalchemy as sa

revision = '5a195a98148a'
down_revision = '81734c0f34bf'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('curriculum_phases') as batch_op:
        batch_op.add_column(sa.Column('updated_by', sa.String(36), nullable=True))
    with op.batch_alter_table('facilitator_type_tags') as batch_op:
        batch_op.add_column(sa.Column('updated_by', sa.String(36), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('facilitator_type_tags') as batch_op:
        batch_op.drop_column('updated_by')
    with op.batch_alter_table('curriculum_phases') as batch_op:
        batch_op.drop_column('updated_by')
