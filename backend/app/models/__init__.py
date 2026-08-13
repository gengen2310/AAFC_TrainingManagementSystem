"""Aggregate model imports so Base.metadata sees every table."""
from .wing_calendar import WingHQEvent, SquadronEventStatus, WingEventCurriculumLink
from .planning import (
    PlanningYear, ParadeDate, HolidayPeriod, AnchorEvent, AnchorPrepRule,
    AnchorPrepPlan, ScheduledSession, PlanningLocation, PlanningConflict,
    PlanningFacilitatorLeave, PlanningNotice,
    CeaImportBatch, CeaActivity, ActivityLocalHide, ActivityLocalOverride,
)
from .organisations import (
    NationalEntity, Wing, Squadron, Flight, User, AccessCode, ProxySession, IpLoginAttempt,
    IpApiRequest,
)
from .training import (
    CurriculumItem, CurriculumElement, CurriculumPhase, CustomPhase, ParadeNight, Session, SessionStatusHistory,
    Facilitator, FacilitatorRankHistory, SubjectAreaTag, FacilitatorTypeTag, SessionStatusReasonTag, TrainingArea, Equipment, Activity, Cadet,
    TimingTemplate, TimingBlock, ParadeNightTimingOverride, TrainingClass, SessionAudience,
    CadetClassMembership,
)
from .operations import (
    ActionItem, Exception, AuditLog, ImportLog, ExportLog, SystemSetting,
)
from .program import (
    Phase, ProgramPackage, ProgramItem, LearningHubResource, ProgramItemDeployment,
    SourceFile, SourceConflict, PromotionRequest, JobStatus,
)

__all__ = [
    "NationalEntity", "Wing", "Squadron", "Flight", "User", "AccessCode", "ProxySession", "IpLoginAttempt", "IpApiRequest",
    "CurriculumItem", "CurriculumElement", "CurriculumPhase", "CustomPhase", "ParadeNight", "Session", "SessionStatusHistory",
    "Facilitator", "FacilitatorRankHistory", "SubjectAreaTag", "FacilitatorTypeTag", "SessionStatusReasonTag", "TrainingArea", "Equipment", "Activity", "Cadet",
    "TimingTemplate", "TimingBlock", "ParadeNightTimingOverride", "TrainingClass", "SessionAudience",
    "CadetClassMembership",
    "ActionItem", "Exception", "AuditLog", "ImportLog", "ExportLog", "SystemSetting",
    "Phase", "ProgramPackage", "ProgramItem", "LearningHubResource", "ProgramItemDeployment",
    "SourceFile", "SourceConflict", "PromotionRequest", "JobStatus",
    "PlanningYear", "ParadeDate", "HolidayPeriod", "AnchorEvent", "AnchorPrepRule",
    "AnchorPrepPlan", "ScheduledSession", "PlanningLocation", "PlanningConflict",
    "PlanningFacilitatorLeave", "PlanningNotice",
    "CeaImportBatch", "CeaActivity", "ActivityLocalHide", "ActivityLocalOverride",
    "WingHQEvent", "SquadronEventStatus", "WingEventCurriculumLink",
]
