"""Tests for lesson outcome endpoints: needs-attention, deliver, cancel, reschedule."""
import pytest
from conftest import login


# ── Helpers ─────────────────────────────────────────────────────────────────

def _get_session_id(client, headers):
    """Return a session id from any existing parade night."""
    pns = client.get("/api/parade-nights", headers=headers).json()
    for pn in (pns if isinstance(pns, list) else []):
        for s in pn.get("sessions", []):
            return s["session_id"]
    return None


def _get_past_pn_id(client, headers):
    """Return a parade-night id whose date is in the past, or None."""
    import datetime
    today = str(datetime.date.today())
    pns = client.get("/api/parade-nights", headers=headers).json()
    for pn in (pns if isinstance(pns, list) else []):
        if pn.get("date", "9999") < today:
            return pn["parade_night_id"]
    return None


def _get_any_pn_id(client, headers):
    pns = client.get("/api/parade-nights", headers=headers).json()
    for pn in (pns if isinstance(pns, list) else []):
        return pn["parade_night_id"]
    return None


# ── needs-attention ──────────────────────────────────────────────────────────

def test_needs_attention_ok(client):
    h = login(client, "ADMIN703")
    r = client.get("/api/sessions/needs-attention", headers=h)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_needs_attention_forbidden_sqn_general(client):
    h_g = login(client, "703SQN2026")  # sqn_general seed code
    r = client.get("/api/sessions/needs-attention", headers=h_g)
    assert r.status_code == 403


def test_needs_attention_unauthenticated(client):
    r = client.get("/api/sessions/needs-attention")
    assert r.status_code == 401


# ── deliver ──────────────────────────────────────────────────────────────────

def test_deliver_session_ok(client):
    """Delivering a session sets status=delivered and returns outcomes_created."""
    from app.database import SessionLocal
    from app.models.training import Session as Sess, ParadeNight
    import datetime

    h = login(client, "ADMIN703")
    db = SessionLocal()
    try:
        # Find a planned session on a past parade night
        today = str(datetime.date.today())
        row = (
            db.query(Sess, ParadeNight)
            .join(ParadeNight, Sess.parade_night_id == ParadeNight.id)
            .filter(
                Sess.is_archived == False,  # noqa: E712
                Sess.status.in_(["planned", "published"]),
                ParadeNight.date < today,
            )
            .first()
        )
        if not row:
            pytest.skip("no past planned session in seed data")
        session_id = row[0].id
    finally:
        db.close()

    r = client.post(
        f"/api/sessions/{session_id}/deliver",
        json={"delivery_note": "Delivered on schedule. Good engagement."},
        headers=h,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "outcomes_created" in body


def test_deliver_session_missing_note(client):
    """Deliver without a delivery_note returns 400."""
    h = login(client, "ADMIN703")
    sid = _get_session_id(client, h)
    if not sid:
        pytest.skip("no session in seed")
    r = client.post(f"/api/sessions/{sid}/deliver", json={"delivery_note": ""}, headers=h)
    assert r.status_code in (400, 422)


def test_deliver_session_unauthenticated(client):
    r = client.post("/api/sessions/fake-id/deliver", json={"delivery_note": "x"})
    assert r.status_code == 401


# ── cancel ───────────────────────────────────────────────────────────────────

def test_cancel_session_ok(client):
    from app.database import SessionLocal
    from app.models.training import Session as Sess, ParadeNight
    import datetime

    h = login(client, "ADMIN703")
    db = SessionLocal()
    try:
        today = str(datetime.date.today())
        row = (
            db.query(Sess, ParadeNight)
            .join(ParadeNight, Sess.parade_night_id == ParadeNight.id)
            .filter(
                Sess.is_archived == False,  # noqa: E712
                Sess.status.in_(["planned", "published"]),
                ParadeNight.date < today,
            )
            .first()
        )
        if not row:
            pytest.skip("no past planned session in seed data")
        session_id = row[0].id
    finally:
        db.close()

    r = client.post(
        f"/api/sessions/{session_id}/cancel",
        json={"cancellation_reason": "Venue unavailable"},
        headers=h,
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_cancel_session_missing_reason(client):
    h = login(client, "ADMIN703")
    sid = _get_session_id(client, h)
    if not sid:
        pytest.skip("no session in seed")
    r = client.post(f"/api/sessions/{sid}/cancel", json={"cancellation_reason": ""}, headers=h)
    assert r.status_code in (400, 422)


def test_cancel_session_unauthenticated(client):
    r = client.post("/api/sessions/fake-id/cancel", json={"cancellation_reason": "x"})
    assert r.status_code == 401


# ── reschedule ───────────────────────────────────────────────────────────────

def test_reschedule_requires_cancelled_session(client):
    """Rescheduling a non-cancelled session returns 409."""
    from app.database import SessionLocal
    from app.models.training import Session as Sess

    h = login(client, "ADMIN703")
    db = SessionLocal()
    try:
        sess = db.query(Sess).filter(
            Sess.is_archived == False,  # noqa: E712
            Sess.status == "planned",
        ).first()
        if not sess:
            pytest.skip("no planned session in seed")
        session_id = sess.id
    finally:
        db.close()

    pn_id = _get_any_pn_id(client, h)
    if not pn_id:
        pytest.skip("no parade night in seed")

    r = client.post(
        f"/api/sessions/{session_id}/reschedule",
        json={"parade_night_id": pn_id, "period_number": 1},
        headers=h,
    )
    assert r.status_code == 409


def test_reschedule_cancelled_session_ok(client):
    """Cancel then reschedule a session — creates replacement with rescheduled_to_session_id link."""
    from app.database import SessionLocal
    from app.models.training import Session as Sess, ParadeNight
    import datetime

    h = login(client, "ADMIN703")
    db = SessionLocal()
    try:
        today = str(datetime.date.today())
        row = (
            db.query(Sess, ParadeNight)
            .join(ParadeNight, Sess.parade_night_id == ParadeNight.id)
            .filter(
                Sess.is_archived == False,  # noqa: E712
                Sess.status.in_(["planned", "published"]),
                ParadeNight.date < today,
            )
            .first()
        )
        if not row:
            pytest.skip("no past planned session")
        session_id = row[0].id
    finally:
        db.close()

    # Cancel first
    r = client.post(
        f"/api/sessions/{session_id}/cancel",
        json={"cancellation_reason": "Weather"},
        headers=h,
    )
    assert r.status_code == 200

    pn_id = _get_any_pn_id(client, h)
    if not pn_id:
        pytest.skip("no parade night available")

    r2 = client.post(
        f"/api/sessions/{session_id}/reschedule",
        json={"parade_night_id": pn_id, "period_number": 1},
        headers=h,
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["ok"] is True
    assert body["original_session_id"] == session_id
    assert body["new_session_id"] != session_id

    # Verify link persisted
    db2 = SessionLocal()
    try:
        original = db2.get(Sess, session_id)
        assert original.rescheduled_to_session_id == body["new_session_id"]
    finally:
        db2.close()


def test_reschedule_unauthenticated(client):
    r = client.post("/api/sessions/fake-id/reschedule", json={"parade_night_id": "x"})
    assert r.status_code == 401


# ── session history ──────────────────────────────────────────────────────────

def test_session_history_ok(client):
    h = login(client, "ADMIN703")
    sid = _get_session_id(client, h)
    if not sid:
        pytest.skip("no session in seed")
    r = client.get(f"/api/sessions/{sid}/history", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert "session_id" in body
    assert "history" in body


def test_session_history_unauthenticated(client):
    r = client.get("/api/sessions/fake-id/history")
    assert r.status_code == 401


# ── previous deliveries ──────────────────────────────────────────────────────

def test_previous_deliveries_ok(client):
    from app.database import SessionLocal
    from app.models.training import CurriculumItem

    h = login(client, "ADMIN703")
    db = SessionLocal()
    try:
        ci = db.query(CurriculumItem).filter(CurriculumItem.is_archived == False).first()  # noqa: E712
        if not ci:
            pytest.skip("no curriculum items in seed")
        item_id = ci.id
    finally:
        db.close()

    r = client.get(f"/api/curriculum-items/{item_id}/previous-deliveries", headers=h)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_previous_deliveries_unauthenticated(client):
    r = client.get("/api/curriculum-items/fake-id/previous-deliveries")
    assert r.status_code == 401


# ── cadet outcome override ───────────────────────────────────────────────────

def test_outcome_override_unauthenticated(client):
    r = client.post("/api/cadets/x/session-outcomes/y", json={"status": "absent"})
    assert r.status_code == 401


def test_outcome_override_ok(client):
    """Manual outcome override creates a CadetSessionOutcome row."""
    from app.database import SessionLocal
    from app.models.training import Cadet, Session as Sess, CadetSessionOutcome

    h = login(client, "ADMIN703")
    db = SessionLocal()
    try:
        cadet = db.query(Cadet).filter(Cadet.is_archived == False).first()  # noqa: E712
        sess = db.query(Sess).filter(Sess.is_archived == False).first()  # noqa: E712
        if not cadet or not sess:
            pytest.skip("no cadet or session in seed")
        cadet_id, session_id = cadet.id, sess.id
    finally:
        db.close()

    r = client.post(
        f"/api/cadets/{cadet_id}/session-outcomes/{session_id}",
        json={"status": "absent", "override_reason": "Medical absence"},
        headers=h,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert "outcome_id" in body

    db2 = SessionLocal()
    try:
        outcome = db2.get(CadetSessionOutcome, body["outcome_id"])
        assert outcome is not None
        assert outcome.status == "absent"
        assert outcome.source == "manual"
    finally:
        db2.close()
