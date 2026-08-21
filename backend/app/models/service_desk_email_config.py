from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base, UUIDMixin, TimestampMixin


class ServiceDeskEmailConfig(Base, UUIDMixin, TimestampMixin):
    """Notification email address for each scope (system / national / per-wing)."""

    __tablename__ = "service_desk_email_configs"

    # "system" | "national" | "wing"
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    # Only set when scope = "wing"
    wing_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("wings.id", ondelete="CASCADE"), nullable=True, index=True
    )
    notification_email: Mapped[str] = mapped_column(String(200), nullable=False)
    updated_by_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
