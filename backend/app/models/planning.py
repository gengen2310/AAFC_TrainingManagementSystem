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


LOCAL_LESSON_CODES = (
    "Skills-01", "Skills-02", "Skills-03", "Skills-04", "Skills-05", "Skills-06",
    "Skills-07", "Skills-08", "Skills-09", "Skills-10", "Skills-11", "Skills-12",
    "Skills-13", "Skills-14",
)

LOCAL_LESSON_DEFAULTS = [
    ("Skills-01", "Admin Session"),
    ("Skills-02", "Term Briefing"),
    ("Skills-03", "Activity Prep"),
    ("Skills-04", "Activity Briefing"),
    ("Skills-05", "Activity Debrief"),
    ("Skills-06", "Activity Day"),
    ("Skills-07", "Guest Speaker"),
    ("Skills-08", "Term Overview"),
    ("Skills-09", "Recruit Administration"),
    ("Skills-10", "Catch-Up / Consolidation"),
    ("Skills-11", "Team Building"),
    ("Skills-12", "Assessment"),
    ("Skills-13", "No Parade — Holiday"),
    ("Skills-14", "No Parade — Activity"),
]


class LocalLesson(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """Custom squadron lesson type — not part of the national curriculum.
    Covers administrative, activity-support, and special session types (Skills-01..14).
    squadron_id=None means it is a system-level template available to all squadrons.
    """
    __tablename__ = "local_lessons"
    squadron_id: Mapped[str | None] = mapped_column(ForeignKey("squadrons.id"), nullable=True, index=True)
    lesson_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    lesson_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject_area: Mapped[str | None] = mapped_column(String(80), nullable=True)
    default_duration_mins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_template: Mapped[bool] = mapped_column(Boolean, default=True)
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
