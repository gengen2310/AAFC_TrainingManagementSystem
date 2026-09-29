"""Tests for SessionAssistantFacilitator join table and related CRUD endpoints."""
from conftest import login


# ── Task 1 Tests ────────────────────────────────────────────────────────────

def test_session_assistant_facilitator_table_exists(client):
    """The session_assistant_facilitators table is accessible via the ORM."""
    from app.models.training import SessionAssistantFacilitator
    assert SessionAssistantFacilitator.__tablename__ == "session_assistant_facilitators"


def test_assistant_facilitator_backfill(client):
    """Backfill logic: run it, then assert every session with assistant_facilitator_id has a SAF row.

    The test DB is built from SQLAlchemy metadata (not Alembic), so the v64
    migration's INSERT never runs automatically. This test also replicates the
    backfill logic — verifying it is idempotent and correct — before asserting.
    """
    import uuid
    import sqlalchemy as sa
    from app.models.training import Session, SessionAssistantFacilitator
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        # Replicate v64 SQLite backfill (idempotent via INSERT OR IGNORE)
        rows = db.execute(sa.text(
            "SELECT id, assistant_facilitator_id FROM sessions "
            "WHERE assistant_facilitator_id IS NOT NULL AND is_archived = 0"
        )).fetchall()
        for row in rows:
            db.execute(sa.text(
                "INSERT OR IGNORE INTO session_assistant_facilitators "
                "(id, session_id, user_id, created_at) "
                "VALUES (:id, :sid, :uid, CURRENT_TIMESTAMP)"
            ), {"id": str(uuid.uuid4()), "sid": row[0], "uid": row[1]})
        db.commit()

        # Now verify
        sessions_with_asst = db.query(Session).filter(
            Session.assistant_facilitator_id.isnot(None),
            Session.is_archived.is_(False),
        ).all()
        for s in sessions_with_asst:
            saf = db.query(SessionAssistantFacilitator).filter_by(
                session_id=s.id, user_id=s.assistant_facilitator_id
            ).first()
            assert saf is not None, (
                f"Session {s.id} missing SAF row for {s.assistant_facilitator_id}"
            )
    finally:
        db.close()


# ── Task 7 Tests ────────────────────────────────────────────────────────────

def _get_sqn_id(client, headers, code="703"):
    r = client.get("/api/squadrons", headers=headers)
    for s in r.json():
        if s["code"] == code:
            return s["squadron_id"]
    return None


def _get_or_create_session_id(client, headers):
    """Get a session ID from an existing parade night, or create one."""
    pns = client.get("/api/parade-nights", headers=headers).json()
    for pn in pns:
        if pn.get("sessions"):
            return pn["sessions"][0]["session_id"]
    return None


def test_add_assistant_facilitator(client):
    """POST /sessions/{id}/assistants adds an assistant facilitator row."""
    from app.models.training import SessionAssistantFacilitator
    from app.database import SessionLocal

    h = login(client, "ADMIN703")
    # Find a session to use
    sess_id = _get_or_create_session_id(client, h)
    if sess_id is None:
        import pytest
        pytest.skip("No sessions available in test DB")

    # Get a facilitator user to add as assistant
    facs = client.get("/api/facilitators", headers=h).json()
    if not facs:
        import pytest
        pytest.skip("No facilitators available in test DB")
    fac_id = facs[0]["facilitator_id"]

    r = client.post(
        f"/api/training/sessions/{sess_id}/assistants",
        headers=h,
        json={"user_id": fac_id},
    )
    assert r.status_code in (200, 201), r.text

    db = SessionLocal()
    try:
        saf = db.query(SessionAssistantFacilitator).filter_by(
            session_id=sess_id, user_id=fac_id
        ).first()
        assert saf is not None, "SAF row not found after adding assistant"
    finally:
        db.close()


def test_add_duplicate_assistant_is_idempotent(client):
    """Adding the same assistant twice does not raise an error."""
    h = login(client, "ADMIN703")
    sess_id = _get_or_create_session_id(client, h)
    if sess_id is None:
        import pytest
        pytest.skip("No sessions available in test DB")

    facs = client.get("/api/facilitators", headers=h).json()
    if not facs:
        import pytest
        pytest.skip("No facilitators available in test DB")
    fac_id = facs[0]["facilitator_id"]

    client.post(f"/api/training/sessions/{sess_id}/assistants",
                headers=h, json={"user_id": fac_id})
    r = client.post(f"/api/training/sessions/{sess_id}/assistants",
                    headers=h, json={"user_id": fac_id})
    assert r.status_code in (200, 201), f"Duplicate add returned {r.status_code}: {r.text}"


def test_delete_assistant_facilitator(client):
    """DELETE /sessions/{id}/assistants/{user_id} removes the row."""
    from app.models.training import SessionAssistantFacilitator
    from app.database import SessionLocal

    h = login(client, "ADMIN703")
    sess_id = _get_or_create_session_id(client, h)
    if sess_id is None:
        import pytest
        pytest.skip("No sessions available in test DB")

    facs = client.get("/api/facilitators", headers=h).json()
    if not facs:
        import pytest
        pytest.skip("No facilitators available in test DB")
    fac_id = facs[0]["facilitator_id"]

    # Add first
    client.post(f"/api/training/sessions/{sess_id}/assistants",
                headers=h, json={"user_id": fac_id})
    # Then remove
    r = client.delete(
        f"/api/training/sessions/{sess_id}/assistants/{fac_id}",
        headers=h,
    )
    assert r.status_code in (200, 204), r.text

    db = SessionLocal()
    try:
        saf = db.query(SessionAssistantFacilitator).filter_by(
            session_id=sess_id, user_id=fac_id
        ).first()
        assert saf is None, "SAF row still present after deletion"
    finally:
        db.close()


def test_session_response_includes_assistant_facilitators(client):
    """GET /api/sessions/{id} includes assistant_facilitators list."""
    h = login(client, "ADMIN703")
    sess_id = _get_or_create_session_id(client, h)
    if sess_id is None:
        import pytest
        pytest.skip("No sessions available in test DB")

    r = client.get(f"/api/training/sessions/{sess_id}", headers=h)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "assistant_facilitators" in data, "assistant_facilitators missing from session response"
    assert isinstance(data["assistant_facilitators"], list)


def _put_session_payload(detail: dict, assistant_ids: list[str]) -> dict:
    """Build the legacy PUT /api/sessions body from a session detail response."""
    return {
        "parade_night_id": detail["parade_night_id"],
        "period_number": detail.get("period_number") or 1,
        "cadet_group": detail.get("cadet_group"),
        "phase_at_time": detail.get("phase_at_time"),
        "curriculum_item_id": detail.get("curriculum_item_id"),
        "custom_title": detail.get("custom_title"),
        "facilitator_id": detail.get("facilitator_id"),
        "assistant_facilitator_ids": assistant_ids,
        "training_area_id": detail.get("training_area_id"),
        "expected_attendance": detail.get("expected_attendance"),
        "version": detail.get("version"),
        "timing_block_id": detail.get("timing_block_id"),
    }


def test_put_session_persists_and_clears_plural_assistants(client):
    """Regression for PR65 review: Quick Edit plural assistant saves must not be a no-op."""
    from app.database import SessionLocal
    from app.models.training import SessionAssistantFacilitator

    h = login(client, "ADMIN703")
    sess_id = _get_or_create_session_id(client, h)
    if sess_id is None:
        import pytest
        pytest.skip("No sessions available in test DB")

    facs = client.get("/api/facilitators", headers=h).json()
    if len(facs) < 2:
        import pytest
        pytest.skip("Need at least two facilitators")
    assistant_ids = [facs[0]["facilitator_id"], facs[1]["facilitator_id"]]

    detail = client.get(f"/api/training/sessions/{sess_id}", headers=h).json()
    # Do not assign the current lead as its own assistant.
    assistant_ids = [x for x in assistant_ids if x != detail.get("facilitator_id")]
    if not assistant_ids:
        import pytest
        pytest.skip("No non-lead facilitator available")

    r = client.put(
        f"/api/sessions/{sess_id}",
        headers=h,
        json=_put_session_payload(detail, assistant_ids),
    )
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        stored = {
            row.user_id for row in db.query(SessionAssistantFacilitator)
            .filter(SessionAssistantFacilitator.session_id == sess_id).all()
        }
        assert stored == set(assistant_ids)
    finally:
        db.close()

    detail2 = client.get(f"/api/training/sessions/{sess_id}", headers=h).json()
    r = client.put(
        f"/api/sessions/{sess_id}",
        headers=h,
        json=_put_session_payload(detail2, []),
    )
    assert r.status_code == 200, r.text

    db = SessionLocal()
    try:
        assert db.query(SessionAssistantFacilitator).filter(
            SessionAssistantFacilitator.session_id == sess_id
        ).count() == 0
    finally:
        db.close()


def test_parade_night_list_returns_canonical_assistant_shape(client):
    """Main TMS list response must expose existing assistants for Quick Edit preselection."""
    h = login(client, "ADMIN703")
    sess_id = _get_or_create_session_id(client, h)
    if sess_id is None:
        import pytest
        pytest.skip("No sessions available in test DB")
    facs = client.get("/api/facilitators", headers=h).json()
    if not facs:
        import pytest
        pytest.skip("No facilitators available in test DB")
    fac_id = facs[0]["facilitator_id"]

    r = client.post(
        f"/api/training/sessions/{sess_id}/assistants",
        headers=h,
        json={"user_id": fac_id},
    )
    assert r.status_code in (200, 201), r.text

    pns = client.get("/api/parade-nights", headers=h)
    assert pns.status_code == 200, pns.text
    found = None
    for pn in pns.json():
        for session in pn.get("sessions", []):
            if session.get("session_id") == sess_id:
                found = session
                break
    assert found is not None
    assistants = found.get("assistant_facilitators")
    assert isinstance(assistants, list)
    assert any(
        a.get("user_id") == fac_id and a.get("facilitator_id") == fac_id
        for a in assistants
    )

