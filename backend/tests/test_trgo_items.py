"""TRGO-01 through TRGO-08: user-feedback traceability items.

Only TRGO-07 (duplicate facilitator detection) changed backend behavior --
see docs/release/trgo_review_traceability.md for the full investigation and
disposition of all 8 items (several are frontend-only fixes or documented,
deliberately-deferred follow-ups with no backend test surface).

Each test uses a distinct name pair -- domain data (unlike rate-limit/lockout
state) is not reset between tests by the `client` fixture, and persists for
the rest of the pytest session, so name collisions across tests in this file
would produce false positives/negatives here.
"""
from tests.conftest import login


def _sqn_admin(client):
    return login(client, "ADMIN703")


def test_duplicate_facilitator_blocked_by_default(client):
    hdr = _sqn_admin(client)
    r = client.post("/api/facilitators", json={"first_name": "Jordan", "last_name": "Trgo07A"}, headers=hdr)
    assert r.status_code == 200, r.text

    r = client.post("/api/facilitators", json={"first_name": "Jordan", "last_name": "Trgo07A"}, headers=hdr)
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "possible_duplicate"
    assert "existing_facilitator_id" in r.json()["detail"]


def test_duplicate_facilitator_name_match_is_case_insensitive(client):
    hdr = _sqn_admin(client)
    client.post("/api/facilitators", json={"first_name": "Jordan", "last_name": "Trgo07B"}, headers=hdr)

    r = client.post("/api/facilitators", json={"first_name": "JORDAN", "last_name": "trgo07b"}, headers=hdr)
    assert r.status_code == 409


def test_duplicate_facilitator_can_be_confirmed(client):
    """The same name may be a genuinely different person -- confirm_duplicate=true must still allow it."""
    hdr = _sqn_admin(client)
    r1 = client.post("/api/facilitators", json={"first_name": "Jordan", "last_name": "Trgo07C"}, headers=hdr)
    assert r1.status_code == 200

    r2 = client.post("/api/facilitators",
                     json={"first_name": "Jordan", "last_name": "Trgo07C", "confirm_duplicate": True},
                     headers=hdr)
    assert r2.status_code == 200, r2.text
    assert r2.json()["facilitator_id"] != r1.json()["facilitator_id"]


def test_different_name_facilitator_not_blocked(client):
    hdr = _sqn_admin(client)
    client.post("/api/facilitators", json={"first_name": "Jordan", "last_name": "Trgo07D"}, headers=hdr)

    r = client.post("/api/facilitators", json={"first_name": "Alex", "last_name": "Trgo07D"}, headers=hdr)
    assert r.status_code == 200


def test_duplicate_409_includes_existing_profile_for_informed_decision(client):
    """REM-96/REM-97: the 409 must carry enough of the existing facilitator's
    profile (rank, type, subject areas, active status, last-updated) that a
    caller can render an informed same-vs-different-person comparison without
    a second request -- and the message text itself must surface the rank
    (REM-96's specific ask), since that's the single most useful distinguisher
    between two same-named facilitators. Does not block creation -- the
    confirm_duplicate bypass must still work exactly as before."""
    hdr = _sqn_admin(client)
    r1 = client.post("/api/facilitators", json={
        "first_name": "Alex", "last_name": "Trgo96", "current_rank": "CUO",
        "type": "Senior Cadet", "subject_areas": ["Drill"],
    }, headers=hdr)
    assert r1.status_code == 200, r1.text

    r2 = client.post("/api/facilitators", json={
        "first_name": "Alex", "last_name": "Trgo96", "current_rank": "CSGT",
    }, headers=hdr)
    assert r2.status_code == 409
    detail = r2.json()["detail"]
    assert detail["existing_rank"] == "CUO"
    assert detail["existing_type"] == "Senior Cadet"
    assert "Drill" in detail["existing_subject_areas"]
    assert detail["existing_active_status"] is True
    assert detail["existing_updated_at"], "must include a timestamp for a 'last-updated' display"
    assert "CUO" in detail["message"], "the existing facilitator's rank must appear in the warning text itself"

    # confirm_duplicate bypass must still work unmodified.
    r3 = client.post("/api/facilitators", json={
        "first_name": "Alex", "last_name": "Trgo96", "current_rank": "CSGT", "confirm_duplicate": True,
    }, headers=hdr)
    assert r3.status_code == 200, r3.text
    assert r3.json()["facilitator_id"] != r1.json()["facilitator_id"]


def test_duplicate_check_is_scoped_per_squadron(client):
    """Same name in a different squadron must not be blocked -- this is a
    per-squadron roster check, not a global one."""
    hdr703 = login(client, "ADMIN703")
    hdr704 = login(client, "ADMIN704")
    r1 = client.post("/api/facilitators", json={"first_name": "Jordan", "last_name": "Trgo07E"}, headers=hdr703)
    assert r1.status_code == 200

    r2 = client.post("/api/facilitators", json={"first_name": "Jordan", "last_name": "Trgo07E"}, headers=hdr704)
    assert r2.status_code == 200
