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
            today = date.today().isoformat()
            # Match the conditions _effective_template() actually resolves on
            # (timing.py). Counting any non-archived template reported "confirmed"
            # for a squadron whose only template was inactive or outside its
            # effective window -- the checklist said done while new parade nights
            # got no timing at all.
            timing_template_confirmed = any(
                t.effective_to is None or t.effective_to >= today
                for t in db.query(TimingTemplate).filter(
                    TimingTemplate.squadron_id == sq_id,
                    TimingTemplate.is_archived == False,   # noqa: E712
                    TimingTemplate.active_status == True,  # noqa: E712
                    TimingTemplate.effective_from <= today,
                ).all()
            )
            parade_nights_generated = db.query(ParadeNight).filter(
                ParadeNight.squadron_id == sq_id, ParadeNight.is_archived == False,  # noqa: E712
                ParadeNight.date >= today).count()
            cea_imported = db.query(CeaActivity).filter(CeaActivity.wing_id == s.wing_id).count() > 0

            active_year_ids = [y.id for y in db.query(PlanningYear).filter(
                PlanningYear.unit_id == sq_id, PlanningYear.status == "active").all()]
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

            # Sessions need a program period (timing_block_id) before they can
            # appear on the Weekly Program grid -- the period is the row. A
            # squadron can hold a full schedule that prints blank without it,
            # which is exactly what happened before 2026-08-23, so it earns a
            # checklist step of its own.
            sq_pn_ids = [
                pn.id for pn in db.query(ParadeNight).filter(
                    ParadeNight.squadron_id == sq_id,
                    ParadeNight.is_archived == False,  # noqa: E712
                ).all()
            ]
            sessions_total = 0
            sessions_with_period = 0
            if sq_pn_ids:
                sessions_total = db.query(TrainingSession).filter(
                    TrainingSession.parade_night_id.in_(sq_pn_ids),
                    TrainingSession.is_archived == False,  # noqa: E712
                ).count()
                sessions_with_period = db.query(TrainingSession).filter(
                    TrainingSession.parade_night_id.in_(sq_pn_ids),
                    TrainingSession.is_archived == False,  # noqa: E712
                    TrainingSession.timing_block_id.isnot(None),
                ).count()
            sessions_have_periods = sessions_total > 0 and sessions_with_period == sessions_total

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
                "sessions_total": sessions_total,
                "sessions_with_period": sessions_with_period,
                "sessions_have_periods": sessions_have_periods,
            }

    steps = []
    if national is not None:
        steps.append({"key": "wings_created", "label": "Create wings", "done": national["wings_created"] > 0,
                      "count": national["wings_created"], "link_page": "accounts"})
        steps.append({"key": "squadrons_created", "label": "Create squadrons and specialist units",
                      "done": national["squadrons_created"] > 0, "count": national["squadrons_created"],
                      "link_page": "accounts"})
    if squadron is not None:
        # Planning Year comes first among squadron steps -- Parade Nights,
        # Anchor Events, and Holidays are all scoped to it, so setting it up
        # is a genuine prerequisite, not just an arbitrary ordering choice.
        steps.append({"key": "planning_year_active", "label": "Set up the active training year",
                      "done": squadron["planning_year_active"], "count": None, "link_page": "settings"})
        # Training Classes: optional because a single-class squadron running one group per Stage
        # does not need to create named classes -- the legacy cadet_group field handles that.
        # Surfaced as guidance so squadrons running multiple parallel groups are prompted to set
        # them up, which unlocks class-aware curriculum progress and Mission Backlog tracking.
        steps.append({"key": "training_classes_created", "label": "Create training classes",
                      "done": squadron["training_classes_created"] > 0,
                      "count": squadron["training_classes_created"],
                      "link_page": "settings", "optional": True})
        steps.append({"key": "facilitators_added", "label": "Add facilitators",
                      "done": squadron["facilitators_added"] > 0, "count": squadron["facilitators_added"],
                      "link_page": "facilitators"})
        steps.append({"key": "training_areas_added", "label": "Add training areas and rooms",
                      "done": squadron["training_areas_added"] > 0, "count": squadron["training_areas_added"],
                      "link_page": "resources"})
        steps.append({"key": "equipment_added", "label": "Add equipment",
                      "done": squadron["equipment_added"] > 0, "count": squadron["equipment_added"],
                      "link_page": "resources"})
        steps.append({"key": "timing_template_confirmed", "label": "Confirm the parade night timing template",
                      "done": squadron["timing_template_confirmed"], "count": None, "link_page": "settings"})
        steps.append({"key": "crest_set", "label": "Set the squadron crest",
                      "done": squadron["crest_set"], "count": None, "link_page": "settings"})
        # "Add cadets to the squadron roster" was removed from the checklist on
        # 2026-08-28 per the TMS ↔ PW Integration Program §7. Cadet rostering is
        # a core capability that continues to work via the Accounts / Settings
        # pages -- it is not a prerequisite for planning and should not gate
        # Getting Started completion. squadron["cadets_added"] is still returned
        # in the response body for any caller that wants the count.
        steps.append({"key": "holidays_configured", "label": "Add or import holidays",
                      "done": squadron["holidays_configured"], "count": None, "link_page": "activities"})
        steps.append({"key": "cea_imported", "label": "Import CEA activities", "done": squadron["cea_imported"],
                      "count": None, "link_page": "activities"})
        steps.append({"key": "activities_classified", "label": "Classify activities by priority and audience",
                      "done": squadron["activities_classified"], "count": None, "link_page": "activities"})
        steps.append({"key": "anchor_events_reviewed", "label": "Review annual program anchor events",
                      "done": squadron["anchor_events_reviewed"], "count": None, "link_page": "activities"})
        steps.append({"key": "parade_nights_generated", "label": "Generate parade nights",
                      "done": squadron["parade_nights_generated"] > 0,
                      "count": squadron["parade_nights_generated"], "link_page": "parade-nights"})
        steps.append({"key": "parade_night_published", "label": "Publish a parade night",
                      "done": squadron["parade_night_published"], "count": None, "link_page": "parade-nights"})
        # Coverage is the share of every curriculum item VISIBLE to this squadron
        # -- the whole national curriculum across all Training Stages -- that has
        # a session. No squadron delivers all of it in one year: a fully seeded
        # 703 SQN measures 46.2%. Requiring 100% meant this step could never be
        # done, and because `complete` below is an AND over the non-optional
        # steps, the checklist could never report complete for anyone.
        # The step now marks done once scheduling has actually started, and keeps
        # the percentage as a progress readout.
        steps.append({"key": "curriculum_coverage", "label": "Schedule curriculum sessions",
                      "done": squadron["curriculum_coverage_pct"] > 0,
                      "count": squadron["curriculum_coverage_pct"], "link_page": "curriculum"})
        # Added 2026-08-23: without a program period a session is invisible on the
        # Weekly Program, so a squadron can look fully planned and print nothing.
        steps.append({"key": "sessions_have_periods", "label": "Assign sessions to program periods",
                      "done": squadron["sessions_have_periods"],
                      "count": squadron["sessions_with_period"], "link_page": "parade-nights"})
        # "Organise cadets into flights" was removed from the checklist on
        # 2026-08-25 at the user's request. Flight is a local, optional
        # cadet-organisation grouping and not a tenancy level or a setup
        # prerequisite (see the Flight model docstring and architecture.md), so
        # listing it as a step -- even an optional one -- implied it was part of
        # getting set up. The capability is untouched: flights are still created
        # and managed in Unit Setup, and squadron["flights_created"] is still
        # returned for anything that reports on them.

    complete = bool(steps) and all(st["done"] for st in steps if not st.get("optional"))
    return {"national": national, "squadron": squadron, "steps": steps, "complete": complete}
