"""Contract guards: 0..N assistant facilitators via planning CREATE/UPDATE.

Ensures:
- assistant_facilitator_ids is honoured on session create (0, 1, N)
- Duplicates are silently deduplicated
- Nonexistent IDs return 422
- Foreign-squadron IDs return 422
- PATCH replaces the join table
- Singular assistant_facilitator_id syncs to the join table (backward compat)
- _real_session_out includes assistant_facilitators in the response
"""
import pytest
from tests.conftest import login, next_test_year


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _setup_year_with_date(client, hdr):
    year = next_test_year()
    r = client.post(
        "/api/planning/years",
        json={"year": year, "name": f"{year} Asst Fac Test Year"},
        headers=hdr,
    )
    assert r.status_code == 200, r.text
    yr_id = r.json()["planning_year_id"]
    rp = client.post(
        f"/api/planning/years/{yr_id}/parade-dates",
        json={"parade_date": "2028-03-15"},
        headers=hdr,
    )
    assert rp.status_code == 200, rp.text
    pd_id = rp.json()["parade_date_id"]
    return yr_id, pd_id


def _get_facs_for_squadron(sqn_code):
    """Return facilitators belonging to the given squadron directly from the DB."""
    from app.database import SessionLocal
    from app.models import Squadron
    from app.models import Facilitator
    db = SessionLocal()
    try:
        sq = db.query(Squadron).filter(Squadron.code == sqn_code).first()
        if sq is None:
            return []
        facs = db.query(Facilitator).filter(
            Facilitator.squadron_id == sq.id,
            Facilitator.is_archived == False,  # noqa: E712
        ).all()
        return [(f.id, sq.id) for f in facs]
    finally:
        db.close()


# ─────────────────────────────────────────────────────────────
# Contract tests
# ─────────────────────────────────────────────────────────────

def test_create_session_with_zero_assistant_facilitator_ids(client):
    """assistant_facilitator_ids=[] results in no SAF rows and empty list in response."""
    hdr = login(client, "ADMIN703")
    _, pd_id = _setup_year_with_date(client, hdr)

    r = client.post(
        f"/api/planning/parade-dates/{pd_id}/sessions",
        json={"cadet_group": "junior", "session_number": 1,
              "assistant_facilitator_ids": []},
        headers=hdr,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert "assistant_facilitators" in d, "Response must include assistant_facilitators list"
    assert d["assistant_facilitators"] == [], (
        "0 IDs must produce an empty assistant_facilitators list"
    )


def test_create_session_with_one_valid_assistant_facilitator_id(client):
    """assistant_facilitator_ids=[id] writes one SAF row and returns it in assistant_facilitators."""
    facs = _get_facs_for_squadron("703")
    if not facs:
        pytest.skip("No facilitators seeded for squadron 703")

    fac_id = facs[0][0]
    hdr = login(client, "ADMIN703")
    _, pd_id = _setup_year_with_date(client, hdr)

    r = client.post(
        f"/api/planning/parade-dates/{pd_id}/sessions",
        json={"cadet_group": "senior", "session_number": 1,
              "assistant_facilitator_ids": [fac_id]},
        headers=hdr,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert "assistant_facilitators" in d
    assert len(d["assistant_facilitators"]) == 1, (
        "One valid ID must produce exactly one assistant_facilitators entry"
    )
    assert d["assistant_facilitators"][0]["user_id"] == fac_id


def test_create_session_with_multiple_assistant_facilitator_ids(client):
    """assistant_facilitator_ids=[id1, id2, id3] writes three SAF rows."""
    facs = _get_facs_for_squadron("703")
    if len(facs) < 3:
        pytest.skip("Need at least 3 facilitators seeded for squadron 703")

    fac_ids = [facs[0][0], facs[1][0], facs[2][0]]
    hdr = login(client, "ADMIN703")
    _, pd_id = _setup_year_with_date(client, hdr)

    r = client.post(
        f"/api/planning/parade-dates/{pd_id}/sessions",
        json={"cadet_group": "initial", "session_number": 1,
              "assistant_facilitator_ids": fac_ids},
        headers=hdr,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["assistant_facilitators"]) == 3, (
        "Three distinct valid IDs must produce three assistant_facilitators entries"
    )
    returned_ids = {a["user_id"] for a in d["assistant_facilitators"]}
    assert returned_ids == set(fac_ids)


def test_create_session_deduplicates_assistant_facilitator_ids(client):
    """Duplicate IDs in assistant_facilitator_ids produce exactly one SAF row."""
    facs = _get_facs_for_squadron("703")
    if not facs:
        pytest.skip("No facilitators seeded for squadron 703")

    fac_id = facs[0][0]
    hdr = login(client, "ADMIN703")
    _, pd_id = _setup_year_with_date(client, hdr)

    r = client.post(
        f"/api/planning/parade-dates/{pd_id}/sessions",
        json={"cadet_group": "junior", "session_number": 2,
              "assistant_facilitator_ids": [fac_id, fac_id, fac_id]},
        headers=hdr,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["assistant_facilitators"]) == 1, (
        "Duplicate IDs must be deduplicated to a single SAF row"
    )


def test_create_session_rejects_nonexistent_assistant_facilitator_id(client):
    """A nonexistent facilitator ID in assistant_facilitator_ids returns 422."""
    hdr = login(client, "ADMIN703")
    _, pd_id = _setup_year_with_date(client, hdr)

    r = client.post(
        f"/api/planning/parade-dates/{pd_id}/sessions",
        json={"cadet_group": "senior", "session_number": 1,
              "assistant_facilitator_ids": ["00000000-0000-0000-0000-nonexistent00"]},
        headers=hdr,
    )
    assert r.status_code == 422, (
        f"Nonexistent facilitator ID must return 422, got {r.status_code}: {r.text}"
    )


def test_create_session_rejects_foreign_squadron_assistant_facilitator_id(client):
    """A facilitator from a different squadron returns 422 (tenancy violation)."""
    import uuid
    import sqlalchemy as sa
    from app.database import SessionLocal
    from app.models import Squadron

    # Use squadron 702 as the foreign squadron (it has no facilitators seeded,
    # and no test checks it for zero facilitators — unlike 704).
    db = SessionLocal()
    try:
        sq702 = db.query(Squadron).filter(Squadron.code == "702").first()
        if sq702 is None:
            pytest.skip("Squadron 702 not seeded")
        foreign_fac_id = str(uuid.uuid4())
        db.execute(sa.text(
            "INSERT INTO facilitators (id, first_name, last_name, squadron_id, wing_id, type, "
            "active_status, is_archived, max_sessions_per_night, max_sessions_per_month, "
            "created_at, updated_at) "
            "VALUES (:id, :fn, :ln, :sqn, :wing, :type, 1, 0, 2, 8, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ), {"id": foreign_fac_id, "fn": "Foreign", "ln": "Facilitator",
            "sqn": sq702.id, "wing": sq702.wing_id or "test-wing", "type": "Staff"})
        db.commit()
    finally:
        db.close()

    hdr = login(client, "ADMIN703")
    _, pd_id = _setup_year_with_date(client, hdr)

    r = client.post(
        f"/api/planning/parade-dates/{pd_id}/sessions",
        json={"cadet_group": "initial", "session_number": 1,
              "assistant_facilitator_ids": [foreign_fac_id]},
        headers=hdr,
    )
    assert r.status_code == 422, (
        f"Foreign-squadron facilitator must return 422, got {r.status_code}: {r.text}"
    )
    body = r.json()
    assert "foreign_assistant" in str(body), (
        "Error detail must identify the rejection as a foreign-assistant violation"
    )


def test_update_session_replaces_assistant_facilitators_via_plural_field(client):
    """PATCH with assistant_facilitator_ids replaces the existing join table rows."""
    facs = _get_facs_for_squadron("703")
    if len(facs) < 2:
        pytest.skip("Need at least 2 facilitators seeded for squadron 703")

    fac1_id = facs[0][0]
    fac2_id = facs[1][0]
    hdr = login(client, "ADMIN703")
    _, pd_id = _setup_year_with_date(client, hdr)

    # Create with one facilitator.
    rc = client.post(
        f"/api/planning/parade-dates/{pd_id}/sessions",
        json={"cadet_group": "junior", "session_number": 3,
              "assistant_facilitator_ids": [fac1_id]},
        headers=hdr,
    )
    assert rc.status_code == 200, rc.text
    sess_id = rc.json()["session_id"]

    # Update to replace with a different facilitator.
    ru = client.patch(
        f"/api/planning/sessions/{sess_id}",
        json={"assistant_facilitator_ids": [fac2_id]},
        headers=hdr,
    )
    assert ru.status_code == 200, ru.text
    d = ru.json()
    assert "assistant_facilitators" in d
    assert len(d["assistant_facilitators"]) == 1, (
        "PATCH must replace the join table, leaving exactly one entry"
    )
    assert d["assistant_facilitators"][0]["user_id"] == fac2_id, (
        "PATCH must replace old assistant with the new one"
    )


def test_update_session_clears_assistants_with_empty_list(client):
    """PATCH with assistant_facilitator_ids=[] clears all SAF rows."""
    facs = _get_facs_for_squadron("703")
    if not facs:
        pytest.skip("No facilitators seeded for squadron 703")

    fac_id = facs[0][0]
    hdr = login(client, "ADMIN703")
    _, pd_id = _setup_year_with_date(client, hdr)

    rc = client.post(
        f"/api/planning/parade-dates/{pd_id}/sessions",
        json={"cadet_group": "senior", "session_number": 4,
              "assistant_facilitator_ids": [fac_id]},
        headers=hdr,
    )
    assert rc.status_code == 200, rc.text
    sess_id = rc.json()["session_id"]

    ru = client.patch(
        f"/api/planning/sessions/{sess_id}",
        json={"assistant_facilitator_ids": []},
        headers=hdr,
    )
    assert ru.status_code == 200, ru.text
    d = ru.json()
    assert d["assistant_facilitators"] == [], (
        "PATCH with [] must clear all assistant facilitator rows"
    )


def test_create_session_singular_assistant_facilitator_id_syncs_to_join_table(client):
    """Backward-compat: singular assistant_facilitator_id also writes a SAF row."""
    facs = _get_facs_for_squadron("703")
    if not facs:
        pytest.skip("No facilitators seeded for squadron 703")

    fac_id = facs[0][0]
    hdr = login(client, "ADMIN703")
    _, pd_id = _setup_year_with_date(client, hdr)

    r = client.post(
        f"/api/planning/parade-dates/{pd_id}/sessions",
        json={"cadet_group": "initial", "session_number": 5,
              "assistant_facilitator_id": fac_id},
        headers=hdr,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert "assistant_facilitators" in d, "Response must include assistant_facilitators"
    assert len(d["assistant_facilitators"]) == 1, (
        "Singular assistant_facilitator_id must also write a SAF row"
    )
    assert d["assistant_facilitators"][0]["user_id"] == fac_id


def test_create_session_response_includes_assistant_facilitators_field(client):
    """_real_session_out always includes assistant_facilitators (may be empty)."""
    hdr = login(client, "ADMIN703")
    _, pd_id = _setup_year_with_date(client, hdr)

    r = client.post(
        f"/api/planning/parade-dates/{pd_id}/sessions",
        json={"cadet_group": "junior", "session_number": 6},
        headers=hdr,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert "assistant_facilitators" in d, (
        "Every session create response must include assistant_facilitators list"
    )
    assert isinstance(d["assistant_facilitators"], list)
