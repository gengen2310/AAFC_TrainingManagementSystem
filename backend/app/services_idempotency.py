"""Idempotency-Key deduplication shared across workers (database-backed).

Production runs several gunicorn workers. The previous per-process dict let a
retry that reached a different worker create a duplicate write -- the exact
case the key exists for. A row keyed by the scoped key is the claim:

    claim()    -> None            caller owns the key: run the handler
               -> "in_progress"   another request is running it now
               -> (status, body)  already completed: return that response
    complete() -> store the response for later retries
    release()  -> drop the claim when the handler failed, so a fixed retry runs

Each call commits on the session it is given; callers pass a session separate
from the request's own, so a claim is visible to other workers immediately.
"""
import json
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from .database import utcnow
from .models import IdempotencyKey

TTL = timedelta(minutes=5)          # completed responses are replayed this long
ABANDONED_AFTER = timedelta(seconds=60)  # an unfinished claim older than this is reclaimable


def _naive(dt):
    return dt.replace(tzinfo=None) if dt is not None and dt.tzinfo else dt


def claim(db: DBSession, key: str):
    now = utcnow()
    for _ in range(2):
        db.add(IdempotencyKey(key=key, created_at=now, expires_at=now + TTL))
        try:
            db.commit()
            return None
        except IntegrityError:
            db.rollback()
        row = db.get(IdempotencyKey, key)
        if row is None:                       # released between our insert and read
            continue
        expired = _naive(row.expires_at) <= _naive(now)
        abandoned = row.status_code is None and _naive(row.created_at) <= _naive(now - ABANDONED_AFTER)
        if expired or abandoned:
            db.delete(row)
            db.commit()
            continue
        if row.status_code is None:
            return "in_progress"
        return row.status_code, json.loads(row.response_json or "{}")
    return "in_progress"


def complete(db: DBSession, key: str, status_code: int, body: dict) -> None:
    row = db.get(IdempotencyKey, key)
    if row is None:
        return
    row.status_code = status_code
    row.response_json = json.dumps(body)
    row.expires_at = utcnow() + TTL
    db.commit()


def release(db: DBSession, key: str) -> None:
    row = db.get(IdempotencyKey, key)
    if row is not None and row.status_code is None:
        db.delete(row)
        db.commit()
