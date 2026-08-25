"""v56 — activity_type_tags, training_area_capability_tags, training_areas.capabilities

REM-23 continuation (part 3): advisory reference-data vocabulary for activity importance
types and training-area capabilities, following the exact same pattern as
facilitator_type_tags and session_status_reason_tags (v45/abc97c354bbb).

Changes:
  - New table: activity_type_tags (same shape as facilitator_type_tags)
  - New table: training_area_capability_tags (same shape)
  - New column: training_areas.capabilities (JSON, nullable) — advisory list of
    capability display_names; not a FK so existing rows need no backfill.

Seeded in this migration for already-deployed Postgres environments:
  Activity types: Must Attend, Key Event, Optional (global scope)
  Capabilities:   Projector, Whiteboard, PA System, WiFi, Computer Terminals,
                  Drill Floor, Outdoor Parade Space, Kitchen/Galley (global scope)

Revision ID: e2f3a4b5c6d7
Revises: d1e4f8a03b27
Create Date: 2026-08-25
"""
from alembic import op
import sqlalchemy as sa
import uuid
from datetime import datetime, timezone

revision = "e2f3a4b5c6d7"
down_revision = "d1e4f8a03b27"
branch_labels = None
depends_on = None

_DEFAULT_ACTIVITY_TYPES = ["Must Attend", "Key Event", "Optional"]
_DEFAULT_CAPABILITIES = [
    "Projector",
    "Whiteboard",
    "PA System",
    "WiFi",
    "Computer Terminals",
    "Drill Floor",
    "Outdoor Parade Space",
    "Kitchen/Galley",
]


def _norm(name: str) -> str:
    return " ".join(name.strip().lower().split())


def upgrade() -> None:
    # ── activity_type_tags ───────────────────────────────────────────────────
    op.create_table(
        "activity_type_tags",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("squadron_id", sa.String(36), sa.ForeignKey("squadrons.id"), nullable=True, index=True),
        sa.Column("wing_id", sa.String(36), nullable=True, index=True),
        sa.Column("scope", sa.String(20), nullable=False, server_default="squadron"),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("normalised_name", sa.String(80), nullable=False, index=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── training_area_capability_tags ────────────────────────────────────────
    op.create_table(
        "training_area_capability_tags",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("squadron_id", sa.String(36), sa.ForeignKey("squadrons.id"), nullable=True, index=True),
        sa.Column("wing_id", sa.String(36), nullable=True, index=True),
        sa.Column("scope", sa.String(20), nullable=False, server_default="squadron"),
        sa.Column("display_name", sa.String(80), nullable=False),
        sa.Column("normalised_name", sa.String(80), nullable=False, index=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(36), nullable=True),
        sa.Column("updated_by", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── training_areas.capabilities ──────────────────────────────────────────
    with op.batch_alter_table("training_areas") as batch_op:
        batch_op.add_column(sa.Column("capabilities", sa.JSON(), nullable=True))

    # ── seed global tags ─────────────────────────────────────────────────────
    conn = op.get_bind()
    now = datetime.now(timezone.utc)

    for name in _DEFAULT_ACTIVITY_TYPES:
        norm = _norm(name)
        existing = conn.execute(
            sa.text("SELECT id FROM activity_type_tags WHERE normalised_name=:n AND scope='global'"),
            {"n": norm},
        ).fetchone()
        if not existing:
            conn.execute(
                sa.text(
                    "INSERT INTO activity_type_tags (id, scope, display_name, normalised_name, is_active, created_at, updated_at) "
                    "VALUES (:id, 'global', :dn, :nn, true, :ts, :ts)"
                ),
                {"id": str(uuid.uuid4()), "dn": name, "nn": norm, "ts": now},
            )

    for name in _DEFAULT_CAPABILITIES:
        norm = _norm(name)
        existing = conn.execute(
            sa.text("SELECT id FROM training_area_capability_tags WHERE normalised_name=:n AND scope='global'"),
            {"n": norm},
        ).fetchone()
        if not existing:
            conn.execute(
                sa.text(
                    "INSERT INTO training_area_capability_tags (id, scope, display_name, normalised_name, is_active, created_at, updated_at) "
                    "VALUES (:id, 'global', :dn, :nn, true, :ts, :ts)"
                ),
                {"id": str(uuid.uuid4()), "dn": name, "nn": norm, "ts": now},
            )


def downgrade() -> None:
    with op.batch_alter_table("training_areas") as batch_op:
        batch_op.drop_column("capabilities")
    op.drop_table("training_area_capability_tags")
    op.drop_table("activity_type_tags")
