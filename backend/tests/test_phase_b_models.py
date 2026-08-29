"""Phase B model-layer smoke tests: verify ParadeNight gains new columns,
ParadeDate is removed, and FK renames propagate to notices/conflicts/anchors."""
import pytest
from app.models.training import ParadeNight
from app.models.planning import PlanningNotice, PlanningConflict, AnchorPrepPlan


def test_parade_night_has_planning_year_id():
    cols = {c.key for c in ParadeNight.__table__.columns}
    assert "planning_year_id" in cols
    assert "training_year" not in cols
    assert "week_number" in cols
    assert "is_active" in cols
    assert "cancellation_reason" in cols


def test_planning_notice_has_parade_night_id():
    cols = {c.key for c in PlanningNotice.__table__.columns}
    assert "parade_night_id" in cols
    assert "parade_date_id" not in cols
    assert "planning_year_id" not in cols


def test_planning_conflict_has_parade_night_id():
    cols = {c.key for c in PlanningConflict.__table__.columns}
    assert "parade_night_id" in cols
    assert "parade_date_id" not in cols


def test_anchor_prep_plan_has_planned_parade_night_id():
    cols = {c.key for c in AnchorPrepPlan.__table__.columns}
    assert "planned_parade_night_id" in cols
    assert "planned_parade_date_id" not in cols


def test_parade_date_class_removed():
    try:
        from app.models.planning import ParadeDate  # noqa
        assert False, "ParadeDate should not be importable after Phase B"
    except ImportError:
        pass
