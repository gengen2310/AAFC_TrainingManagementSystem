"""Tests for CLASS-14's scripts/migrate_legacy_class_data.py.

This script is NOT wired into any API route or app startup path -- it is a
standalone, explicitly-authorised-per-run backfill tool (see its own module
docstring and gap register CLASS-14). These tests exercise its core
correctness/safety properties directly against the ORM layer: idempotency,
never guessing at ambiguous cases, and rollback safety. They do not exercise
CLI argument parsing (main()) -- that is a thin wrapper over run()/rollback(),
already exercised manually during rehearsal (see release doc).

Uses direct SQLAlchemy manipulation (not the HTTP client) because the script
itself reads Session.cadet_group / ParadeNight.training_year / Cadet.phase
directly at the ORM layer -- these tests construct exactly the rows the
script scans, the same way the script itself will encounter real historical
data. Squadron 703 (already seeded) is reused, looked up by its stable code
(never a hardcoded id -- UUIDs are freshly generated per seed run). Every
fixture row uses a unique stage name / high year value and is cleaned up at
the end of each test, matching this suite's established pollution-safety
convention.
"""
import uuid

from app.database import SessionLocal
from app.models import (
    Cadet, CadetClassMembership, CurriculumPhase, ParadeNight, PlanningYear,
    Session as TrainingSession, SessionAudience, Squadron, TrainingClass,
)
from scripts.migrate_legacy_class_data import MIGRATION_SOURCE, MIGRATION_TAG, migrate_squadron, rollback


def _unique(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def _sqn_703(db) -> Squadron:
    return db.query(Squadron).filter(Squadron.code == "703").one()


def _setup_squadron_year_stage_session(db, sqn, *, year_num, stage_display, cadet_group):
    """Creates one fresh PlanningYear + squadron-scoped CurriculumPhase (named
    to match `stage_display` under the script's own normalization rule) +
    ParadeNight + Session with the given cadet_group. Returns the created rows.

    active_status=False: these tests exercise Part 1 (Session.cadet_group
    backfill) only. A default-active PlanningYear with a high test year number
    would otherwise become squadron 703's "current active year" (highest
    active year wins) and unexpectedly pull real seeded demo cadets' Cadet.phase
    data into Part 2's backfill against this throwaway year -- caught during
    development: a "happy path" test asserting exactly 1 created class saw 3,
    the other 2 being seeded cadets with phase='Initial'/'Junior' migrated into
    this test's own year by pure accident of it being the newest active one.
    """
    py = PlanningYear(
        unit_id=sqn.id, wing_id=sqn.wing_id, year=year_num, name=_unique("CLASS-14-TEST-YEAR"),
        active_status=False,
    )
    db.add(py)
    db.flush()
    stage = CurriculumPhase(
        name=_unique("CLASS-14-TEST-STAGE"), display_name=stage_display,
        scope_level="squadron", squadron_id=sqn.id, sort_order=0,
    )
    db.add(stage)
    db.flush()
    pn = ParadeNight(squadron_id=sqn.id, wing_id=sqn.wing_id, training_year=year_num, date="2030-01-01")
    db.add(pn)
    db.flush()
    sess = TrainingSession(parade_night_id=pn.id, squadron_id=sqn.id, cadet_group=cadet_group)
    db.add(sess)
    db.flush()
    db.commit()
    return py, stage, pn, sess


def _cleanup(db, *, planning_years=(), stages=(), parade_nights=(), sessions=(), cadets=()):
    db.query(SessionAudience).filter(
        SessionAudience.session_id.in_([s.id for s in sessions]),
    ).delete(synchronize_session=False)
    db.query(CadetClassMembership).filter(
        CadetClassMembership.cadet_id.in_([c.id for c in cadets]),
    ).delete(synchronize_session=False)
    db.query(TrainingClass).filter(
        TrainingClass.training_year_id.in_([y.id for y in planning_years]),
    ).delete(synchronize_session=False)
    for s in sessions:
        db.query(TrainingSession).filter(TrainingSession.id == s.id).delete()
    for pn in parade_nights:
        db.query(ParadeNight).filter(ParadeNight.id == pn.id).delete()
    for c in cadets:
        db.query(Cadet).filter(Cadet.id == c.id).delete()
    for st in stages:
        db.query(CurriculumPhase).filter(CurriculumPhase.id == st.id).delete()
    for y in planning_years:
        db.query(PlanningYear).filter(PlanningYear.id == y.id).delete()
    db.commit()


def test_happy_path_creates_class_audience_and_reads_never_touch_source_field():
    db = SessionLocal()
    try:
        sqn = _sqn_703(db)
        py, stage, pn, sess = _setup_squadron_year_stage_session(
            db, sqn, year_num=9101, stage_display="Senior", cadet_group="senior",
        )
        report = migrate_squadron(db, sqn, dry_run=False)
        db.commit()

        assert report.created_audiences >= 1
        created = [c for c in report.created_classes if c.get("training_year_id") == py.id]
        assert len(created) == 1

        tclass = db.query(TrainingClass).filter(
            TrainingClass.training_year_id == py.id, TrainingClass.training_stage_id == stage.id,
        ).first()
        assert tclass is not None
        assert tclass.created_by == MIGRATION_TAG
        assert tclass.display_name == "Senior"

        audience = db.query(SessionAudience).filter(
            SessionAudience.session_id == sess.id, SessionAudience.training_class_id == tclass.id,
        ).first()
        assert audience is not None

        # Read-only guarantee: source field is untouched.
        db.refresh(sess)
        assert sess.cadet_group == "senior"

        _cleanup(db, planning_years=[py], stages=[stage], parade_nights=[pn], sessions=[sess])
    finally:
        db.close()


def test_idempotent_rerun_creates_nothing_new():
    db = SessionLocal()
    try:
        sqn = _sqn_703(db)
        py, stage, pn, sess = _setup_squadron_year_stage_session(
            db, sqn, year_num=9102, stage_display="Junior", cadet_group="junior",
        )
        migrate_squadron(db, sqn, dry_run=False)
        db.commit()

        classes_before = db.query(TrainingClass).filter(TrainingClass.training_year_id == py.id).count()
        audiences_before = db.query(SessionAudience).filter(SessionAudience.session_id == sess.id).count()

        report2 = migrate_squadron(db, sqn, dry_run=False)
        db.commit()

        classes_after = db.query(TrainingClass).filter(TrainingClass.training_year_id == py.id).count()
        audiences_after = db.query(SessionAudience).filter(SessionAudience.session_id == sess.id).count()

        assert classes_after == classes_before
        assert audiences_after == audiences_before
        assert not [c for c in report2.created_classes if c.get("training_year_id") == py.id]
        assert report2.created_audiences == 0

        _cleanup(db, planning_years=[py], stages=[stage], parade_nights=[pn], sessions=[sess])
    finally:
        db.close()


def test_dry_run_report_matches_what_a_real_commit_would_do():
    """Regression test for the exact bug found during CLASS-14's own rehearsal:
    dry-run under-reported audiences to zero for brand-new classes (returned
    None instead of a placeholder id) and could double-count a class across
    two callers sharing the same not-yet-real stage. This asserts a dry-run's
    counts equal what a subsequent real commit actually produces."""
    db = SessionLocal()
    try:
        sqn = _sqn_703(db)
        py, stage, pn, sess = _setup_squadron_year_stage_session(
            db, sqn, year_num=9103, stage_display="Intermediate", cadet_group="intermediate",
        )

        dry_report = migrate_squadron(db, sqn, dry_run=True)
        db.rollback()
        dry_classes = len([c for c in dry_report.created_classes if c.get("training_year_id") == py.id])
        dry_audiences = dry_report.created_audiences

        real_report = migrate_squadron(db, sqn, dry_run=False)
        db.commit()
        real_classes = len([c for c in real_report.created_classes if c.get("training_year_id") == py.id])
        real_audiences = real_report.created_audiences

        assert dry_classes == real_classes == 1
        assert dry_audiences == real_audiences

        _cleanup(db, planning_years=[py], stages=[stage], parade_nights=[pn], sessions=[sess])
    finally:
        db.close()


def test_no_matching_stage_is_skipped_not_guessed():
    db = SessionLocal()
    try:
        sqn = _sqn_703(db)
        py = PlanningYear(
            unit_id=sqn.id, wing_id=sqn.wing_id, year=9104, name=_unique("CLASS-14-TEST-YEAR"),
            active_status=False,
        )
        db.add(py)
        db.flush()
        pn = ParadeNight(squadron_id=sqn.id, wing_id=sqn.wing_id, training_year=9104, date="2030-01-01")
        db.add(pn)
        db.flush()
        # A cadet_group value with no corresponding CurriculumPhase anywhere.
        sess = TrainingSession(parade_night_id=pn.id, squadron_id=sqn.id, cadet_group=_unique("nonexistent-stage"))
        db.add(sess)
        db.commit()

        report = migrate_squadron(db, sqn, dry_run=False)
        db.commit()

        reasons = [s["reason"] for s in report.skipped]
        assert "NO_MATCHING_STAGE" in reasons
        assert report.created_audiences == 0
        assert db.query(SessionAudience).filter(SessionAudience.session_id == sess.id).count() == 0

        _cleanup(db, planning_years=[py], parade_nights=[pn], sessions=[sess])
    finally:
        db.close()


def test_no_matching_planning_year_is_skipped_not_guessed():
    db = SessionLocal()
    try:
        sqn = _sqn_703(db)
        # ParadeNight with a training_year that has no matching PlanningYear row.
        pn = ParadeNight(squadron_id=sqn.id, wing_id=sqn.wing_id, training_year=9105, date="2030-01-01")
        db.add(pn)
        db.flush()
        sess = TrainingSession(parade_night_id=pn.id, squadron_id=sqn.id, cadet_group="senior")
        db.add(sess)
        db.commit()

        report = migrate_squadron(db, sqn, dry_run=False)
        db.commit()

        reasons = [s["reason"] for s in report.skipped]
        assert "NO_MATCHING_PLANNING_YEAR" in reasons
        assert db.query(SessionAudience).filter(SessionAudience.session_id == sess.id).count() == 0

        _cleanup(db, parade_nights=[pn], sessions=[sess])
    finally:
        db.close()


def test_ambiguous_existing_manual_class_is_never_auto_linked():
    """If a squadron has already manually created its own TrainingClass for
    this exact (year, stage) -- e.g. adopted CLASS-01 and split into 'Senior
    1'/'Senior 2' -- the script must not guess which one historical sessions
    belong to. It must skip, not silently pick one or create a duplicate."""
    db = SessionLocal()
    try:
        sqn = _sqn_703(db)
        py, stage, pn, sess = _setup_squadron_year_stage_session(
            db, sqn, year_num=9106, stage_display="Senior", cadet_group="senior",
        )
        # Simulate a real, manually-created class for this exact stage/year --
        # created_by is a real user id, not the migration tag.
        manual_class = TrainingClass(
            squadron_id=sqn.id, training_year_id=py.id, training_stage_id=stage.id,
            display_name="Senior 1", sequence=1, created_by="some-real-user-id",
        )
        db.add(manual_class)
        db.commit()

        report = migrate_squadron(db, sqn, dry_run=False)
        db.commit()

        reasons = [s["reason"] for s in report.skipped]
        assert "AMBIGUOUS_EXISTING_CLASS" in reasons
        # No new TrainingClass created, no audience linked to the manual class.
        classes = db.query(TrainingClass).filter(TrainingClass.training_year_id == py.id).all()
        assert len(classes) == 1
        assert classes[0].id == manual_class.id
        assert db.query(SessionAudience).filter(SessionAudience.session_id == sess.id).count() == 0

        _cleanup(db, planning_years=[py], stages=[stage], parade_nights=[pn], sessions=[sess])
    finally:
        db.close()


def test_cadet_phase_creates_active_membership():
    db = SessionLocal()
    try:
        sqn = _sqn_703(db)
        py = PlanningYear(
            unit_id=sqn.id, wing_id=sqn.wing_id, year=9107, name=_unique("CLASS-14-TEST-YEAR"),
            active_status=True,
        )
        db.add(py)
        db.flush()
        stage = CurriculumPhase(
            name=_unique("CLASS-14-TEST-STAGE"), display_name="Junior",
            scope_level="squadron", squadron_id=sqn.id, sort_order=0,
        )
        db.add(stage)
        db.flush()
        cadet = Cadet(squadron_id=sqn.id, first_name="Test", last_name=_unique("Cadet"), phase="Junior")
        db.add(cadet)
        db.commit()

        # Deactivate any other active years so this test's year is the
        # unambiguous "current active year" the script resolves to.
        others = db.query(PlanningYear).filter(
            PlanningYear.unit_id == sqn.id, PlanningYear.active_status == True,  # noqa: E712
            PlanningYear.id != py.id,
        ).all()
        for o in others:
            o.active_status = False
        db.commit()

        try:
            report = migrate_squadron(db, sqn, dry_run=False)
            db.commit()

            assert report.created_memberships >= 1
            membership = db.query(CadetClassMembership).filter(CadetClassMembership.cadet_id == cadet.id).first()
            assert membership is not None
            assert membership.source == MIGRATION_SOURCE
            assert membership.active_status is True

            db.refresh(cadet)
            assert cadet.phase == "Junior"  # untouched
        finally:
            for o in others:
                o.active_status = True
            db.commit()

        _cleanup(db, planning_years=[py], stages=[stage], cadets=[cadet])
    finally:
        db.close()


def test_rollback_removes_only_migration_created_rows():
    db = SessionLocal()
    try:
        sqn = _sqn_703(db)
        py, stage, pn, sess = _setup_squadron_year_stage_session(
            db, sqn, year_num=9108, stage_display="Orientation", cadet_group="orientation",
        )
        migrate_squadron(db, sqn, dry_run=False)
        db.commit()

        tclass = db.query(TrainingClass).filter(TrainingClass.training_year_id == py.id).first()
        assert tclass is not None
        tclass_id = tclass.id

        result = rollback(squadron_id=sqn.id, dry_run=False)
        assert any(d["training_class_id"] == tclass_id for d in result["deleted_classes"])
        assert db.query(TrainingClass).filter(TrainingClass.id == tclass_id).first() is None
        assert db.query(SessionAudience).filter(SessionAudience.session_id == sess.id).count() == 0

        _cleanup(db, planning_years=[py], stages=[stage], parade_nights=[pn], sessions=[sess])
    finally:
        db.close()


def test_rollback_refuses_to_delete_class_with_foreign_link_added_since():
    """If a real user has since linked their own SessionAudience or
    CadetClassMembership to a migration-created class, rollback must refuse to
    delete it (that would destroy real subsequent work), not silently do it."""
    db = SessionLocal()
    try:
        sqn = _sqn_703(db)
        py, stage, pn, sess = _setup_squadron_year_stage_session(
            db, sqn, year_num=9109, stage_display="Initial", cadet_group="initial",
        )
        migrate_squadron(db, sqn, dry_run=False)
        db.commit()

        tclass = db.query(TrainingClass).filter(TrainingClass.training_year_id == py.id).first()
        tclass_id = tclass.id

        # Simulate a real user adding a second session to this migration-created
        # class via the normal API path (created_by left as a real user id).
        pn2 = ParadeNight(squadron_id=sqn.id, wing_id=sqn.wing_id, training_year=9109, date="2030-01-02")
        db.add(pn2)
        db.flush()
        sess2 = TrainingSession(parade_night_id=pn2.id, squadron_id=sqn.id)
        db.add(sess2)
        db.flush()
        foreign_audience = SessionAudience(session_id=sess2.id, training_class_id=tclass_id, created_by="real-user")
        db.add(foreign_audience)
        db.commit()

        result = rollback(squadron_id=sqn.id, dry_run=False)
        refused_ids = [r["training_class_id"] for r in result["refused"]]
        assert tclass_id in refused_ids
        # The class and BOTH audience rows must still exist -- nothing deleted.
        assert db.query(TrainingClass).filter(TrainingClass.id == tclass_id).first() is not None
        assert db.query(SessionAudience).filter(SessionAudience.training_class_id == tclass_id).count() == 2

        db.query(SessionAudience).filter(SessionAudience.session_id == sess2.id).delete()
        db.query(TrainingSession).filter(TrainingSession.id == sess2.id).delete()
        db.query(ParadeNight).filter(ParadeNight.id == pn2.id).delete()
        db.commit()
        # Now rollback should succeed since the foreign link is gone.
        result2 = rollback(squadron_id=sqn.id, dry_run=False)
        assert any(d["training_class_id"] == tclass_id for d in result2["deleted_classes"])

        _cleanup(db, planning_years=[py], stages=[stage], parade_nights=[pn], sessions=[sess])
    finally:
        db.close()
