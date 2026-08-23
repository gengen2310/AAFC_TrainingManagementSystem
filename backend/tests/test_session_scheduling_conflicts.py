"""Phase 3.1: accessible module-scheduling controls' backend support --
PUT /api/sessions/{sid} moving a session to a different Parade Night (the
"Move to session" control) and the new synchronous resource-conflict check
(facilitator/room double-booking at the same period, adapted from the
previously read-only-only GET /resources/clashes).
"""
from tests.conftest import login


def _sqn_admin_703(client):
    return login(client, "ADMIN703")


def _sqn_admin_704(client):
    return login(client, "ADMIN704")


def _make_pn(client, hdr, date, session_count=1):
    r = client.post("/api/parade-nights", json={"date": date, "term": "T1", "session_count": session_count}, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["parade_night_id"]


def _make_session(client, hdr, pn_id, period_number, facilitator_id=None, training_area_id=None):
    body = {"parade_night_id": pn_id, "period_number": period_number,
            "facilitator_id": facilitator_id, "training_area_id": training_area_id}
    r = client.post("/api/sessions", json=body, headers=hdr)
    assert r.status_code == 200, r.text
    return r.json()["session_id"]


def _first_facilitator_id(client, hdr):
    facs = client.get("/api/facilitators", headers=hdr).json()
    assert facs, "no seeded facilitators for 703"
    return facs[0]["facilitator_id"]


def _first_training_area_id(client, hdr):
    areas = client.get("/api/training-areas", headers=hdr).json()
    assert areas, "no seeded training areas for 703"
    return areas[0]["training_area_id"]


# ─────────────────────────────────────────────────────────────
# Moving a session to a different Parade Night
# ─────────────────────────────────────────────────────────────

def test_edit_session_moves_to_different_parade_night(client):
    hdr = _sqn_admin_703(client)
    pn_a = _make_pn(client, hdr, "2027-11-01")
    pn_b = _make_pn(client, hdr, "2027-11-08")
    sid = _make_session(client, hdr, pn_a, 1)

    r = client.put(f"/api/sessions/{sid}", json={"parade_night_id": pn_b, "period_number": 1}, headers=hdr)
    assert r.status_code == 200, r.text

    builder_a = client.get(f"/api/parade-nights/{pn_a}/builder", headers=hdr).json()
    builder_b = client.get(f"/api/parade-nights/{pn_b}/builder", headers=hdr).json()
    assert not any(s["id"] == sid for s in builder_a["sessions"])
    assert any(s["id"] == sid for s in builder_b["sessions"])


def test_edit_session_cross_squadron_move_forbidden(client):
    hdr703 = _sqn_admin_703(client)
    hdr704 = _sqn_admin_704(client)
    pn_703 = _make_pn(client, hdr703, "2027-11-02")
    sid = _make_session(client, hdr703, pn_703, 1)
    pn_704 = _make_pn(client, hdr704, "2027-11-02")

    r = client.put(f"/api/sessions/{sid}", json={"parade_night_id": pn_704, "period_number": 1}, headers=hdr703)
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "cross_squadron_move_forbidden"


def test_edit_session_move_to_nonexistent_parade_night_404(client):
    hdr = _sqn_admin_703(client)
    pn_a = _make_pn(client, hdr, "2027-11-03")
    sid = _make_session(client, hdr, pn_a, 1)

    r = client.put(f"/api/sessions/{sid}", json={"parade_night_id": "does-not-exist", "period_number": 1}, headers=hdr)
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "target_parade_night_not_found"


# ─────────────────────────────────────────────────────────────
# Synchronous resource-conflict check
# ─────────────────────────────────────────────────────────────

def test_edit_session_facilitator_clash_blocked(client):
    hdr = _sqn_admin_703(client)
    fac_id = _first_facilitator_id(client, hdr)
    pn = _make_pn(client, hdr, "2027-11-04", session_count=2)
    _make_session(client, hdr, pn, 1, facilitator_id=fac_id)
    sid_b = _make_session(client, hdr, pn, 2)

    r = client.put(f"/api/sessions/{sid_b}", json={
        "parade_night_id": pn, "period_number": 1, "facilitator_id": fac_id,
    }, headers=hdr)
    assert r.status_code == 409, r.text
    d = r.json()["detail"]
    assert d["error"] == "resource_conflict"
    assert any(c["type"] == "facilitator_clash" for c in d["conflicts"])


def test_edit_session_room_clash_blocked(client):
    hdr = _sqn_admin_703(client)
    area_id = _first_training_area_id(client, hdr)
    pn = _make_pn(client, hdr, "2027-11-05", session_count=2)
    _make_session(client, hdr, pn, 1, training_area_id=area_id)
    sid_b = _make_session(client, hdr, pn, 2)

    r = client.put(f"/api/sessions/{sid_b}", json={
        "parade_night_id": pn, "period_number": 1, "training_area_id": area_id,
    }, headers=hdr)
    assert r.status_code == 409, r.text
    d = r.json()["detail"]
    assert d["error"] == "resource_conflict"
    assert any(c["type"] == "room_clash" for c in d["conflicts"])


def test_edit_session_conflict_override_bypasses_check(client):
    hdr = _sqn_admin_703(client)
    fac_id = _first_facilitator_id(client, hdr)
    pn = _make_pn(client, hdr, "2027-11-06", session_count=2)
    _make_session(client, hdr, pn, 1, facilitator_id=fac_id)
    sid_b = _make_session(client, hdr, pn, 2)

    r = client.put(f"/api/sessions/{sid_b}", json={
        "parade_night_id": pn, "period_number": 1, "facilitator_id": fac_id,
        "override_conflict": True,
    }, headers=hdr)
    assert r.status_code == 200, r.text


def test_edit_session_same_facilitator_different_period_no_conflict(client):
    hdr = _sqn_admin_703(client)
    fac_id = _first_facilitator_id(client, hdr)
    pn = _make_pn(client, hdr, "2027-11-07", session_count=2)
    _make_session(client, hdr, pn, 1, facilitator_id=fac_id)
    sid_b = _make_session(client, hdr, pn, 2)

    r = client.put(f"/api/sessions/{sid_b}", json={
        "parade_night_id": pn, "period_number": 3, "facilitator_id": fac_id,
    }, headers=hdr)
    assert r.status_code == 200, r.text


def test_edit_session_swap_periods_does_not_self_conflict(client):
    """Two sessions with different resources at periods 1 and 2 -- swapping their
    period_numbers via two sequential PUTs (the "Move up/down" control's
    implementation) must never trip the conflict check against EACH OTHER,
    regardless of call order, since relabelling two already-non-overlapping
    period numbers can't create new overlap between just the two of them."""
    hdr = _sqn_admin_703(client)
    fac_id = _first_facilitator_id(client, hdr)
    pn = _make_pn(client, hdr, "2027-11-09", session_count=2)
    sid_a = _make_session(client, hdr, pn, 1, facilitator_id=fac_id)
    sid_b = _make_session(client, hdr, pn, 2)

    r1 = client.put(f"/api/sessions/{sid_a}", json={"parade_night_id": pn, "period_number": 2,
                                                     "facilitator_id": fac_id}, headers=hdr)
    assert r1.status_code == 200, r1.text
    r2 = client.put(f"/api/sessions/{sid_b}", json={"parade_night_id": pn, "period_number": 1}, headers=hdr)
    assert r2.status_code == 200, r2.text


def test_edit_session_conflict_check_scoped_to_target_parade_night(client):
    """The same facilitator at the same period number in a DIFFERENT parade
    night must never be treated as a conflict -- only siblings within the
    target Parade Night count."""
    hdr = _sqn_admin_703(client)
    fac_id = _first_facilitator_id(client, hdr)
    pn_a = _make_pn(client, hdr, "2027-11-10")
    pn_b = _make_pn(client, hdr, "2027-11-11")
    _make_session(client, hdr, pn_a, 1, facilitator_id=fac_id)
    sid_b = _make_session(client, hdr, pn_b, 1)

    r = client.put(f"/api/sessions/{sid_b}", json={
        "parade_night_id": pn_b, "period_number": 1, "facilitator_id": fac_id,
    }, headers=hdr)
    assert r.status_code == 200, r.text


# ─────────────────────────────────────────────────────────────
# Create-path conflict check (Stage 8) -- previously only PUT /sessions/{sid}
# (edit) was checked; POST /sessions (create) had zero conflict enforcement,
# so a facilitator/room could be double-booked with no warning by creating a
# brand new session directly into an existing clash rather than editing one.
# ─────────────────────────────────────────────────────────────

def test_create_session_facilitator_clash_blocked(client):
    hdr = _sqn_admin_703(client)
    fac_id = _first_facilitator_id(client, hdr)
    pn = _make_pn(client, hdr, "2027-11-12", session_count=2)
    _make_session(client, hdr, pn, 1, facilitator_id=fac_id)

    r = client.post("/api/sessions", json={
        "parade_night_id": pn, "period_number": 1, "facilitator_id": fac_id,
    }, headers=hdr)
    assert r.status_code == 409, r.text
    d = r.json()["detail"]
    assert d["error"] == "resource_conflict"
    assert any(c["type"] == "facilitator_clash" for c in d["conflicts"])


def test_create_session_room_clash_blocked(client):
    hdr = _sqn_admin_703(client)
    area_id = _first_training_area_id(client, hdr)
    pn = _make_pn(client, hdr, "2027-11-13", session_count=2)
    _make_session(client, hdr, pn, 1, training_area_id=area_id)

    r = client.post("/api/sessions", json={
        "parade_night_id": pn, "period_number": 1, "training_area_id": area_id,
    }, headers=hdr)
    assert r.status_code == 409, r.text
    d = r.json()["detail"]
    assert d["error"] == "resource_conflict"
    assert any(c["type"] == "room_clash" for c in d["conflicts"])


def test_create_session_conflict_override_bypasses_check(client):
    hdr = _sqn_admin_703(client)
    fac_id = _first_facilitator_id(client, hdr)
    pn = _make_pn(client, hdr, "2027-11-14", session_count=2)
    _make_session(client, hdr, pn, 1, facilitator_id=fac_id)

    r = client.post("/api/sessions", json={
        "parade_night_id": pn, "period_number": 1, "facilitator_id": fac_id,
        "override_conflict": True,
    }, headers=hdr)
    assert r.status_code == 200, r.text


def test_create_session_different_period_no_conflict(client):
    hdr = _sqn_admin_703(client)
    fac_id = _first_facilitator_id(client, hdr)
    pn = _make_pn(client, hdr, "2027-11-15", session_count=2)
    _make_session(client, hdr, pn, 1, facilitator_id=fac_id)

    r = client.post("/api/sessions", json={
        "parade_night_id": pn, "period_number": 2, "facilitator_id": fac_id,
    }, headers=hdr)
    assert r.status_code == 200, r.text


# ─────────────────────────────────────────────────────────────
# Parallel Training Classes are one delivery, not a double-booking
#
# A squadron routinely runs Senior 1 and Senior 2 through the same lesson with
# the same instructor in the same room. The printed Weekly Program renders one
# session per class column, so that is recorded as two sessions in one period --
# and the resource check used to reject it, which made those parade nights
# impossible to save at all.
# ─────────────────────────────────────────────────────────────

def _curriculum_items(client, hdr):
    # GET /api/curriculum returns {"items": [...]}, not a bare list.
    return client.get("/api/curriculum", headers=hdr).json()["items"]


def _first_curriculum_id(client, hdr):
    items = _curriculum_items(client, hdr)
    assert items, "no seeded curriculum for 703"
    return items[0]["curriculum_id"]


def test_same_lesson_same_facilitator_and_room_is_not_a_clash(client):
    """Two parallel classes taking one lesson from one instructor in one room."""
    hdr = _sqn_admin_703(client)
    fac = _first_facilitator_id(client, hdr)
    area = _first_training_area_id(client, hdr)
    item = _first_curriculum_id(client, hdr)
    pn = _make_pn(client, hdr, "2027-12-01", session_count=2)

    a = client.post("/api/sessions", json={
        "parade_night_id": pn, "period_number": 1, "facilitator_id": fac,
        "training_area_id": area, "curriculum_item_id": item, "cadet_group": "senior",
    }, headers=hdr)
    assert a.status_code == 200, a.text

    b = client.post("/api/sessions", json={
        "parade_night_id": pn, "period_number": 1, "facilitator_id": fac,
        "training_area_id": area, "curriculum_item_id": item, "cadet_group": "intermediate",
    }, headers=hdr)
    assert b.status_code == 200, b.text


def test_different_lessons_same_facilitator_is_still_a_clash(client):
    """The instructor would have to be in two places -- still rejected."""
    hdr = _sqn_admin_703(client)
    fac = _first_facilitator_id(client, hdr)
    items = _curriculum_items(client, hdr)
    assert len(items) >= 2, "need two curriculum items"
    pn = _make_pn(client, hdr, "2027-12-02", session_count=2)

    client.post("/api/sessions", json={
        "parade_night_id": pn, "period_number": 1, "facilitator_id": fac,
        "curriculum_item_id": items[0]["curriculum_id"],
    }, headers=hdr)
    r = client.post("/api/sessions", json={
        "parade_night_id": pn, "period_number": 1, "facilitator_id": fac,
        "curriculum_item_id": items[1]["curriculum_id"],
    }, headers=hdr)
    assert r.status_code == 409, r.text
    assert any(c["type"] == "facilitator_clash" for c in r.json()["detail"]["conflicts"])


def test_same_lesson_in_two_different_rooms_is_still_a_clash(client):
    """One lesson cannot happen in two rooms at once."""
    hdr = _sqn_admin_703(client)
    fac = _first_facilitator_id(client, hdr)
    item = _first_curriculum_id(client, hdr)
    areas = client.get("/api/training-areas", headers=hdr).json()
    assert len(areas) >= 2, "need two training areas"
    pn = _make_pn(client, hdr, "2027-12-03", session_count=2)

    client.post("/api/sessions", json={
        "parade_night_id": pn, "period_number": 1, "facilitator_id": fac,
        "training_area_id": areas[0]["training_area_id"], "curriculum_item_id": item,
    }, headers=hdr)
    r = client.post("/api/sessions", json={
        "parade_night_id": pn, "period_number": 1, "facilitator_id": fac,
        "training_area_id": areas[1]["training_area_id"], "curriculum_item_id": item,
    }, headers=hdr)
    assert r.status_code == 409, r.text
    assert any(c["type"] == "facilitator_clash" for c in r.json()["detail"]["conflicts"])


def test_untitled_sessions_sharing_a_facilitator_still_clash(client):
    """Two sessions with no curriculum item and no title are not evidence of one
    delivery, so the check must not treat 'both blank' as a match."""
    hdr = _sqn_admin_703(client)
    fac = _first_facilitator_id(client, hdr)
    pn = _make_pn(client, hdr, "2027-12-04", session_count=2)

    client.post("/api/sessions", json={
        "parade_night_id": pn, "period_number": 1, "facilitator_id": fac,
    }, headers=hdr)
    r = client.post("/api/sessions", json={
        "parade_night_id": pn, "period_number": 1, "facilitator_id": fac,
    }, headers=hdr)
    assert r.status_code == 409, r.text


def test_editing_into_a_parallel_delivery_is_allowed(client):
    """The same rule applies on PUT, not just POST."""
    hdr = _sqn_admin_703(client)
    fac = _first_facilitator_id(client, hdr)
    area = _first_training_area_id(client, hdr)
    item = _first_curriculum_id(client, hdr)
    pn = _make_pn(client, hdr, "2027-12-05", session_count=2)

    client.post("/api/sessions", json={
        "parade_night_id": pn, "period_number": 1, "facilitator_id": fac,
        "training_area_id": area, "curriculum_item_id": item,
    }, headers=hdr)
    sid_b = _make_session(client, hdr, pn, 2)

    r = client.put(f"/api/sessions/{sid_b}", json={
        "parade_night_id": pn, "period_number": 1, "facilitator_id": fac,
        "training_area_id": area, "curriculum_item_id": item,
    }, headers=hdr)
    assert r.status_code == 200, r.text
