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


def _own_squadron_id(client, hdr):
    return client.get("/api/auth/me", headers=hdr).json()["session"]["squadron_id"]


# ── DEFECT-001 (general-release qualification) ───────────────────────────
# Root cause: _can_create_phase's squadron-scope branch let wing_admin/
# national_admin/system_admin create a squadron-scope phase for ANY squadron
# with no Proxy/Delegated Intervention check at all — a real tenancy gap,
# inconsistent with require_can_write_squadron's doctrine used everywhere
# else in this app. Omitting squadron_id entirely also silently created an
# orphaned phase row (scope_level="squadron", squadron_id=None) since the
# caller has no own squadron_id to fall back to. Separately, connected-
# frontend's inline "+ New" phase creator always sent scope_level:"national"
# regardless of who clicked it, so a sqn_admin's own click always hit the
# national-only check and got "Access not permitted" — the literal reported
# symptom, but a frontend bug, not a backend one (the backend already
# correctly allows sqn_admin to create squadron-scope phases).

def test_wing_admin_without_proxy_cannot_create_squadron_scope_phase_for_specific_squadron(client):
    """A wing_admin who has NOT entered Proxy Mode must not be able to create
    a squadron-scope phase for an explicit squadron_id — writing into a lower
    scope always requires Proxy/Delegated Intervention in this app."""
    hdr_sqn = _sqn_admin(client)
    sqn_id = _own_squadron_id(client, hdr_sqn)

    hdr_wing = _wing_admin(client)
    r = client.post("/api/curriculum/phases", json={
        "name": "NO_PROXY_SQN_PHASE", "display_name": "No Proxy Squadron Phase",
        "scope_level": "squadron", "squadron_id": sqn_id,
    }, headers=hdr_wing)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["error"] == "proxy_required"


def test_wing_admin_without_proxy_and_no_squadron_id_does_not_orphan_a_phase(client):
    """Omitting squadron_id entirely must not silently create an orphaned
    scope_level="squadron", squadron_id=None row."""
    hdr_wing = _wing_admin(client)
    r = client.post("/api/curriculum/phases", json={
        "name": "NO_PROXY_NO_SQNID_PHASE", "display_name": "No Proxy No Squadron Id",
        "scope_level": "squadron",
    }, headers=hdr_wing)
    assert r.status_code == 403, r.text


def test_wing_admin_with_active_proxy_can_create_squadron_scope_phase(client):
    """Once a wing_admin has entered Proxy Mode for a specific squadron, they
    may create a squadron-scope phase for THAT squadron — the sanctioned
    write-into-a-lower-scope mechanism, matching require_can_write_squadron."""
    hdr_sqn = _sqn_admin(client)
    sqn_id = _own_squadron_id(client, hdr_sqn)

    hdr_wing = _wing_admin(client)
    enter = client.post(f"/api/proxy/enter/{sqn_id}", json={"reason": "Assist with phase setup"}, headers=hdr_wing)
    assert enter.status_code == 200, enter.text
    try:
        r = client.post("/api/curriculum/phases", json={
            "name": "PROXY_SQN_PHASE", "display_name": "Proxy Squadron Phase",
            "scope_level": "squadron",
        }, headers=hdr_wing)
        assert r.status_code == 200, r.text
        assert r.json()["scope_level"] == "squadron"
        phases = client.get("/api/curriculum/phases", headers=hdr_sqn).json()
        assert any(p["name"] == "PROXY_SQN_PHASE" for p in phases)
    finally:
        client.post("/api/proxy/exit", headers=hdr_wing)


def test_wing_admin_proxy_cannot_create_squadron_phase_for_a_different_squadron(client):
    """Proxy into squadron A must not authorise creating a squadron-scope
    phase explicitly targeting squadron B."""
    hdr_sqn = _sqn_admin(client)
    sqn_a = _own_squadron_id(client, hdr_sqn)

    hdr_nat = _nat_admin(client)
    wings = client.get("/api/wings", headers=hdr_nat).json()
    squadrons = client.get("/api/squadrons", headers=hdr_nat).json()
    sqn_b = next((s["squadron_id"] for s in squadrons if s["squadron_id"] != sqn_a), None)
    if not sqn_b:
        return  # only one squadron seeded in this environment — nothing to assert

    hdr_wing = _wing_admin(client)
    enter = client.post(f"/api/proxy/enter/{sqn_a}", json={"reason": "Assist squadron A"}, headers=hdr_wing)
    if enter.status_code != 200:
        return  # sqn_b may not be in this wing_admin's wing — not a useful case here
    try:
        r = client.post("/api/curriculum/phases", json={
            "name": "CROSS_SQN_PHASE", "display_name": "Cross Squadron Phase",
            "scope_level": "squadron", "squadron_id": sqn_b,
        }, headers=hdr_wing)
        assert r.status_code == 403, r.text
    finally:
        client.post("/api/proxy/exit", headers=hdr_wing)


def test_national_admin_without_intervention_cannot_create_squadron_scope_phase(client):
    hdr_sqn = _sqn_admin(client)
    sqn_id = _own_squadron_id(client, hdr_sqn)

    hdr_nat = _nat_admin(client)
    r = client.post("/api/curriculum/phases", json={
        "name": "NO_INTERVENTION_SQN_PHASE", "display_name": "No Intervention Squadron Phase",
        "scope_level": "squadron", "squadron_id": sqn_id,
    }, headers=hdr_nat)
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["error"] == "intervention_required"


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


def test_sysadmin_can_create_national_and_wing_scope_phase_directly(client):
    hdr = _sysadmin(client)
    for scope in ("national", "wing"):
        r = client.post("/api/curriculum/phases", json={
            "name": f"SYSADM_PHASE_{scope.upper()[:3]}", "display_name": f"SysAdmin {scope} phase",
            "scope_level": scope,
        }, headers=hdr)
        assert r.status_code == 200, f"scope={scope} failed: {r.text}"


def test_sysadmin_needs_intervention_to_create_squadron_scope_phase(client):
    """DEFECT-001: system_admin is grouped with national_admin for squadron-
    scope writes — Delegated Intervention required, same as every other
    squadron-scope write in this app (Principal.can_write_squadron)."""
    hdr_sqn = _sqn_admin(client)
    sqn_id = _own_squadron_id(client, hdr_sqn)

    hdr = _sysadmin(client)
    denied = client.post("/api/curriculum/phases", json={
        "name": "SYSADM_PHASE_SQN", "display_name": "SysAdmin squadron phase",
        "scope_level": "squadron", "squadron_id": sqn_id,
    }, headers=hdr)
    assert denied.status_code == 403, denied.text
    assert denied.json()["detail"]["error"] == "intervention_required"

    enter = client.post(f"/api/proxy/enter/{sqn_id}", json={"reason": "System admin phase setup"}, headers=hdr)
    assert enter.status_code == 200, enter.text
    try:
        r = client.post("/api/curriculum/phases", json={
            "name": "SYSADM_PHASE_SQN", "display_name": "SysAdmin squadron phase",
            "scope_level": "squadron",
        }, headers=hdr)
        assert r.status_code == 200, r.text
    finally:
        client.post("/api/proxy/exit", headers=hdr)


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
