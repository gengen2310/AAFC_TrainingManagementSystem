"""Tests for TrainingClass (CLASS-01) -- the Squadron-specific local group
undertaking a Training Stage during a Training Year. See
docs/product-review/parallel-class-impact-analysis.md and
docs/remediation/master_gap_register.csv's CLASS-01..14 for the full design
rationale and dependent follow-up work (Session audience linkage, Mission
Backlog/dashboard class-awareness, bulk setup -- none of that is built yet;
this covers only the base CRUD surface added this pass).
"""
import pytest
from tests.conftest import login


def _sqn_admin_hdr(client):
    return login(client, "ADMIN703")


def _wing_admin_hdr(client):
    return login(client, "ADMIN7WG")


def _general_hdr(client):
    return login(client, "703SQN2026")


def _make_year(client, hdr, year=2099):
    r = client.post("/api/planning/years", json={"year": year, "name": f"{year} Training Year"}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def _senior_stage_id(client, hdr):
    r = client.get("/api/curriculum/phases", headers=hdr)
    assert r.status_code == 200, r.text
    phases = r.json()
    senior = next(p for p in phases if p["name"] == "E. Senior")
    return senior["phase_id"]


# ─────────────────────────────────────────────────────────────
# Happy path
# ─────────────────────────────────────────────────────────────

def test_sqn_admin_can_create_training_class(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr)
    stage_id = _senior_stage_id(client, hdr)
    r = client.post("/api/training-classes", json={
        "training_year_id": year["planning_year_id"],
        "training_stage_id": stage_id,
        "display_name": "Senior 1",
        "sequence": 1,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    cid = r.json()["training_class_id"]

    listed = client.get("/api/training-classes", params={"training_year_id": year["planning_year_id"]}, headers=hdr)
    assert listed.status_code == 200
    names = [c["display_name"] for c in listed.json()]
    assert "Senior 1" in names
    match = next(c for c in listed.json() if c["training_class_id"] == cid)
    assert match["training_stage_id"] == stage_id
    assert match["version"] == 0
    assert match["is_archived"] is False


def test_five_parallel_senior_classes_are_independent(client):
    """Five Training Classes may share one Training Stage without collision
    -- the core addendum requirement (one Stage = many Classes, not the
    'ONE STAGE = ONE COLUMN = ONE CLASS' anti-pattern this program's
    impact analysis confirmed the pre-existing schema had)."""
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, year=2098)
    stage_id = _senior_stage_id(client, hdr)
    created_ids = []
    for i in range(1, 6):
        r = client.post("/api/training-classes", json={
            "training_year_id": year["planning_year_id"],
            "training_stage_id": stage_id,
            "display_name": f"Senior {i}",
            "sequence": i,
        }, headers=hdr)
        assert r.status_code == 200, r.text
        created_ids.append(r.json()["training_class_id"])

    assert len(set(created_ids)) == 5, "each class must be a distinct record, not deduplicated by shared stage"
    listed = client.get("/api/training-classes", params={"training_year_id": year["planning_year_id"]}, headers=hdr).json()
    senior_classes = [c for c in listed if c["training_stage_id"] == stage_id]
    assert len(senior_classes) == 5
    assert sorted(c["display_name"] for c in senior_classes) == [f"Senior {i}" for i in range(1, 6)]


def test_update_training_class_rename_and_version_increments(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, year=2097)
    stage_id = _senior_stage_id(client, hdr)
    created = client.post("/api/training-classes", json={
        "training_year_id": year["planning_year_id"],
        "training_stage_id": stage_id,
        "display_name": "Senior 1",
    }, headers=hdr).json()
    cid = created["training_class_id"]

    r = client.patch(f"/api/training-classes/{cid}", json={
        "display_name": "Senior 1 (Renamed)", "client_version": 0,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["version"] == 1

    # Renaming does not change the canonical ID -- the class's identity is
    # the UUID, not the display name (addendum §35's explicit requirement).
    listed = client.get("/api/training-classes", params={"training_year_id": year["planning_year_id"]}, headers=hdr).json()
    match = next(c for c in listed if c["training_class_id"] == cid)
    assert match["display_name"] == "Senior 1 (Renamed)"


def test_stale_version_update_returns_409(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, year=2096)
    stage_id = _senior_stage_id(client, hdr)
    created = client.post("/api/training-classes", json={
        "training_year_id": year["planning_year_id"],
        "training_stage_id": stage_id,
        "display_name": "Senior 1",
    }, headers=hdr).json()
    cid = created["training_class_id"]

    # First edit succeeds and bumps the version to 1.
    ok = client.patch(f"/api/training-classes/{cid}", json={"notes": "first edit", "client_version": 0}, headers=hdr)
    assert ok.status_code == 200

    # A second edit still targeting the now-stale version 0 must conflict.
    stale = client.patch(f"/api/training-classes/{cid}", json={"notes": "stale edit", "client_version": 0}, headers=hdr)
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"]["error"] == "version_conflict"


def test_archive_training_class_is_soft_delete(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, year=2095)
    stage_id = _senior_stage_id(client, hdr)
    created = client.post("/api/training-classes", json={
        "training_year_id": year["planning_year_id"],
        "training_stage_id": stage_id,
        "display_name": "Bronze 1",
    }, headers=hdr).json()
    cid = created["training_class_id"]

    r = client.delete(f"/api/training-classes/{cid}", headers=hdr)
    assert r.status_code == 200, r.text

    default_list = client.get("/api/training-classes", params={"training_year_id": year["planning_year_id"]}, headers=hdr).json()
    assert cid not in [c["training_class_id"] for c in default_list], "archived class must not appear in the default list"

    with_archived = client.get(
        "/api/training-classes",
        params={"training_year_id": year["planning_year_id"], "include_archived": True},
        headers=hdr,
    ).json()
    match = next(c for c in with_archived if c["training_class_id"] == cid)
    assert match["is_archived"] is True, "archive must be a soft delete, not a hard delete -- history must survive"


# ─────────────────────────────────────────────────────────────
# RBAC
# ─────────────────────────────────────────────────────────────

def test_sqn_general_cannot_create_training_class(client):
    hdr_admin = _sqn_admin_hdr(client)
    year = _make_year(client, hdr_admin, year=2094)
    stage_id = _senior_stage_id(client, hdr_admin)
    hdr_general = _general_hdr(client)
    r = client.post("/api/training-classes", json={
        "training_year_id": year["planning_year_id"],
        "training_stage_id": stage_id,
        "display_name": "Senior 1",
    }, headers=hdr_general)
    assert r.status_code == 403


def test_create_training_class_unauthenticated(client):
    r = client.post("/api/training-classes", json={
        "training_year_id": "x", "training_stage_id": "y", "display_name": "Senior 1",
    })
    assert r.status_code == 401


def test_list_training_classes_unauthenticated(client):
    r = client.get("/api/training-classes")
    assert r.status_code == 401


def test_wing_admin_without_proxy_cannot_write_squadron_training_class(client):
    """Wing admin has no active squadron scope and no Proxy/Delegated
    Intervention session -- writing to a squadron-scoped Training Class must
    still go through require_can_write_squadron like every other squadron
    write, not bypass it because the caller is a higher role."""
    hdr_admin = _sqn_admin_hdr(client)
    year = _make_year(client, hdr_admin, year=2093)
    stage_id = _senior_stage_id(client, hdr_admin)
    hdr_wing = _wing_admin_hdr(client)
    r = client.post("/api/training-classes", json={
        "training_year_id": year["planning_year_id"],
        "training_stage_id": stage_id,
        "display_name": "Senior 1",
    }, headers=hdr_wing)
    assert r.status_code in (400, 403), r.text


# ─────────────────────────────────────────────────────────────
# Validation
# ─────────────────────────────────────────────────────────────

def test_cannot_create_training_class_for_another_squadrons_year(client):
    hdr_703 = _sqn_admin_hdr(client)
    year_703 = _make_year(client, hdr_703, year=2092)
    stage_id = _senior_stage_id(client, hdr_703)

    hdr_704 = login(client, "ADMIN704")
    r = client.post("/api/training-classes", json={
        "training_year_id": year_703["planning_year_id"],
        "training_stage_id": stage_id,
        "display_name": "Senior 1",
    }, headers=hdr_704)
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["error"] == "training_year_not_found_for_squadron"


def test_cannot_create_training_class_with_nonexistent_stage(client):
    hdr = _sqn_admin_hdr(client)
    year = _make_year(client, hdr, year=2091)
    r = client.post("/api/training-classes", json={
        "training_year_id": year["planning_year_id"],
        "training_stage_id": "not-a-real-phase-id",
        "display_name": "Senior 1",
    }, headers=hdr)
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["error"] == "training_stage_not_visible"
