"""REM-103: squadron-local adjustments (date/time/notes/relevance) to a
Wing/National-owned inherited Activity. The source Activity row is never
modified -- ActivityLocalOverride is a per-(activity, squadron) annotation,
mirroring the established ActivityLocalHide pattern for the general Activity
model instead of CEA-only.
"""
from tests.conftest import login


def _sysadmin(client):
    return login(client, "SYSADMIN2026")


def _sqn_admin_703(client):
    return login(client, "ADMIN703")


def _sqn_general_703(client):
    return login(client, "703SQN2026")


def _wing_admin_7wg(client):
    return login(client, "ADMIN7WG")


def _create_wing_activity(client, wing_admin_hdr, name="Wing Test Activity", date_start="2099-05-01"):
    r = client.post("/api/activities/wing", json={
        "activity_name": name, "date_start": date_start,
    }, headers=wing_admin_hdr)
    assert r.status_code == 200, r.text
    return r.json()["activity_id"]


def _create_national_activity(client, sysadmin_hdr, name="National Test Activity", date_start="2099-06-01"):
    r = client.post("/api/activities/national", json={
        "activity_name": name, "date_start": date_start,
    }, headers=sysadmin_hdr)
    assert r.status_code == 200, r.text
    return r.json()["activity_id"]


def _create_squadron_activity(client, sqn_admin_hdr, name="Own Squadron Activity", date_start="2099-07-01"):
    r = client.post("/api/activities", json={"activity_name": name, "date_start": date_start}, headers=sqn_admin_hdr)
    assert r.status_code == 200, r.text
    return r.json()["activity_id"]


# ── Create / update (upsert) ──────────────────────────────────────────────────

def test_sqn_admin_can_create_local_override_on_inherited_wing_activity(client):
    wing_hdr = _wing_admin_7wg(client)
    aid = _create_wing_activity(client, wing_hdr)
    sqn_hdr = _sqn_admin_703(client)

    r = client.put(f"/api/activities/{aid}/local-override", json={
        "local_date_start": "2099-05-02", "local_time_start": "18:00",
        "local_notes": "Moved a day later for our squadron.",
    }, headers=sqn_hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["local_date_start"] == "2099-05-02"
    assert body["local_time_start"] == "18:00"
    assert body["local_notes"] == "Moved a day later for our squadron."
    assert body["is_hidden"] is False
    assert body["version"] == 0


def test_local_override_source_values_unchanged_after_override_created(client):
    """The source Activity row itself must never be modified -- inheritance
    integrity is the whole point of a separate override table."""
    wing_hdr = _wing_admin_7wg(client)
    aid = _create_wing_activity(client, wing_hdr, date_start="2099-05-01")
    sqn_hdr = _sqn_admin_703(client)

    client.put(f"/api/activities/{aid}/local-override", json={
        "local_date_start": "2099-05-15",
    }, headers=sqn_hdr)

    # A different squadron (via wing admin's own view) still sees the
    # original, unmodified source date.
    wing_id = client.get("/api/auth/me", headers=wing_hdr).json()["session"]["wing_id"]
    wing_items = client.get(f"/api/activities?scope_type=wing&scope_id={wing_id}", headers=wing_hdr).json()["items"]
    item = next(i for i in wing_items if i["activity_id"] == aid)
    assert item["date_start"] == "2099-05-01"
    assert item["local_override"] is None  # wing_admin viewing at wing scope has no squadron override context


def test_local_override_appears_in_squadron_scoped_list_and_get(client):
    wing_hdr = _wing_admin_7wg(client)
    aid = _create_wing_activity(client, wing_hdr, date_start="2099-05-01")
    sqn_hdr = _sqn_admin_703(client)
    sq_id = client.get("/api/auth/me", headers=sqn_hdr).json()["session"]["squadron_id"]

    client.put(f"/api/activities/{aid}/local-override", json={
        "local_notes": "Local squadron note.",
    }, headers=sqn_hdr)

    listed = client.get(f"/api/activities?scope_type=squadron&scope_id={sq_id}", headers=sqn_hdr).json()["items"]
    item = next(i for i in listed if i["activity_id"] == aid)
    assert item["local_override"] is not None
    assert item["local_override"]["local_notes"] == "Local squadron note."
    # Source values are still present alongside the override, per the
    # addendum's "display source vs local value side-by-side" ask.
    assert item["date_start"] == "2099-05-01"

    single = client.get(f"/api/activities/{aid}", headers=sqn_hdr).json()
    assert single["local_override"]["local_notes"] == "Local squadron note."


def test_upsert_updates_existing_override_not_duplicate(client):
    wing_hdr = _wing_admin_7wg(client)
    aid = _create_wing_activity(client, wing_hdr)
    sqn_hdr = _sqn_admin_703(client)

    r1 = client.put(f"/api/activities/{aid}/local-override", json={"local_notes": "First"}, headers=sqn_hdr)
    assert r1.json()["version"] == 0
    r2 = client.put(f"/api/activities/{aid}/local-override", json={
        "local_notes": "Second", "version": 0,
    }, headers=sqn_hdr)
    assert r2.status_code == 200, r2.text
    assert r2.json()["local_notes"] == "Second"
    assert r2.json()["version"] == 1

    sq_id = client.get("/api/auth/me", headers=sqn_hdr).json()["session"]["squadron_id"]
    listed = client.get(f"/api/activities?scope_type=squadron&scope_id={sq_id}", headers=sqn_hdr).json()["items"]
    matches = [i for i in listed if i["activity_id"] == aid]
    assert len(matches) == 1  # exactly one row, not duplicated
    assert matches[0]["local_override"]["local_notes"] == "Second"


def test_stale_version_returns_409(client):
    wing_hdr = _wing_admin_7wg(client)
    aid = _create_wing_activity(client, wing_hdr)
    sqn_hdr = _sqn_admin_703(client)
    client.put(f"/api/activities/{aid}/local-override", json={"local_notes": "v0"}, headers=sqn_hdr)

    r = client.put(f"/api/activities/{aid}/local-override", json={
        "local_notes": "stale write", "version": 99,
    }, headers=sqn_hdr)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["error"] == "version_conflict"


def test_cannot_override_own_squadron_activity(client):
    sqn_hdr = _sqn_admin_703(client)
    aid = _create_squadron_activity(client, sqn_hdr)
    r = client.put(f"/api/activities/{aid}/local-override", json={"local_notes": "x"}, headers=sqn_hdr)
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["error"] == "cannot_override_own_activity"


def test_national_activity_can_also_be_overridden(client):
    sysadmin_hdr = _sysadmin(client)
    aid = _create_national_activity(client, sysadmin_hdr)
    sqn_hdr = _sqn_admin_703(client)
    r = client.put(f"/api/activities/{aid}/local-override", json={
        "local_date_start": "2099-06-05",
    }, headers=sqn_hdr)
    assert r.status_code == 200, r.text
    assert r.json()["local_date_start"] == "2099-06-05"


def test_sqn_general_cannot_create_override(client):
    wing_hdr = _wing_admin_7wg(client)
    aid = _create_wing_activity(client, wing_hdr)
    general_hdr = _sqn_general_703(client)
    r = client.put(f"/api/activities/{aid}/local-override", json={"local_notes": "x"}, headers=general_hdr)
    assert r.status_code == 403, r.text


def test_sqn_general_can_still_see_an_override_created_by_admin(client):
    wing_hdr = _wing_admin_7wg(client)
    aid = _create_wing_activity(client, wing_hdr)
    admin_hdr = _sqn_admin_703(client)
    client.put(f"/api/activities/{aid}/local-override", json={"local_notes": "Visible to viewers too"}, headers=admin_hdr)

    general_hdr = _sqn_general_703(client)
    single = client.get(f"/api/activities/{aid}", headers=general_hdr).json()
    assert single["local_override"]["local_notes"] == "Visible to viewers too"


def test_unauthenticated_cannot_create_override(client):
    r = client.put("/api/activities/does-not-exist/local-override", json={"local_notes": "x"})
    assert r.status_code == 401


def test_override_on_nonexistent_activity_404s(client):
    sqn_hdr = _sqn_admin_703(client)
    r = client.put("/api/activities/does-not-exist/local-override", json={"local_notes": "x"}, headers=sqn_hdr)
    assert r.status_code == 404


def test_is_hidden_flag_returned_but_does_not_remove_from_list(client):
    """REM-103 residual note: unlike ActivityLocalHide (which has no
    unhide/review UI anywhere and hard-filters), is_hidden here is returned
    as a flag so the item stays discoverable and reversible."""
    wing_hdr = _wing_admin_7wg(client)
    aid = _create_wing_activity(client, wing_hdr)
    sqn_hdr = _sqn_admin_703(client)
    sq_id = client.get("/api/auth/me", headers=sqn_hdr).json()["session"]["squadron_id"]

    client.put(f"/api/activities/{aid}/local-override", json={"is_hidden": True}, headers=sqn_hdr)

    listed = client.get(f"/api/activities?scope_type=squadron&scope_id={sq_id}", headers=sqn_hdr).json()["items"]
    item = next(i for i in listed if i["activity_id"] == aid)
    assert item["local_override"]["is_hidden"] is True


# ── Delete (revert) ────────────────────────────────────────────────────────────

def test_delete_removes_override_and_reverts_to_source(client):
    wing_hdr = _wing_admin_7wg(client)
    aid = _create_wing_activity(client, wing_hdr, date_start="2099-05-01")
    sqn_hdr = _sqn_admin_703(client)
    sq_id = client.get("/api/auth/me", headers=sqn_hdr).json()["session"]["squadron_id"]

    client.put(f"/api/activities/{aid}/local-override", json={"local_date_start": "2099-05-20"}, headers=sqn_hdr)
    listed = client.get(f"/api/activities?scope_type=squadron&scope_id={sq_id}", headers=sqn_hdr).json()["items"]
    assert next(i for i in listed if i["activity_id"] == aid)["local_override"] is not None

    r = client.delete(f"/api/activities/{aid}/local-override", headers=sqn_hdr)
    assert r.status_code == 200, r.text

    listed2 = client.get(f"/api/activities?scope_type=squadron&scope_id={sq_id}", headers=sqn_hdr).json()["items"]
    item2 = next(i for i in listed2 if i["activity_id"] == aid)
    assert item2["local_override"] is None
    assert item2["date_start"] == "2099-05-01"  # source value, unaffected all along


def test_delete_nonexistent_override_404s(client):
    wing_hdr = _wing_admin_7wg(client)
    aid = _create_wing_activity(client, wing_hdr)
    sqn_hdr = _sqn_admin_703(client)
    r = client.delete(f"/api/activities/{aid}/local-override", headers=sqn_hdr)
    assert r.status_code == 404


def test_delete_requires_write_authority(client):
    wing_hdr = _wing_admin_7wg(client)
    aid = _create_wing_activity(client, wing_hdr)
    admin_hdr = _sqn_admin_703(client)
    client.put(f"/api/activities/{aid}/local-override", json={"local_notes": "x"}, headers=admin_hdr)

    general_hdr = _sqn_general_703(client)
    r = client.delete(f"/api/activities/{aid}/local-override", headers=general_hdr)
    assert r.status_code == 403


# ── get_activity inheritance-visibility fix (found while building this feature) ──
# Pre-existing bug, unrelated to the override mechanism itself: a squadron
# user could see an inherited wing/national activity in their LIST
# (list_activities' _activities_visibility_filter correctly includes it) but
# got a 403 viewing that exact same activity by ID via GET /activities/{id}
# (get_activity required NATIONAL_LEVEL for national / require_can_view_wing
# for wing, neither of which a squadron role ever satisfies). This blocked
# the override feature itself -- a squadron admin needs to view an inherited
# activity before creating a local override on it.

def test_sqn_admin_can_view_inherited_wing_activity_by_id(client):
    wing_hdr = _wing_admin_7wg(client)
    aid = _create_wing_activity(client, wing_hdr)
    sqn_hdr = _sqn_admin_703(client)
    r = client.get(f"/api/activities/{aid}", headers=sqn_hdr)
    assert r.status_code == 200, r.text
    assert r.json()["owning_level"] == "wing"


def test_sqn_general_can_view_inherited_wing_activity_by_id(client):
    wing_hdr = _wing_admin_7wg(client)
    aid = _create_wing_activity(client, wing_hdr)
    general_hdr = _sqn_general_703(client)
    r = client.get(f"/api/activities/{aid}", headers=general_hdr)
    assert r.status_code == 200, r.text


def test_sqn_admin_can_view_national_activity_by_id(client):
    sysadmin_hdr = _sysadmin(client)
    aid = _create_national_activity(client, sysadmin_hdr)
    sqn_hdr = _sqn_admin_703(client)
    r = client.get(f"/api/activities/{aid}", headers=sqn_hdr)
    assert r.status_code == 200, r.text
    assert r.json()["owning_level"] == "national"


def test_squadron_in_a_different_wing_still_cannot_view_this_wings_activity(client):
    """Regression guard: the fix must not become a blanket allow -- a
    squadron under a DIFFERENT wing must still get 403 on a wing-owned
    activity that isn't theirs to inherit."""
    sysadmin_hdr = _sysadmin(client)
    # Distinctive codes -- "OTHRW" collides with test_org_account_linking.py's
    # own unrelated "Other Wing" fixture in this file's shared test-session DB.
    wing_r = client.post("/api/wings", json={"code": "ALOVWG", "name": "Local Override Other Wing"}, headers=sysadmin_hdr)
    assert wing_r.status_code == 200, wing_r.text
    other_wing_id = wing_r.json()["wing_id"]
    sqn_r = client.post("/api/squadrons", json={"wing_id": other_wing_id, "code": "ALOVSQ", "name": "Local Override Other Sqn"},
                        headers=sysadmin_hdr)
    assert sqn_r.status_code == 200, sqn_r.text
    acct_r = client.post("/api/accounts", json={
        "display_name": "Other Sqn Admin", "role": "sqn_admin",
        "squadron_id": sqn_r.json()["squadron_id"], "new_code": "ALOVSQNADMIN",
    }, headers=sysadmin_hdr)
    assert acct_r.status_code == 200, acct_r.text
    other_sqn_hdr = login(client, "ALOVSQNADMIN")

    wing_hdr = _wing_admin_7wg(client)
    aid = _create_wing_activity(client, wing_hdr)
    r = client.get(f"/api/activities/{aid}", headers=other_sqn_hdr)
    assert r.status_code == 403, r.text


# ── Audit ────────────────────────────────────────────────────────────────────

def test_override_create_and_delete_are_audited(client):
    wing_hdr = _wing_admin_7wg(client)
    aid = _create_wing_activity(client, wing_hdr)
    sqn_hdr = _sqn_admin_703(client)

    client.put(f"/api/activities/{aid}/local-override", json={"local_notes": "audit me"}, headers=sqn_hdr)
    client.delete(f"/api/activities/{aid}/local-override", headers=sqn_hdr)

    audit_rows = client.get("/api/audit?object_type=activity_local_override", headers=_sysadmin(client)).json()
    actions = {r["action"] for r in audit_rows if r.get("object_type") == "activity_local_override"}
    assert "create" in actions
    assert "delete" in actions
