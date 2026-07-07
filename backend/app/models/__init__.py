"""Aggregate model imports so Base.metadata sees every table."""
from .wing_calendar import WingHQEvent, SquadronEventStatus, WingEventCurriculumLink
from .planning import (
    PlanningYear, ParadeDate, HolidayPeriod, AnchorEvent, AnchorPrepRule,
    AnchorPrepPlan, ScheduledSession, PlanningLocation, PlanningConflict,
)
from .organisations import (
    NationalEntity, Wing, Squadron, Flight, User, AccessCode, ProxySession, IpLoginAttempt,
)
from .training import (
    CurriculumItem, CurriculumElement, CustomPhase, ParadeNight, Session, SessionStatusHistory,
    Facilitator, FacilitatorRankHistory, TrainingArea, Equipment, Activity, Cadet,
    TimingTemplate, TimingBlock, ParadeNightTimingOverride,
)
from .operations import (
    ActionItem, Exception, AuditLog, ImportLog, ExportLog, SystemSetting,
)
from .program import (
    Phase, ProgramPackage, ProgramItem, LearningHubResource, ProgramItemDeployment,
    SourceFile, SourceConflict, PromotionRequest, JobStatus,
)

__all__ = [
    "NationalEntity", "Wing", "Squadron", "Flight", "User", "AccessCode", "ProxySession", "IpLoginAttempt",
    "CurriculumItem", "CurriculumElement", "CustomPhase", "ParadeNight", "Session", "SessionStatusHistory",
    "Facilitator", "FacilitatorRankHistory", "TrainingArea", "Equipment", "Activity", "Cadet",
    "TimingTemplate", "TimingBlock", "ParadeNightTimingOverride",
    "ActionItem", "Exception", "AuditLog", "ImportLog", "ExportLog", "SystemSetting",
    "Phase", "ProgramPackage", "ProgramItem", "LearningHubResource", "ProgramItemDeployment",
    "SourceFile", "SourceConflict", "PromotionRequest", "JobStatus",
    "PlanningYear", "ParadeDate", "HolidayPeriod", "AnchorEvent", "AnchorPrepRule",
    "AnchorPrepPlan", "ScheduledSession", "PlanningLocation", "PlanningConflict",
    "WingHQEvent", "SquadronEventStatus", "WingEventCurriculumLink",
]
