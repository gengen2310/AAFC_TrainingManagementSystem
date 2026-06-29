"""Maintenance mode enforcement tests.

Verifies that during maintenance mode:
  - Normal user POST/PUT/PATCH/DELETE returns 503 with maintenance error
  - GET requests remain accessible for normal users
  - system_admin write operations remain permitted
  - Auth (login/me) remains reachable regardless
  - After disabling maintenance, normal writes resume

Also covers Wing/Squadron archive endpoints.
"""
import pytest
from tests.conftest import login


def _sysadmin(client):
    return login(client, "SYSADMIN2026")


def _sqn_admin(client):
    return login(client, "ADMIN703")


def _nat_admin(client):
    return login(client, "ADMINNATIONAL")


def _wing_admin(client):
    return login(client, "ADMIN7WG")


def _enable_maintenance(client, sysadmin_hdr):
    r = client.post("/api/system/maintenance/enable", json={
        "confirm": "ENABLE MAINTENANCE",
        "message": "Test maintenance window",
    }, headers=sysadmin_hdr)
    assert r.status_code == 200, r.text


def _disable_maintenance(client, sysadmin_hdr):
    r = client.post("/api/system/maintenance/disable", headers=sysadmin_hdr)
    assert r.status_code == 200, r.text


# ─────────────────────────────────────────────────────────────
# Maintenance mode: write blocking
# ─────────────────────────────────────────────────────────────

def test_normal_user_write_blocked_during_maintenance(client):
    """sqn_admin POST is blocked with 503 when maintenance mode is on."""
    sysadmin_hdr = _sysadmin(client)
    sqn_hdr = _sqn_admin(client)
    _enable_maintenance(client, sysadmin_hdr)
    try:
        r = client.post("/api/curriculum", json={
            "title": "Test during maint", "phase_code": "PO", "level": "proficiency",
            "duration_minutes": 60,
        }, headers=sqn_hdr)
        assert r.status_code == 503
        assert r.json()["error"] == "maintenance_mode"
        assert "maintenance" in r.json()["message"].lower()
    finally:
        _disable_maintenance(client, sysadmin_hdr)


def test_normal_user_put_blocked_during_maintenance(client):
    """PUT is blocked during maintenance."""
    sysadmin_hdr = _sysadmin(client)
    sqn_hdr = _sqn_admin(client)
    _enable_maintenance(client, sysadmin_hdr)
    try:
        r = client.put("/api/accounts/some-id", json={"display_name": "x"}, headers=sqn_hdr)
        assert r.status_code == 503
    finally:
        _disable_maintenance(client, sysadmin_hdr)


def test_normal_user_patch_blocked_during_maintenance(client):
    """PATCH is blocked during maintenance."""
    sysadmin_hdr = _sysadmin(client)
    sqn_hdr = _sqn_admin(client)
    _enable_maintenance(client, sysadmin_hdr)
    try:
        r = client.patch("/api/accounts/some-id", json={"active_status": True}, headers=sqn_hdr)
        assert r.status_code == 503
    finally:
        _disable_maintenance(client, sysadmin_hdr)


def test_normal_user_delete_blocked_during_maintenance(client):
    """DELETE is blocked during maintenance."""
    sysadmin_hdr = _sysadmin(client)
    sqn_hdr = _sqn_admin(client)
    _enable_maintenance(client, sysadmin_hdr)
    try:
        r = client.delete("/api/training/curriculum/some-id", headers=sqn_hdr)
        assert r.status_code == 503
    finally:
        _disable_maintenance(client, sysadmin_hdr)


def test_national_admin_write_blocked_during_maintenance(client):
    """national_admin is also blocked from writes during maintenance."""
    sysadmin_hdr = _sysadmin(client)
    nat_hdr = _nat_admin(client)
    _enable_maintenance(client, sysadmin_hdr)
    try:
        r = client.post("/api/wings", json={
            "code": "MAINT99", "name": "Maint Test Wing"
        }, headers=nat_hdr)
        assert r.status_code == 503
    finally:
        _disable_maintenance(client, sysadmin_hdr)


def test_unauthenticated_write_blocked_during_maintenance(client):
    """Unauthenticated POST is blocked during maintenance.
    Clears the client cookie jar so no session leaks from the sysadmin login call.
    """
    sysadmin_hdr = _sysadmin(client)
    _enable_maintenance(client, sysadmin_hdr)
    try:
        # Clear the session cookie stored from the sysadmin login so the
        # request is truly unauthenticated (no cookie, no Authorization header).
        client.cookies.clear()
        r = client.post("/api/curriculum", json={"title": "x"})
        assert r.status_code == 503
        assert r.json()["error"] == "maintenance_mode"
    finally:
        # Re-login as sysadmin to disable maintenance (previous cookie was cleared)
        new_hdr = login(client, "SYSADMIN2026")
        _disable_maintenance(client, new_hdr)


# ─────────────────────────────────────────────────────────────
# Maintenance mode: reads remain accessible
# ─────────────────────────────────────────────────────────────

def test_get_requests_work_during_maintenance(client):
    """GETs are not blocked by maintenance mode (returns anything except 503)."""
    sysadmin_hdr = _sysadmin(client)
    sqn_hdr = _sqn_admin(client)
    _enable_maintenance(client, sysadmin_hdr)
    try:
        r = client.get("/api/health", headers=sqn_hdr)
        assert r.status_code != 503, "Health check should not be blocked by maintenance"
        r = client.get("/api/curriculum", headers=sqn_hdr)
        assert r.status_code != 503, "GET curriculum should not be blocked by maintenance"
        r = client.get("/api/auth/me", headers=sqn_hdr)
        assert r.status_code != 503, "/auth/me should not be blocked by maintenance"
    finally:
        _disable_maintenance(client, sysadmin_hdr)


def test_login_works_during_maintenance(client):
    """Login endpoint is exempt from maintenance gate."""
    sysadmin_hdr = _sysadmin(client)
    _enable_maintenance(client, sysadmin_hdr)
    try:
        r = client.post("/api/auth/login", json={"code": "ADMIN703"})
        assert r.status_code == 200
    finally:
        _disable_maintenance(client, sysadmin_hdr)


# ─────────────────────────────────────────────────────────────
# system_admin writes allowed during maintenance
# ─────────────────────────────────────────────────────────────

def test_sysadmin_can_disable_maintenance_during_maintenance(client):
    """system_admin can POST to disable maintenance while maintenance is on."""
    sysadmin_hdr = _sysadmin(client)
    _enable_maintenance(client, sysadmin_hdr)
    r = client.post("/api/system/maintenance/disable", headers=sysadmin_hdr)
    assert r.status_code == 200
    assert r.json()["enabled"] is False


def test_sysadmin_can_create_backup_during_maintenance(client):
    """system_admin write operations work during maintenance."""
    sysadmin_hdr = _sysadmin(client)
    _enable_maintenance(client, sysadmin_hdr)
    try:
        r = client.post("/api/system/backups", headers=sysadmin_hdr)
        assert r.status_code == 200
    finally:
        _disable_maintenance(client, sysadmin_hdr)


# ─────────────────────────────────────────────────────────────
# After disabling maintenance, writes resume
# ─────────────────────────────────────────────────────────────

def test_writes_resume_after_maintenance_disabled(client):
    """Normal writes work again after maintenance mode is disabled."""
    sysadmin_hdr = _sysadmin(client)
    sqn_hdr = _sqn_admin(client)
    _enable_maintenance(client, sysadmin_hdr)
    r_blocked = client.post("/api/auth/login", json={"code": "ADMIN703"})
    # login is exempt but let's verify writes are blocked first
    r_write = client.post("/api/curriculum", json={
        "title": "Post-maint", "phase_code": "PO", "level": "proficiency", "duration_minutes": 60
    }, headers=sqn_hdr)
    assert r_write.status_code == 503
    _disable_maintenance(client, sysadmin_hdr)
    # Now write should proceed (may fail 422 on body but not 503)
    r_after = client.post("/api/curriculum", json={
        "title": "Post-maint", "phase_code": "PO", "level": "proficiency", "duration_minutes": 60
    }, headers=sqn_hdr)
    assert r_after.status_code != 503, "Writes should not return 503 after maintenance disabled"


# ─────────────────────────────────────────────────────────────
# Wing archive
# ─────────────────────────────────────────────────────────────

def test_create_and_archive_wing(client):
    """system_admin can create and then archive a Wing."""
    nat_hdr = _nat_admin(client)
    sysadmin_hdr = _sysadmin(client)
    # Create wing via nat_admin (nat_admin can create wings)
    r = client.post("/api/wings", json={"code": "ARCHTEST", "name": "Archive Test Wing"}, headers=nat_hdr)
    assert r.status_code == 200, r.text
    wing_id = r.json()["wing_id"]
    # Archive via system_admin
    r2 = client.post(f"/api/wings/{wing_id}/archive", headers=sysadmin_hdr)
    assert r2.status_code == 200
    assert r2.json()["archived"] is True


def test_cannot_archive_wing_with_active_squadrons(client):
    """Wing with active squadrons cannot be archived."""
    nat_hdr = _nat_admin(client)
    # Get a wing that has squadrons
    r = client.get("/api/wings", headers=nat_hdr)
    wings = r.json()
    if not wings:
        pytest.skip("No wings in test DB")
    wing_id = wings[0]["wing_id"]
    sysadmin_hdr = _sysadmin(client)
    r2 = client.post(f"/api/wings/{wing_id}/archive", headers=sysadmin_hdr)
    # Should fail because it has active squadrons
    assert r2.status_code == 409
    assert r2.json()["detail"]["error"] == "has_active_squadrons"


def test_archive_wing_forbidden_sqn(client):
    sqn_hdr = _sqn_admin(client)
    r = client.post("/api/wings/some-id/archive", headers=sqn_hdr)
    assert r.status_code == 403


# ─────────────────────────────────────────────────────────────
# Squadron archive
# ─────────────────────────────────────────────────────────────

def test_create_and_archive_squadron(client):
    """nat_admin can create and archive a Squadron."""
    nat_hdr = _nat_admin(client)
    sysadmin_hdr = _sysadmin(client)
    # Get a wing to place the squadron under
    r = client.get("/api/wings", headers=nat_hdr)
    wings = r.json()
    if not wings:
        pytest.skip("No wings in test DB")
    wing_id = wings[0]["wing_id"]
    # Create
    r2 = client.post("/api/squadrons", json={
        "wing_id": wing_id, "code": "ARCHTST2", "name": "Archive Test SQN",
        "unit_type": "standard_squadron",
    }, headers=nat_hdr)
    assert r2.status_code == 200, r2.text
    sqn_id = r2.json()["squadron_id"]
    # Archive
    r3 = client.post(f"/api/squadrons/{sqn_id}/archive", headers=sysadmin_hdr)
    assert r3.status_code == 200
    assert r3.json()["archived"] is True
    # Archived unit not in active list
    r4 = client.get("/api/squadrons", headers=nat_hdr)
    ids = [s["squadron_id"] for s in r4.json()]
    assert sqn_id not in ids


def test_archive_squadron_forbidden_wing_other(client):
    """wing_admin cannot archive a squadron in a different wing."""
    wing_hdr = _wing_admin(client)
    nat_hdr = _nat_admin(client)
    # Find a squadron not in 7WG
    r = client.get("/api/wings", headers=nat_hdr)
    other_wing_id = None
    for w in r.json():
        if "7WG" not in (w.get("code") or ""):
            other_wing_id = w["wing_id"]
            break
    if not other_wing_id:
        pytest.skip("Only one wing in test DB")
    r2 = client.get("/api/squadrons", headers=nat_hdr)
    other_sqn = next((s for s in r2.json() if s["wing_id"] == other_wing_id), None)
    if not other_sqn:
        pytest.skip("No squadrons in other wing")
    r3 = client.post(f"/api/squadrons/{other_sqn['squadron_id']}/archive", headers=wing_hdr)
    assert r3.status_code == 403


def test_archive_squadron_forbidden_sqn_general(client):
    sqn_hdr = login(client, "703SQN2026")
    r = client.post("/api/squadrons/some-id/archive", headers=sqn_hdr)
    assert r.status_code == 403
