"""Tests for CLASS-10: Training Class split/merge lifecycle.

Addendum §62/§63 requires split/merge to preserve historical data -- past
Session/SessionAudience records must survive intact, never be silently
rewritten. This is the crux of why the design here deliberately does NOT
copy the Facilitator absorb() pattern (blind FK reassignment of all child
rows onto the survivor): SessionAudience has no "at-time" snapshot field,
so reassigning it on merge would silently rewrite which class a past,
already-delivered session belonged to. Instead, split/merge only ever
mutates CadetClassMembership (a lifecycle join designed for exactly this)
via end-old+create-new, and SessionAudience is never touched -- see
test_merge_does_not_rewrite_session_audience below, the regression test
that would have caught the Facilitator-pattern mistake if copied verbatim.
"""
from datetime import date, timedelta

from tests.conftest import login

ADM703 = "ADMIN703"
GEN703 = "703SQN2026"
ADM704 = "ADMIN704"


def _sqn_admin_hdr(client):
    return login(client, ADM703)


def _cadet_ids(client, hdr, n=1):
    r = client.get("/api/cadets", headers=hdr)
    assert r.status_code == 200, r.text
    cadets = r.json()
    assert len(cadets) >= n, f"seeded 703 squadron must have at least {n} cadet(s) for this test"
    return [c["cadet_id"] for c in cadets[:n]]


def _make_stage(client, hdr, squadron_id, name_prefix="CLASS-10-TEST"):
    import uuid
    name = f"{name_prefix}-{uuid.uuid4().hex[:10]}"
    r = client.post("/api/curriculum/phases", json={
        "name": name, "display_name": name, "scope_level": "squadron", "squadron_id": squadron_id,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["phase_id"]


def _make_year(client, hdr, year):
    r = client.post("/api/planning/years", json={"year": year, "name": f"{year} Training Year"}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["planning_year_id"]


def _own_squadron_id(client, hdr):
    return client.get("/api/auth/me", headers=hdr).json()["session"]["squadron_id"]


def _make_class(client, hdr, year_id, stage_id, name):
    r = client.post("/api/training-classes", json={
        "training_year_id": year_id, "training_stage_id": stage_id, "display_name": name,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["training_class_id"]


def _add_membership(client, hdr, cadet_id, class_id):
    r = client.post(f"/api/cadets/{cadet_id}/class-memberships",
                     json={"training_class_id": class_id}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()


def _make_session(client, hdr, days_ahead):
    """Same weekday-collision avoidance as test_session_audience.py's helper --
    703's seeded demo data recurs weekly on its default parade day (Friday)."""
    candidate = date.today() + timedelta(days=days_ahead)
    if candidate.weekday() == 4:  # Friday
        candidate += timedelta(days=1)
    target_date = candidate.isoformat()
    session_info = client.get("/api/auth/me", headers=hdr).json()["session"]
    sqn_id, wing_id = session_info.get("squadron_id"), session_info.get("wing_id")
    pn = client.post("/api/parade-nights", json={
        "squadron_id": sqn_id, "wing_id": wing_id, "date": target_date, "parade_type": "normal",
    }, headers=hdr)
    assert pn.status_code in (200, 201), pn.text
    pn_id = pn.json().get("parade_night_id") or pn.json().get("id")
    sess = client.post("/api/sessions", json={
        "parade_night_id": pn_id, "period_number": 1, "cadet_group": "senior",
    }, headers=hdr)
    assert sess.status_code in (200, 201), sess.text
    return sess.json()["session_id"]


def _setup_two_classes(client, hdr, year_no, stage_prefix="CLASS-10"):
    sqn_id = _own_squadron_id(client, hdr)
    year_id = _make_year(client, hdr, year_no)
    stage_id = _make_stage(client, hdr, sqn_id, stage_prefix)
    a = _make_class(client, hdr, year_id, stage_id, "Class A")
    b = _make_class(client, hdr, year_id, stage_id, "Class B")
    return year_id, stage_id, a, b


# ─────────────────────────────────────────────────────────────
# reassign-members
# ─────────────────────────────────────────────────────────────

def test_reassign_members_ends_old_membership_and_creates_new_one(client):
    hdr = _sqn_admin_hdr(client)
    _, _, class_a, class_b = _setup_two_classes(client, hdr, 2087)
    cadet_id = _cadet_ids(client, hdr, 1)[0]
    old = _add_membership(client, hdr, cadet_id, class_a)

    r = client.post(f"/api/training-classes/{class_a}/reassign-members", json={
        "cadet_ids": [cadet_id], "to_training_class_id": class_b, "effective_date": "2026-03-01",
    }, headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["moved"] == [cadet_id]
    assert body["skipped"] == []

    all_memberships = client.get(
        f"/api/cadets/{cadet_id}/class-memberships?include_archived=true", headers=hdr
    ).json()
    mine = [m for m in all_memberships if m["training_class_id"] in (class_a, class_b)]
    old_row = next(m for m in mine if m["membership_id"] == old["membership_id"])
    new_rows = [m for m in mine if m["membership_id"] != old["membership_id"] and m["training_class_id"] == class_b]

    # History preserved: the old row survives with active_status flipped off,
    # not deleted -- this is the assertion that would fail if reassign used
    # a hard delete or in-place FK reassignment instead of end-old+create-new.
    assert old_row["active_status"] is False
    assert old_row["end_date"] == "2026-03-01"
    assert old_row["training_class_id"] == class_a, "the old row's own class link must not be rewritten"

    assert len(new_rows) == 1
    assert new_rows[0]["active_status"] is True
    assert new_rows[0]["start_date"] == "2026-03-01"


def test_reassign_skips_cadet_with_no_active_membership(client):
    hdr = _sqn_admin_hdr(client)
    _, _, class_a, class_b = _setup_two_classes(client, hdr, 2086)
    cadet_id = _cadet_ids(client, hdr, 1)[0]
    # cadet_id has no membership in class_a at all.

    r = client.post(f"/api/training-classes/{class_a}/reassign-members", json={
        "cadet_ids": [cadet_id], "to_training_class_id": class_b,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["moved"] == []
    assert body["skipped"] == [cadet_id]


def test_reassign_rejects_cross_stage_target(client):
    hdr = _sqn_admin_hdr(client)
    sqn_id = _own_squadron_id(client, hdr)
    year_id = _make_year(client, hdr, 2085)
    stage_1 = _make_stage(client, hdr, sqn_id, "CLASS-10-STAGE-1")
    stage_2 = _make_stage(client, hdr, sqn_id, "CLASS-10-STAGE-2")
    class_a = _make_class(client, hdr, year_id, stage_1, "Class A")
    class_c = _make_class(client, hdr, year_id, stage_2, "Class C (different stage)")
    cadet_id = _cadet_ids(client, hdr, 1)[0]
    _add_membership(client, hdr, cadet_id, class_a)

    r = client.post(f"/api/training-classes/{class_a}/reassign-members", json={
        "cadet_ids": [cadet_id], "to_training_class_id": class_c,
    }, headers=hdr)
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["error"] == "cross_stage"


def test_reassign_rejects_cross_year_target(client):
    hdr = _sqn_admin_hdr(client)
    sqn_id = _own_squadron_id(client, hdr)
    year_1 = _make_year(client, hdr, 2084)
    year_2 = _make_year(client, hdr, 2083)
    stage_id = _make_stage(client, hdr, sqn_id, "CLASS-10-CROSSYEAR")
    class_a = _make_class(client, hdr, year_1, stage_id, "Class A")
    class_c = _make_class(client, hdr, year_2, stage_id, "Class C (different year)")
    cadet_id = _cadet_ids(client, hdr, 1)[0]
    _add_membership(client, hdr, cadet_id, class_a)

    r = client.post(f"/api/training-classes/{class_a}/reassign-members", json={
        "cadet_ids": [cadet_id], "to_training_class_id": class_c,
    }, headers=hdr)
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["error"] == "cross_year"


def test_reassign_cross_squadron_forbidden(client):
    hdr_703 = _sqn_admin_hdr(client)
    _, _, class_a, class_b = _setup_two_classes(client, hdr_703, 2082)
    cadet_id = _cadet_ids(client, hdr_703, 1)[0]
    _add_membership(client, hdr_703, cadet_id, class_a)

    hdr_704 = login(client, ADM704)
    r = client.post(f"/api/training-classes/{class_a}/reassign-members", json={
        "cadet_ids": [cadet_id], "to_training_class_id": class_b,
    }, headers=hdr_704)
    assert r.status_code == 403, r.text


def test_reassign_sqn_general_forbidden(client):
    hdr_admin = _sqn_admin_hdr(client)
    _, _, class_a, class_b = _setup_two_classes(client, hdr_admin, 2081)
    cadet_id = _cadet_ids(client, hdr_admin, 1)[0]
    _add_membership(client, hdr_admin, cadet_id, class_a)

    hdr_general = login(client, GEN703)
    r = client.post(f"/api/training-classes/{class_a}/reassign-members", json={
        "cadet_ids": [cadet_id], "to_training_class_id": class_b,
    }, headers=hdr_general)
    assert r.status_code == 403, r.text


def test_reassign_members_unauthenticated(client):
    r = client.post("/api/training-classes/x/reassign-members", json={
        "cadet_ids": ["y"], "to_training_class_id": "z",
    })
    assert r.status_code == 401


# ─────────────────────────────────────────────────────────────
# merge-into
# ─────────────────────────────────────────────────────────────

def test_merge_moves_all_active_members_and_archives_source(client):
    hdr = _sqn_admin_hdr(client)
    _, _, source, target = _setup_two_classes(client, hdr, 2080)
    cadet_id = _cadet_ids(client, hdr, 1)[0]
    _add_membership(client, hdr, cadet_id, source)

    r = client.post(f"/api/training-classes/{source}/merge-into", json={
        "target_training_class_id": target,
    }, headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    assert cadet_id in body["moved"]

    # Source is archived (restorable soft-delete), not hard-deleted.
    listed = client.get("/api/training-classes", params={"include_archived": True}, headers=hdr).json()
    src_row = next(c for c in listed if c["training_class_id"] == source)
    assert src_row["is_archived"] is True

    members = client.get(f"/api/training-classes/{target}/members", headers=hdr).json()
    assert cadet_id in [m["cadet_id"] for m in members]

    # Dual audit entries, mirroring the Facilitator absorb() pattern.
    audit_target = client.get("/api/audit", params={"object_type": "training_class", "object_id": target},
                               headers=hdr).json()
    assert any(a["action"] == "merge_members_in" for a in audit_target)
    audit_source = client.get("/api/audit", params={"object_type": "training_class", "object_id": source},
                               headers=hdr).json()
    assert any(a["action"] == "archive" for a in audit_source)


def test_merge_self_rejected(client):
    hdr = _sqn_admin_hdr(client)
    _, _, class_a, _ = _setup_two_classes(client, hdr, 2079)
    r = client.post(f"/api/training-classes/{class_a}/merge-into", json={
        "target_training_class_id": class_a,
    }, headers=hdr)
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["error"] == "same_class"


def test_merge_rejects_cross_stage_target(client):
    hdr = _sqn_admin_hdr(client)
    sqn_id = _own_squadron_id(client, hdr)
    year_id = _make_year(client, hdr, 2078)
    stage_1 = _make_stage(client, hdr, sqn_id, "CLASS-10-MERGE-STAGE-1")
    stage_2 = _make_stage(client, hdr, sqn_id, "CLASS-10-MERGE-STAGE-2")
    source = _make_class(client, hdr, year_id, stage_1, "Source")
    target = _make_class(client, hdr, year_id, stage_2, "Target (different stage)")

    r = client.post(f"/api/training-classes/{source}/merge-into", json={
        "target_training_class_id": target,
    }, headers=hdr)
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["error"] == "cross_stage"


def test_merge_does_not_rewrite_session_audience(client):
    """The critical CLASS-10 regression test: a merge must never rewrite
    which class a past, already-delivered Session belonged to. Reusing the
    Facilitator absorb() pattern's blind-FK-reassignment approach here would
    make this test fail."""
    hdr = _sqn_admin_hdr(client)
    _, _, source, target = _setup_two_classes(client, hdr, 2077)
    sid = _make_session(client, hdr, days_ahead=200)
    aud = client.put(f"/api/sessions/{sid}/audience", json={"training_class_ids": [source]}, headers=hdr)
    assert aud.status_code == 200, aud.text

    r = client.post(f"/api/training-classes/{source}/merge-into", json={
        "target_training_class_id": target,
    }, headers=hdr)
    assert r.status_code == 200, r.text

    after = client.get(f"/api/sessions/{sid}/audience", headers=hdr).json()
    assert len(after) == 1
    assert after[0]["training_class_id"] == source, \
        "SessionAudience must still reference the (now-archived) source class -- merge must not rewrite history"


def test_merge_cross_squadron_forbidden(client):
    hdr_703 = _sqn_admin_hdr(client)
    _, _, source, target = _setup_two_classes(client, hdr_703, 2076)

    hdr_704 = login(client, ADM704)
    r = client.post(f"/api/training-classes/{source}/merge-into", json={
        "target_training_class_id": target,
    }, headers=hdr_704)
    assert r.status_code == 403, r.text


# ─────────────────────────────────────────────────────────────
# restore
# ─────────────────────────────────────────────────────────────

def test_restore_reverses_archive(client):
    hdr = _sqn_admin_hdr(client)
    _, _, class_a, _ = _setup_two_classes(client, hdr, 2075)
    arc = client.delete(f"/api/training-classes/{class_a}", headers=hdr)
    assert arc.status_code == 200, arc.text

    r = client.post(f"/api/training-classes/{class_a}/restore", headers=hdr)
    assert r.status_code == 200, r.text

    listed = client.get("/api/training-classes", params={"training_year_id": None}, headers=hdr).json()
    # class_a must be visible again in the default (non-archived) list.
    all_default = client.get("/api/training-classes", headers=hdr).json()
    assert class_a in [c["training_class_id"] for c in all_default]


def test_restore_already_active_returns_409(client):
    hdr = _sqn_admin_hdr(client)
    _, _, class_a, _ = _setup_two_classes(client, hdr, 2074)
    r = client.post(f"/api/training-classes/{class_a}/restore", headers=hdr)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["error"] == "not_archived"


def test_restore_cross_squadron_forbidden(client):
    hdr_703 = _sqn_admin_hdr(client)
    _, _, class_a, _ = _setup_two_classes(client, hdr_703, 2073)
    client.delete(f"/api/training-classes/{class_a}", headers=hdr_703)

    hdr_704 = login(client, ADM704)
    r = client.post(f"/api/training-classes/{class_a}/restore", headers=hdr_704)
    assert r.status_code == 403, r.text


def test_restore_unauthenticated(client):
    r = client.post("/api/training-classes/x/restore")
    assert r.status_code == 401
