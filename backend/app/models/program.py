"""RETIRED — the Cadet Program subsystem (Part 41, user decision 2026-08-30).

CurriculumItem is the canonical curriculum entity. ProgramItem duplicated it and
disagreed with it about who may see a squadron-local item, so the API surface
here (14 endpoints), its service layer and its seed data were removed.

The MODELS and their tables are deliberately still here. Removing the API stops
the duplicate entity being used; dropping the tables destroys whatever rows an
environment already holds, and no production data can be inspected from here.
Dropping them is a separate, explicit step that needs a row count per
environment first -- see docs/final/10-curriculum-vs-program.md.

Two things in this file are NOT retired and must stay:
  * JobStatus  -- background jobs (routers/jobs.py, routers/system.py, workers/)
  * ExportLog's SourceFile reference in routers/export_import.py
"""
from sqlalchemy import String, Integer, ForeignKey, Boolean, Text, DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from ..database import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, UTCDateTime


class Phase(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "phases"
    name: Mapped[str] = mapped_column(String(80))
    short_name: Mapped[str] = mapped_column(String(40))
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    parent_program: Mapped[str | None] = mapped_column(String(80))
    is_core: Mapped[bool] = mapped_column(Boolean, default=True)
    is_extension: Mapped[bool] = mapped_column(Boolean, default=False)
    learning_hub_url: Mapped[str | None] = mapped_column(String(400))
    active_status: Mapped[bool] = mapped_column(Boolean, default=True)


class ProgramPackage(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "program_packages"
    title: Mapped[str] = mapped_column(String(200))
    description_internal: Mapped[str | None] = mapped_column(Text)
    owning_scope: Mapped[str] = mapped_column(String(20), index=True)  # national|wing|squadron
    national_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    wing_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    squadron_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    program_year: Mapped[int] = mapped_column(Integer, default=2026)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)  # draft|review|approved|published|retired|archived
    effective_from: Mapped[str | None] = mapped_column(String(10))
    effective_to: Mapped[str | None] = mapped_column(String(10))
    approved_by: Mapped[str | None] = mapped_column(String(36))
    published_by: Mapped[str | None] = mapped_column(String(36))
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class ProgramItem(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "program_items"
    package_id: Mapped[str] = mapped_column(ForeignKey("program_packages.id"), index=True)
    owning_scope: Mapped[str] = mapped_column(String(20), index=True)
    national_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    wing_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    squadron_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    code: Mapped[str] = mapped_column(String(40), index=True)
    title: Mapped[str] = mapped_column(String(200))
    phase_id: Mapped[str | None] = mapped_column(String(36), index=True)
    phase_name_at_time: Mapped[str | None] = mapped_column(String(80))
    element: Mapped[str | None] = mapped_column(String(40))
    category: Mapped[str | None] = mapped_column(String(40))
    foundation_or_extension: Mapped[str] = mapped_column(String(20), default="foundation")
    core_status: Mapped[str] = mapped_column(String(20), default="core")  # core|optional|extension|local|wing_required|national_required
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    duration_variable: Mapped[bool] = mapped_column(Boolean, default=False)
    suggested_parts: Mapped[int | None] = mapped_column(Integer)
    instructor_suitability: Mapped[str | None] = mapped_column(String(120))
    location_type: Mapped[str | None] = mapped_column(String(40))
    required_equipment: Mapped[str | None] = mapped_column(Text)
    prerequisite_item_ids: Mapped[str | None] = mapped_column(Text)  # JSON array
    learning_hub_resource_id: Mapped[str | None] = mapped_column(String(36), index=True)
    source_file_id: Mapped[str | None] = mapped_column(String(36))
    source_row_reference: Mapped[str | None] = mapped_column(String(80))
    source_sheet_name: Mapped[str | None] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)  # draft|active|retired|replaced|archived
    replacement_item_id: Mapped[str | None] = mapped_column(String(36))
    internal_notes: Mapped[str | None] = mapped_column(Text)


class LearningHubResource(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "learning_hub_resources"
    title: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(400))
    phase: Mapped[str | None] = mapped_column(String(80))
    resource_type: Mapped[str] = mapped_column(String(20), default="page")  # page|file|activity|guide|unknown
    source: Mapped[str] = mapped_column(String(40), default="Learning Hub")
    requires_login: Mapped[bool] = mapped_column(Boolean, default=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    verification_status: Mapped[str] = mapped_column(String(20), default="unknown")  # unknown|valid|invalid|requires_login|changed


class ProgramItemDeployment(Base, UUIDMixin, TimestampMixin):
    """Materialised visibility: which scope a program item is available to."""
    __tablename__ = "program_item_deployments"
    program_item_id: Mapped[str] = mapped_column(ForeignKey("program_items.id"), index=True)
    available_to_scope: Mapped[str] = mapped_column(String(20), index=True)  # national|wing|squadron
    national_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    wing_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    squadron_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    inherited_from_scope: Mapped[str | None] = mapped_column(String(20))
    inherited_from_package_id: Mapped[str | None] = mapped_column(String(36))
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    can_schedule: Mapped[bool] = mapped_column(Boolean, default=True)
    can_copy: Mapped[bool] = mapped_column(Boolean, default=False)
    can_request_change: Mapped[bool] = mapped_column(Boolean, default=False)


class SourceFile(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "source_files"
    filename: Mapped[str] = mapped_column(String(200))
    file_type: Mapped[str | None] = mapped_column(String(20))
    source_category: Mapped[str] = mapped_column(String(40), default="other")
    uploaded_by: Mapped[str | None] = mapped_column(String(36))
    parsed_status: Mapped[str] = mapped_column(String(20), default="uploaded")
    parser_version: Mapped[str | None] = mapped_column(String(20))
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text)


class SourceConflict(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "source_conflicts"
    source_file_id: Mapped[str | None] = mapped_column(String(36), index=True)
    conflict_type: Mapped[str] = mapped_column(String(60))
    object_type: Mapped[str | None] = mapped_column(String(40))
    object_key: Mapped[str | None] = mapped_column(String(80))
    field_name: Mapped[str | None] = mapped_column(String(60))
    value_a: Mapped[str | None] = mapped_column(Text)
    value_b: Mapped[str | None] = mapped_column(Text)
    source_a: Mapped[str | None] = mapped_column(String(80))
    source_b: Mapped[str | None] = mapped_column(String(80))
    resolution_status: Mapped[str] = mapped_column(String(20), default="open")
    resolved_value: Mapped[str | None] = mapped_column(Text)
    resolution_reason: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[str | None] = mapped_column(String(36))
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class PromotionRequest(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "promotion_requests"
    program_item_id: Mapped[str] = mapped_column(String(36), index=True)
    from_scope: Mapped[str] = mapped_column(String(20))
    to_scope: Mapped[str] = mapped_column(String(20))
    requested_by: Mapped[str | None] = mapped_column(String(36))
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|approved|rejected|changes_requested
    decided_by: Mapped[str | None] = mapped_column(String(36))
    decision_note: Mapped[str | None] = mapped_column(Text)


class JobStatus(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "job_status"
    job_type: Mapped[str] = mapped_column(String(40))
    requested_by: Mapped[str | None] = mapped_column(String(36))
    scope: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|running|succeeded|failed|cancelled
    progress_percentage: Mapped[int] = mapped_column(Integer, default=0)
    result_reference: Mapped[str | None] = mapped_column(String(300))
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
