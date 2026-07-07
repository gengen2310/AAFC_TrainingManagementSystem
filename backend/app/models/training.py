"""Training-domain models with point-in-time historical fields."""
from sqlalchemy import String, Integer, ForeignKey, Boolean, Text, Float, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone

from ..database import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin

BLOCK_TYPES = frozenset({
    "arrival", "administration", "roll_call", "parade", "flight_period",
    "instructional_period", "break", "fatigues", "debrief", "dismissal", "custom",
})


class CurriculumItem(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "curriculum_items"
    owning_level: Mapped[str] = mapped_column(String(20), default="national")  # national|wing|squadron
    wing_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    squadron_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    # identifier is the globally unique lesson/mission key from the curriculum workbook,
    # e.g. "ORI-M01-01(2)". Multiple rows can share the same code (Module_Code) for
    # different parts. The 409/uniqueness check uses identifier, not code alone.
    identifier: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(40), index=True)
    part_number: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(200))
    phase: Mapped[str] = mapped_column(String(40), index=True)
    element: Mapped[str | None] = mapped_column(String(40))
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    part_count: Mapped[int] = mapped_column(Integer, default=1)
    instructor_suitability: Mapped[str | None] = mapped_column(String(120), nullable=True)
    core_status: Mapped[str] = mapped_column(String(20), default="core")  # core|additional
    learning_hub_url: Mapped[str | None] = mapped_column(String(400))
    recommended_term: Mapped[str | None] = mapped_column(String(10))
    recommended_sequence: Mapped[int] = mapped_column(Integer, default=0)
    active_status: Mapped[bool] = mapped_column(Boolean, default=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    replacement_curriculum_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    location_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    internal_admin_notes: Mapped[str | None] = mapped_column(Text)


class CustomPhase(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "custom_phases"
    squadron_id: Mapped[str] = mapped_column(ForeignKey("squadrons.id"), index=True)
    phase_key: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(80))
    abbr: Mapped[str | None] = mapped_column(String(20))


class ParadeNight(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "parade_nights"
    squadron_id: Mapped[str] = mapped_column(ForeignKey("squadrons.id"), index=True)
    wing_id: Mapped[str] = mapped_column(String(36), index=True)
    training_year: Mapped[int] = mapped_column(Integer, default=2026, index=True)
    date: Mapped[str] = mapped_column(String(10), index=True)  # ISO date
    term: Mapped[str | None] = mapped_column(String(10))
    start_time: Mapped[str | None] = mapped_column(String(10))
    end_time: Mapped[str | None] = mapped_column(String(10))
    session_count: Mapped[int] = mapped_column(Integer, default=3)
    parade_type: Mapped[str] = mapped_column(String(20), default="normal")  # normal|activity|ceremonial|admin|stand_down|cancelled
    notes: Mapped[str | None] = mapped_column(Text)
    published_status: Mapped[bool] = mapped_column(Boolean, default=False)
    readiness_score: Mapped[int] = mapped_column(Integer, default=0)
    closeout_status: Mapped[str] = mapped_column(String(20), default="open")  # open|closed
    published_by: Mapped[str | None] = mapped_column(String(36))
    closed_by: Mapped[str | None] = mapped_column(String(36))
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    timing_template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class Session(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "sessions"
    parade_night_id: Mapped[str] = mapped_column(ForeignKey("parade_nights.id"), index=True)
    squadron_id: Mapped[str] = mapped_column(String(36), index=True)
    period_number: Mapped[int] = mapped_column(Integer, default=1)
    session_title: Mapped[str | None] = mapped_column(String(200))
    curriculum_item_id: Mapped[str | None] = mapped_column(String(36), index=True)
    curriculum_code_at_time: Mapped[str | None] = mapped_column(String(40))
    curriculum_title_at_time: Mapped[str | None] = mapped_column(String(200))
    custom_title: Mapped[str | None] = mapped_column(String(200))
    phase_at_time: Mapped[str | None] = mapped_column(String(40))
    element_at_time: Mapped[str | None] = mapped_column(String(40))
    facilitator_id: Mapped[str | None] = mapped_column(String(36), index=True)
    facilitator_rank_at_time: Mapped[str | None] = mapped_column(String(40))
    facilitator_display_name_at_time: Mapped[str | None] = mapped_column(String(120))
    assistant_facilitator_id: Mapped[str | None] = mapped_column(String(36))
    backup_facilitator_id: Mapped[str | None] = mapped_column(String(36))
    training_area_id: Mapped[str | None] = mapped_column(String(36))
    training_area_name_at_time: Mapped[str | None] = mapped_column(String(120))
    equipment_required: Mapped[str | None] = mapped_column(Text)
    expected_attendance: Mapped[int | None] = mapped_column(Integer)
    actual_attendance: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="planned", index=True)
    delivery_notes: Mapped[str | None] = mapped_column(Text)
    issue_notes: Mapped[str | None] = mapped_column(Text)
    not_delivered_reason: Mapped[str | None] = mapped_column(Text)
    cancelled_reason: Mapped[str | None] = mapped_column(Text)
    rescheduled_to_date: Mapped[str | None] = mapped_column(String(10))
    cadet_group: Mapped[str | None] = mapped_column(String(30), nullable=True)  # orientation/initial/junior/intermediate/senior
    part_number: Mapped[int | None] = mapped_column(Integer, nullable=True)  # which part of multi-part curriculum
    follow_up_required: Mapped[bool] = mapped_column(Boolean, default=False)
    follow_up_due_date: Mapped[str | None] = mapped_column(String(10))
    evidence_text: Mapped[str | None] = mapped_column(Text)
    evidence_url: Mapped[str | None] = mapped_column(String(400))


class SessionStatusHistory(Base, UUIDMixin):
    __tablename__ = "session_status_history"
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    old_status: Mapped[str | None] = mapped_column(String(30))
    new_status: Mapped[str | None] = mapped_column(String(30))
    changed_by: Mapped[str | None] = mapped_column(String(36))
    reason: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Facilitator(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "facilitators"
    squadron_id: Mapped[str] = mapped_column(ForeignKey("squadrons.id"), index=True)
    wing_id: Mapped[str] = mapped_column(String(36), index=True)
    first_name: Mapped[str | None] = mapped_column(String(80))
    last_name: Mapped[str] = mapped_column(String(80))
    current_rank: Mapped[str | None] = mapped_column(String(40))
    type: Mapped[str] = mapped_column(String(30), default="Staff")
    qualifications: Mapped[str | None] = mapped_column(Text)
    subject_areas: Mapped[list[str] | None] = mapped_column(JSON)
    max_sessions_per_night: Mapped[int] = mapped_column(Integer, default=2)
    max_sessions_per_month: Mapped[int] = mapped_column(Integer, default=8)
    active_status: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)


class FacilitatorRankHistory(Base, UUIDMixin):
    __tablename__ = "facilitator_rank_history"
    facilitator_id: Mapped[str] = mapped_column(ForeignKey("facilitators.id"), index=True)
    rank: Mapped[str | None] = mapped_column(String(40))
    effective_from: Mapped[str | None] = mapped_column(String(10))
    effective_to: Mapped[str | None] = mapped_column(String(10))
    changed_by: Mapped[str | None] = mapped_column(String(36))
    reason: Mapped[str | None] = mapped_column(Text)


class TrainingArea(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "training_areas"
    squadron_id: Mapped[str] = mapped_column(ForeignKey("squadrons.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[str | None] = mapped_column(String(40))
    capacity: Mapped[int | None] = mapped_column(Integer)
    indoor_outdoor: Mapped[str | None] = mapped_column(String(20))
    availability_status: Mapped[str] = mapped_column(String(20), default="available")
    notes: Mapped[str | None] = mapped_column(Text)
    active_status: Mapped[bool] = mapped_column(Boolean, default=True)


class Equipment(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "equipment"
    squadron_id: Mapped[str] = mapped_column(ForeignKey("squadrons.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    type: Mapped[str | None] = mapped_column(String(40))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    available_quantity: Mapped[int] = mapped_column(Integer, default=1)
    condition: Mapped[str] = mapped_column(String(20), default="good")
    approval_required: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    active_status: Mapped[bool] = mapped_column(Boolean, default=True)


class Activity(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "activities"
    owning_level: Mapped[str] = mapped_column(String(20), default="squadron")
    national_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    wing_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    squadron_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    activity_name: Mapped[str] = mapped_column(String(200))
    activity_type: Mapped[str | None] = mapped_column(String(40))
    date_start: Mapped[str] = mapped_column(String(10))
    date_end: Mapped[str | None] = mapped_column(String(10))
    audience: Mapped[list | None] = mapped_column(JSON, nullable=True)
    location: Mapped[str | None] = mapped_column(String(200))
    time_start: Mapped[str | None] = mapped_column(String(8), nullable=True)
    time_end: Mapped[str | None] = mapped_column(String(8), nullable=True)
    cea_seq_nr: Mapped[str | None] = mapped_column(String(30), nullable=True, index=True)
    planning_importance: Mapped[str | None] = mapped_column(String(30), nullable=True)  # must_attend/key_event/home_parade/optional/noting
    importance_level: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1=Must Attend … 5=Noting
    oic: Mapped[str | None] = mapped_column(String(120))
    twoic: Mapped[str | None] = mapped_column(String(120))
    risk_status: Mapped[str] = mapped_column(String(20), default="pending")
    permission_status: Mapped[str] = mapped_column(String(20), default="pending")
    workflow_status: Mapped[str] = mapped_column(String(30), default="planning")
    closeout_status: Mapped[str] = mapped_column(String(20), default="open")
    notes: Mapped[str | None] = mapped_column(Text)


class Cadet(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "cadets"
    squadron_id: Mapped[str] = mapped_column(ForeignKey("squadrons.id"), index=True)
    service_number: Mapped[str | None] = mapped_column(String(40), index=True)
    rank: Mapped[str | None] = mapped_column(String(40))
    first_name: Mapped[str | None] = mapped_column(String(80))
    last_name: Mapped[str | None] = mapped_column(String(80))
    phase: Mapped[str | None] = mapped_column(String(40))
    flight: Mapped[str | None] = mapped_column(String(40))
    attendance_percentage: Mapped[float | None] = mapped_column(Float)
    recent_attendance_trend: Mapped[str | None] = mapped_column(String(20))
    last_attended: Mapped[str | None] = mapped_column(String(10))
    sitrep_part_1_status: Mapped[str | None] = mapped_column(String(20))
    sitrep_part_2_status: Mapped[str | None] = mapped_column(String(20))
    promotion_interest: Mapped[str | None] = mapped_column(String(20))
    extension_completion: Mapped[str | None] = mapped_column(String(20))
    support_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    support_notes: Mapped[str | None] = mapped_column(Text)  # sensitive — gated access
    active_status: Mapped[bool] = mapped_column(Boolean, default=True)


# ── TIMING TEMPLATES ──────────────────────────────────────────────────────────

class TimingTemplate(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """Squadron parade-night timing structure, effective from a given date.

    A template defines the ordered block structure (Arrival, Roll Call, Period 1 …)
    and which blocks are instructional periods that generate schedulable sessions.
    effective_from / effective_to define the date range. Changing future templates
    does not alter already-created parade nights.
    """
    __tablename__ = "timing_templates"
    squadron_id: Mapped[str] = mapped_column(ForeignKey("squadrons.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    effective_from: Mapped[str] = mapped_column(String(10), index=True)   # ISO YYYY-MM-DD
    effective_to: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    active_status: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    blocks: Mapped[list["TimingBlock"]] = relationship(
        back_populates="template",
        order_by="TimingBlock.display_order",
        cascade="all, delete-orphan",
    )


class TimingBlock(Base, UUIDMixin, TimestampMixin):
    """An ordered block within a TimingTemplate.

    block_type must be one of BLOCK_TYPES.
    is_instructional_period=True means this block generates a schedulable curriculum session.
    'Flight Period' as a block_type is a timing slot before Period 1 — it is NOT the
    same as a Flight (squadron sub-group) or a separate account scope.
    """
    __tablename__ = "timing_blocks"
    timing_template_id: Mapped[str] = mapped_column(ForeignKey("timing_templates.id"), index=True)
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    block_name: Mapped[str] = mapped_column(String(80))
    block_type: Mapped[str] = mapped_column(String(40), default="custom")
    start_time: Mapped[str | None] = mapped_column(String(10), nullable=True)   # HH:MM
    end_time: Mapped[str | None] = mapped_column(String(10), nullable=True)     # HH:MM
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_instructional_period: Mapped[bool] = mapped_column(Boolean, default=False)
    period_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_optional: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    template: Mapped["TimingTemplate"] = relationship(back_populates="blocks")


class ParadeNightTimingOverride(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """Override the timing template for one specific parade night.

    Does not alter the default future template. The override references an existing
    TimingTemplate (typically a one-off template created for that occasion).
    Archived overrides are retained for audit history.
    """
    __tablename__ = "parade_night_timing_overrides"
    parade_night_id: Mapped[str] = mapped_column(
        ForeignKey("parade_nights.id"), index=True, unique=True,
    )
    timing_template_id: Mapped[str | None] = mapped_column(
        ForeignKey("timing_templates.id"), nullable=True, index=True,
    )
    reason: Mapped[str] = mapped_column(Text)


# Scope constants (also used by the endpoint and migration)
ELEMENT_SCOPE_LEVELS = frozenset({"national", "wing", "squadron", "system"})


class CurriculumElement(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """Managed subject/category groupings for curriculum items.

    Elements are scoped: system > national > wing > squadron. Squadron users see
    national elements, wing elements for their wing, and their own squadron elements.
    Elements at higher scopes are read-only to lower-scope admins.
    """
    __tablename__ = "curriculum_elements"
    name: Mapped[str] = mapped_column(String(60), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    scope_level: Mapped[str] = mapped_column(String(20), index=True)  # system|national|wing|squadron
    wing_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    squadron_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    active_status: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
