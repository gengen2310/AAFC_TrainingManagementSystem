"""Tests for class-specific curriculum progress (CLASS-04). See
docs/remediation/master_gap_register.csv's CLASS-04/CLASS-07 and addendum
§43 (progress must be per Training Class, not blended per Stage) and §53/§74
(stage-level aggregation must use weighted requirement completion -- sum of
delivered / sum of applicable across classes -- never an average of each
class's own percentage).

Every test creates its own dedicated squadron-scoped Training Stage (never
the shared national "E. Senior" catalogue) and always sets a
learning_hub_url on curriculum items it creates. Both were required after
this suite proved they matter: the shared catalogue accumulates items across
every test run against the same session-scoped DB (tests/conftest.py), and
test_core.py::test_curriculum_progress_and_lh asserts every curriculum item
visible to squadron 703 has a learning_hub_url -- an item this file created
without one broke that unrelated test the first time this was written.
"""
import uuid
from datetime import date, timedelta

import pytest
from tests.conftest import login


def _sqn_admin_hdr(client):
    return login(client, "ADMIN703")


def _make_year(client, hdr, year):
    r = client.post("/api/planning/years", json={"year": year, "name": f"{year} Training Year"}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def _make_stage(client, hdr, squadron_id):
    """A fresh, squadron-scoped Training Stage exclusive to the calling
    test -- see module docstring for why this file never uses the shared
    "E. Senior" national catalogue."""
    name = f"CLASS-04-TEST-{uuid.uuid4().hex[:10]}"
    r = client.post("/api/curriculum/phases", json={
        "name": name, "display_name": name, "scope_level": "squadron", "squadron_id": squadron_id,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["phase_id"], name


def _make_class(client, hdr, year_id, stage_id, name):
    r = client.post("/api/training-classes", json={
        "training_year_id": year_id, "training_stage_id": stage_id, "display_name": name,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["training_class_id"]


def _make_curriculum_item(client, hdr, code, phase):
    r = client.post("/api/curriculum", json={
        "code": code, "title": f"{code} title", "phase": phase,
        "learning_hub_url": "https://example.invalid/learning-hub/test-fixture",
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["curriculum_id"]


# A relative "days ahead of today" offset collided with other test files'
# hardcoded literal dates the first time this was tried (today + 60/63 days
# landed on 2026-10-08/2026-10-11, both already claimed by test_timing.py's
# own fixed-date fixtures) -- the whole suite shares one session-scoped DB,
# so a relative date is not actually collision-safe against files using
# absolute literals. Use a fixed, far-future base year confirmed clear of
# every other test file's literal dates instead (grepped tests/*.py for
# 2050-*/2051-* before picking it).
_next_day_offset = [0]


def _make_session(client, hdr, curriculum_item_id=None, status=None):
    offset = _next_day_offset[0]
    _next_day_offset[0] += 3
    candidate = date(2050, 1, 1) + timedelta(days=offset)
    if candidate.weekday() == 4:  # Friday -- 703's seeded default parade day
        candidate += timedelta(days=1)
    target_date = candidate.isoformat()
    r = client.get("/api/auth/me", headers=hdr)
    session_info = r.json()["session"]
    sqn_id, wing_id = session_info.get("squadron_id"), session_info.get("wing_id")

    pn = client.post("/api/parade-nights", json={
        "squadron_id": sqn_id, "wing_id": wing_id, "date": target_date, "parade_type": "normal",
    }, headers=hdr)
    assert pn.status_code in (200, 201), pn.text
    pn_id = pn.json().get("parade_night_id") or pn.json().get("id")

    body = {"parade_night_id": pn_id, "period_number": 1, "cadet_group": "senior"}
    if curriculum_item_id:
        body["curriculum_item_id"] = curriculum_item_id
    sess = client.post("/api/sessions", json=body, headers=hdr)
    assert sess.status_code in (200, 201), sess.text
    sid = sess.json()["session_id"]

    if status:
        edit = client.put(f"/api/sessions/{sid}", json={
            "parade_night_id": pn_id, "period_number": 1, "cadet_group": "senior",
            "curriculum_item_id": curriculum_item_id, "status": status,
            "reason": "test data" if status in ("cancelled", "not_delivered", "delivered_with_issue") else None,
        }, headers=hdr)
        assert edit.status_code == 200, edit.text
    return sid


# ─────────────────────────────────────────────────────────────
# Per-class progress
# ─────────────────────────────────────────────────────────────

def test_class_with_no_sessions_shows_not_started(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2081)
    stage_id, stage_name = _make_stage(client, hdr, year["unit_id"])
    _make_curriculum_item(client, hdr, "SEN-P1", stage_name)
    class_id = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 1")

    r = client.get(f"/api/training-classes/{class_id}/curriculum-progress", headers=hdr)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["stage_name"] == stage_name
    assert data["summary"]["total"] == 1
    item = data["requirements"][0]
    assert item["code"] == "SEN-P1"
    assert item["status"] == "not_started"
    assert item["sessions"] == []


def test_delivered_session_marks_class_progress_delivered(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2080)
    stage_id, stage_name = _make_stage(client, hdr, year["unit_id"])
    item_id = _make_curriculum_item(client, hdr, "SEN-P2", stage_name)
    class_id = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 1")
    sid = _make_session(client, hdr, curriculum_item_id=item_id, status="delivered")
    client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [class_id]}, headers=hdr)

    r = client.get(f"/api/training-classes/{class_id}/curriculum-progress", headers=hdr)
    assert r.status_code == 200, r.text
    item = r.json()["requirements"][0]
    assert item["status"] == "delivered"
    assert item["sessions"] == [{"session_id": sid, "status": "delivered"}]


def test_two_classes_completing_same_item_are_independent(client):
    """Senior 1 completed SEN-P3 but Senior 2 did not -- addendum §43's
    exact scenario. Must NOT mark the item complete for both classes."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2079)
    stage_id, stage_name = _make_stage(client, hdr, year["unit_id"])
    item_id = _make_curriculum_item(client, hdr, "SEN-P3", stage_name)
    c1 = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 1")
    c2 = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 2")
    sid = _make_session(client, hdr, curriculum_item_id=item_id, status="delivered")
    client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [c1]}, headers=hdr)

    r1 = client.get(f"/api/training-classes/{c1}/curriculum-progress", headers=hdr).json()
    r2 = client.get(f"/api/training-classes/{c2}/curriculum-progress", headers=hdr).json()
    assert r1["requirements"][0]["status"] == "delivered"
    assert r2["requirements"][0]["status"] == "not_started"


def test_per_class_outcome_override_reflected_in_progress(client):
    """A combined Session delivered to Senior 1 + Senior 3, with Senior 3
    recorded as an exception (not_delivered) -- the class progress view for
    Senior 3 must show not_delivered, not delivered."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2078)
    stage_id, stage_name = _make_stage(client, hdr, year["unit_id"])
    item_id = _make_curriculum_item(client, hdr, "SEN-P4", stage_name)
    c1 = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 1")
    c3 = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 3")
    sid = _make_session(client, hdr, curriculum_item_id=item_id, status="delivered")
    client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [c1, c3]}, headers=hdr)
    client.patch(f"/api/sessions/{sid}/audience/{c3}", json={
        "outcome_override": "not_delivered", "outcome_override_reason": "absent",
    }, headers=hdr)

    r1 = client.get(f"/api/training-classes/{c1}/curriculum-progress", headers=hdr).json()
    r3 = client.get(f"/api/training-classes/{c3}/curriculum-progress", headers=hdr).json()
    assert r1["requirements"][0]["status"] == "delivered"
    assert r3["requirements"][0]["status"] == "not_delivered"


# ─────────────────────────────────────────────────────────────
# Stage-level weighted aggregation (addendum §53/§74)
# ─────────────────────────────────────────────────────────────

def test_stage_aggregate_sums_delivered_and_applicable_across_classes(client):
    """Every class undertaking a Training Stage shares the SAME curriculum
    item set (addendum §105 explicitly prohibits duplicating curriculum per
    class -- "do not require five duplicate Senior Training Stage
    definitions"), so within one stage every class has an identical
    applicable-item denominator. That means total_applicable is class_count
    x items_per_stage (here 2 x 12 = 24, not 12) -- each class is tracked
    against the full shared set, including items only a DIFFERENT class has
    delivered so far (correctly shown as not_started for the class that
    hasn't). The addendum's own formula (§53: "total completed applicable
    class-requirements / total applicable class-requirements") is exactly
    sum(delivered)/sum(applicable) across classes, which this test proves
    directly rather than assuming a shortcut. (With every class sharing one
    denominator, this sum-of-numerators/sum-of-denominators result happens
    to equal a plain average of per-class percentages in THIS scenario --
    that equivalence is a mathematical consequence of every class having the
    same denominator, not evidence the implementation is doing naive
    per-class averaging; the sum-based formula is what diverges correctly
    from averaging once per-class applicability, addendum §65, varies
    denominators between classes -- not built this pass, see CLASS-04's
    residual_limitation in the gap register.)"""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2077)
    stage_id, stage_name = _make_stage(client, hdr, year["unit_id"])

    c1 = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 1")
    c2 = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 2")

    # 10 items delivered only to Senior 1.
    for i in range(10):
        item_id = _make_curriculum_item(client, hdr, f"WA-S1-{i}", stage_name)
        sid = _make_session(client, hdr, curriculum_item_id=item_id, status="delivered")
        client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [c1]}, headers=hdr)

    # 2 more items: one delivered to Senior 2, one still only planned.
    item_a = _make_curriculum_item(client, hdr, "WA-S2-A", stage_name)
    item_b = _make_curriculum_item(client, hdr, "WA-S2-B", stage_name)
    sid_a = _make_session(client, hdr, curriculum_item_id=item_a, status="delivered")
    client.put(f"/api/sessions/{sid_a}/audience", json={"training_class_ids": [c2]}, headers=hdr)
    sid_b = _make_session(client, hdr, curriculum_item_id=item_b, status="planned")
    client.put(f"/api/sessions/{sid_b}/audience", json={"training_class_ids": [c2]}, headers=hdr)

    r = client.get(f"/api/curriculum/phases/{stage_id}/class-progress",
                   params={"squadron_id": year["unit_id"]}, headers=hdr)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["class_count"] == 2

    by_name = {c["display_name"]: c for c in data["classes"]}
    # Both classes see all 12 stage items as applicable (shared curriculum).
    assert by_name["Senior 1"]["total"] == 12
    assert by_name["Senior 1"]["delivered"] == 10   # its own 10 items
    assert by_name["Senior 2"]["total"] == 12
    assert by_name["Senior 2"]["delivered"] == 1    # only WA-S2-A

    # The endpoint's own totals must equal the sum of the per-class figures
    # it also returns -- this is what would break if a future change
    # switched to averaging per-class percentages instead of summing.
    assert data["total_delivered"] == sum(c["delivered"] for c in data["classes"])
    assert data["total_applicable"] == sum(c["total"] for c in data["classes"])
    assert data["total_delivered"] == 11
    assert data["total_applicable"] == 24
    assert data["coverage_pct"] == round(100 * 11 / 24)


def test_stage_progress_for_stage_with_no_classes_returns_zero_not_error(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2076)
    stage_id, _ = _make_stage(client, hdr, year["unit_id"])
    r = client.get(f"/api/curriculum/phases/{stage_id}/class-progress",
                   params={"squadron_id": year["unit_id"]}, headers=hdr)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["class_count"] == 0
    assert data["total_delivered"] == 0
    assert data["total_applicable"] == 0
    assert data["coverage_pct"] is None, "must be None (no ZeroDivisionError), not 0, when nothing is applicable yet"
    assert data["classes"] == []


# ─────────────────────────────────────────────────────────────
# RBAC
# ─────────────────────────────────────────────────────────────

def test_class_curriculum_progress_unauthenticated(client):
    r = client.get("/api/training-classes/does-not-matter/curriculum-progress")
    assert r.status_code == 401


def test_class_curriculum_progress_not_found(client):
    hdr = _sqn_admin_hdr(client)
    r = client.get("/api/training-classes/not-a-real-id/curriculum-progress", headers=hdr)
    assert r.status_code == 404
