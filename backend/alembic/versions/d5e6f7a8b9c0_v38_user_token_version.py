"""v38 — add token_version to users for session revocation on code reset

Revision ID: d5e6f7a8b9c0
Revises: c4bc5b76104e
Create Date: 2026-07-17
"""
from alembic import op
import sqlalchemy as sa

revision = 'd5e6f7a8b9c0'
down_revision = 'c4bc5b76104e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column(
            'token_version', sa.Integer(),
            server_default='0', nullable=False,
        ))


def downgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('token_version')
