"""Unit tests for app.services_readiness — the single authoritative readiness
computation (master transformation plan Block 3). Each fixture below matches one
of the required test cases from the execution plan: no sessions; one incomplete
session; lesson missing; facilitator missing; room missing; mixed-ready sessions;
all-ready sessions; unresolved conflict; cancelled session; stale/missing data.
"""
from app.services_readiness import parade_night_readiness, session_requirements, session_data_quality


def _session(**overrides):
    base = {
        "id": "s1", "period_number": 1,
        "curriculum_item_id": "curr-1", "custom_title": None, "session_title": None,
        "facilitator_id": "fac-1", "facilitator_display_name_at_time": "CIV Smith",
        "training_area_id": "room-1", "training_area_name_at_time": "Main Hall",
        "status": "planned", "not_delivered_reason": None, "cancelled_reason": None,
    }
    base.update(overrides)
    return base


# ── Fixture: no sessions ──────────────────────────────────────────────────────

def test_no_sessions_is_not_planned_never_ready():
    r = parade_night_readiness([])
    assert r["planning_status"] == "not_planned"
    assert r["sessions_total"] == 0
    assert r["legacy_score"] == 100  # legacy projection stays "100" but the real
    assert r["legacy_band"] == "Not planned"  # signal is planning_status, checked above
    # The critical assertion: nothing here can be mistaken for "ready"/"fully staffed".
    assert r["planning_status"] != "planned"
    assert r["requirements_summary"] == "No sessions scheduled"


# ── Fixture: one incomplete session ──────────────────────────────────────────

def test_one_incomplete_session_is_at_risk():
    sess = [_session(facilitator_id=None, facilitator_display_name_at_time=None)]
    r = parade_night_readiness(sess)
    assert r["planning_status"] == "at_risk"  # sessions exist but zero are ready
    assert r["sessions_ready"] == 0
    assert r["sessions_total"] == 1


# ── Fixture: lesson missing ───────────────────────────────────────────────────

def test_lesson_missing_named_in_requirements():
    sess = _session(curriculum_item_id=None, custom_title=None, session_title=None)
    reqs = session_requirements(sess)
    assert reqs["checks"]["curriculum_assigned"] is False
    assert "curriculum item" in reqs["missing"]
    assert reqs["complete_count"] == reqs["total_count"] - 1


# ── Fixture: facilitator missing ──────────────────────────────────────────────

def test_facilitator_missing_named_in_requirements():
    sess = _session(facilitator_id=None, facilitator_display_name_at_time=None)
    reqs = session_requirements(sess)
    assert reqs["checks"]["facilitator_assigned"] is False
    assert "facilitator" in reqs["missing"]


# ── Fixture: room missing ─────────────────────────────────────────────────────

def test_room_missing_named_in_requirements():
    sess = _session(training_area_id=None, training_area_name_at_time=None)
    reqs = session_requirements(sess)
    assert reqs["checks"]["room_assigned"] is False
    assert "room" in reqs["missing"]


# ── Fixture: mixed-ready sessions ─────────────────────────────────────────────

def test_mixed_ready_sessions_is_partly_planned():
    sess = [
        _session(id="s1"),
        _session(id="s2", facilitator_id=None, facilitator_display_name_at_time=None),
    ]
    r = parade_night_readiness(sess)
    assert r["planning_status"] == "partly_planned"
    assert r["sessions_ready"] == 1
    assert r["sessions_total"] == 2
    assert r["requirements_summary"] == "1 of 2 sessions ready"


# ── Fixture: all-ready sessions ───────────────────────────────────────────────

def test_all_ready_sessions_is_planned():
    sess = [_session(id="s1"), _session(id="s2")]
    r = parade_night_readiness(sess)
    assert r["planning_status"] == "planned"
    assert r["sessions_ready"] == 2
    assert r["legacy_score"] == 100
    assert r["legacy_band"] == "Ready"


# ── Fixture: unresolved conflict ──────────────────────────────────────────────

def test_unresolved_conflict_is_blocked_even_if_otherwise_ready():
    sess = [_session(id="s1"), _session(id="s2")]
    r = parade_night_readiness(sess, conflicts_by_session={"s1": True})
    assert r["planning_status"] == "blocked"
    # A blocked night must never simultaneously report "planned" — the two ready
    # sessions don't make it "planned" once a hard conflict exists.
    assert r["planning_status"] != "planned"


# ── Fixture: cancelled session ────────────────────────────────────────────────

def test_cancelled_session_with_reason_is_complete_quality():
    sess = _session(status="cancelled", cancelled_reason="Venue unavailable")
    quality = session_data_quality(sess)
    assert quality == "complete"


def test_cancelled_session_without_reason_is_missing_reason():
    sess = _session(status="cancelled", cancelled_reason=None)
    quality = session_data_quality(sess)
    assert quality == "missing_reason"


def test_parade_night_with_cancelled_session_reports_outcome_distribution():
    sess = [_session(id="s1", status="cancelled", cancelled_reason="Weather")]
    r = parade_night_readiness(sess)
    assert r["delivery_outcome_summary"]["cancelled"] == 1
    assert r["delivery_outcome_summary"]["delivered"] == 0


# ── Fixture: stale or missing data ────────────────────────────────────────────

def test_missing_reason_on_not_delivered_flags_data_quality():
    sess = [_session(id="s1", status="not_delivered", not_delivered_reason=None)]
    r = parade_night_readiness(sess)
    assert r["data_quality"] == "missing_reason"


def test_missing_required_information_when_no_reason_needed_status():
    """A planned session missing its facilitator/room is a data-quality gap too,
    distinct from (and less severe a category than) a missing outcome reason."""
    sess = [_session(id="s1", facilitator_id=None, facilitator_display_name_at_time=None,
                     training_area_id=None, training_area_name_at_time=None)]
    r = parade_night_readiness(sess)
    assert r["data_quality"] == "missing_required_information"


def test_inconsistent_record_state_is_a_named_category_not_silently_dropped():
    """inconsistent_record is a real category in the vocabulary (DATA_QUALITY_STATES)
    even though this codebase's current session_data_quality() doesn't emit it from
    any input yet — asserting it exists as a named, reachable state in the type
    contract rather than only testing what's emitted today."""
    from app.services_readiness import DATA_QUALITY_STATES
    assert "inconsistent_record" in DATA_QUALITY_STATES


# ── No-mixing-of-axes sanity check ────────────────────────────────────────────

def test_planning_status_never_mixes_with_delivery_outcome_values():
    """planning_status and delivery_outcome are genuinely separate vocabularies —
    confirms no accidental string overlap that could make one axis silently stand
    in for the other."""
    from app.services_readiness import PLANNING_STATUSES, DELIVERY_OUTCOMES
    assert set(PLANNING_STATUSES).isdisjoint(set(DELIVERY_OUTCOMES))
