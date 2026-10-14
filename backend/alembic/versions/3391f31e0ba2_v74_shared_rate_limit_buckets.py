"""v74: shared fixed-window rate-limit buckets (rate_limit_buckets).

The forgot-code limiter was a per-process dict: with 2 gunicorn workers the
effective limit doubled and every restart reset it. Additive: new table only.

Revision ID: 3391f31e0ba2
Revises: ee2824345611
"""
from alembic import op
import sqlalchemy as sa

revision = "3391f31e0ba2"
down_revision = "ee2824345611"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rate_limit_buckets",
        sa.Column("key", sa.String(300), primary_key=True),
        sa.Column("window_start", sa.DateTime(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_table("rate_limit_buckets")
