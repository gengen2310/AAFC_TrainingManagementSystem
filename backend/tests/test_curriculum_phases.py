"""Curriculum phase catalogue tests (master transformation plan Block 10) —
RBAC, scope visibility, and idempotency. Mirrors test_curriculum_elements.py's
structure exactly since CurriculumPhase is built as CurriculumElement's
sibling with the identical scope/visibility/idempotent-create rules.
"""
from tests.conftest import login


def _sysadmin(client):
    return login(client, "SYSADMIN2026")


def _nat_admin(client):
    return login(client, "ADMINNATIONAL")


def _wing_admin(client):
    return login(client, "ADMIN7WG")


def _sqn_admin(client):
    return login(client, "ADMIN703")


def _auditor(client):
    return login(client, "AUDITOR2026")


# ── Phase list ────────────────────────────────────────────────────────────

def test_phases_list_returns_seeded_defaults_in_order(client):
    """GET /api/curriculum/phases returns the 8 seeded national phases,
    ordered by sort_order (training progression), not alphabetically."""
    hdr = _sqn_admin(client)
    r = client.get("/api/curriculum/phases", headers=hdr)
    assert r.status_code == 200, r.text
    data = r.json()
    names = [p["name"] for p in data]
    assert "A. Orientation" in names
    assert "K. Gold" in names
    orientation_idx = names.index("A. Orientation")
    gold_idx = names.index("K. Gold")
    assert orientation_idx < gold_idx, "phases must be returned in training-progression order"


def test_phases_list_unauthenticated(client):
    r = client.get("/api/curriculum/phases")
    assert r.status_code == 401


def test_phases_shape_matches_frontend_contract(client):
    hdr = _sqn_admin(client)
    phases = client.get("/api/curriculum/phases", headers=hdr).json()
    assert isinstance(phases, list)
    for ph in phases:
        assert "phase_id" in ph
        assert "name" in ph
        assert "display_name" in ph
        assert "scope_level" in ph
        assert "sort_order" in ph


# ── RBAC: who can create phases ──────────────────────────────────────────

def test_sqn_admin_can_create_sqn_phase(client):
    hdr = _sqn_admin(client)
    r = client.post("/api/curriculum/phases", json={
        "name": "SQN Custom Phase", "display_name": "Squadron Custom Phase",
        "scope_level": "squadron",
    }, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "SQN Custom Phase"


def test_sqn_admin_cannot_create_national_phase(client):
    hdr = _sqn_admin(client)
    r = client.post("/api/curriculum/phases", json={
        "name": "NAT_PHASE_TEST", "display_name": "National Phase Test",
        "scope_level": "national",
    }, headers=hdr)
    assert r.status_code == 403


def test_sqn_admin_cannot_create_wing_phase(client):
    hdr = _sqn_admin(client)
    r = client.post("/api/curriculum/phases", json={
        "name": "WING_PHASE_TEST", "display_name": "Wing Phase Test",
        "scope_level": "wing",
    }, headers=hdr)
    assert r.status_code == 403


def test_wing_admin_can_create_wing_phase(client):
    hdr = _wing_admin(client)
    r = client.post("/api/curriculum/phases", json={
        "name": "WING_CUSTOM_PHASE", "display_name": "Wing Custom Phase",
        "scope_level": "wing",
    }, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["scope_level"] == "wing"


def test_nat_admin_can_create_national_phase(client):
    hdr = _nat_admin(client)
    r = client.post("/api/curriculum/phases", json={
        "name": "NAT_CUSTOM_PHASE", "display_name": "National Custom Phase",
        "scope_level": "national",
    }, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["scope_level"] == "national"


def test_sysadmin_can_create_any_scope_phase(client):
    hdr = _sysadmin(client)
    for scope in ("national", "wing", "squadron"):
        r = client.post("/api/curriculum/phases", json={
            "name": f"SYSADM_PHASE_{scope.upper()[:3]}", "display_name": f"SysAdmin {scope} phase",
            "scope_level": scope,
        }, headers=hdr)
        assert r.status_code == 200, f"scope={scope} failed: {r.text}"


def test_auditor_cannot_create_phase(client):
    hdr = _auditor(client)
    r = client.post("/api/curriculum/phases", json={
        "name": "AUD_PHASE", "display_name": "Auditor Attempt",
        "scope_level": "national",
    }, headers=hdr)
    assert r.status_code == 403


def test_invalid_scope_level_rejected(client):
    hdr = _sysadmin(client)
    r = client.post("/api/curriculum/phases", json={
        "name": "BAD_SCOPE_PHASE", "display_name": "Bad Scope",
        "scope_level": "galactic",
    }, headers=hdr)
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "invalid_scope"


# ── Idempotency ───────────────────────────────────────────────────────────

def test_duplicate_phase_is_idempotent(client):
    hdr = _nat_admin(client)
    payload = {"name": "IDEM_PHASE", "display_name": "Idempotent Phase", "scope_level": "national"}
    r1 = client.post("/api/curriculum/phases", json=payload, headers=hdr)
    r2 = client.post("/api/curriculum/phases", json=payload, headers=hdr)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json()["existed"] is True
    assert r1.json()["phase_id"] == r2.json()["phase_id"]


# ── Scope visibility ──────────────────────────────────────────────────────

def test_squadron_admin_does_not_see_other_wings_wing_phase(client):
    """A squadron admin must not see a wing-scoped phase belonging to a
    DIFFERENT wing — visibility is national + own-wing + own-squadron only."""
    hdr_wing = _wing_admin(client)
    r = client.post("/api/curriculum/phases", json={
        "name": "OTHER_WING_ONLY_PHASE", "display_name": "Other Wing Only Phase",
        "scope_level": "wing",
    }, headers=hdr_wing)
    assert r.status_code == 200, r.text

    hdr_nat = _nat_admin(client)
    wings = client.get("/api/wings", headers=hdr_nat).json()
    own_wing_id = client.get("/api/auth/me", headers=hdr_wing).json()["session"]["wing_id"]
    other_wing = next((w for w in wings if w["wing_id"] != own_wing_id), None)
    if not other_wing:
        return  # only one wing seeded in this environment — nothing to assert
    r2 = client.post("/api/curriculum/phases", json={
        "name": "OTHER_WING_ONLY_PHASE_2", "display_name": "Other Wing Only Phase 2",
        "scope_level": "wing", "wing_id": other_wing["wing_id"],
    }, headers=hdr_nat)
    assert r2.status_code == 200, r2.text

    hdr_sqn = _sqn_admin(client)
    own_wing_via_sqn = client.get("/api/auth/me", headers=hdr_sqn).json()["session"]["wing_id"]
    if own_wing_via_sqn == other_wing["wing_id"]:
        return  # this squadron actually belongs to that wing — not a useful negative case
    phases = client.get("/api/curriculum/phases", headers=hdr_sqn).json()
    names = [p["name"] for p in phases]
    assert "OTHER_WING_ONLY_PHASE_2" not in names


# ── Archive ───────────────────────────────────────────────────────────────

def test_archive_phase_removes_it_from_visible_list(client):
    hdr = _nat_admin(client)
    r = client.post("/api/curriculum/phases", json={
        "name": "ARCHIVE_ME_PHASE", "display_name": "Archive Me Phase", "scope_level": "national",
    }, headers=hdr)
    assert r.status_code == 200
    phase_id = r.json()["phase_id"]

    archive_r = client.post(f"/api/curriculum/phases/{phase_id}/archive", headers=hdr)
    assert archive_r.status_code == 200, archive_r.text

    phases = client.get("/api/curriculum/phases", headers=hdr).json()
    names = [p["name"] for p in phases]
    assert "ARCHIVE_ME_PHASE" not in names


def test_archive_nonexistent_phase_404s(client):
    hdr = _nat_admin(client)
    r = client.post("/api/curriculum/phases/00000000-0000-0000-0000-000000000000/archive", headers=hdr)
    assert r.status_code == 404
