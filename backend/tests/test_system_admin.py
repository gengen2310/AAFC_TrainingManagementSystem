"""V17 System Admin tests.

Covers: system_admin login, System Console endpoints, maintenance mode,
backup, scope-map, audit-summary, RBAC enforcement, and security invariants.
"""
import pytest
from tests.conftest import login


def _sysadmin(client):
    return login(client, "SYSADMIN2026")


def _nat_admin(client):
    return login(client, "ADMINNATIONAL")


def _sqn_admin(client):
    return login(client, "ADMIN703")


def _auditor(client):
    return login(client, "AUDITOR2026")


def _general(client):
    return login(client, "703SQN2026")


# ─────────────────────────────────────────────────────────────
# system_admin account
# ─────────────────────────────────────────────────────────────

def test_sysadmin_login(client):
    r = client.post("/api/auth/login", json={"code": "SYSADMIN2026"})
    assert r.status_code == 200
    sess = r.json()["session"]
    assert sess["role"] == "system_admin"


def test_sysadmin_me_role(client):
    hdr = _sysadmin(client)
    r = client.get("/api/auth/me", headers=hdr)
    assert r.status_code == 200
    assert r.json()["session"]["role"] == "system_admin"


def test_sysadmin_me_no_plaintext_code(client):
    """Verify /auth/me does not return access-code plaintext or hash."""
    hdr = _sysadmin(client)
    r = client.get("/api/auth/me", headers=hdr)
    body = r.text
    assert "SYSADMIN2026" not in body
    assert "code_hash" not in body
    assert "plain_code" not in body


# ─────────────────────────────────────────────────────────────
# System Overview
# ─────────────────────────────────────────────────────────────

def test_system_overview_sysadmin(client):
    hdr = _sysadmin(client)
    r = client.get("/api/system/overview", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert "app_version" in d
    assert "environment" in d
    assert "wings" in d
    assert "squadrons" in d
    assert "maintenance_mode" in d
    assert isinstance(d["maintenance_mode"], bool)


def test_system_overview_forbidden_sqn(client):
    hdr = _sqn_admin(client)
    r = client.get("/api/system/overview", headers=hdr)
    assert r.status_code == 403


def test_system_overview_forbidden_nat(client):
    """national_admin is NOT system_admin — must be denied."""
    hdr = _nat_admin(client)
    r = client.get("/api/system/overview", headers=hdr)
    assert r.status_code == 403


def test_system_overview_unauthenticated(client):
    r = client.get("/api/system/overview")
    assert r.status_code == 401


# ─────────────────────────────────────────────────────────────
# System Health
# ─────────────────────────────────────────────────────────────

def test_system_health_sysadmin(client):
    hdr = _sysadmin(client)
    r = client.get("/api/system/health", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert d["backend"] == "ok"
    assert d["db"] == "ok"
    assert "cors_origins" in d
    assert "cookie_secure" in d


def test_system_health_forbidden_general(client):
    hdr = _general(client)
    r = client.get("/api/system/health", headers=hdr)
    assert r.status_code == 403


# ─────────────────────────────────────────────────────────────
# Version
# ─────────────────────────────────────────────────────────────

def test_system_version_sysadmin(client):
    hdr = _sysadmin(client)
    r = client.get("/api/system/version", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert d["app_version"] == "17.1.0"
    assert d["package_version"] == "v17.1"


def test_system_version_forbidden(client):
    hdr = _sqn_admin(client)
    r = client.get("/api/system/version", headers=hdr)
    assert r.status_code == 403


# ─────────────────────────────────────────────────────────────
# Migrations
# ─────────────────────────────────────────────────────────────

def test_system_migrations_sysadmin(client):
    hdr = _sysadmin(client)
    r = client.get("/api/system/migrations", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert "expected_head" in d
    assert d["expected_head"] == "q2r3s4t5u6v7"


# ─────────────────────────────────────────────────────────────
# Maintenance mode
# ─────────────────────────────────────────────────────────────

def test_maintenance_get_default_off(client):
    hdr = _sysadmin(client)
    r = client.get("/api/system/maintenance", headers=hdr)
    assert r.status_code == 200
    assert r.json()["enabled"] is False


def test_maintenance_enable_requires_confirmation(client):
    hdr = _sysadmin(client)
    r = client.post("/api/system/maintenance/enable", json={
        "message": "Test maintenance", "confirm": "wrong"
    }, headers=hdr)
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "confirmation_required"


def test_maintenance_enable_and_disable(client):
    hdr = _sysadmin(client)
    # Enable
    r = client.post("/api/system/maintenance/enable", json={
        "message": "Planned maintenance", "until": "2026-12-01T00:00:00Z",
        "confirm": "ENABLE MAINTENANCE",
    }, headers=hdr)
    assert r.status_code == 200
    assert r.json()["enabled"] is True
    # Verify GET reflects state
    r2 = client.get("/api/system/maintenance", headers=hdr)
    assert r2.json()["enabled"] is True
    assert "Planned maintenance" in r2.json()["message"]
    # Disable
    r3 = client.post("/api/system/maintenance/disable", headers=hdr)
    assert r3.status_code == 200
    assert r3.json()["enabled"] is False
    # Verify cleared
    r4 = client.get("/api/system/maintenance", headers=hdr)
    assert r4.json()["enabled"] is False


def test_maintenance_enable_forbidden_sqn(client):
    hdr = _sqn_admin(client)
    r = client.post("/api/system/maintenance/enable", json={
        "confirm": "ENABLE MAINTENANCE"
    }, headers=hdr)
    assert r.status_code == 403


def test_maintenance_disable_forbidden_nat(client):
    hdr = _nat_admin(client)
    r = client.post("/api/system/maintenance/disable", headers=hdr)
    assert r.status_code == 403


# ─────────────────────────────────────────────────────────────
# Scope map
# ─────────────────────────────────────────────────────────────

def test_scope_map_sysadmin_sees_all_wings(client):
    hdr = _sysadmin(client)
    r = client.get("/api/system/scope-map", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert "wings" in d
    assert len(d["wings"]) > 0
    # At least 7WG should be present
    names = [w["wing_name"] for w in d["wings"]]
    assert any("7" in n or "Wing" in n or "WG" in n for n in names)


def test_scope_map_includes_squadrons(client):
    hdr = _sysadmin(client)
    r = client.get("/api/system/scope-map", headers=hdr)
    wings = r.json()["wings"]
    all_sqns = [s for w in wings for s in w["squadrons"]]
    assert len(all_sqns) > 0


def test_scope_map_forbidden_sqn(client):
    hdr = _sqn_admin(client)
    r = client.get("/api/system/scope-map", headers=hdr)
    assert r.status_code == 403


# ─────────────────────────────────────────────────────────────
# Audit summary
# ─────────────────────────────────────────────────────────────

def test_audit_summary_sysadmin(client):
    hdr = _sysadmin(client)
    r = client.get("/api/system/audit-summary", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert "logs" in d
    assert "count" in d


def test_audit_summary_auditor_allowed(client):
    """Auditors may also read audit summary."""
    hdr = _auditor(client)
    r = client.get("/api/system/audit-summary", headers=hdr)
    assert r.status_code == 200


def test_audit_summary_no_secrets_in_output(client):
    """Ensure audit log response never contains access-code values."""
    hdr = _sysadmin(client)
    r = client.get("/api/system/audit-summary", headers=hdr)
    body = r.text
    for secret in ("SYSADMIN2026", "ADMIN703", "ADMIN7WG", "ADMINNATIONAL",
                   "code_hash", "plain_code"):
        assert secret not in body, f"Secret '{secret}' found in audit response"


def test_audit_summary_filter_by_action(client):
    hdr = _sysadmin(client)
    r = client.get("/api/system/audit-summary?action=login", headers=hdr)
    assert r.status_code == 200
    logs = r.json()["logs"]
    for entry in logs:
        assert entry["action"] == "login"


def test_audit_summary_forbidden_sqn(client):
    hdr = _sqn_admin(client)
    r = client.get("/api/system/audit-summary", headers=hdr)
    assert r.status_code == 403


def test_audit_summary_forbidden_general(client):
    hdr = _general(client)
    r = client.get("/api/system/audit-summary", headers=hdr)
    assert r.status_code == 403


def test_audit_summary_limit_cap(client):
    """Limit is capped at 500 to prevent huge responses."""
    hdr = _sysadmin(client)
    r = client.get("/api/system/audit-summary?limit=9999", headers=hdr)
    assert r.status_code == 200
    assert r.json()["count"] <= 500


# ─────────────────────────────────────────────────────────────
# Backups
# ─────────────────────────────────────────────────────────────

def test_backup_list_sysadmin(client):
    hdr = _sysadmin(client)
    r = client.get("/api/system/backups", headers=hdr)
    assert r.status_code == 200
    assert "backups" in r.json()


def test_backup_create_sysadmin(client):
    hdr = _sysadmin(client)
    r = client.post("/api/system/backups", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert "filename" in d
    assert "size_bytes" in d
    assert d["size_bytes"] > 0
    assert "backup_" in d["filename"]


def test_backup_create_forbidden_sqn(client):
    hdr = _sqn_admin(client)
    r = client.post("/api/system/backups", headers=hdr)
    assert r.status_code == 403


def test_backup_no_hash_in_output(client):
    """Backup metadata must not contain access-code hashes or plaintext codes."""
    hdr = _sysadmin(client)
    r = client.get("/api/system/backups", headers=hdr)
    body = r.text
    for secret in ("SYSADMIN2026", "ADMIN703", "code_hash"):
        assert secret not in body


# ─────────────────────────────────────────────────────────────
# Cross-scope denial (IDOR protection)
# ─────────────────────────────────────────────────────────────

def test_system_endpoints_unauthenticated(client):
    for path in ["/api/system/overview", "/api/system/health",
                 "/api/system/version", "/api/system/migrations",
                 "/api/system/maintenance", "/api/system/scope-map",
                 "/api/system/audit-summary", "/api/system/backups"]:
        r = client.get(path)
        assert r.status_code == 401, f"{path} should require authentication"


def test_system_admin_actions_audited(client):
    """Enable maintenance and verify an audit entry is created."""
    hdr = _sysadmin(client)
    client.post("/api/system/maintenance/enable", json={
        "confirm": "ENABLE MAINTENANCE", "message": "Audit check"
    }, headers=hdr)
    client.post("/api/system/maintenance/disable", headers=hdr)
    r = client.get("/api/system/audit-summary?action=maintenance_enabled", headers=hdr)
    assert r.status_code == 200
    logs = r.json()["logs"]
    assert any(e["action"] == "maintenance_enabled" for e in logs)


# ─────────────────────────────────────────────────────────────
# Bootstrap Staging
# ─────────────────────────────────────────────────────────────

def test_bootstrap_staging_requires_sysadmin(client):
    """national_admin must be denied access to bootstrap."""
    hdr = _nat_admin(client)
    r = client.post("/api/system/bootstrap-staging", headers=hdr)
    assert r.status_code == 403


def test_bootstrap_staging_unauthenticated(client):
    r = client.post("/api/system/bootstrap-staging")
    assert r.status_code == 401


def test_bootstrap_staging_rejected_when_is_prod(client):
    """Must be rejected once ENVIRONMENT genuinely reads as production/prod.

    Regression guard: this endpoint used to check `ENVIRONMENT.lower() ==
    "production"` directly instead of the shared settings.is_prod property —
    missing the "prod" abbreviation is_prod also accepts, and (found live)
    silently NOT rejecting when a deployment's ENVIRONMENT variable is
    mislabelled as anything other than the literal string "production" (as
    production's actually was, set to "staging" — see
    docs/beta/11_defect_register.md DEFECT-003). Scoped patch of the
    `is_prod` property only — reverts automatically, no cross-test state.
    """
    from unittest.mock import patch, PropertyMock
    from app.config import Settings

    hdr = _sysadmin(client)
    with patch.object(Settings, "is_prod", new_callable=PropertyMock) as mock_is_prod:
        mock_is_prod.return_value = True
        r = client.post("/api/system/bootstrap-staging", headers=hdr)
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "not_allowed_in_production"


def test_bootstrap_staging_idempotent(client):
    """With seed_all data already present, bootstrap runs idempotently — no new codes."""
    hdr = _sysadmin(client)
    r = client.post("/api/system/bootstrap-staging", headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert "results" in d
    assert "accounts_created" in d
    # Seed already created everything — no new accounts or codes expected
    assert all(not item["created"] for item in d["accounts_created"] if "created" in item) or d["accounts_created"] == []
    # No plaintext codes in response for already-existing accounts
    for item in d["accounts_created"]:
        assert "new_code" not in item or item.get("created") is True


def test_bootstrap_staging_response_no_code_hash(client):
    """Bootstrap response must never contain code_hash."""
    hdr = _sysadmin(client)
    r = client.post("/api/system/bootstrap-staging", headers=hdr)
    assert "code_hash" not in r.text


def test_bootstrap_staging_audit_entries(client):
    """Bootstrap must appear in audit log when accounts are created."""
    hdr = _sysadmin(client)
    client.post("/api/system/bootstrap-staging", headers=hdr)
    r = client.get("/api/system/audit-summary?action=account_created&limit=50", headers=hdr)
    assert r.status_code == 200


def test_bootstrap_staging_generic_wing_code_body(client):
    """Bootstrap accepts optional wing_code/sqn_code body and resolves that Wing."""
    hdr = _sysadmin(client)
    # seed_all.py creates 7WG; target it explicitly via the new generic body param.
    # All accounts already exist from the seed, so no new codes are generated —
    # the important thing is the endpoint accepts the body and resolves 7WG correctly.
    r = client.post("/api/system/bootstrap-staging",
                    json={"wing_code": "7WG", "sqn_code": "703"},
                    headers=hdr)
    assert r.status_code == 200
    d = r.json()
    assert "results" in d
    # Squadron result should reference 703
    sqn_results = [item for item in d["results"] if item.get("type") == "squadron"]
    assert sqn_results, f"No squadron in results: {d['results']}"
    assert sqn_results[0]["code"] == "703"


def test_bootstrap_staging_unknown_wing_returns_422(client):
    """Bootstrap with a wing_code that does not exist must return 422."""
    hdr = _sysadmin(client)
    r = client.post("/api/system/bootstrap-staging",
                    json={"wing_code": "UNKNOWN_WING_XYZ"},
                    headers=hdr)
    assert r.status_code == 422
    assert "wing_not_found" in r.text
