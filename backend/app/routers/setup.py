"""Phase 3.5: initial setup status. A thin read-only aggregation endpoint --
no new "wizard" backend infrastructure, per the plan; the frontend stepper
built on top of this reuses every existing create/import endpoint unchanged.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session as DBSession

from ..database import get_db
from ..models import (
    Wing, Squadron, Facilitator, TrainingArea, TimingTemplate, CurriculumItem,
    ParadeNight, Session as TrainingSession, CeaActivity, PlanningYear, HolidayPeriod,
    Equipment, Cadet, Activity, AnchorEvent, Flight, TrainingClass,
)
from ..dependencies import get_principal
from ..permissions import Principal
from .training import _view_squadron_id, _NAT_ADMIN_ROLES

router = APIRouter(prefix="/api", tags=["setup"])

_NATIONAL_VISIBLE_ROLES = frozenset({"national_admin", "national_viewer", "system_admin", "auditor"})


@router.get("/setup/status")
def setup_status(squadron_id: str | None = None, db: DBSession = Depends(get_db),
                 p: Principal = Depends(get_principal)):
    national = None
    if p.role in _NATIONAL_VISIBLE_ROLES:
        wings_created = db.query(Wing).filter(Wing.is_archived == False).count()  # noqa: E712
        squadrons_created = db.query(Squadron).filter(Squadron.is_archived == False).count()  # noqa: E712
        national = {"wings_created": wings_created, "squadrons_created": squadrons_created}

    squadron = None
    sq_id = _view_squadron_id(p, squadron_id, db)
    if sq_id:
        s = db.get(Squadron, sq_id)
        if s:
            facilitators_added = db.query(Facilitator).filter(
                Facilitator.squadron_id == sq_id, Facilitator.is_archived == False).count()  # noqa: E712
            training_areas_added = db.query(TrainingArea).filter(
                TrainingArea.squadron_id == sq_id, TrainingArea.is_archived == False).count()  # noqa: E712
            timing_template_confirmed = db.query(TimingTemplate).filter(
                TimingTemplate.squadron_id == sq_id, TimingTemplate.is_archived == False).count() > 0  # noqa: E712
            today = date.today().isoformat()
            parade_nights_generated = db.query(ParadeNight).filter(
                ParadeNight.squadron_id == sq_id, ParadeNight.is_archived == False,  # noqa: E712
                ParadeNight.date >= today).count()
            cea_imported = db.query(CeaActivity).filter(CeaActivity.wing_id == s.wing_id).count() > 0

            active_year_ids = [y.id for y in db.query(PlanningYear).filter(
                PlanningYear.unit_id == sq_id, PlanningYear.active_status == True).all()]  # noqa: E712
            holidays_configured = bool(active_year_ids) and db.query(HolidayPeriod).filter(
                HolidayPeriod.planning_year_id.in_(active_year_ids)).count() > 0

            planning_year_active = bool(active_year_ids)
            crest_set = bool(s.crest_url)
            equipment_added = db.query(Equipment).filter(
                Equipment.squadron_id == sq_id, Equipment.is_archived == False).count()  # noqa: E712
            cadets_added = db.query(Cadet).filter(
                Cadet.squadron_id == sq_id, Cadet.is_archived == False).count()  # noqa: E712
            activities_classified = db.query(Activity).filter(
                Activity.squadron_id == sq_id, Activity.is_archived == False,  # noqa: E712
                Activity.activity_type.isnot(None), Activity.audience.isnot(None)).count() > 0
            anchor_events_reviewed = bool(active_year_ids) and db.query(AnchorEvent).filter(
                AnchorEvent.planning_year_id.in_(active_year_ids), AnchorEvent.is_archived == False).count() > 0  # noqa: E712
            parade_night_published = db.query(ParadeNight).filter(
                ParadeNight.squadron_id == sq_id, ParadeNight.is_archived == False,  # noqa: E712
                ParadeNight.published_status == True).count() > 0  # noqa: E712
            flights_created = db.query(Flight).filter(
                Flight.squadron_id == sq_id, Flight.is_archived == False).count()  # noqa: E712
            # Training Classes: count of active classes across all active Planning Years.
            # A squadron may run without classes (using the legacy cadet_group free-text
            # field) -- this step is "optional" in the checklist so it doesn't block
            # setup completion for existing configurations, but we surface it as guidance.
            training_classes_created = 0
            if active_year_ids:
                training_classes_created = db.query(TrainingClass).filter(
                    TrainingClass.squadron_id == sq_id,
                    TrainingClass.training_year_id.in_(active_year_ids),
                    TrainingClass.is_archived == False).count()  # noqa: E712

            # Curriculum coverage: % of items visible to this squadron (national +
            # this wing + this squadron -- same visibility rule as GET /curriculum)
            # that have at least one scheduled session.
            conditions = [CurriculumItem.owning_level == "national",
                         (CurriculumItem.owning_level == "wing") & (CurriculumItem.wing_id == s.wing_id),
                         CurriculumItem.squadron_id == sq_id]
            items = db.query(CurriculumItem).filter(
                CurriculumItem.is_archived == False, or_(*conditions)).all()  # noqa: E712
            item_ids = [i.id for i in items]
            covered_ids = set()
            if item_ids:
                covered_ids = {row[0] for row in db.query(TrainingSession.curriculum_item_id).filter(
                    TrainingSession.curriculum_item_id.in_(item_ids), TrainingSession.squadron_id == sq_id,
                    TrainingSession.is_archived == False).distinct().all()}  # noqa: E712
            curriculum_coverage_pct = round(100 * len(covered_ids) / len(items), 1) if items else 0.0

            squadron = {
                "squadron_id": sq_id, "squadron_code": s.code,
                "facilitators_added": facilitators_added,
                "training_areas_added": training_areas_added,
                "timing_template_confirmed": timing_template_confirmed,
                "parade_nights_generated": parade_nights_generated,
                "cea_imported": cea_imported,
                "curriculum_coverage_pct": curriculum_coverage_pct,
                "holidays_configured": holidays_configured,
                "planning_year_active": planning_year_active,
                "crest_set": crest_set,
                "equipment_added": equipment_added,
                "cadets_added": cadets_added,
                "activities_classified": activities_classified,
                "anchor_events_reviewed": anchor_events_reviewed,
                "parade_night_published": parade_night_published,
                "flights_created": flights_created,
                "training_classes_created": training_classes_created,
            }

    steps = []
    if national is not None:
        steps.append({"key": "wings_created", "label": "Create Wings", "done": national["wings_created"] > 0,
                      "count": national["wings_created"], "link_page": "accounts"})
        steps.append({"key": "squadrons_created", "label": "Create Squadrons / Specialist Units",
                      "done": national["squadrons_created"] > 0, "count": national["squadrons_created"],
                      "link_page": "accounts"})
    if squadron is not None:
        # Planning Year comes first among squadron steps -- Parade Nights,
        # Anchor Events, and Holidays are all scoped to it, so setting it up
        # is a genuine prerequisite, not just an arbitrary ordering choice.
        steps.append({"key": "planning_year_active", "label": "Set Up Active Planning Year",
                      "done": squadron["planning_year_active"], "count": None, "link_page": "settings"})
        # Training Classes: optional because a single-class squadron running one group per Stage
        # does not need to create named classes -- the legacy cadet_group field handles that.
        # Surfaced as guidance so squadrons running multiple parallel groups are prompted to set
        # them up, which unlocks class-aware curriculum progress and Mission Backlog tracking.
        steps.append({"key": "training_classes_created", "label": "Create Training Classes",
                      "done": squadron["training_classes_created"] > 0,
                      "count": squadron["training_classes_created"],
                      "link_page": "settings", "optional": True})
        steps.append({"key": "facilitators_added", "label": "Add Facilitators",
                      "done": squadron["facilitators_added"] > 0, "count": squadron["facilitators_added"],
                      "link_page": "facilitators"})
        steps.append({"key": "training_areas_added", "label": "Add Training Areas / Rooms",
                      "done": squadron["training_areas_added"] > 0, "count": squadron["training_areas_added"],
                      "link_page": "resources"})
        steps.append({"key": "equipment_added", "label": "Add Equipment",
                      "done": squadron["equipment_added"] > 0, "count": squadron["equipment_added"],
                      "link_page": "resources"})
        steps.append({"key": "timing_template_confirmed", "label": "Confirm Parade Night Timing Template",
                      "done": squadron["timing_template_confirmed"], "count": None, "link_page": "settings"})
        steps.append({"key": "crest_set", "label": "Set Squadron Crest",
                      "done": squadron["crest_set"], "count": None, "link_page": "settings"})
        steps.append({"key": "cadets_added", "label": "Add Cadets to Squadron Roster",
                      "done": squadron["cadets_added"] > 0, "count": squadron["cadets_added"],
                      "link_page": "settings"})
        steps.append({"key": "holidays_configured", "label": "Add or Import Holidays",
                      "done": squadron["holidays_configured"], "count": None, "link_page": "activities"})
        steps.append({"key": "cea_imported", "label": "Import CEA Activities", "done": squadron["cea_imported"],
                      "count": None, "link_page": "activities"})
        steps.append({"key": "activities_classified", "label": "Classify Activities by Priority & Audience",
                      "done": squadron["activities_classified"], "count": None, "link_page": "activities"})
        steps.append({"key": "anchor_events_reviewed", "label": "Review Annual Training Program Anchor Events",
                      "done": squadron["anchor_events_reviewed"], "count": None, "link_page": "activities"})
        steps.append({"key": "parade_nights_generated", "label": "Generate Parade Nights",
                      "done": squadron["parade_nights_generated"] > 0,
                      "count": squadron["parade_nights_generated"], "link_page": "parade-nights"})
        steps.append({"key": "parade_night_published", "label": "Publish a Parade Night",
                      "done": squadron["parade_night_published"], "count": None, "link_page": "parade-nights"})
        steps.append({"key": "curriculum_coverage", "label": "Schedule Curriculum Items",
                      "done": squadron["curriculum_coverage_pct"] >= 100,
                      "count": squadron["curriculum_coverage_pct"], "link_page": "curriculum"})
        # Flight is a local, optional cadet-organisation grouping, not a
        # required setup action (see Flight model docstring / architecture.md)
        # -- surfaced as guidance in the fuller sequence but excluded from the
        # `complete` calculation below via its own "optional" flag.
        steps.append({"key": "flights_created", "label": "Organise Cadets into Flights",
                      "done": squadron["flights_created"] > 0, "count": squadron["flights_created"],
                      "link_page": "settings", "optional": True})

    complete = bool(steps) and all(st["done"] for st in steps if not st.get("optional"))
    return {"national": national, "squadron": squadron, "steps": steps, "complete": complete}
