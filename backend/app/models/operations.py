"""Action items, exceptions, immutable audit log, import/export logs."""
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timezone

from ..database import Base, UUIDMixin, TimestampMixin, UTCDateTime


class ActionItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "action_items"
    scope: Mapped[str] = mapped_column(String(20), default="squadron")
    squadron_id: Mapped[str | None] = mapped_column(String(36), index=True)
    wing_id: Mapped[str | None] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[str | None] = mapped_column(String(120))
    due_date: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    severity: Mapped[str] = mapped_column(String(30), default="action_required")
    linked_object_type: Mapped[str | None] = mapped_column(String(40))
    linked_object_id: Mapped[str | None] = mapped_column(String(36))
    source: Mapped[str] = mapped_column(String(20), default="manual")  # manual|automation
    closed_by: Mapped[str | None] = mapped_column(String(36))
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    closure_note: Mapped[str | None] = mapped_column(Text)


class Exception(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "exceptions"
    scope: Mapped[str] = mapped_column(String(20), default="squadron")
    squadron_id: Mapped[str | None] = mapped_column(String(36), index=True)
    wing_id: Mapped[str | None] = mapped_column(String(36), index=True)
    source_module: Mapped[str | None] = mapped_column(String(40))
    affected_object_type: Mapped[str | None] = mapped_column(String(40))
    affected_object_id: Mapped[str | None] = mapped_column(String(36))
    severity: Mapped[str] = mapped_column(String(30), default="watch")
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    owner: Mapped[str | None] = mapped_column(String(120))
    due_date: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base, UUIDMixin):
    """Immutable. There is no update/delete path through the API."""
    __tablename__ = "audit_logs"
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime, default=lambda: datetime.now(timezone.utc), index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), index=True)
    role: Mapped[str | None] = mapped_column(String(40))
    scope: Mapped[str | None] = mapped_column(String(20))
    wing_id: Mapped[str | None] = mapped_column(String(36), index=True)
    squadron_id: Mapped[str | None] = mapped_column(String(36), index=True)
    proxy_session_id: Mapped[str | None] = mapped_column(String(36))
    object_type: Mapped[str | None] = mapped_column(String(40), index=True)
    object_id: Mapped[str | None] = mapped_column(String(36), index=True)
    action: Mapped[str] = mapped_column(String(40), index=True)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    batch_id: Mapped[str | None] = mapped_column(String(36), index=True)


class SystemSetting(Base):
    """Single key→value store for platform-level settings (e.g. maintenance mode).
    Not tenant-scoped — there is one shared row per key across the whole deployment."""
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class ImportLog(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "import_logs"
    user_id: Mapped[str | None] = mapped_column(String(36))
    squadron_id: Mapped[str | None] = mapped_column(String(36))
    import_type: Mapped[str] = mapped_column(String(40))
    filename: Mapped[str | None] = mapped_column(String(200))
    rows_read: Mapped[int] = mapped_column(Integer, default=0)
    rows_accepted: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)
    validation_errors: Mapped[str | None] = mapped_column(Text)
    committed: Mapped[int] = mapped_column(Integer, default=0)
    rollback_status: Mapped[str | None] = mapped_column(String(20))


class ExportLog(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "export_logs"
    user_id: Mapped[str | None] = mapped_column(String(36))
    scope: Mapped[str | None] = mapped_column(String(20))
    export_type: Mapped[str] = mapped_column(String(40))
    filters: Mapped[str | None] = mapped_column(Text)
    filename: Mapped[str | None] = mapped_column(String(200))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
