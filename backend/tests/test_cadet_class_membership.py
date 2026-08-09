"""Tests for CLASS-09: Cadet<->Training Class membership.

Explicitly product-scope-confirmed by the user before this was built (see
CadetClassMembership's own docstring in models/training.py and gap
register CLASS-09) -- individual cadet-class tracking is conditional on an
explicit product decision, not an engineering default, per addendum
§38/§39's data-minimisation principle.

Enables a Cadet to hold concurrent Foundation (e.g. Senior 1) and
Extension (e.g. Bronze CLP) membership -- the addendum's own scenario that
Cadet.phase's single free-text column cannot express. Cadet.phase is
untouched by any of this.
"""
import uuid

from tests.conftest import login

ADM703 = "ADMIN703"
GEN703 = "703SQN2026"
ADM704 = "ADMIN704"


def _sqn_admin_hdr(client):
    return login(client, ADM703)


def _first_cadet_id(client, hdr):
    r = client.get("/api/cadets", headers=hdr)
    assert r.status_code == 200, r.text
    cadets = r.json()
    assert cadets, "seeded 703 squadron must have at least one cadet for this test"
    return cadets[0]["cadet_id"]


def _make_stage(client, hdr, squadron_id, name_prefix="CLASS-09-TEST"):
    name = f"{name_prefix}-{uuid.uuid4().hex[:10]}"
    r = client.post("/api/curriculum/phases", json={
        "name": name, "display_name": name, "scope_level": "squadron", "squadron_id": squadron_id,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["phase_id"]


def _make_year(client, hdr):
    r = client.get("/api/planning/years", headers=hdr)
    assert r.status_code == 200, r.text
    years = r.json()
    if years:
        return years[0]["planning_year_id"], years[0]["unit_id"]
    # Not every seeded squadron has a planning year (e.g. 704) -- create one.
    me = client.get("/api/auth/me", headers=hdr).json()
    sqn_id = me["session"]["squadron_id"]
    created = client.post("/api/planning/years", json={"year": 2026, "name": "CLASS-09 Test Year"}, headers=hdr)
    assert created.status_code == 200, created.text
    return created.json()["planning_year_id"], sqn_id


def _make_class(client, hdr, year_id, stage_id, name):
    r = client.post("/api/training-classes", json={
        "training_year_id": year_id, "training_stage_id": stage_id, "display_name": name,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["training_class_id"]


def test_add_membership_and_list_it(client):
    hdr = _sqn_admin_hdr(client)
    cadet_id = _first_cadet_id(client, hdr)
    year_id, sqn_id = _make_year(client, hdr)
    stage_id = _make_stage(client, hdr, sqn_id)
    class_id = _make_class(client, hdr, year_id, stage_id, "Foundation Class")

    r = client.post(f"/api/cadets/{cadet_id}/class-memberships", json={
        "training_class_id": class_id, "start_date": "2026-02-01",
    }, headers=hdr)
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["cadet_id"] == cadet_id
    assert m["training_class_id"] == class_id
    assert m["training_class_name"] == "Foundation Class"
    assert m["active_status"] is True
    assert m["source"] == "manual"

    lst = client.get(f"/api/cadets/{cadet_id}/class-memberships", headers=hdr)
    assert lst.status_code == 200, lst.text
    memberships = lst.json()
    assert len(memberships) == 1
    assert memberships[0]["membership_id"] == m["membership_id"]


def test_cadet_can_hold_concurrent_foundation_and_extension_membership(client):
    """The addendum's own core scenario for CLASS-09: one Cadet, two
    simultaneously-active memberships in different Stages."""
    hdr = _sqn_admin_hdr(client)
    cadet_id = _first_cadet_id(client, hdr)
    year_id, sqn_id = _make_year(client, hdr)
    foundation_stage = _make_stage(client, hdr, sqn_id, "CLASS-09-FOUNDATION")
    extension_stage = _make_stage(client, hdr, sqn_id, "CLASS-09-EXTENSION")
    foundation_class = _make_class(client, hdr, year_id, foundation_stage, "Senior 1")
    extension_class = _make_class(client, hdr, year_id, extension_stage, "Bronze CLP")

    r1 = client.post(f"/api/cadets/{cadet_id}/class-memberships",
                      json={"training_class_id": foundation_class}, headers=hdr)
    assert r1.status_code == 200, r1.text
    r2 = client.post(f"/api/cadets/{cadet_id}/class-memberships",
                      json={"training_class_id": extension_class}, headers=hdr)
    assert r2.status_code == 200, r2.text

    # Only 3 cadets are seeded and this suite's DB is not rolled back between
    # tests, so this cadet may already carry leftover memberships from
    # earlier tests in this file -- filter to just the two rows this test
    # itself created rather than asserting on the account's full list.
    memberships = client.get(f"/api/cadets/{cadet_id}/class-memberships", headers=hdr).json()
    mine = [m for m in memberships if m["membership_id"] in (r1.json()["membership_id"], r2.json()["membership_id"])]
    class_names = {m["training_class_name"] for m in mine}
    assert class_names == {"Senior 1", "Bronze CLP"}
    assert all(m["active_status"] for m in mine)


def test_duplicate_active_membership_returns_409(client):
    hdr = _sqn_admin_hdr(client)
    cadet_id = _first_cadet_id(client, hdr)
    year_id, sqn_id = _make_year(client, hdr)
    stage_id = _make_stage(client, hdr, sqn_id)
    class_id = _make_class(client, hdr, year_id, stage_id, "Dup Test Class")

    r1 = client.post(f"/api/cadets/{cadet_id}/class-memberships",
                      json={"training_class_id": class_id}, headers=hdr)
    assert r1.status_code == 200, r1.text
    r2 = client.post(f"/api/cadets/{cadet_id}/class-memberships",
                      json={"training_class_id": class_id}, headers=hdr)
    assert r2.status_code == 409, r2.text
    assert r2.json()["detail"]["error"] == "already_a_member"


def test_rejoining_after_ending_membership_is_allowed(client):
    """Ending a membership (active_status=False) then adding a new one for
    the same Cadet+Class pair must succeed -- a Cadet can leave and rejoin
    a Class over time; only a currently-*active* duplicate is blocked."""
    hdr = _sqn_admin_hdr(client)
    cadet_id = _first_cadet_id(client, hdr)
    year_id, sqn_id = _make_year(client, hdr)
    stage_id = _make_stage(client, hdr, sqn_id)
    class_id = _make_class(client, hdr, year_id, stage_id, "Rejoin Test Class")

    r1 = client.post(f"/api/cadets/{cadet_id}/class-memberships",
                      json={"training_class_id": class_id}, headers=hdr)
    assert r1.status_code == 200, r1.text
    m1 = r1.json()

    ended = client.patch(f"/api/cadet-class-memberships/{m1['membership_id']}", json={
        "end_date": "2026-06-01", "active_status": False, "client_version": m1["version"],
    }, headers=hdr)
    assert ended.status_code == 200, ended.text
    assert ended.json()["active_status"] is False
    assert ended.json()["end_date"] == "2026-06-01"

    r2 = client.post(f"/api/cadets/{cadet_id}/class-memberships",
                      json={"training_class_id": class_id}, headers=hdr)
    assert r2.status_code == 200, r2.text

    # Filter to this test's own class_id -- this cadet may carry leftover
    # memberships in other classes from earlier tests in this file (the
    # suite's DB is not rolled back between tests, and only 3 cadets are
    # seeded so every test here reuses the same one).
    all_memberships = client.get(
        f"/api/cadets/{cadet_id}/class-memberships?include_archived=true", headers=hdr
    ).json()
    for_this_class = [m for m in all_memberships if m["training_class_id"] == class_id]
    assert len(for_this_class) == 2


def test_wrong_squadron_training_class_rejected(client):
    """A Training Class belonging to a different squadron must not be
    attachable to this Cadet, even if both IDs are individually valid."""
    hdr_703 = _sqn_admin_hdr(client)
    hdr_704 = login(client, ADM704)
    cadet_id = _first_cadet_id(client, hdr_703)

    year_id_704, sqn_id_704 = _make_year(client, hdr_704)
    stage_704 = _make_stage(client, hdr_704, sqn_id_704, "CLASS-09-704")
    class_704 = _make_class(client, hdr_704, year_id_704, stage_704, "704 Class")

    r = client.post(f"/api/cadets/{cadet_id}/class-memberships",
                     json={"training_class_id": class_704}, headers=hdr_703)
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["error"] == "training_class_wrong_squadron"


def test_704_admin_cannot_view_or_write_703_cadet_memberships(client):
    hdr_703 = _sqn_admin_hdr(client)
    hdr_704 = login(client, ADM704)
    cadet_id = _first_cadet_id(client, hdr_703)
    year_id, sqn_id = _make_year(client, hdr_703)
    stage_id = _make_stage(client, hdr_703, sqn_id)
    class_id = _make_class(client, hdr_703, year_id, stage_id, "Isolation Test Class")

    view = client.get(f"/api/cadets/{cadet_id}/class-memberships", headers=hdr_704)
    assert view.status_code == 403, view.text

    write = client.post(f"/api/cadets/{cadet_id}/class-memberships",
                         json={"training_class_id": class_id}, headers=hdr_704)
    assert write.status_code == 403, write.text


def test_sqn_general_cannot_add_membership(client):
    hdr_admin = _sqn_admin_hdr(client)
    hdr_general = login(client, GEN703)
    cadet_id = _first_cadet_id(client, hdr_admin)
    year_id, sqn_id = _make_year(client, hdr_admin)
    stage_id = _make_stage(client, hdr_admin, sqn_id)
    class_id = _make_class(client, hdr_admin, year_id, stage_id, "General Blocked Class")

    r = client.post(f"/api/cadets/{cadet_id}/class-memberships",
                     json={"training_class_id": class_id}, headers=hdr_general)
    assert r.status_code == 403, r.text


def test_sqn_general_cannot_list_memberships(client):
    hdr_admin = _sqn_admin_hdr(client)
    hdr_general = login(client, GEN703)
    cadet_id = _first_cadet_id(client, hdr_admin)

    r = client.get(f"/api/cadets/{cadet_id}/class-memberships", headers=hdr_general)
    assert r.status_code == 403, r.text


def test_archive_membership_removes_it_from_default_list(client):
    hdr = _sqn_admin_hdr(client)
    cadet_id = _first_cadet_id(client, hdr)
    year_id, sqn_id = _make_year(client, hdr)
    stage_id = _make_stage(client, hdr, sqn_id)
    class_id = _make_class(client, hdr, year_id, stage_id, "Archive Test Class")

    m = client.post(f"/api/cadets/{cadet_id}/class-memberships",
                     json={"training_class_id": class_id}, headers=hdr).json()

    arc = client.delete(f"/api/cadet-class-memberships/{m['membership_id']}", headers=hdr)
    assert arc.status_code == 200, arc.text

    default_list = client.get(f"/api/cadets/{cadet_id}/class-memberships", headers=hdr).json()
    assert m["membership_id"] not in [x["membership_id"] for x in default_list]

    full_list = client.get(
        f"/api/cadets/{cadet_id}/class-memberships?include_archived=true", headers=hdr
    ).json()
    assert m["membership_id"] in [x["membership_id"] for x in full_list]


def test_training_class_members_endpoint_lists_active_cadets(client):
    hdr = _sqn_admin_hdr(client)
    cadet_id = _first_cadet_id(client, hdr)
    year_id, sqn_id = _make_year(client, hdr)
    stage_id = _make_stage(client, hdr, sqn_id)
    class_id = _make_class(client, hdr, year_id, stage_id, "Members Endpoint Class")

    client.post(f"/api/cadets/{cadet_id}/class-memberships",
                json={"training_class_id": class_id}, headers=hdr)

    members = client.get(f"/api/training-classes/{class_id}/members", headers=hdr)
    assert members.status_code == 200, members.text
    body = members.json()
    assert len(body) == 1
    assert body[0]["cadet_id"] == cadet_id


def test_stale_version_update_returns_409(client):
    hdr = _sqn_admin_hdr(client)
    cadet_id = _first_cadet_id(client, hdr)
    year_id, sqn_id = _make_year(client, hdr)
    stage_id = _make_stage(client, hdr, sqn_id)
    class_id = _make_class(client, hdr, year_id, stage_id, "Version Conflict Class")

    m = client.post(f"/api/cadets/{cadet_id}/class-memberships",
                     json={"training_class_id": class_id}, headers=hdr).json()

    stale = client.patch(f"/api/cadet-class-memberships/{m['membership_id']}", json={
        "active_status": False, "client_version": m["version"] + 1,
    }, headers=hdr)
    assert stale.status_code == 409, stale.text
