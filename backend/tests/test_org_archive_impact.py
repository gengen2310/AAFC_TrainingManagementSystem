"""Phase 2.4: GET /api/wings/{id}/archive-impact and
GET /api/squadrons/{id}/archive-impact -- read-only pre-checks for the
existing archive_wing/archive_squadron endpoints (organisations.py).

Covers: hard_blockers matching the real archive endpoint's own block
condition exactly (can_archive must never disagree with what POST .../archive
actually does), soft_warnings for things archiving does not itself block on,
role/scope permission checks, and unauthenticated access.
"""
from datetime import date, timedelta

from tests.conftest import login


def _sysadmin(client):
    return login(client, "SYSADMIN2026")


def _wing_admin_7wg(client):
    return login(client, "ADMIN7WG")


def _sqn_admin_703(client):
    return login(client, "ADMIN703")


def _auditor(client):
    return login(client, "AUDITOR2026")


def _make_wing(client, hdr, code):
    r = client.post("/api/wings", json={"code": code, "name": code + " Test Wing"}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["wing_id"]


def _make_sqn(client, hdr, wing_id, code):
    r = client.post("/api/squadrons", json={"wing_id": wing_id, "code": code, "name": code + " Test Unit"}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["squadron_id"]


# ─────────────────────────────────────────────────────────────
# Wing archive-impact
# ─────────────────────────────────────────────────────────────

def test_wing_archive_impact_can_archive_true_for_wing_with_no_active_squadrons(client):
    hdr = _sysadmin(client)
    wing_id = _make_wing(client, hdr, "IMWG1")
    r = client.get(f"/api/wings/{wing_id}/archive-impact", headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["can_archive"] is True
    assert d["hard_blockers"] == []
    assert d["subordinate_orgs"] == []


def test_wing_archive_impact_blocked_by_active_squadron(client):
    hdr = _sysadmin(client)
    wing_id = _make_wing(client, hdr, "IMWG2")
    sqn_id = _make_sqn(client, hdr, wing_id, "IM201")
    r = client.get(f"/api/wings/{wing_id}/archive-impact", headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["can_archive"] is False
    assert d["hard_blockers"][0]["type"] == "active_squadrons"
    assert d["hard_blockers"][0]["count"] == 1
    assert d["subordinate_orgs"][0]["squadron_id"] == sqn_id


def test_wing_archive_impact_can_archive_matches_actual_archive_result(client):
    """The whole point of this endpoint: its can_archive prediction must never
    disagree with what the real POST .../archive endpoint does."""
    hdr = _sysadmin(client)

    clean_wing_id = _make_wing(client, hdr, "IMWG3")
    impact = client.get(f"/api/wings/{clean_wing_id}/archive-impact", headers=hdr).json()
    assert impact["can_archive"] is True
    archived = client.post(f"/api/wings/{clean_wing_id}/archive", headers=hdr)
    assert archived.status_code == 200, archived.text

    blocked_wing_id = _make_wing(client, hdr, "IMWG4")
    _make_sqn(client, hdr, blocked_wing_id, "IM401")
    impact2 = client.get(f"/api/wings/{blocked_wing_id}/archive-impact", headers=hdr).json()
    assert impact2["can_archive"] is False
    archived2 = client.post(f"/api/wings/{blocked_wing_id}/archive", headers=hdr)
    assert archived2.status_code == 409


def test_wing_archive_impact_surfaces_active_wing_accounts_as_soft_warning(client):
    hdr = _sysadmin(client)
    wing_id = _make_wing(client, hdr, "IMWG5")
    acct = client.post("/api/accounts", json={"display_name": "Wing Acct Holder",
                                              "role": "wing_admin", "wing_id": wing_id}, headers=hdr)
    assert acct.status_code == 200, acct.text

    r = client.get(f"/api/wings/{wing_id}/archive-impact", headers=hdr)
    d = r.json()
    # A wing account is not a hard blocker today (archive_wing only checks
    # active squadrons) -- it must appear as a soft warning instead, since
    # the impact endpoint must not disagree with the real archive endpoint.
    assert d["can_archive"] is True
    warning_types = {w["type"] for w in d["soft_warnings"]}
    assert "active_wing_accounts" in warning_types
    assert any(a["user_id"] == acct.json()["user_id"] for a in d["active_accounts"])


def test_wing_archive_impact_forbidden_for_wing_admin(client):
    hdr = _wing_admin_7wg(client)
    sysadm_hdr = _sysadmin(client)
    wing_id = _make_wing(client, sysadm_hdr, "IMWG6")
    r = client.get(f"/api/wings/{wing_id}/archive-impact", headers=hdr)
    assert r.status_code == 403


def test_wing_archive_impact_unauthenticated(client):
    hdr = _sysadmin(client)
    wing_id = _make_wing(client, hdr, "IMWG7")
    client.cookies.clear()  # login() leaves the session-cookie fallback set on this client
    r = client.get(f"/api/wings/{wing_id}/archive-impact")
    assert r.status_code == 401


# ─────────────────────────────────────────────────────────────
# Squadron archive-impact
# ─────────────────────────────────────────────────────────────

def test_squadron_archive_impact_can_archive_true_for_clean_squadron(client):
    hdr = _sysadmin(client)
    wing_id = _make_wing(client, hdr, "IMSW1")
    sqn_id = _make_sqn(client, hdr, wing_id, "IMS101")
    r = client.get(f"/api/squadrons/{sqn_id}/archive-impact", headers=hdr)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["can_archive"] is True
    assert d["hard_blockers"] == []


def test_squadron_archive_impact_blocked_by_active_accounts(client):
    hdr = _sysadmin(client)
    wing_id = _make_wing(client, hdr, "IMSW2")
    sqn_id = _make_sqn(client, hdr, wing_id, "IMS201")
    acct = client.post("/api/accounts", json={"display_name": "Sqn Acct Holder",
                                              "role": "sqn_general", "squadron_id": sqn_id}, headers=hdr)
    assert acct.status_code == 200, acct.text

    r = client.get(f"/api/squadrons/{sqn_id}/archive-impact", headers=hdr)
    d = r.json()
    assert d["can_archive"] is False
    assert d["hard_blockers"][0]["type"] == "active_accounts"
    assert d["hard_blockers"][0]["count"] == 1
    assert any(a["user_id"] == acct.json()["user_id"] for a in d["active_accounts"])


def test_squadron_archive_impact_can_archive_matches_actual_archive_result(client):
    hdr = _sysadmin(client)
    wing_id = _make_wing(client, hdr, "IMSW3")

    clean_sqn_id = _make_sqn(client, hdr, wing_id, "IMS301")
    impact = client.get(f"/api/squadrons/{clean_sqn_id}/archive-impact", headers=hdr).json()
    assert impact["can_archive"] is True
    archived = client.post(f"/api/squadrons/{clean_sqn_id}/archive", headers=hdr)
    assert archived.status_code == 200, archived.text

    blocked_sqn_id = _make_sqn(client, hdr, wing_id, "IMS401")
    client.post("/api/accounts", json={"display_name": "Blocker Acct",
                                       "role": "sqn_general", "squadron_id": blocked_sqn_id}, headers=hdr)
    impact2 = client.get(f"/api/squadrons/{blocked_sqn_id}/archive-impact", headers=hdr).json()
    assert impact2["can_archive"] is False
    archived2 = client.post(f"/api/squadrons/{blocked_sqn_id}/archive", headers=hdr)
    assert archived2.status_code == 409


def test_squadron_archive_impact_surfaces_future_parade_night_soft_warning(client):
    from app.database import SessionLocal
    from app.models import ParadeNight

    hdr = _sysadmin(client)
    wing_id = _make_wing(client, hdr, "IMSW5")
    sqn_id = _make_sqn(client, hdr, wing_id, "IMS501")

    future_date = (date.today() + timedelta(days=30)).isoformat()
    db = SessionLocal()
    try:
        pn = ParadeNight(squadron_id=sqn_id, wing_id=wing_id, training_year=date.today().year,
                         date=future_date, term="1", session_count=3)
        db.add(pn); db.commit()
    finally:
        db.close()

    r = client.get(f"/api/squadrons/{sqn_id}/archive-impact", headers=hdr)
    d = r.json()
    assert d["can_archive"] is True  # a future parade night is a soft warning, never a hard blocker
    warning_types = {w["type"] for w in d["soft_warnings"]}
    assert "future_parade_nights" in warning_types
    assert d["historical_record_counts"]["future_parade_nights"] == 1


def test_squadron_archive_impact_wing_admin_out_of_scope_for_other_wing(client):
    sysadm_hdr = _sysadmin(client)
    other_wing_id = _make_wing(client, sysadm_hdr, "IMSW6")
    other_sqn_id = _make_sqn(client, sysadm_hdr, other_wing_id, "IMS601")

    wing_admin_hdr = _wing_admin_7wg(client)  # 7WG admin, not this new wing
    r = client.get(f"/api/squadrons/{other_sqn_id}/archive-impact", headers=wing_admin_hdr)
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "out_of_scope"


def test_squadron_archive_impact_wing_admin_allowed_for_own_wing(client):
    sysadm_hdr = _sysadmin(client)
    wing_id = client.get("/api/wings", headers=sysadm_hdr).json()
    wing_7wg_id = next(w["wing_id"] for w in wing_id if w["code"] == "7WG")
    sqn_id = _make_sqn(client, sysadm_hdr, wing_7wg_id, "IMS701")

    wing_admin_hdr = _wing_admin_7wg(client)
    r = client.get(f"/api/squadrons/{sqn_id}/archive-impact", headers=wing_admin_hdr)
    assert r.status_code == 200, r.text


def test_squadron_archive_impact_forbidden_for_sqn_admin(client):
    hdr = _sqn_admin_703(client)
    sysadm_hdr = _sysadmin(client)
    wing_id = _make_wing(client, sysadm_hdr, "IMSW8")
    sqn_id = _make_sqn(client, sysadm_hdr, wing_id, "IMS801")
    r = client.get(f"/api/squadrons/{sqn_id}/archive-impact", headers=hdr)
    assert r.status_code == 403


def test_squadron_archive_impact_forbidden_for_auditor(client):
    hdr = _auditor(client)
    sysadm_hdr = _sysadmin(client)
    wing_id = _make_wing(client, sysadm_hdr, "IMSW9")
    sqn_id = _make_sqn(client, sysadm_hdr, wing_id, "IMS901")
    r = client.get(f"/api/squadrons/{sqn_id}/archive-impact", headers=hdr)
    assert r.status_code == 403


def test_squadron_archive_impact_unauthenticated(client):
    hdr = _sysadmin(client)
    wing_id = _make_wing(client, hdr, "IMSWA")
    sqn_id = _make_sqn(client, hdr, wing_id, "IMSA01")
    client.cookies.clear()  # login() leaves the session-cookie fallback set on this client
    r = client.get(f"/api/squadrons/{sqn_id}/archive-impact")
    assert r.status_code == 401
