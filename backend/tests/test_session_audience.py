"""Tests for SessionAudience (CLASS-03) -- the Session<->TrainingClass
many-to-many linkage. See docs/product-review/parallel-class-impact-analysis.md
Finding 2 (Session.cadet_group is a single free-text string, unable to
represent which specific Training Class(es) a Session targets) and
docs/remediation/master_gap_register.csv's CLASS-03.
"""
from datetime import date, timedelta

import pytest
from tests.conftest import login


def _sqn_admin_hdr(client):
    return login(client, "ADMIN703")


def _general_hdr(client):
    return login(client, "703SQN2026")


def _make_year(client, hdr, year):
    r = client.post("/api/planning/years", json={"year": year, "name": f"{year} Training Year"}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def _senior_stage_id(client, hdr):
    r = client.get("/api/curriculum/phases", headers=hdr)
    assert r.status_code == 200, r.text
    senior = next(p for p in r.json() if p["name"] == "E. Senior")
    return senior["phase_id"]


def _make_class(client, hdr, year_id, stage_id, name, sequence=0):
    r = client.post("/api/training-classes", json={
        "training_year_id": year_id, "training_stage_id": stage_id,
        "display_name": name, "sequence": sequence,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["training_class_id"]


def _make_session(client, hdr, days_ahead):
    """Same weekday-collision avoidance as test_readiness_contract.py's helper --
    703's seeded demo data recurs weekly on its default parade day (Friday)."""
    candidate = date.today() + timedelta(days=days_ahead)
    if candidate.weekday() == 4:  # Friday
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

    sess = client.post("/api/sessions", json={
        "parade_night_id": pn_id, "period_number": 1, "cadet_group": "senior",
    }, headers=hdr)
    assert sess.status_code in (200, 201), sess.text
    return sess.json()["session_id"]


# ─────────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────────

def test_set_and_get_single_class_audience(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2090)
    stage_id = _senior_stage_id(client, hdr)
    class_id = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 1")
    sid = _make_session(client, hdr, days_ahead=20)

    r = client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [class_id]}, headers=hdr)
    assert r.status_code == 200, r.text
    assert [row["training_class_id"] for row in r.json()] == [class_id]

    listed = client.get(f"/api/sessions/{sid}/audience", headers=hdr)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["training_class_id"] == class_id
    assert listed.json()[0]["outcome_override"] is None


def test_combined_session_targets_multiple_classes_without_duplication(client):
    """One Session may target several Training Classes -- addendum §40
    Example 2 (Senior 1 + Senior 2 -> one combined Drill Session), not a
    duplicated Session per class."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2089)
    stage_id = _senior_stage_id(client, hdr)
    c1 = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 1")
    c2 = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 2")
    sid = _make_session(client, hdr, days_ahead=23)

    r = client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [c1, c2]}, headers=hdr)
    assert r.status_code == 200, r.text
    ids = {row["training_class_id"] for row in r.json()}
    assert ids == {c1, c2}

    # Exactly 2 audience rows for 1 Session -- confirms no Session duplication
    # occurred (a naive "one Session per class" implementation would instead
    # produce two separate Sessions, each with its own single-row audience).
    listed = client.get(f"/api/sessions/{sid}/audience", headers=hdr).json()
    assert len(listed) == 2


def test_put_audience_is_idempotent_replace_not_append(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2088)
    stage_id = _senior_stage_id(client, hdr)
    c1 = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 1")
    c2 = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 2")
    c3 = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 3")
    sid = _make_session(client, hdr, days_ahead=26)

    first = client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [c1, c2]}, headers=hdr)
    assert first.status_code == 200
    assert {r["training_class_id"] for r in first.json()} == {c1, c2}

    # Replace with a different set -- c1 dropped, c3 added, c2 kept.
    second = client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [c2, c3]}, headers=hdr)
    assert second.status_code == 200
    assert {r["training_class_id"] for r in second.json()} == {c2, c3}

    listed = client.get(f"/api/sessions/{sid}/audience", headers=hdr).json()
    assert {r["training_class_id"] for r in listed} == {c2, c3}, "PUT must replace, not accumulate"


def test_split_session_removes_one_class_without_losing_the_others(client):
    """addendum §59.2: a Session originally planned for two classes can be
    split so one class is removed from this Session's audience (the caller
    is expected to create a separate Session for the removed class -- the
    audience endpoint itself only needs to support the removal half)."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2087)
    stage_id = _senior_stage_id(client, hdr)
    c1 = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 1")
    c2 = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 2")
    # days_ahead=29 previously collided with test_org_account_linking.py's
    # test_sysadmin_enter_intervention_then_write_succeeds_and_is_audited,
    # which hardcodes 703's parade night to the literal date "2026-09-08" --
    # a relative today+N offset isn't collision-safe against another file's
    # absolute literal (same class of issue test_class_curriculum_progress.py
    # already hit and fixed by moving off the shared near-term date range
    # entirely). 209 is well outside every other days_ahead value used in
    # this file (20-47) and outside test_class_split_merge.py/
    # test_readiness_contract.py's own days_ahead=200.
    sid = _make_session(client, hdr, days_ahead=209)
    client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [c1, c2]}, headers=hdr)

    r = client.delete(f"/api/sessions/{sid}/audience/{c1}", headers=hdr)
    assert r.status_code == 200, r.text

    listed = client.get(f"/api/sessions/{sid}/audience", headers=hdr).json()
    assert [row["training_class_id"] for row in listed] == [c2]


# ─────────────────────────────────────────────────────────────
# Per-class outcome exception (addendum §48)
# ─────────────────────────────────────────────────────────────

def test_per_class_outcome_exception_on_combined_session(client):
    """A Session delivered jointly to three classes where one class didn't
    actually receive it -- addendum §48's exact scenario. Must not require
    three separate Sessions."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2086)
    stage_id = _senior_stage_id(client, hdr)
    c1 = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 1")
    c2 = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 2")
    c3 = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 3")
    sid = _make_session(client, hdr, days_ahead=32)
    client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [c1, c2, c3]}, headers=hdr)

    r = client.patch(f"/api/sessions/{sid}/audience/{c3}", json={
        "outcome_override": "not_delivered", "outcome_override_reason": "Senior 3 absent -- local excursion",
    }, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["outcome_override"] == "not_delivered"

    listed = {row["training_class_id"]: row for row in client.get(f"/api/sessions/{sid}/audience", headers=hdr).json()}
    assert listed[c1]["outcome_override"] is None
    assert listed[c2]["outcome_override"] is None
    assert listed[c3]["outcome_override"] == "not_delivered"
    assert "excursion" in listed[c3]["outcome_override_reason"]


def test_outcome_override_requires_reason_for_reason_required_statuses(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2085)
    stage_id = _senior_stage_id(client, hdr)
    c1 = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 1")
    sid = _make_session(client, hdr, days_ahead=35)
    client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [c1]}, headers=hdr)

    r = client.patch(f"/api/sessions/{sid}/audience/{c1}", json={"outcome_override": "cancelled"}, headers=hdr)
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["error"] == "reason_required_cancelled"


def test_clearing_outcome_override_reverts_to_null(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, 2084)
    stage_id = _senior_stage_id(client, hdr)
    c1 = _make_class(client, hdr, year["planning_year_id"], stage_id, "Senior 1")
    sid = _make_session(client, hdr, days_ahead=38)
    client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [c1]}, headers=hdr)
    client.patch(f"/api/sessions/{sid}/audience/{c1}", json={
        "outcome_override": "cancelled", "outcome_override_reason": "weather",
    }, headers=hdr)

    r = client.patch(f"/api/sessions/{sid}/audience/{c1}", json={"outcome_override": None}, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["outcome_override"] is None


# ─────────────────────────────────────────────────────────────
# RBAC and validation
# ─────────────────────────────────────────────────────────────

def test_sqn_general_cannot_set_session_audience(client):
    hdr_admin = _sqn_admin_hdr(client)
    year = _make_year(client, hdr_admin, 2083)
    stage_id = _senior_stage_id(client, hdr_admin)
    c1 = _make_class(client, hdr_admin, year["planning_year_id"], stage_id, "Senior 1")
    sid = _make_session(client, hdr_admin, days_ahead=41)

    hdr_general = _general_hdr(client)
    r = client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [c1]}, headers=hdr_general)
    assert r.status_code == 403


def test_set_session_audience_unauthenticated(client):
    r = client.put("/api/sessions/does-not-matter/audience", json={"training_class_ids": []})
    assert r.status_code == 401


def test_cannot_link_a_class_from_another_squadron(client):
    hdr_703 = _sqn_admin_hdr(client)
    year_703 = _make_year(client, hdr_703, 2082)
    stage_id = _senior_stage_id(client, hdr_703)
    class_703 = _make_class(client, hdr_703, year_703["planning_year_id"], stage_id, "Senior 1")

    hdr_704 = login(client, "ADMIN704")
    sid_704 = _make_session(client, hdr_704, days_ahead=44)

    r = client.put(f"/api/sessions/{sid_704}/audience", json={"training_class_ids": [class_703]}, headers=hdr_704)
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["error"] == "invalid_training_class"


def test_cannot_link_a_nonexistent_class(client):
    hdr = _sqn_admin_hdr(client)
    sid = _make_session(client, hdr, days_ahead=47)
    r = client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": ["not-a-real-id"]}, headers=hdr)
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["error"] == "invalid_training_class"
