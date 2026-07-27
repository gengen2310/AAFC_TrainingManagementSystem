"""
Gap #10 — Report Catalogue: shape and RBAC tests for all report endpoints.

Squadron-level reports: summary, readiness, curriculum-coverage, facilitator-load, not-delivered
Wing-level reports:     wing-overview, wing-not-delivered, wing-phase-coverage, wing-capability,
                        wing-cancellation-trend
National-level reports: national-overview, national-capability
"""
import pytest
from conftest import login

# ── helpers ──────────────────────────────────────────────────────────────────

SQN_GENERAL  = "703SQN2026"   # sqn_general
SQN_ADMIN    = "ADMIN703"     # sqn_admin
WING_VIEWER  = "7WG2026"      # wing_viewer
WING_ADMIN   = "ADMIN7WG"     # wing_admin
NAT_ADMIN    = "ADMINNATIONAL"  # national_admin
NAT_VIEWER   = "NATIONAL2026"   # national_viewer
SYSADMIN     = "SYSADMIN2026"   # system_admin
AUDITOR      = "AUDITOR2026"    # auditor


# ── Facilitator-load ─────────────────────────────────────────────────────────

def test_facilitator_load_shape_sqn_admin(client):
    h = login(client, SQN_ADMIN)
    r = client.get("/api/reports/facilitator-load", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "title" in body and "facilitators" in body and "decision" in body
    for fac in body["facilitators"]:
        assert "name" in fac and "sessions" in fac and "risk" in fac
        assert fac["risk"] in ("ok", "high", "overloaded")
    assert body["decision"] in ("no_action", "action_required")


def test_facilitator_load_sqn_general_can_access(client):
    h = login(client, SQN_GENERAL)
    r = client.get("/api/reports/facilitator-load", headers=h)
    assert r.status_code == 200, r.text


def test_facilitator_load_unauthenticated(client):
    r = client.get("/api/reports/facilitator-load")
    assert r.status_code == 401


# ── Wing-not-delivered ────────────────────────────────────────────────────────

def test_wing_not_delivered_shape_wing_admin(client):
    h = login(client, WING_ADMIN)
    r = client.get("/api/reports/wing-not-delivered", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "title" in body and "squadrons" in body
    assert "total_not_delivered" in body and "decision" in body
    assert isinstance(body["squadrons"], list)
    for sq in body["squadrons"]:
        assert "squadron_id" in sq and "not_delivered_count" in sq
        assert sq["not_delivered_count"] >= 1
        assert isinstance(sq["sessions"], list)


def test_wing_not_delivered_accessible_to_wing_viewer(client):
    h = login(client, WING_VIEWER)
    r = client.get("/api/reports/wing-not-delivered", headers=h)
    assert r.status_code == 200, r.text


def test_wing_not_delivered_accessible_to_national_admin(client):
    h = login(client, NAT_ADMIN)
    r = client.get("/api/reports/wing-not-delivered", headers=h)
    assert r.status_code == 200, r.text


def test_wing_not_delivered_403_for_sqn_admin(client):
    h = login(client, SQN_ADMIN)
    r = client.get("/api/reports/wing-not-delivered", headers=h)
    assert r.status_code == 403, r.text


def test_wing_not_delivered_403_for_sqn_general(client):
    h = login(client, SQN_GENERAL)
    r = client.get("/api/reports/wing-not-delivered", headers=h)
    assert r.status_code == 403, r.text


def test_wing_not_delivered_unauthenticated(client):
    r = client.get("/api/reports/wing-not-delivered")
    assert r.status_code == 401


# ── Wing-capability ───────────────────────────────────────────────────────────

def test_wing_capability_shape_wing_admin(client):
    h = login(client, WING_ADMIN)
    r = client.get("/api/reports/wing-capability", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "subjects" in body and "squadrons" in body
    assert "wing_avg" in body and "capability_gaps" in body
    assert isinstance(body["subjects"], list) and len(body["subjects"]) > 0
    for sq in body["squadrons"]:
        assert "squadron_id" in sq and "facilitator_count" in sq
        assert "subject_facilitators" in sq and "subject_sessions" in sq


def test_wing_capability_accessible_to_auditor(client):
    h = login(client, AUDITOR)
    r = client.get("/api/reports/wing-capability", headers=h)
    assert r.status_code == 200, r.text


def test_wing_capability_403_for_sqn_admin(client):
    h = login(client, SQN_ADMIN)
    r = client.get("/api/reports/wing-capability", headers=h)
    assert r.status_code == 403, r.text


def test_wing_capability_403_for_sqn_general(client):
    h = login(client, SQN_GENERAL)
    r = client.get("/api/reports/wing-capability", headers=h)
    assert r.status_code == 403, r.text


def test_wing_capability_unauthenticated(client):
    r = client.get("/api/reports/wing-capability")
    assert r.status_code == 401


# ── National-capability ───────────────────────────────────────────────────────

def test_national_capability_shape_national_admin(client):
    h = login(client, NAT_ADMIN)
    r = client.get("/api/reports/national-capability", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "subjects" in body and "wings" in body
    assert isinstance(body["wings"], list)
    for w in body["wings"]:
        assert "wing_id" in w and "code" in w and "facilitator_total" in w
        assert "subject_none_sqns" in w and "subject_distribution" in w


def test_national_capability_accessible_to_nat_viewer(client):
    h = login(client, NAT_VIEWER)
    r = client.get("/api/reports/national-capability", headers=h)
    assert r.status_code == 200, r.text


def test_national_capability_accessible_to_sysadmin(client):
    h = login(client, SYSADMIN)
    r = client.get("/api/reports/national-capability", headers=h)
    assert r.status_code == 200, r.text


def test_national_capability_403_for_wing_admin(client):
    h = login(client, WING_ADMIN)
    r = client.get("/api/reports/national-capability", headers=h)
    assert r.status_code == 403, r.text


def test_national_capability_403_for_sqn_admin(client):
    h = login(client, SQN_ADMIN)
    r = client.get("/api/reports/national-capability", headers=h)
    assert r.status_code == 403, r.text


def test_national_capability_403_for_sqn_general(client):
    h = login(client, SQN_GENERAL)
    r = client.get("/api/reports/national-capability", headers=h)
    assert r.status_code == 403, r.text


def test_national_capability_unauthenticated(client):
    r = client.get("/api/reports/national-capability")
    assert r.status_code == 401


# ── RBAC: sqn_general access to squadron-level reports ───────────────────────

@pytest.mark.parametrize("path", [
    "/api/reports/summary",
    "/api/reports/readiness",
    "/api/reports/curriculum-coverage",
    "/api/reports/facilitator-load",
    "/api/reports/not-delivered",
])
def test_sqn_general_can_access_squadron_reports(client, path):
    h = login(client, SQN_GENERAL)
    r = client.get(path, headers=h)
    assert r.status_code == 200, f"{path} returned {r.status_code}: {r.text}"


@pytest.mark.parametrize("path", [
    "/api/reports/wing-overview",
    "/api/reports/wing-not-delivered",
    "/api/reports/wing-phase-coverage",
    "/api/reports/wing-capability",
    "/api/reports/wing-cancellation-trend",
])
def test_sqn_general_403_for_wing_reports(client, path):
    h = login(client, SQN_GENERAL)
    r = client.get(path, headers=h)
    assert r.status_code == 403, f"{path} should be 403 for sqn_general, got {r.status_code}"


@pytest.mark.parametrize("path", [
    "/api/reports/wing-overview",
    "/api/reports/wing-not-delivered",
    "/api/reports/wing-phase-coverage",
    "/api/reports/wing-capability",
    "/api/reports/wing-cancellation-trend",
])
def test_sqn_admin_403_for_wing_reports(client, path):
    h = login(client, SQN_ADMIN)
    r = client.get(path, headers=h)
    assert r.status_code == 403, f"{path} should be 403 for sqn_admin, got {r.status_code}"


@pytest.mark.parametrize("path", [
    "/api/reports/national-overview",
    "/api/reports/national-capability",
])
def test_wing_admin_403_for_national_reports(client, path):
    h = login(client, WING_ADMIN)
    r = client.get(path, headers=h)
    assert r.status_code == 403, f"{path} should be 403 for wing_admin, got {r.status_code}"


# ── Wing-cancellation-trend ───────────────────────────────────────────────────

def test_wing_cancellation_trend_shape_wing_admin(client):
    h = login(client, WING_ADMIN)
    r = client.get("/api/reports/wing-cancellation-trend", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "title" in body and body["title"] == "Cancelled / rescheduled trend"
    assert "squadrons" in body and isinstance(body["squadrons"], list)
    assert "total_cancelled_sessions" in body and "total_cancelled_nights" in body
    assert "decision" in body and body["decision"] in ("no_action", "action_required")
    for sq in body["squadrons"]:
        assert "squadron_id" in sq and "cancelled_sessions" in sq and "cancelled_nights" in sq
        assert isinstance(sq["reasons"], list)
        for reason in sq["reasons"]:
            assert "reason" in reason and "count" in reason and reason["count"] >= 1


def test_wing_cancellation_trend_accessible_to_national_viewer(client):
    h = login(client, NAT_VIEWER)
    r = client.get("/api/reports/wing-cancellation-trend", headers=h)
    assert r.status_code == 200, r.text


def test_wing_cancellation_trend_unauthenticated(client):
    r = client.get("/api/reports/wing-cancellation-trend")
    assert r.status_code == 401


# ── Facilitator list — upcoming_leave enrichment (Gap 4) ─────────────────────

def test_facilitators_list_includes_upcoming_leave_field(client):
    h = login(client, SQN_ADMIN)
    r = client.get("/api/facilitators", headers=h)
    assert r.status_code == 200, r.text
    facs = r.json()
    assert isinstance(facs, list)
    # upcoming_leave must be present on every facilitator (empty list when no leave booked)
    for f in facs:
        assert "upcoming_leave" in f, f"facilitator_id {f.get('facilitator_id')} missing upcoming_leave"
        assert isinstance(f["upcoming_leave"], list)


def test_facilitators_upcoming_leave_shape_when_present(client):
    """Each leave record must have start_date, end_date, reason fields."""
    h = login(client, SQN_ADMIN)
    r = client.get("/api/facilitators", headers=h)
    assert r.status_code == 200, r.text
    for f in r.json():
        for lv in f["upcoming_leave"]:
            assert "start_date" in lv and "end_date" in lv and "reason" in lv
