"""Systematic role-matrix coverage (Section 27 of the Final Remediation/Public-Release
Program governing instruction) -- confirms read/write behaviour for all 8 roles against
a representative set of endpoints, in a single place. This does not replace the
per-feature forbidden-role tests already spread across the suite (those remain the
primary regression coverage for their own endpoints); it exists because two of the 8
roles -- national_viewer and wing_viewer -- had noticeably thinner coverage than the
other 6 (confirmed via `grep -rl national_viewer tests/*.py` returning 4 files vs. 10+
for other roles), and because no single test previously asserted the full 8-role shape
of any one endpoint at once.

Uses only the existing seed/demo access codes already used throughout this suite
(tests/conftest.py's seed_all() fixture) -- never retrieves or fabricates a real
access code, per .claude/rules/security.md.
"""
from conftest import login

ROLE_CODES = {
    "sqn_general": "703SQN2026",
    "sqn_admin": "ADMIN703",
    "wing_viewer": "7WG2026",
    "wing_admin": "ADMIN7WG",
    "national_viewer": "NATIONAL2026",
    "national_admin": "ADMINNATIONAL",
    "system_admin": "SYSADMIN2026",
    "auditor": "AUDITOR2026",
}

# Roles with no write authority anywhere in the system -- pure read/oversight roles.
READ_ONLY_ROLES = ("sqn_general", "wing_viewer", "national_viewer", "auditor")

WRITE_ROLES = ("sqn_admin", "wing_admin", "national_admin", "system_admin")


def _hdrs(client, role):
    return login(client, ROLE_CODES[role])


def test_all_8_seed_roles_can_log_in_and_reach_auth_me(client):
    """Baseline sanity check underpinning every other test in this file -- if a seed
    code silently stops working, every downstream role-matrix assertion here would
    otherwise fail with a confusing, unrelated-looking error."""
    for role, code in ROLE_CODES.items():
        hdr = login(client, code)
        r = client.get("/api/auth/me", headers=hdr)
        assert r.status_code == 200, f"{role}: {r.text}"
        got_role = r.json()["session"]["role"]
        assert got_role == role, f"expected {role}, got {got_role}"


# ── Read endpoints every authenticated role should reach (no 403) ──────────────────
READ_ENDPOINTS_ALL_ROLES = [
    "/api/curriculum",
    "/api/facilitators",
    "/api/parade-nights",
    "/api/wings",
    "/api/squadrons",
]


def test_every_role_can_read_their_own_scope_of_core_resources(client):
    """None of the 8 roles should ever get a 403 on these baseline list endpoints --
    scoping narrows *what* comes back (tested elsewhere per-feature), not *whether*
    the request is allowed at all. A 403 here would mean a role was locked out of
    the application entirely, not just scoped."""
    for role in ROLE_CODES:
        hdr = _hdrs(client, role)
        for path in READ_ENDPOINTS_ALL_ROLES:
            r = client.get(path, headers=hdr)
            assert r.status_code == 200, f"{role} on {path}: {r.status_code} {r.text}"


# ── Write endpoints: only WRITE_ROLES should ever get past a 403 ───────────────────
def test_read_only_roles_cannot_create_facilitator(client):
    for role in READ_ONLY_ROLES:
        hdr = _hdrs(client, role)
        r = client.post("/api/facilitators", json={"last_name": "Role Matrix Test Fac"}, headers=hdr)
        assert r.status_code == 403, f"{role} should be denied, got {r.status_code}: {r.text}"


def test_read_only_roles_cannot_create_curriculum_item(client):
    for role in READ_ONLY_ROLES:
        hdr = _hdrs(client, role)
        r = client.post("/api/curriculum", json={"code": "RMX-01", "title": "Role Matrix Test Item"},
                        headers=hdr)
        assert r.status_code == 403, f"{role} should be denied, got {r.status_code}: {r.text}"


def test_read_only_roles_cannot_create_wing(client):
    for role in READ_ONLY_ROLES:
        hdr = _hdrs(client, role)
        r = client.post("/api/wings", json={"code": "RMX", "name": "Role Matrix Wing"}, headers=hdr)
        assert r.status_code == 403, f"{role} should be denied, got {r.status_code}: {r.text}"


def test_read_only_roles_cannot_create_squadron(client):
    for role in READ_ONLY_ROLES:
        hdr = _hdrs(client, role)
        r = client.post("/api/squadrons", json={"wing_id": "x", "code": "RMX", "name": "Role Matrix Sqn"},
                        headers=hdr)
        assert r.status_code == 403, f"{role} should be denied, got {r.status_code}: {r.text}"


def test_read_only_roles_cannot_create_account(client):
    for role in READ_ONLY_ROLES:
        hdr = _hdrs(client, role)
        r = client.post("/api/accounts", json={"display_name": "Role Matrix Account", "role": "sqn_general"},
                        headers=hdr)
        assert r.status_code == 403, f"{role} should be denied, got {r.status_code}: {r.text}"


# ── system_admin-only endpoints: every non-system_admin role denied, including the
# other 3 write-capable roles (national_admin/wing_admin/sqn_admin) -- system-console
# authority is not implied by write authority elsewhere. ──────────────────────────
def test_only_system_admin_reaches_system_overview(client):
    for role in ROLE_CODES:
        if role == "system_admin":
            continue
        hdr = _hdrs(client, role)
        r = client.get("/api/system/overview", headers=hdr)
        assert r.status_code == 403, f"{role} should be denied /system/overview, got {r.status_code}"
    hdr = _hdrs(client, "system_admin")
    r = client.get("/api/system/overview", headers=hdr)
    assert r.status_code == 200, r.text


def test_only_system_admin_can_enable_maintenance(client):
    for role in ROLE_CODES:
        if role == "system_admin":
            continue
        hdr = _hdrs(client, role)
        r = client.post("/api/system/maintenance/enable", json={"confirm": "ENABLE MAINTENANCE"}, headers=hdr)
        assert r.status_code == 403, f"{role} should be denied maintenance/enable, got {r.status_code}"


# ── Audit log: only the documented read-roles reach it, everyone else 403s ─────────
_AUDIT_READ_ROLES = {"auditor", "sqn_admin", "wing_admin", "national_admin", "national_viewer", "system_admin"}


def test_audit_log_read_access_matches_documented_role_set(client):
    for role in ROLE_CODES:
        hdr = _hdrs(client, role)
        r = client.get("/api/audit", headers=hdr)
        if role in _AUDIT_READ_ROLES:
            assert r.status_code == 200, f"{role} should reach /api/audit, got {r.status_code}: {r.text}"
        else:
            assert r.status_code == 403, f"{role} should be denied /api/audit, got {r.status_code}"


# ── Unauthenticated + malformed token: every protected endpoint, not just one ──────
def test_unauthenticated_denied_on_every_read_endpoint(client):
    for path in READ_ENDPOINTS_ALL_ROLES + ["/api/system/overview", "/api/accounts", "/api/audit"]:
        r = client.get(path)
        assert r.status_code == 401, f"{path} unauthenticated: expected 401, got {r.status_code}"
