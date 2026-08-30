"""Training-domain models with point-in-time historical fields."""
from sqlalchemy import String, Integer, ForeignKey, Boolean, Text, Float, DateTime, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone

from ..database import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, UTCDateTime

BLOCK_TYPES = frozenset({
    "arrival", "admin", "parade", "briefing", "training_period",
    "drinks_break", "fatigue", "dismissal", "other",
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
    retired_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    replacement_curriculum_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    location_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    internal_admin_notes: Mapped[str | None] = mapped_column(Text)


class ParadeNight(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "parade_nights"
    squadron_id: Mapped[str] = mapped_column(ForeignKey("squadrons.id"), index=True)
    wing_id: Mapped[str] = mapped_column(String(36), index=True)
    planning_year_id: Mapped[str] = mapped_column(ForeignKey("planning_years.id"), nullable=False, index=True)
    planning_year: Mapped["PlanningYear"] = relationship("PlanningYear", back_populates="parade_nights", lazy="select")
    week_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String, nullable=True)
    date: Mapped[str] = mapped_column(String(10), index=True)  # ISO date
    term: Mapped[str | None] = mapped_column(String(10))
    start_time: Mapped[str | None] = mapped_column(String(10))
    end_time: Mapped[str | None] = mapped_column(String(10))
    session_count: Mapped[int] = mapped_column(Integer, default=3)
    parade_type: Mapped[str] = mapped_column(String(20), default="normal")  # normal|activity|ceremonial|admin|stand_down|cancelled
    notes: Mapped[str | None] = mapped_column(Text)
    published_status: Mapped[bool] = mapped_column(Boolean, default=False)
    # readiness_score is a legacy 0-100 projection, DERIVED from planning_status by
    # services_readiness.parade_night_readiness() — not independently authoritative.
    # planning_status/data_quality (services_readiness.PLANNING_STATUSES /
    # DATA_QUALITY_STATES) are the real source of truth; nullable because existing
    # rows are backfilled by a migration, not because either is optional going forward.
    readiness_score: Mapped[int] = mapped_column(Integer, default=0)
    planning_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    data_quality: Mapped[str | None] = mapped_column(String(30), nullable=True)
    closeout_status: Mapped[str] = mapped_column(String(20), default="open")  # open|closed
    published_by: Mapped[str | None] = mapped_column(String(36))
    closed_by: Mapped[str | None] = mapped_column(String(36))
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    timing_template_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Optimistic locking for update_parade_night's own-field edits (date/term/time/notes/
    # etc.) -- confirmed via live testing that two concurrent PATCHes silently last-write-
    # win with zero conflict signal before this. Same pattern already used on PlanningYear/
    # AnchorEvent/PlanningNotice/Session.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


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
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    timing_block_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    # FK to timing_blocks.id — not a SQLAlchemy FK constraint; enforced at the
    # app layer by _validate_timing_block() in routers/training.py, on both the
    # create and edit paths. That enforcement was missing until 2026-08-26:
    # this comment asserted a guarantee nothing implemented, and any string was
    # accepted and stored.
    # to avoid cascade complexity across SQLite and PostgreSQL.
    # ON DELETE behaviour: set to null when the timing template is changed.


class SessionStatusHistory(Base, UUIDMixin):
    __tablename__ = "session_status_history"
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    old_status: Mapped[str | None] = mapped_column(String(30))
    new_status: Mapped[str | None] = mapped_column(String(30))
    changed_by: Mapped[str | None] = mapped_column(String(36))
    reason: Mapped[str | None] = mapped_column(Text)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime, default=lambda: datetime.now(timezone.utc))


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


class SubjectAreaTag(Base, UUIDMixin, TimestampMixin):
    """Canonical subject-area tags; user-creatable, scoped to squadron/wing/global."""
    __tablename__ = "subject_area_tags"
    squadron_id: Mapped[str | None] = mapped_column(ForeignKey("squadrons.id"), nullable=True, index=True)
    wing_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    scope: Mapped[str] = mapped_column(String(20), default="squadron")  # global / wing / squadron
    display_name: Mapped[str] = mapped_column(String(80))
    normalised_name: Mapped[str] = mapped_column(String(80), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(36))


class FacilitatorTypeTag(Base, UUIDMixin, TimestampMixin):
    """Canonical facilitator-type reference data; user-creatable, scoped to
    squadron/wing/global -- mirrors SubjectAreaTag's exact shape (remediation
    program Section 6, Stage 3). Facilitator.type stays a free-text column
    (matches the existing Facilitator.subject_areas convention: reference
    tags are advisory/suggested, not a hard foreign key), so this table adds
    governance without a migration risk to existing Facilitator rows."""
    __tablename__ = "facilitator_type_tags"
    squadron_id: Mapped[str | None] = mapped_column(ForeignKey("squadrons.id"), nullable=True, index=True)
    wing_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    scope: Mapped[str] = mapped_column(String(20), default="squadron")  # global / wing / squadron
    display_name: Mapped[str] = mapped_column(String(80))
    normalised_name: Mapped[str] = mapped_column(String(80), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(36))


class SessionStatusReasonTag(Base, UUIDMixin, TimestampMixin):
    """Canonical session-status-change reason reference data; user-creatable,
    scoped to squadron/wing/global -- mirrors SubjectAreaTag/FacilitatorTypeTag's
    exact shape (REM-23 continuation). The #or-reason dropdown's reason text
    stays free-text on the Session/SessionStatusHistory row (matches
    Facilitator.type's own convention: reference tags are advisory/governed,
    not a hard foreign key), so this table adds governance with zero
    migration risk to existing history rows."""
    __tablename__ = "session_status_reason_tags"
    squadron_id: Mapped[str | None] = mapped_column(ForeignKey("squadrons.id"), nullable=True, index=True)
    wing_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    scope: Mapped[str] = mapped_column(String(20), default="squadron")  # global / wing / squadron
    display_name: Mapped[str] = mapped_column(String(80))
    normalised_name: Mapped[str] = mapped_column(String(80), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(36))


class ActivityTypeTag(Base, UUIDMixin, TimestampMixin):
    """Canonical activity-importance/type reference data; user-creatable, scoped
    to squadron/wing/global -- mirrors FacilitatorTypeTag/SessionStatusReasonTag's
    exact shape (REM-23 continuation). Activity.activity_type stays a free-text
    column (advisory, not a hard FK), so this table adds governance with zero
    migration risk to existing Activity rows."""
    __tablename__ = "activity_type_tags"
    squadron_id: Mapped[str | None] = mapped_column(ForeignKey("squadrons.id"), nullable=True, index=True)
    wing_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    scope: Mapped[str] = mapped_column(String(20), default="squadron")  # global / wing / squadron
    display_name: Mapped[str] = mapped_column(String(80))
    normalised_name: Mapped[str] = mapped_column(String(80), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(36))


class TrainingAreaCapabilityTag(Base, UUIDMixin, TimestampMixin):
    """Canonical training-area capability reference data; user-creatable, scoped
    to squadron/wing/global -- mirrors the same advisory tag pattern. TrainingArea.capabilities
    stays a JSON column storing display_name strings (advisory, not hard FKs)."""
    __tablename__ = "training_area_capability_tags"
    squadron_id: Mapped[str | None] = mapped_column(ForeignKey("squadrons.id"), nullable=True, index=True)
    wing_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    scope: Mapped[str] = mapped_column(String(20), default="squadron")  # global / wing / squadron
    display_name: Mapped[str] = mapped_column(String(80))
    normalised_name: Mapped[str] = mapped_column(String(80), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(36))


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
    capabilities: Mapped[list | None] = mapped_column(JSON, nullable=True)


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
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
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
    # R5-M14: unique=True removed; replaced by partial unique index in v55
    # migration (uq_pnto_active_per_night WHERE is_archived = 0) so that a
    # new override can be created after the previous one is archived.
    parade_night_id: Mapped[str] = mapped_column(
        ForeignKey("parade_nights.id"), index=True,
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


# Scope constants for the phase catalogue — same shape as ELEMENT_SCOPE_LEVELS
PHASE_SCOPE_LEVELS = frozenset({"national", "wing", "squadron", "system"})


class CurriculumPhase(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """Managed training-phase catalogue (master transformation plan Block 10).

    Mirrors CurriculumElement's proven scope/visibility pattern exactly:
    system > national > wing > squadron, squadron users see national + their
    wing's + their own squadron's phases, higher-scope phases are read-only
    to lower-scope admins. CurriculumItem.phase / Session.phase_at_time stay
    plain strings matched by name — same relationship CurriculumElement has
    to CurriculumItem.element today, not a schema-level FK, so this table
    governs the catalogue and visibility of phase names without touching
    existing historical free-text data.
    """
    __tablename__ = "curriculum_phases"
    name: Mapped[str] = mapped_column(String(60), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    scope_level: Mapped[str] = mapped_column(String(20), index=True)  # system|national|wing|squadron
    wing_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    squadron_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    active_status: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


STAGE_CODES = frozenset({"ORI", "INI", "JNR", "INT", "SNR"})


class TrainingClass(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """A Squadron-specific local group undertaking a Training Stage during a
    Training Year (e.g. "Senior 1", "Senior 2" — both undertaking the same
    Senior CurriculumPhase). See docs/product-review/parallel-class-impact-analysis.md
    for the full design rationale.

    Distinct from CurriculumPhase (the Stage/program definition, which stays
    a single scoped catalogue row shared by every class undertaking it) and
    from Flight (Cadet/User sub-squadron grouping — a different, unrelated
    concept; see .claude/rules/architecture.md).

    Squadron-and-year scoped, like PlanningYear, not nationally/wing
    inheritable like CurriculumPhase — a class belongs to exactly one
    Squadron's one Training Year. Session.cadet_group and Cadet.phase remain
    in place as free-text compatibility fields; this table is additive, not
    a replacement, until every consumer has migrated (addendum §86-87).
    """
    __tablename__ = "training_classes"
    squadron_id: Mapped[str] = mapped_column(ForeignKey("squadrons.id"), index=True)
    training_year_id: Mapped[str] = mapped_column(ForeignKey("planning_years.id"), index=True)
    training_stage_id: Mapped[str | None] = mapped_column(ForeignKey("curriculum_phases.id"), index=True, nullable=True)
    stage_code: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    # ORI | INI | JNR | INT | SNR — null for classes created before this feature
    display_name: Mapped[str] = mapped_column(String(80))
    sequence: Mapped[int] = mapped_column(Integer, default=0)
    start_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # ISO date
    end_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    expected_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Optimistic locking, same pattern as ParadeNight/PlanningYear/Session --
    # rename/archive is exactly the kind of low-frequency-but-real-conflict
    # edit that pattern protects.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class SessionAudience(Base, UUIDMixin, TimestampMixin):
    """Which Training Class(es) a Session was planned for/delivered to (CLASS-03).

    A Session can target one or many Training Classes (e.g. a combined Drill
    Session for Senior 1 + Senior 2). This is what Session.cadet_group's
    single free-text string could never represent — see
    docs/product-review/parallel-class-impact-analysis.md Finding 2.

    outcome_override/outcome_override_reason support addendum §48: a Session
    delivered jointly to several classes defaults to the Session's own
    status for every class, but one class can be recorded as an exception
    (e.g. delivered to Senior 1 and Senior 2, but Senior 3 didn't attend)
    without needing three separate Sessions. NULL override means "use the
    parent Session's own status" -- this row does not duplicate outcome data
    that already lives on Session; it only stores the deviation.

    No SoftDeleteMixin -- membership rows are removed via DELETE, not
    archived, since "this class was never part of this session" has no
    historical value once corrected (unlike TrainingClass/Session themselves,
    which are never hard-deleted). A session/class pair may exist only once
    (unique constraint) -- the API is idempotent create, not append.
    """
    __tablename__ = "session_audience"
    __table_args__ = (
        UniqueConstraint("session_id", "training_class_id", name="uq_session_audience_pair"),
    )
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), index=True)
    training_class_id: Mapped[str] = mapped_column(ForeignKey("training_classes.id"), index=True)
    outcome_override: Mapped[str | None] = mapped_column(String(30), nullable=True)
    outcome_override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class CadetClassMembership(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """Which Training Class(es) a Cadet belongs to, currently or historically
    (CLASS-09). Explicitly product-scope-confirmed by the user before this
    was built -- the addendum (§38/§39) makes individual cadet-class tracking
    conditional on an explicit product decision, not an engineering default,
    since class-level planning (TrainingClass/SessionAudience) works without
    it and this program's own data-minimisation principle warns against
    collecting cadet-identifiable data speculatively.

    Distinct from SessionAudience (CLASS-03, which Class a *Session*
    targets): this is the Cadet side, and unlike SessionAudience it is a
    genuine lifecycle record (start/end dates), not an idempotent current-set
    membership a UI just replaces wholesale.

    Enables the addendum's own "Foundation + Extension concurrent
    membership" scenario -- a Cadet can hold an active membership in a
    Foundation-stage class (e.g. Senior 1) and an Extension-stage class
    (e.g. Bronze CLP) at the same time, which Cadet.phase's single free-text
    column can never express. Cadet.phase is NOT dropped or replaced here --
    kept in place as the existing compatibility field, per
    capability-preservation and this program's own §86/§87 migration
    discipline (every new planning surface is additive until every consumer
    has migrated, not a forced cutover).

    No DB-level unique constraint on (cadet_id, training_class_id) -- a
    Cadet can legitimately hold more than one historical (archived) or
    ended (active_status=False) membership in the same Class over time
    (left and rejoined). "No duplicate *currently active* membership for
    the same Cadet+Class pair" is enforced at the API layer instead, where
    it can be checked against active_status/is_archived together rather
    than needing a partial/conditional unique index.
    """
    __tablename__ = "cadet_class_memberships"
    cadet_id: Mapped[str] = mapped_column(ForeignKey("cadets.id"), index=True)
    training_class_id: Mapped[str] = mapped_column(ForeignKey("training_classes.id"), index=True)
    start_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # ISO date
    end_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    active_status: Mapped[bool] = mapped_column(Boolean, default=True)
    # Provenance -- "manual" (the only path this pass builds) vs a future
    # import path, matching the same source-tagging pattern already used
    # elsewhere in this codebase (e.g. CeaActivity.source).
    source: Mapped[str] = mapped_column(String(20), default="manual", server_default="manual")
    # Optimistic locking -- this is a real lifecycle record meant to be
    # edited (closing out with an end_date), unlike SessionAudience's
    # replace-the-whole-set model, so the same ParadeNight/PlanningYear/
    # TrainingClass conflict-protection pattern applies here too.
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class ParadeNightTemplate(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """A named, reusable session structure that can be applied to any future
    Parade Night without needing an existing night to copy from (WORK-17).

    Captures planning intent only: curriculum items, facilitators, and rooms.
    Does NOT capture SessionAudience (Training Class) rows because Training
    Classes are year-specific — a template applied in a new Training Year must
    have its audiences re-assigned to that year's classes.

    Squadron-scoped. Not year-scoped — templates persist across Training Years
    by design, which is the key value-add over WORK-11's copy-from-existing-
    night approach.
    """
    __tablename__ = "parade_night_templates"
    squadron_id: Mapped[str] = mapped_column(ForeignKey("squadrons.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)

    sessions: Mapped[list["ParadeNightTemplateSession"]] = relationship(
        "ParadeNightTemplateSession",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="ParadeNightTemplateSession.period_number",
    )


class ParadeNightTemplateSession(Base, UUIDMixin):
    """One session slot within a ParadeNightTemplate.

    Mirrors the planning fields of Session (not outcome fields).
    period_number matches Session.period_number.
    """
    __tablename__ = "parade_night_template_sessions"
    template_id: Mapped[str] = mapped_column(
        ForeignKey("parade_night_templates.id", ondelete="CASCADE"), index=True
    )
    period_number: Mapped[int] = mapped_column(Integer)
    curriculum_item_id: Mapped[str | None] = mapped_column(
        ForeignKey("curriculum_items.id"), nullable=True
    )
    custom_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    facilitator_id: Mapped[str | None] = mapped_column(
        ForeignKey("facilitators.id"), nullable=True
    )
    training_area_id: Mapped[str | None] = mapped_column(
        ForeignKey("training_areas.id"), nullable=True
    )
    cadet_group: Mapped[str | None] = mapped_column(String(40), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    template: Mapped["ParadeNightTemplate"] = relationship(
        "ParadeNightTemplate", back_populates="sessions"
    )
