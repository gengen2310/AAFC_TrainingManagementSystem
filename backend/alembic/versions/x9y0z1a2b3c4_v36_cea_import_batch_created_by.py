"""v36 add created_by and updated_by to cea_import_batches

Revision ID: x9y0z1a2b3c4
Revises: w8x9y0z1a2b3
Create Date: 2026-07-13
"""
from alembic import op
import sqlalchemy as sa

revision = "x9y0z1a2b3c4"
down_revision = "w8x9y0z1a2b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cea_import_batches", sa.Column("created_by", sa.String(36), nullable=True))
    op.add_column("cea_import_batches", sa.Column("updated_by", sa.String(36), nullable=True))


def downgrade() -> None:
    op.drop_column("cea_import_batches", "updated_by")
    op.drop_column("cea_import_batches", "created_by")
