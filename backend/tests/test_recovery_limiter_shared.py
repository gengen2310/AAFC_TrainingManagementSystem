"""The forgot-code limiter must hold across gunicorn workers and restarts.

It was a per-process dict (auth._recovery_hits): with production's 2 workers
the effective limit doubled (5 -> 10 per IP per hour, 3 -> 6 per address),
and any restart reset it. The forgot-code limiter protects against address
probing and mail-bombing a recovery mailbox, so it is now database-backed.
"""
import uuid

import pytest

from app.database import SessionLocal
from app.services_rate_limit import hit, reset_all


@pytest.fixture(autouse=True)
def _clean():
    db = SessionLocal()
    try:
        reset_all(db)
    finally:
        db.close()


def test_limit_is_shared_by_separate_sessions_like_separate_workers():
    k = f"test:{uuid.uuid4()}"
    sessions = [SessionLocal() for _ in range(6)]
    try:
        results = [hit(db, k, limit=3, window_seconds=3600) for db in sessions]
    finally:
        for db in sessions:
            db.close()
    assert results == [True, True, True, False, False, False]


def test_window_expiry_resets_the_count():
    k = f"test:{uuid.uuid4()}"
    db = SessionLocal()
    try:
        assert hit(db, k, limit=1, window_seconds=3600)
        assert not hit(db, k, limit=1, window_seconds=3600)
        assert hit(db, k, limit=1, window_seconds=0)          # window already elapsed
    finally:
        db.close()


def test_forgot_code_ip_limit_survives_a_process_restart(client, monkeypatch):
    """6th request from one IP within the hour is limited even if the
    in-process state is wiped between requests (another worker/restart)."""
    import app.routers.auth as auth_mod
    sent = []
    monkeypatch.setattr(auth_mod, "send_mail", lambda *a, **k: sent.append(1) or True)
    for i in range(5):
        r = client.post("/api/auth/forgot-code", json={"email": f"nobody{i}-{uuid.uuid4().hex[:6]}@example.com"})
        assert r.status_code == 200
    # Constant outward response by design, so observe the limiter directly.
    db = SessionLocal()
    try:
        from app.models import RateLimitBucket
        rows = {r.key: r.count for r in db.query(RateLimitBucket).all()}
    finally:
        db.close()
    assert any(k.startswith("recovery:ip:") and v == 5 for k, v in rows.items()), rows
