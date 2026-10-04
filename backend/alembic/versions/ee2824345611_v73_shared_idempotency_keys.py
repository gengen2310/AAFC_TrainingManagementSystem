"""v73: shared Idempotency-Key claims (idempotency_keys).

The Idempotency-Key dedup for POST /api/facilitators was a per-process dict,
so with several gunicorn workers a retry reaching a different worker created a
duplicate. The claim is now a row whose primary key is the scoped key, shared
by every worker. Additive: a new table only; no existing data is touched.

Revision ID: ee2824345611
Revises: c0e3a6b8d4f2
"""
from alembic import op
import sqlalchemy as sa

revision = "ee2824345611"
down_revision = "c0e3a6b8d4f2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(255), primary_key=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("response_json", sa.Text(), nullable=True),
    )
    op.create_index("ix_idempotency_keys_expires_at", "idempotency_keys", ["expires_at"])


def downgrade():
    op.drop_index("ix_idempotency_keys_expires_at", table_name="idempotency_keys")
    op.drop_table("idempotency_keys")
