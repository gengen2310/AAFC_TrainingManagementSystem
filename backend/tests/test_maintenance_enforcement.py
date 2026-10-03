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
    # drain_seconds=0 bypasses the PENDING phase and enters LOCKED immediately,
    # which is what write-blocking tests require. MAINT-02 added the PENDING phase;
    # tests that specifically test PENDING are in test_system_admin.py.
    r = client.post("/api/system/maintenance/enable", json={
        "confirm": "ENABLE MAINTENANCE",
        "message": "Test maintenance window",
        "drain_seconds": 0,
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
    """Login is not blocked by default maintenance (block_logins=False)."""
    sysadmin_hdr = _sysadmin(client)
    _enable_maintenance(client, sysadmin_hdr)
    try:
        # Clear cookie so the login is genuinely unauthenticated (not sysadmin bypass)
        client.cookies.clear()
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
    """wing_admin cannot archive a squadron in a different wing.

    Previously skipped whenever the test DB held one Wing -- which is always --
    so this cross-Wing check never ran. It now creates its own second Wing and
    Squadron, and also proves the same wing_admin CAN archive in its own Wing
    (so the 403 is the scope rule, not a blanket denial).
    """
    import uuid
    wing_hdr = _wing_admin(client)
    sysadmin_hdr = _sysadmin(client)
    tag = uuid.uuid4().hex[:5].upper()
    w = client.post("/api/wings", json={"code": f"X{tag}", "name": f"Other Wing {tag}",
                                        "timezone": "Australia/Perth"}, headers=sysadmin_hdr)
    assert w.status_code in (200, 201), w.text
    other = client.post("/api/squadrons", json={"wing_id": w.json()["wing_id"], "code": f"9{tag}",
                                                "name": f"Other Sqn {tag}"}, headers=sysadmin_hdr)
    assert other.status_code == 200, other.text
    r = client.post(f"/api/squadrons/{other.json()['squadron_id']}/archive", headers=wing_hdr)
    assert r.status_code == 403, r.text

    me = client.get("/api/auth/me", headers=wing_hdr).json()["session"]
    own = client.post("/api/squadrons", json={"wing_id": me["wing_id"], "code": f"8{tag}",
                                              "name": f"Own Sqn {tag}"}, headers=sysadmin_hdr)
    assert own.status_code == 200, own.text
    r = client.post(f"/api/squadrons/{own.json()['squadron_id']}/archive", headers=wing_hdr)
    assert r.status_code == 200, r.text


def test_archive_squadron_forbidden_sqn_general(client):
    sqn_hdr = login(client, "703SQN2026")
    r = client.post("/api/squadrons/some-id/archive", headers=sqn_hdr)
    assert r.status_code == 403


# ─────────────────────────────────────────────────────────────
# block_reads flag (Gap #18)
# ─────────────────────────────────────────────────────────────

def _enable_maintenance_opts(client, sysadmin_hdr, block_reads=False, block_logins=False):
    r = client.post("/api/system/maintenance/enable", json={
        "confirm": "ENABLE MAINTENANCE",
        "message": "Test maintenance window",
        "block_reads": block_reads,
        "block_logins": block_logins,
        "drain_seconds": 0,  # MAINT-02: skip PENDING phase so tests enter LOCKED immediately
    }, headers=sysadmin_hdr)
    assert r.status_code == 200, r.text


def test_block_reads_false_allows_get_during_maintenance(client):
    """Default: block_reads=False means GET requests succeed even during maintenance."""
    sysadmin_hdr = _sysadmin(client)
    sqn_hdr = _sqn_admin(client)
    _enable_maintenance(client, sysadmin_hdr)
    try:
        r = client.get("/api/curriculum", headers=sqn_hdr)
        assert r.status_code != 503
    finally:
        _disable_maintenance(client, sysadmin_hdr)


def test_block_reads_true_blocks_get_during_maintenance(client):
    """block_reads=True causes GET /api/* to return 503 for non-system_admin."""
    sysadmin_hdr = _sysadmin(client)
    sqn_hdr = _sqn_admin(client)
    _enable_maintenance_opts(client, sysadmin_hdr, block_reads=True)
    try:
        r = client.get("/api/curriculum", headers=sqn_hdr)
        assert r.status_code == 503
        assert r.json()["error"] == "maintenance_mode"
    finally:
        _disable_maintenance(client, sysadmin_hdr)


def test_block_reads_true_still_allows_health(client):
    """Health endpoints are always exempt even when block_reads=True."""
    sysadmin_hdr = _sysadmin(client)
    _enable_maintenance_opts(client, sysadmin_hdr, block_reads=True)
    try:
        r = client.get("/api/health")
        assert r.status_code == 200
    finally:
        _disable_maintenance(client, sysadmin_hdr)


def test_block_reads_true_still_allows_auth_me(client):
    """GET /api/auth/me must always be accessible so users see maintenance status."""
    sysadmin_hdr = _sysadmin(client)
    sqn_hdr = _sqn_admin(client)
    _enable_maintenance_opts(client, sysadmin_hdr, block_reads=True)
    try:
        r = client.get("/api/auth/me", headers=sqn_hdr)
        assert r.status_code != 503
    finally:
        _disable_maintenance(client, sysadmin_hdr)


def test_block_reads_true_sysadmin_can_still_read(client):
    """system_admin bypasses block_reads and can still issue GET requests."""
    sysadmin_hdr = _sysadmin(client)
    _enable_maintenance_opts(client, sysadmin_hdr, block_reads=True)
    try:
        r = client.get("/api/curriculum", headers=sysadmin_hdr)
        assert r.status_code != 503
    finally:
        _disable_maintenance(client, sysadmin_hdr)


# ─────────────────────────────────────────────────────────────
# block_logins flag (Gap #18)
# ─────────────────────────────────────────────────────────────

def test_block_logins_false_allows_login_during_maintenance(client):
    """Default: block_logins=False means /api/auth/login succeeds during maintenance."""
    sysadmin_hdr = _sysadmin(client)
    _enable_maintenance(client, sysadmin_hdr)
    try:
        r = client.post("/api/auth/login", json={"code": "ADMIN703"})
        assert r.status_code == 200
    finally:
        _disable_maintenance(client, sysadmin_hdr)


def test_block_logins_true_blocks_login_during_maintenance(client):
    """block_logins=True causes /api/auth/login to return 503 for non-SA logins (MAINT-03).

    Previously enforced by middleware; now enforced inside the login handler after role is known
    (so system_admin can always log back in). Response body uses HTTPException wrapping:
    {"detail": {"error": "maintenance_mode", ...}}.
    """
    sysadmin_hdr = _sysadmin(client)
    _enable_maintenance_opts(client, sysadmin_hdr, block_logins=True)
    try:
        client.cookies.clear()
        r = client.post("/api/auth/login", json={"code": "ADMIN703"})
        assert r.status_code == 503
        body = r.json()
        # Handler raises HTTPException → {"detail": {"error": ...}}
        err = body.get("error") or body.get("detail", {}).get("error")
        assert err == "maintenance_mode", f"Unexpected body: {body}"
    finally:
        # Use Bearer token from sysadmin_hdr — don't re-login while block_logins is True.
        _disable_maintenance(client, sysadmin_hdr)


def test_block_logins_true_logout_me_refresh_still_accessible(client):
    """block_logins=True must not block already-authenticated users' session endpoints."""
    sysadmin_hdr = _sysadmin(client)
    sqn_hdr = _sqn_admin(client)
    _enable_maintenance_opts(client, sysadmin_hdr, block_logins=True)
    try:
        r = client.get("/api/auth/me", headers=sqn_hdr)
        assert r.status_code != 503
        r2 = client.post("/api/auth/refresh", headers=sqn_hdr)
        assert r2.status_code != 503
    finally:
        _disable_maintenance(client, sysadmin_hdr)


def test_maintenance_get_returns_block_flags(client):
    """GET /api/system/maintenance now includes block_reads and block_logins fields."""
    sysadmin_hdr = _sysadmin(client)
    _enable_maintenance_opts(client, sysadmin_hdr, block_reads=True, block_logins=True)
    try:
        r = client.get("/api/system/maintenance", headers=sysadmin_hdr)
        assert r.status_code == 200
        d = r.json()
        assert d["block_reads"] is True
        assert d["block_logins"] is True
    finally:
        _disable_maintenance(client, sysadmin_hdr)


def test_disable_maintenance_clears_block_flags(client):
    """Disabling maintenance resets block_reads and block_logins to False."""
    sysadmin_hdr = _sysadmin(client)
    _enable_maintenance_opts(client, sysadmin_hdr, block_reads=True, block_logins=True)
    _disable_maintenance(client, sysadmin_hdr)
    r = client.get("/api/system/maintenance", headers=sysadmin_hdr)
    d = r.json()
    assert d["enabled"] is False
    assert d["block_reads"] is False
    assert d["block_logins"] is False


def test_expired_maintenance_cache_refresh_is_single_flight(monkeypatch):
    """Concurrent requests at one cache boundary must cause one DB checkout.

    This is the regression guard for the pool-stampede failure mode: fresh
    reads stay lock-free, while every waiter after expiry observes the first
    thread's refreshed cache instead of opening another SessionLocal.
    """
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor
    import app.main as main_module

    snapshot = dict(main_module._maint_cache)
    session_opens = 0
    count_lock = threading.Lock()
    worker_count = 16
    barrier = threading.Barrier(worker_count)

    class FakeSession:
        def __enter__(self):
            # Keep the elected refresher busy briefly so the other workers all
            # reach the refresh boundary while it owns the single-flight lock.
            time.sleep(0.05)
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, model, key):
            return None

    def fake_session_local():
        nonlocal session_opens
        with count_lock:
            session_opens += 1
        return FakeSession()

    monkeypatch.setattr(main_module, "SessionLocal", fake_session_local)
    main_module._maint_cache.update({
        "active": False,
        "msg": "",
        "block_reads": False,
        "block_logins": False,
        "pending_until": None,
        "expires": 0.0,
    })

    def read_at_boundary():
        barrier.wait(timeout=5)
        return main_module._maintenance_active()

    try:
        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            results = list(pool.map(lambda _: read_at_boundary(), range(worker_count)))
        assert session_opens == 1
        assert all(result[0] is False for result in results)
        assert all(result[4] == "normal" for result in results)
    finally:
        main_module._maint_cache.clear()
        main_module._maint_cache.update(snapshot)
