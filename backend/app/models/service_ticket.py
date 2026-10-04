from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base, UUIDMixin, TimestampMixin, UTCDateTime


class ServiceTicket(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "service_tickets"

    rank: Mapped[str] = mapped_column(String(40), nullable=False)
    first_name: Mapped[str] = mapped_column(String(80), nullable=False)
    last_name: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str] = mapped_column(String(200), nullable=False)
    # nullable in DB so archived squadrons can SET NULL; validated non-null at app layer
    squadron_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("squadrons.id", ondelete="SET NULL"), nullable=True
    )
    # Authoritative wing scope for wing-level submissions and for preserving
    # support-ticket tenancy if the originating squadron is later archived.
    wing_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("wings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    unit_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    category: Mapped[str | None] = mapped_column(String(40), nullable=True, default="other")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_to_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # Canonical assignment relationship. assigned_to_name remains a snapshot for
    # historical/display compatibility, but new assignments are account-backed.
    assigned_to_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    squadron: Mapped["Squadron"] = relationship("Squadron", lazy="joined", foreign_keys=[squadron_id])
    wing: Mapped["Wing"] = relationship("Wing", lazy="joined", foreign_keys=[wing_id])
    assigned_to_user: Mapped["User"] = relationship("User", lazy="joined", foreign_keys=[assigned_to_user_id])
