"""Aggregate model imports so Base.metadata sees every table."""
from .service_ticket import ServiceTicket
from .faq import FaqEntry
from .service_desk_email_config import ServiceDeskEmailConfig
from .wing_calendar import WingHQEvent, SquadronEventStatus, WingEventCurriculumLink
from .planning import (
    PlanningYear, HolidayPeriod, AnchorEvent, AnchorPrepRule,
    AnchorPrepPlan, PlanningConflict,
    PlanningFacilitatorLeave, PlanningNotice,
    CeaImportBatch, CeaActivity, ActivityLocalHide, ActivityLocalOverride,
)
from .organisations import (
    NationalEntity, Wing, Squadron, Flight, User, AccessCode, ProxySession, IpLoginAttempt,
    IpApiRequest, UserApiRequest,
)
from .training import (
    CurriculumItem, CurriculumElement, CurriculumPhase, ParadeNight, Session, SessionStatusHistory,
    Facilitator, FacilitatorRankHistory, SubjectAreaTag, FacilitatorTypeTag, SessionStatusReasonTag, ActivityTypeTag, TrainingAreaCapabilityTag, TrainingArea, Equipment, Activity, Cadet,
    TimingTemplate, TimingBlock, ParadeNightTimingOverride, TrainingClass, SessionAudience,
    CadetClassMembership, ParadeNightTemplate, ParadeNightTemplateSession,
)
from .operations import (
    ActionItem, Exception, AuditLog, ImportLog, ExportLog, SystemSetting,
)
from .program import (
    Phase, ProgramPackage, ProgramItem, LearningHubResource, ProgramItemDeployment,
    SourceFile, SourceConflict, PromotionRequest, JobStatus,
)
from .custom_phases import CustomTrainingPhase  # noqa: F401

__all__ = [
    "NationalEntity", "Wing", "Squadron", "Flight", "User", "AccessCode", "ProxySession", "IpLoginAttempt", "IpApiRequest", "UserApiRequest",
    "CurriculumItem", "CurriculumElement", "CurriculumPhase", "ParadeNight", "Session", "SessionStatusHistory",
    "Facilitator", "FacilitatorRankHistory", "SubjectAreaTag", "FacilitatorTypeTag", "SessionStatusReasonTag", "ActivityTypeTag", "TrainingAreaCapabilityTag", "TrainingArea", "Equipment", "Activity", "Cadet",
    "TimingTemplate", "TimingBlock", "ParadeNightTimingOverride", "TrainingClass", "SessionAudience",
    "CadetClassMembership", "ParadeNightTemplate", "ParadeNightTemplateSession",
    "ActionItem", "Exception", "AuditLog", "ImportLog", "ExportLog", "SystemSetting",
    "Phase", "ProgramPackage", "ProgramItem", "LearningHubResource", "ProgramItemDeployment",
    "SourceFile", "SourceConflict", "PromotionRequest", "JobStatus",
    "PlanningYear", "HolidayPeriod", "AnchorEvent", "AnchorPrepRule",
    "AnchorPrepPlan", "PlanningConflict",
    "PlanningFacilitatorLeave", "PlanningNotice",
    "CeaImportBatch", "CeaActivity", "ActivityLocalHide", "ActivityLocalOverride",
    "WingHQEvent", "SquadronEventStatus", "WingEventCurriculumLink",
    "ServiceTicket",
    "ServiceDeskEmailConfig",
    "CustomTrainingPhase",
    "FaqEntry",
]
