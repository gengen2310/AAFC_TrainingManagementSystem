"""v24 Patch missing TimestampMixin columns on planning tables.

Six tables created by v11/v14 migrations were built before created_by /
updated_by were part of TimestampMixin.  The ORM now selects these columns,
so every query against them crashes with UndefinedColumn on Postgres.

Affected tables:
  parade_dates        — add created_by, updated_by
  holiday_periods     — add created_by, updated_by
  planning_conflicts  — add created_by, updated_by
  anchor_prep_plans   — add created_by, updated_by
  anchor_prep_rules   — add created_by, updated_by
  planning_locations  — add updated_by  (created_by already present)

Revision ID: l7g8h9i0j1k2
Revises: k6f7g8h9i0j1
Create Date: 2026-07-06
"""
from alembic import op
import sqlalchemy as sa

revision = 'l7g8h9i0j1k2'
down_revision = 'k6f7g8h9i0j1'
branch_labels = None
depends_on = None

_COL_CREATED_BY = sa.Column('created_by', sa.String(36), nullable=True)
_COL_UPDATED_BY = sa.Column('updated_by', sa.String(36), nullable=True)

_NEED_BOTH = [
    'parade_dates',
    'holiday_periods',
    'planning_conflicts',
    'anchor_prep_plans',
    'anchor_prep_rules',
]


def upgrade():
    for table in _NEED_BOTH:
        op.add_column(table, sa.Column('created_by', sa.String(36), nullable=True))
        op.add_column(table, sa.Column('updated_by', sa.String(36), nullable=True))

    op.add_column('planning_locations', sa.Column('updated_by', sa.String(36), nullable=True))


def downgrade():
    for table in _NEED_BOTH:
        op.drop_column(table, 'updated_by')
        op.drop_column(table, 'created_by')

    op.drop_column('planning_locations', 'updated_by')
