"""Idempotency must hold across gunicorn workers (production runs 2).

The Idempotency-Key dedup for POST /api/facilitators lived in a per-process
dict (security._idempotency_cache). A client retry routed to the OTHER worker
found an empty cache and created a duplicate facilitator -- exactly the
"request the client believes failed but the server completed" case the key
exists for. The dedup is now a database claim row, shared by every worker.
"""
import uuid

from app.database import SessionLocal
from app.models import Facilitator
from tests.conftest import login


def _other_worker():
    """A second worker starts with an empty in-process cache."""
    from app import security
    if hasattr(security, "reset_idempotency_cache"):
        security.reset_idempotency_cache()


def _count(last):
    db = SessionLocal()
    try:
        return db.query(Facilitator).filter(Facilitator.last_name == last).count()
    finally:
        db.close()


def test_retry_on_another_worker_returns_the_first_result_and_creates_nothing(client):
    h = login(client, "ADMIN703")
    last = f"Idem{uuid.uuid4().hex[:8]}"
    key = str(uuid.uuid4())
    body = {"first_name": "Retry", "last_name": last, "confirm_duplicate": True}
    r1 = client.post("/api/facilitators", json=body, headers={**h, "Idempotency-Key": key})
    assert r1.status_code == 200, r1.text
    _other_worker()
    r2 = client.post("/api/facilitators", json=body, headers={**h, "Idempotency-Key": key})
    assert r2.status_code == 200, r2.text
    assert r2.json()["facilitator_id"] == r1.json()["facilitator_id"]
    assert _count(last) == 1, "a retried request must not create a second facilitator"


def test_same_key_from_another_user_is_independent(client):
    key = str(uuid.uuid4())
    last = f"IdemU{uuid.uuid4().hex[:8]}"
    body = {"first_name": "Scope", "last_name": last, "confirm_duplicate": True}
    a = client.post("/api/facilitators", json=body, headers={**login(client, "ADMIN703"), "Idempotency-Key": key})
    b = client.post("/api/facilitators", json={**body, "first_name": "Other"},
                    headers={**login(client, "ADMIN7WG"), "Idempotency-Key": key})
    assert a.status_code == 200
    assert b.status_code in (200, 400, 403)        # wing_admin may lack a squadron scope
    if b.status_code == 200:
        assert b.json()["facilitator_id"] != a.json()["facilitator_id"]


def test_add_anyway_after_a_duplicate_warning_reuses_the_key_and_succeeds(client):
    """The real TMS flow: the first submit gets 409 possible_duplicate, the user
    clicks "Add anyway", and the client resubmits with the SAME key plus
    confirm_duplicate=true (connected-frontend keeps _facIdemKey until success).
    A failed request must release its claim or that resubmit would be refused."""
    h = login(client, "ADMIN703")
    last = f"IdemD{uuid.uuid4().hex[:8]}"
    assert client.post("/api/facilitators", json={"first_name": "Dup", "last_name": last},
                       headers=h).status_code == 200                      # existing person
    key = str(uuid.uuid4())
    warn = client.post("/api/facilitators", json={"first_name": "Dup", "last_name": last},
                       headers={**h, "Idempotency-Key": key})
    assert warn.status_code == 409 and warn.json()["detail"]["error"] == "possible_duplicate"
    _other_worker()
    anyway = client.post("/api/facilitators", json={"first_name": "Dup", "last_name": last, "confirm_duplicate": True},
                         headers={**h, "Idempotency-Key": key})
    assert anyway.status_code == 200, anyway.text
    assert _count(last) == 2
    again = client.post("/api/facilitators", json={"first_name": "Dup", "last_name": last, "confirm_duplicate": True},
                        headers={**h, "Idempotency-Key": key})            # a network retry of "Add anyway"
    assert again.json()["facilitator_id"] == anyway.json()["facilitator_id"]
    assert _count(last) == 2


def test_claim_in_progress_is_reported_not_duplicated():
    """Two workers racing on the same key: the loser does not run the handler."""
    from app.services_idempotency import claim, complete
    db1, db2 = SessionLocal(), SessionLocal()
    try:
        k = f"race:{uuid.uuid4()}"
        assert claim(db1, k) is None                 # first worker owns it
        assert claim(db2, k) == "in_progress"        # second worker must not run
        complete(db1, k, 200, {"ok": True, "facilitator_id": "f1"})
        assert claim(db2, k) == (200, {"ok": True, "facilitator_id": "f1"})
    finally:
        db1.close(); db2.close()
