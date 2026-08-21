"""Custom training phases — ad-hoc scheduling groups beyond the 5 standard stages."""
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from ..database import Base, UUIDMixin, TimestampMixin

CUSTOM_PHASE_SCOPE_TYPES = frozenset({"squadron", "wing", "national", "system"})


class CustomTrainingPhase(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "custom_training_phases"
    name: Mapped[str] = mapped_column(String(120))
    scope_type: Mapped[str] = mapped_column(String(20), index=True)
    scope_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    applies_from: Mapped[str] = mapped_column(String(10))   # ISO YYYY-MM-DD
    applies_to: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
