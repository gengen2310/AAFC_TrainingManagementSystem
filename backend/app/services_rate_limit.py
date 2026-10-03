"""Fixed-window rate limiting shared across workers (database-backed).

Per-process counters undercount by the number of gunicorn workers and reset
on every restart. Used for limits that protect people rather than capacity --
e.g. forgot-code, where the limit resists address probing and mail-bombing a
recovery mailbox.
"""
from datetime import timedelta

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from .database import utcnow
from .models import RateLimitBucket


def hit(db: DBSession, key: str, *, limit: int, window_seconds: int) -> bool:
    """Record one hit; return True while the key is within its limit."""
    now = utcnow().replace(tzinfo=None)
    window_open = now - timedelta(seconds=window_seconds)
    for _ in range(3):
        # Atomic increment inside the current window: no read-modify-write race.
        res = db.execute(update(RateLimitBucket)
                         .where(RateLimitBucket.key == key, RateLimitBucket.window_start > window_open)
                         .values(count=RateLimitBucket.count + 1))
        if res.rowcount:
            db.commit()
            return db.get(RateLimitBucket, key).count <= limit
        # No live window: start one (replacing an expired row).
        db.query(RateLimitBucket).filter(RateLimitBucket.key == key).delete()
        db.add(RateLimitBucket(key=key, window_start=now, count=1))
        try:
            db.commit()
            return 1 <= limit
        except IntegrityError:          # another worker started the window first
            db.rollback()
    return False


def reset_all(db: DBSession) -> None:
    db.query(RateLimitBucket).delete()
    db.commit()
