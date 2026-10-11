"""D14 (2026-10-11): the DB-backed API limiters lost increments under concurrency.

check_api_rate_db / check_user_api_rate_db read the row, added one in Python
and committed (read-modify-write), so concurrent requests overwrote each
other's counts: 16 threads x 25 requests recorded 25-36 instead of 400. With
several gunicorn workers that makes the shared 300/60 s limit many times
weaker than configured, and two workers inserting the first row for a new
key could raise IntegrityError (an unhandled 500 in the middleware).

Each request is now one atomic UPDATE inside the live window, or a window
(re)start that tolerates a concurrent insert.
"""
import threading
import uuid

import pytest

from app.database import SessionLocal
from app.models import IpApiRequest, UserApiRequest
from app.security import check_api_rate_db, check_user_api_rate_db

THREADS, PER_THREAD = 12, 20


def _hammer(fn, key):
    errors = []

    def worker():
        for _ in range(PER_THREAD):
            db = SessionLocal()
            try:
                fn(key, db)
            except Exception as e:  # noqa: BLE001 - any error is the finding
                errors.append(repr(e))
            finally:
                db.close()

    threads = [threading.Thread(target=worker) for _ in range(THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return errors


@pytest.mark.parametrize("fn,model,keycol", [
    (check_api_rate_db, IpApiRequest, "ip"),
    (check_user_api_rate_db, UserApiRequest, "user_id"),
])
def test_concurrent_requests_are_all_counted(client, fn, model, keycol):
    key = f"d14-{uuid.uuid4()}"
    errors = _hammer(fn, key)
    db = SessionLocal()
    try:
        row = db.get(model, key)
        assert errors == []
        assert row is not None and row.request_count == THREADS * PER_THREAD
    finally:
        db.query(model).filter(getattr(model, keycol) == key).delete()
        db.commit()
        db.close()
