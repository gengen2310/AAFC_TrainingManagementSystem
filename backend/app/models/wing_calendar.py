"""Wing HQ Calendar models.

Wing-level events that appear as read-only overlays in squadron Annual
Program, Training Planner and Long Range views. Squadrons never copy
Wing events — they see them as inherited overlays and can record their
own response status separately.
"""
from sqlalchemy import String, Integer, Boolean, Text, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from ..database import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, UTCDateTime


WING_EVENT_TYPES = (
    "wing_event", "cadet_training", "adult_training", "public_holiday",
    "school_holiday", "meeting", "course", "competition", "ceremony",
    "staff_activity", "home_parade", "noting",
)

PLANNING_IMPORTANCE_LEVELS = (
    "must_attend", "key_event", "recommended", "optional", "home_parade", "noting",
)

WING_EVENT_STATUS = ("active", "cancelled", "postponed")

SQN_STATUS_VALUES = ("not_reviewed", "reviewed", "preparation_planned", "not_applicable")


class WingHQEvent(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """A Wing HQ calendar event. All squadrons in the wing inherit it as a read-only overlay."""
    __tablename__ = "wing_hq_events"

    wing_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_type: Mapped[str] = mapped_column(String(40), default="wing_event")
    start_date: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    end_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    start_time: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_time: Mapped[str | None] = mapped_column(String(8), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Import provenance — used for idempotent upserts
    source_system: Mapped[str | None] = mapped_column(String(60), nullable=True)   # e.g. "7WG_MASTER_2026"
    source_reference: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)  # sheet:row or hash
    source_event_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    planning_importance: Mapped[str] = mapped_column(String(30), default="key_event")
    audience: Mapped[list | None] = mapped_column(JSON, nullable=True)  # list of strings
    visibility: Mapped[str] = mapped_column(String(20), default="wing_only")
    status: Mapped[str] = mapped_column(String(20), default="active")
    requires_squadron_action: Mapped[bool] = mapped_column(Boolean, default=False)
    is_planning_anchor: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class SquadronEventStatus(Base, UUIDMixin, TimestampMixin):
    """Per-squadron response to a Wing HQ event.

    703SQN and 704SQN each maintain an independent status. Marking a Wing
    event 'reviewed' for one squadron does not affect any other squadron.
    """
    __tablename__ = "squadron_event_status"
    __table_args__ = (UniqueConstraint("wing_event_id", "squadron_id", name="uq_sqn_event_status"),)

    wing_event_id: Mapped[str] = mapped_column(ForeignKey("wing_hq_events.id"), index=True)
    squadron_id: Mapped[str] = mapped_column(ForeignKey("squadrons.id"), index=True)
    status: Mapped[str] = mapped_column(String(30), default="not_reviewed")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    local_activity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class WingEventCurriculumLink(Base, UUIDMixin, TimestampMixin):
    """Links a Wing HQ event to one or more curriculum items.

    Example: Gold 1 Consolidation Day links to GCLP-M01-01 and GCLP-M01-02.
    Not every Wing event needs a curriculum link.
    """
    __tablename__ = "wing_event_curriculum_links"
    __table_args__ = (UniqueConstraint("wing_event_id", "curriculum_item_id", name="uq_wing_event_curriculum"),)

    wing_event_id: Mapped[str] = mapped_column(ForeignKey("wing_hq_events.id"), index=True)
    curriculum_item_id: Mapped[str] = mapped_column(ForeignKey("curriculum_items.id"), index=True)
    link_type: Mapped[str] = mapped_column(String(30), default="covers")  # covers|prepares_for|references
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
