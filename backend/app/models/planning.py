"""TRGO Planning Module models.

Provides data models for the annual training planning workflow:
planning years, parade dates, holidays, anchor events, term planner,
parade night builder, scheduled sessions, planning locations, and
conflict detection.
"""
from sqlalchemy import String, Integer, Boolean, Text, Date, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin

CADET_GROUPS = ("orientation", "initial", "junior", "intermediate", "senior")
IMPORTANCE_LEVELS = ("must_attend", "key_event", "optional")
EVENT_TYPES = (
    "ceremonial", "fieldcraft", "adventure_training", "dining_in",
    "orientation_weekend", "community", "sport", "admin", "inspection", "other"
)
CONFLICT_TYPES = (
    "facilitator_double_booked", "room_double_booked", "empty_session",
    "anchor_no_prep", "holiday_conflict", "outdoor_winter",
    "consecutive_classroom", "capacity_mismatch", "multi_part_gap",
)
SEVERITY = ("info", "warning", "critical")
SESSION_STATUS = ("draft", "confirmed", "published")
PREP_STATUS = ("planned", "confirmed", "complete")


class PlanningYear(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "planning_years"
    unit_id: Mapped[str | None] = mapped_column(ForeignKey("squadrons.id"), nullable=True, index=True)
    wing_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    active_status: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class ParadeDate(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "parade_dates"
    planning_year_id: Mapped[str] = mapped_column(ForeignKey("planning_years.id"), index=True)
    unit_id: Mapped[str | None] = mapped_column(ForeignKey("squadrons.id"), nullable=True, index=True)
    parade_date: Mapped[str] = mapped_column(String(10), nullable=False)  # ISO date YYYY-MM-DD
    parade_type: Mapped[str] = mapped_column(String(30), default="standard")  # standard/special/cancelled
    term: Mapped[str | None] = mapped_column(String(10), nullable=True)  # T1/T2/T3/T4
    week_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    parade_night_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # FK → parade_nights.id


class HolidayPeriod(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "holiday_periods"
    planning_year_id: Mapped[str] = mapped_column(ForeignKey("planning_years.id"), index=True)
    jurisdiction: Mapped[str | None] = mapped_column(String(40), nullable=True)  # national/state/local
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    end_date: Mapped[str] = mapped_column(String(10), nullable=False)
    holiday_type: Mapped[str] = mapped_column(String(40), default="school_holiday")
    affects_parade: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class AnchorEvent(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "anchor_events"
    planning_year_id: Mapped[str] = mapped_column(ForeignKey("planning_years.id"), index=True)
    owning_level: Mapped[str] = mapped_column(String(20), default="unit")  # national/wing/unit
    wing_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    unit_id: Mapped[str | None] = mapped_column(ForeignKey("squadrons.id"), nullable=True, index=True)
    event_name: Mapped[str] = mapped_column(String(200), nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), default="other")
    importance: Mapped[str] = mapped_column(String(20), default="key_event")
    importance_level: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1=Must Attend … 5=Noting
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    end_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    audience_orientation: Mapped[bool] = mapped_column(Boolean, default=True)
    audience_initial: Mapped[bool] = mapped_column(Boolean, default=True)
    audience_junior: Mapped[bool] = mapped_column(Boolean, default=True)
    audience_intermediate: Mapped[bool] = mapped_column(Boolean, default=True)
    audience_senior: Mapped[bool] = mapped_column(Boolean, default=True)
    audience_staff_only: Mapped[bool] = mapped_column(Boolean, default=False)
    audience_proficient: Mapped[bool] = mapped_column(Boolean, default=False)
    audience_first_years: Mapped[bool] = mapped_column(Boolean, default=False)
    cea_activity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    nomination_end_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    unit_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    planning_impact: Mapped[str | None] = mapped_column(Text, nullable=True)
    readiness_requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class AnchorPrepRule(Base, UUIDMixin, TimestampMixin):
    """Seeded rule set: for event_type X, suggest subject Y N weeks before."""
    __tablename__ = "anchor_prep_rules"
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    subject_area: Mapped[str | None] = mapped_column(String(80), nullable=True)
    suggested_curriculum_tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    weeks_before_min: Mapped[int] = mapped_column(Integer, default=1)
    weeks_before_max: Mapped[int] = mapped_column(Integer, default=3)
    suggested_activity: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class AnchorPrepPlan(Base, UUIDMixin, TimestampMixin):
    """A preparation lesson linked to an anchor event."""
    __tablename__ = "anchor_prep_plans"
    anchor_event_id: Mapped[str] = mapped_column(ForeignKey("anchor_events.id"), index=True)
    curriculum_id: Mapped[str | None] = mapped_column(ForeignKey("curriculum_items.id"), nullable=True)
    planned_parade_date_id: Mapped[str | None] = mapped_column(ForeignKey("parade_dates.id"), nullable=True)
    planned_session_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cadet_group: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="planned")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class ScheduledSession(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """One instructional session in the parade night planning grid."""
    __tablename__ = "scheduled_sessions"
    parade_date_id: Mapped[str] = mapped_column(ForeignKey("parade_dates.id"), index=True)
    unit_id: Mapped[str] = mapped_column(ForeignKey("squadrons.id"), index=True)
    cadet_group: Mapped[str] = mapped_column(String(30), nullable=False)
    session_number: Mapped[int] = mapped_column(Integer, nullable=False)
    curriculum_id: Mapped[str | None] = mapped_column(ForeignKey("curriculum_items.id"), nullable=True)
    activity_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    facilitator_id: Mapped[str | None] = mapped_column(ForeignKey("facilitators.id"), nullable=True)
    location_id: Mapped[str | None] = mapped_column(ForeignKey("planning_locations.id"), nullable=True)
    is_combined: Mapped[bool] = mapped_column(Boolean, default=False)
    combined_groups: Mapped[list | None] = mapped_column(JSON, nullable=True)
    override_conflict: Mapped[bool] = mapped_column(Boolean, default=False)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class PlanningLocation(Base, UUIDMixin, TimestampMixin):
    """A room or outdoor area used for scheduling."""
    __tablename__ = "planning_locations"
    unit_id: Mapped[str] = mapped_column(ForeignKey("squadrons.id"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    location_type: Mapped[str] = mapped_column(String(30), default="indoor")
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active_status: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class PlanningConflict(Base, UUIDMixin, TimestampMixin):
    """A detected planning conflict, with optional override."""
    __tablename__ = "planning_conflicts"
    planning_year_id: Mapped[str | None] = mapped_column(ForeignKey("planning_years.id"), nullable=True, index=True)
    parade_date_id: Mapped[str | None] = mapped_column(ForeignKey("parade_dates.id"), nullable=True)
    scheduled_session_id: Mapped[str | None] = mapped_column(ForeignKey("scheduled_sessions.id"), nullable=True)
    conflict_type: Mapped[str] = mapped_column(String(60), nullable=False)
    severity: Mapped[str] = mapped_column(String(10), default="warning")
    message: Mapped[str] = mapped_column(String(400), nullable=False)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class PlanningFacilitatorLeave(Base, UUIDMixin, TimestampMixin):
    """Facilitator leave/unavailability period for planning conflict detection."""
    __tablename__ = "planning_facilitator_leave"
    facilitator_id: Mapped[str] = mapped_column(ForeignKey("facilitators.id"), nullable=False, index=True)
    planning_year_id: Mapped[str | None] = mapped_column(ForeignKey("planning_years.id"), nullable=True, index=True)
    start_date: Mapped[str] = mapped_column(String(10), nullable=False)
    end_date: Mapped[str] = mapped_column(String(10), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class PlanningNotice(Base, UUIDMixin, TimestampMixin):
    """A notice attached to a specific parade date (shown in planning views)."""
    __tablename__ = "planning_notices"
    planning_year_id: Mapped[str | None] = mapped_column(ForeignKey("planning_years.id"), nullable=True, index=True)
    parade_date_id: Mapped[str] = mapped_column(ForeignKey("parade_dates.id"), nullable=False, index=True)
    notice_text: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[str | None] = mapped_column(String(60), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="normal")
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class CeaImportBatch(Base, UUIDMixin, TimestampMixin):
    """Tracks each CEA activity import run."""
    __tablename__ = "cea_import_batches"
    planning_year_id: Mapped[str | None] = mapped_column(ForeignKey("planning_years.id"), nullable=True, index=True)
    wing_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    imported_by: Mapped[str] = mapped_column(String(36), nullable=False)
    source_file_name: Mapped[str | None] = mapped_column(String(260), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)


class CeaActivity(Base, UUIDMixin, TimestampMixin):
    """An activity imported from CEA or manually created for planning overlay."""
    __tablename__ = "cea_activities"
    import_batch_id: Mapped[str | None] = mapped_column(ForeignKey("cea_import_batches.id"), nullable=True, index=True)
    planning_year_id: Mapped[str | None] = mapped_column(ForeignKey("planning_years.id"), nullable=True, index=True)
    wing_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    unit_id: Mapped[str | None] = mapped_column(ForeignKey("squadrons.id"), nullable=True, index=True)
    # CEA source identifiers
    cea_activity_id: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    activity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status_name: Mapped[str | None] = mapped_column(String(60), nullable=True)
    parent_unit: Mapped[str | None] = mapped_column(String(200), nullable=True)
    host_unit: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # Core fields
    activity_name: Mapped[str] = mapped_column(String(300), nullable=False)
    nomination_start_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    nomination_end_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    activity_start_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    activity_end_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    start_time: Mapped[str | None] = mapped_column(String(8), nullable=True)
    end_time: Mapped[str | None] = mapped_column(String(8), nullable=True)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    activity_poc: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(20), default="cea")  # cea / manual
    # Classification (required before appearing as active overlay)
    classification_status: Mapped[str] = mapped_column(String(20), default="needs_review")
    importance: Mapped[str | None] = mapped_column(String(30), nullable=True)
    audience_staff_only: Mapped[bool] = mapped_column(Boolean, default=False)
    audience_seniors: Mapped[bool] = mapped_column(Boolean, default=False)
    audience_proficient: Mapped[bool] = mapped_column(Boolean, default=False)
    audience_first_years: Mapped[bool] = mapped_column(Boolean, default=False)
    classified_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    classified_at: Mapped[str | None] = mapped_column(String(26), nullable=True)
    # Lifecycle flags
    is_removed_from_cea: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class ActivityLocalHide(Base, UUIDMixin, TimestampMixin):
    """Per-squadron local hide/note on a CEA activity overlay."""
    __tablename__ = "activity_local_hides"
    cea_activity_id: Mapped[str] = mapped_column(ForeignKey("cea_activities.id"), nullable=False, index=True)
    unit_id: Mapped[str] = mapped_column(ForeignKey("squadrons.id"), nullable=False, index=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=True)
    local_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    hidden_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
