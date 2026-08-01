"""Phase 2: NATHQ/Wing/Squadron Activities inheritance.

Covers: National/Wing/Squadron visibility inheritance, cross-wing isolation,
the IDOR regression (a Squadron admin must never be able to write a Wing/
National-owned Activity by ID), the permission matrix for create/edit/archive
at each owning level, archived filtering, and backward compatibility of the
existing single-squadron GET /api/activities shape.
"""
import pytest
from tests.conftest import login


def _sysadmin(client):
    return login(client, "SYSADMIN2026")


def _nat_admin(client):
    return login(client, "ADMINNATIONAL")


def _wing_admin_7wg(client):
    return login(client, "ADMIN7WG")


def _sqn_admin_703(client):
    return login(client, "ADMIN703")


def _wing_id_by_code(client, hdr, code):
    r = client.get("/api/wings", headers=hdr)
    for w in r.json():
        if w["code"] == code:
            return w["wing_id"]
    raise AssertionError(f"wing {code} not found")


def _sqn_id_by_code(client, hdr, code):
    r = client.get("/api/squadrons", headers=hdr)
    for s in r.json():
        if s["code"] == code:
            return s["squadron_id"]
    raise AssertionError(f"squadron {code} not found")


def _make_second_wing_with_admin(client, sysadmin_hdr, wing_code, sqn_code, admin_code):
    """Returns (wing_id, sqn_id, wing_admin_hdr). Wing-owned activities must be
    created via the returned wing_admin_hdr, not sysadmin_hdr directly --
    system_admin/national_admin writing a Wing-owned Activity correctly
    requires Delegated Intervention under this feature's permission design
    (require_can_write_activity), which no test setup step should route
    around."""
    r = client.post("/api/wings", json={"code": wing_code, "name": f"{wing_code} Test Wing"}, headers=sysadmin_hdr)
    assert r.status_code == 200, r.text
    wing_id = r.json()["wing_id"]
    r2 = client.post("/api/squadrons", json={"wing_id": wing_id, "code": sqn_code, "name": f"{sqn_code} Test Sqn"},
                     headers=sysadmin_hdr)
    assert r2.status_code == 200, r2.text
    sqn_id = r2.json()["squadron_id"]
    r3 = client.post("/api/accounts", json={"display_name": f"{wing_code} Admin", "role": "wing_admin",
                                            "wing_id": wing_id, "new_code": admin_code}, headers=sysadmin_hdr)
    assert r3.status_code == 200, r3.text
    wing_admin_hdr = login(client, admin_code)
    return wing_id, sqn_id, wing_admin_hdr


# ─────────────────────────────────────────────────────────────
# Inheritance visibility
# ─────────────────────────────────────────────────────────────

def test_national_activity_visible_at_wing_and_squadron_scope_without_republish(client):
    hdr = _sysadmin(client)
    r = client.post("/api/activities/national",
                    json={"activity_name": "INH01 National Camp", "date_start": "2026-09-01"}, headers=hdr)
    assert r.status_code == 200, r.text
    aid = r.json()["activity_id"]

    wing_id = _wing_id_by_code(client, hdr, "7WG")
    sqn_id = _sqn_id_by_code(client, hdr, "703")

    wing_items = client.get(f"/api/activities?scope_type=wing&scope_id={wing_id}", headers=hdr).json()["items"]
    assert any(i["activity_id"] == aid and i["is_inherited"] for i in wing_items)

    sqn_items = client.get(f"/api/activities?scope_type=squadron&scope_id={sqn_id}", headers=hdr).json()["items"]
    match = next(i for i in sqn_items if i["activity_id"] == aid)
    assert match["is_inherited"] is True
    # sysadmin has unconditional write authority over national-owned rows
    # (require_can_write_activity: owning_level=="national" -> role check only,
    # no scope/intervention gate) -- read_only reflects the VIEWER's own write
    # capability, not a generic "is this row editable from here" flag, so this
    # is correctly False for a system_admin even though a sqn_admin viewing
    # the same row would see read_only=True.
    assert match["read_only"] is False


def test_wing_activity_visible_to_own_squadrons_not_other_wings(client):
    sysadmin_hdr = _sysadmin(client)
    wing_id, sqn_id, wing_admin_hdr = _make_second_wing_with_admin(client, sysadmin_hdr, "ACTW1", "ACT01", "ACTWADM01")
    r = client.post("/api/activities/wing", json={"wing_id": wing_id, "activity_name": "INH02 Wing Exercise",
                                                   "date_start": "2026-09-05"}, headers=wing_admin_hdr)
    assert r.status_code == 200, r.text
    aid = r.json()["activity_id"]

    own_sqn_items = client.get(f"/api/activities?scope_type=squadron&scope_id={sqn_id}", headers=sysadmin_hdr).json()["items"]
    assert any(i["activity_id"] == aid for i in own_sqn_items)

    other_sqn_id = _sqn_id_by_code(client, sysadmin_hdr, "703")
    other_sqn_items = client.get(f"/api/activities?scope_type=squadron&scope_id={other_sqn_id}", headers=sysadmin_hdr).json()["items"]
    assert not any(i["activity_id"] == aid for i in other_sqn_items)


def test_squadron_activity_stays_local_not_visible_at_wing_scope(client):
    hdr = _sqn_admin_703(client)
    r = client.post("/api/activities", json={"activity_name": "INH03 Local Parade Prep",
                                              "date_start": "2026-09-06"}, headers=hdr)
    assert r.status_code == 200, r.text
    aid = r.json()["activity_id"]

    sysadmin_hdr = _sysadmin(client)
    wing_id = _wing_id_by_code(client, sysadmin_hdr, "7WG")
    wing_items = client.get(f"/api/activities?scope_type=wing&scope_id={wing_id}", headers=sysadmin_hdr).json()["items"]
    assert not any(i["activity_id"] == aid for i in wing_items)


def test_national_scope_sees_only_national_activities_not_wing_or_squadron(client):
    hdr = _sysadmin(client)
    client.post("/api/activities/wing", json={"wing_id": _wing_id_by_code(client, hdr, "7WG"),
                                               "activity_name": "INH04 Wing Only", "date_start": "2026-09-07"},
               headers=hdr)
    national_items = client.get("/api/activities?scope_type=national", headers=hdr).json()["items"]
    assert not any(i["activity_name"] == "INH04 Wing Only" for i in national_items)


# ─────────────────────────────────────────────────────────────
# IDOR regression -- a Squadron admin must never write a Wing/National row
# ─────────────────────────────────────────────────────────────

def test_squadron_admin_cannot_patch_national_activity_by_id(client):
    sysadmin_hdr = _sysadmin(client)
    aid = client.post("/api/activities/national", json={"activity_name": "IDOR01", "date_start": "2026-09-08"},
                      headers=sysadmin_hdr).json()["activity_id"]
    sqn_hdr = _sqn_admin_703(client)
    r = client.patch(f"/api/activities/{aid}", json={"activity_name": "HACKED"}, headers=sqn_hdr)
    assert r.status_code == 403
    unchanged = client.get(f"/api/activities/{aid}", headers=sysadmin_hdr).json()
    assert unchanged["activity_name"] == "IDOR01"


def test_squadron_admin_cannot_delete_national_activity_by_id(client):
    sysadmin_hdr = _sysadmin(client)
    aid = client.post("/api/activities/national", json={"activity_name": "IDOR02", "date_start": "2026-09-09"},
                      headers=sysadmin_hdr).json()["activity_id"]
    sqn_hdr = _sqn_admin_703(client)
    r = client.delete(f"/api/activities/{aid}", headers=sqn_hdr)
    assert r.status_code == 403


def test_squadron_admin_cannot_patch_other_wings_activity_by_id(client):
    sysadmin_hdr = _sysadmin(client)
    wing_id, _, wing_admin_hdr = _make_second_wing_with_admin(client, sysadmin_hdr, "ACTW2", "ACT02", "ACTWADM02")
    aid = client.post("/api/activities/wing", json={"wing_id": wing_id, "activity_name": "IDOR03",
                                                     "date_start": "2026-09-10"}, headers=wing_admin_hdr).json()["activity_id"]
    sqn_hdr = _sqn_admin_703(client)  # 703 is in 7WG, not ACTW2
    r = client.patch(f"/api/activities/{aid}", json={"activity_name": "HACKED"}, headers=sqn_hdr)
    assert r.status_code == 403


def test_wing_admin_cannot_patch_a_different_wings_activity(client):
    sysadmin_hdr = _sysadmin(client)
    wing_id, _, wing_admin_hdr = _make_second_wing_with_admin(client, sysadmin_hdr, "ACTW3", "ACT03", "ACTWADM03")
    aid = client.post("/api/activities/wing", json={"wing_id": wing_id, "activity_name": "IDOR04",
                                                     "date_start": "2026-09-11"}, headers=wing_admin_hdr).json()["activity_id"]
    other_wing_admin_hdr = _wing_admin_7wg(client)  # 7WG admin, not ACTW3's admin
    r = client.patch(f"/api/activities/{aid}", json={"activity_name": "HACKED"}, headers=other_wing_admin_hdr)
    assert r.status_code == 403


# ─────────────────────────────────────────────────────────────
# Permission matrix
# ─────────────────────────────────────────────────────────────

def test_wing_admin_can_edit_own_wings_activity_directly_no_intervention(client):
    hdr = _wing_admin_7wg(client)
    wing_id = _wing_id_by_code(client, hdr, "7WG")
    aid = client.post("/api/activities/wing", json={"wing_id": wing_id, "activity_name": "PERM01",
                                                     "date_start": "2026-09-12"}, headers=hdr).json()["activity_id"]
    r = client.patch(f"/api/activities/{aid}", json={"activity_name": "PERM01 Updated"}, headers=hdr)
    assert r.status_code == 200, r.text


def test_national_admin_cannot_edit_wing_activity_without_intervention(client):
    wing_admin_hdr = _wing_admin_7wg(client)
    wing_id = _wing_id_by_code(client, wing_admin_hdr, "7WG")
    aid = client.post("/api/activities/wing", json={"wing_id": wing_id, "activity_name": "PERM02",
                                                     "date_start": "2026-09-13"}, headers=wing_admin_hdr).json()["activity_id"]
    nat_hdr = _nat_admin(client)
    r = client.patch(f"/api/activities/{aid}", json={"activity_name": "HACKED"}, headers=nat_hdr)
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "intervention_required"


def test_squadron_general_cannot_create_squadron_activity(client):
    hdr = login(client, "703SQN2026")
    r = client.post("/api/activities", json={"activity_name": "PERM03", "date_start": "2026-09-14"}, headers=hdr)
    assert r.status_code == 403


def test_wing_viewer_cannot_create_wing_activity(client):
    wing_id = _wing_id_by_code(client, _sysadmin(client), "7WG")
    hdr = login(client, "7WG2026")  # seeded 7 Wing Viewer
    r = client.post("/api/activities/wing", json={"wing_id": wing_id, "activity_name": "PERM05",
                                                   "date_start": "2026-09-18"}, headers=hdr)
    assert r.status_code == 403


def test_only_national_admin_or_system_admin_can_create_national_activity(client):
    hdr = _wing_admin_7wg(client)
    r = client.post("/api/activities/national", json={"activity_name": "PERM04", "date_start": "2026-09-15"}, headers=hdr)
    assert r.status_code == 403


# ─────────────────────────────────────────────────────────────
# Archived filtering
# ─────────────────────────────────────────────────────────────

def test_archived_activity_excluded_from_active_view_included_in_archived_view(client):
    hdr = _sysadmin(client)
    aid = client.post("/api/activities/national", json={"activity_name": "ARCH01", "date_start": "2026-09-16"},
                      headers=hdr).json()["activity_id"]
    client.delete(f"/api/activities/{aid}", headers=hdr)

    active = client.get("/api/activities?scope_type=national&view=list", headers=hdr).json()["items"]
    assert not any(i["activity_id"] == aid for i in active)

    archived = client.get("/api/activities?scope_type=national&view=archived", headers=hdr).json()["items"]
    assert any(i["activity_id"] == aid for i in archived)


# ─────────────────────────────────────────────────────────────
# Backward compatibility -- existing single-squadron shape unchanged
# ─────────────────────────────────────────────────────────────

def test_get_activities_without_scope_type_returns_legacy_list_shape(client):
    hdr = _sqn_admin_703(client)
    client.post("/api/activities", json={"activity_name": "LEGACY01", "date_start": "2026-09-17"}, headers=hdr)
    r = client.get("/api/activities", headers=hdr)
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)  # legacy shape: a bare list, not {"items": [...]}
    assert any(a["activity_name"] == "LEGACY01" for a in body)
