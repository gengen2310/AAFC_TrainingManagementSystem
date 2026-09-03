"""Release qualification: 8-role API permission matrix.

Confirms that the remediated build (fix/v17-1-pre-release-remediation) enforces
the correct access matrix across all 8 roles for the key endpoint categories.

Run against the remediated build only; any unexpected result is a release defect —
fix the product, not the expectation.

Roles tested:
  sqn_general   (703SQN2026) — read-own-squadron only
  sqn_admin     (ADMIN703)   — write-own-squadron
  wing_viewer   (7WG2026)    — read-own-wing only
  wing_admin    (ADMIN7WG)   — write-any-squadron-in-wing (via proxy)
  national_viewer (NATIONAL2026) — read-national only
  national_admin (ADMINNATIONAL) — write-national scope
  system_admin  (SYSADMIN2026)  — all access
  auditor       (AUDITOR2026)   — read-only audit access
"""
import pytest
from tests.conftest import login


# ── Fixtures ──────────────────────────────────────────────────────────────────

ROLES = {
    "sqn_general":    "703SQN2026",
    "sqn_admin":      "ADMIN703",
    "wing_viewer":    "7WG2026",
    "wing_admin":     "ADMIN7WG",
    "national_viewer":"NATIONAL2026",
    "national_admin": "ADMINNATIONAL",
    "system_admin":   "SYSADMIN2026",
    "auditor":        "AUDITOR2026",
}


def hdr(client, role_name):
    return login(client, ROLES[role_name])


# ── Auth ───────────────────────────────────────────────────────────────────────

def test_all_roles_can_authenticate(client):
    """Every seeded role must be able to obtain a token."""
    for role, code in ROLES.items():
        h = login(client, code)
        r = client.get("/api/auth/me", headers=h)
        assert r.status_code == 200, f"{role} cannot authenticate: {r.text}"
        assert r.json()["session"]["role"] == role, f"{role}: role mismatch in /auth/me"


# ── Read endpoints ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("role", list(ROLES))
def test_parade_nights_readable_by_all_roles(client, role):
    """All authenticated roles must be able to read parade-nights for their scope."""
    r = client.get("/api/parade-nights", headers=hdr(client, role))
    assert r.status_code == 200, f"{role} cannot read parade-nights: {r.text}"


@pytest.mark.parametrize("role", list(ROLES))
def test_curriculum_readable_by_all_roles(client, role):
    r = client.get("/api/curriculum", headers=hdr(client, role))
    assert r.status_code == 200, f"{role} cannot read curriculum: {r.text}"


@pytest.mark.parametrize("role", list(ROLES))
def test_facilitators_readable_by_all_roles(client, role):
    r = client.get("/api/facilitators", headers=hdr(client, role))
    assert r.status_code == 200, f"{role} cannot read facilitators: {r.text}"


_AUDIT_READ_ROLES = frozenset({
    "auditor", "sqn_admin", "wing_admin", "national_admin", "national_viewer", "system_admin"
})
_AUDIT_BLOCKED_ROLES = frozenset({"sqn_general", "wing_viewer"})


@pytest.mark.parametrize("role", list(ROLES))
def test_audit_log_access_by_role(client, role):
    """Audit log (/api/audit) enforces scoped read: admin/viewer/auditor allowed; sqn_general and wing_viewer blocked."""
    r = client.get("/api/audit", headers=hdr(client, role))
    if role in _AUDIT_READ_ROLES:
        assert r.status_code == 200, f"{role} should be able to read audit log: {r.text}"
    else:
        assert r.status_code in (403, 401), (
            f"{role} should be blocked from audit log, got {r.status_code}"
        )


# ── Write endpoints ────────────────────────────────────────────────────────────

WRITE_ONLY_ROLES = {"sqn_admin", "wing_admin", "national_admin", "system_admin"}
READ_ONLY_ROLES = set(ROLES) - WRITE_ONLY_ROLES


@pytest.mark.parametrize("role", sorted(READ_ONLY_ROLES))
def test_parade_night_creation_blocked_for_read_only_roles(client, role):
    """Read-only roles must not be able to create parade nights."""
    r = client.post("/api/parade-nights",
                    json={"date": "2042-11-01", "term": "T1"},
                    headers=hdr(client, role))
    assert r.status_code in (403, 401), (
        f"{role} should be blocked from creating parade nights, got {r.status_code}: {r.text}"
    )


@pytest.mark.parametrize("role", sorted(WRITE_ONLY_ROLES - {"wing_admin", "national_admin", "system_admin"}))
def test_sqn_admin_can_create_parade_night(client, role):
    """sqn_admin must be able to create parade nights for their own squadron."""
    r = client.post("/api/parade-nights",
                    json={"date": "2042-11-08", "term": "T1"},
                    headers=hdr(client, role))
    assert r.status_code in (200, 201), (
        f"{role} should be able to create parade nights, got {r.status_code}: {r.text}"
    )


def test_unauthenticated_request_rejected(client):
    """Requests without auth must be rejected."""
    r = client.get("/api/parade-nights")
    assert r.status_code == 401, f"Unauthenticated request returned {r.status_code}"


# ── System Admin exclusive endpoints ──────────────────────────────────────────

NON_SYSTEM_ROLES = [r for r in ROLES if r != "system_admin"]


@pytest.mark.parametrize("role", NON_SYSTEM_ROLES)
def test_system_console_blocked_for_non_sysadmin(client, role):
    """System console overview must reject all non-system_admin roles."""
    r = client.get("/api/system/overview", headers=hdr(client, role))
    assert r.status_code in (403, 401), (
        f"{role} should be blocked from system console, got {r.status_code}"
    )


def test_system_admin_can_read_system_overview(client):
    r = client.get("/api/system/overview", headers=hdr(client, "system_admin"))
    assert r.status_code == 200, f"system_admin blocked from own endpoint: {r.text}"


# ── Session CREATE cross-squadron tenancy (Task 2 regression) ─────────────────

def test_session_create_rejects_cross_squadron_facilitator_rbac(client):
    """Verify Task 2 fix is present: a cross-squadron facilitator must be rejected at CREATE."""
    a703 = login(client, "ADMIN703")
    a705 = login(client, "ADMIN705")

    fac = client.post("/api/facilitators",
                      json={"last_name": "RbacForeign705", "current_rank": "CIV"},
                      headers=a705)
    assert fac.status_code in (200, 201), fac.text
    fid = fac.json()["facilitator_id"]

    pn = client.post("/api/parade-nights", json={"date": "2042-12-05", "term": "T1"}, headers=a703)
    assert pn.status_code == 200, pn.text
    pnid = pn.json()["parade_night_id"]

    r = client.post("/api/sessions",
                    json={"parade_night_id": pnid, "period_number": 1,
                          "cadet_group": "senior", "facilitator_id": fid},
                    headers=a703)
    assert r.status_code in (200, 400, 403, 422), r.text
    if r.status_code in (200,):
        sid = r.json().get("session_id") or r.json().get("id")
        row = client.get(f"/api/planning/sessions/{sid}", headers=a703).json()
        assert row.get("facilitator_id") != fid, \
            "Task 2 regression: cross-squadron facilitator stored on CREATE"


# ── Curriculum import squadron check (Task 3 regression) ──────────────────────

def test_import_rejects_nonexistent_squadron_rbac(client):
    """Verify Task 3 fix: curriculum import with nonexistent squadron_id returns 404."""
    import uuid
    hdr_nat = hdr(client, "national_admin")
    r = client.post("/api/curriculum/import",
                    json={"owning_level": "national",
                          "squadron_id": str(uuid.uuid4()),
                          "items": [{"code": "RBAC-T3", "title": "RBAC T3 item",
                                     "phase": "E. Senior", "element": "Fitness",
                                     "duration_minutes": 60, "part_number": 1}]},
                    headers=hdr_nat)
    assert r.status_code == 404, (
        f"Task 3 regression: nonexistent squadron_id returned {r.status_code} not 404"
    )
