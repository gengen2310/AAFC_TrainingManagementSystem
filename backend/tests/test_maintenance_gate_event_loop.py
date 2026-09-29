"""maintenance_gate must never do synchronous DB work on the event loop.

Found by the 250-user load test (2026-09-29): _maintenance_active() opened a
synchronous DB session inside async middleware. Under connection-pool
saturation every request blocked the event loop for up to DB_POOL_TIMEOUT, the
failure was swallowed (no cache refresh), so the next request blocked again;
gunicorn's heartbeat starved and both workers hit WORKER TIMEOUT together.
A/B probe: /api/health (no DB work) exceeded 60 s under pool saturation.
"""
import asyncio

import app.main as main


def test_maintenance_check_runs_off_the_event_loop(client, monkeypatch):
    seen = []

    def fake_check():
        try:
            asyncio.get_running_loop()
            seen.append("ON_EVENT_LOOP")
        except RuntimeError:
            seen.append("off_loop")
        return False, "", False, False, "normal", None

    monkeypatch.setattr(main, "_maintenance_active", fake_check)
    assert client.get("/api/health").status_code == 200
    assert seen and all(s == "off_loop" for s in seen), seen


def test_db_failure_keeps_last_known_state_and_backs_off(monkeypatch):
    calls = {"n": 0}

    class Boom:
        def __enter__(self):
            calls["n"] += 1
            raise TimeoutError("QueuePool limit reached")  # what pool exhaustion raises

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(main, "SessionLocal", lambda: Boom())
    monkeypatch.setitem(main._maint_cache, "active", True)       # maintenance was ON
    monkeypatch.setitem(main._maint_cache, "pending_until", None)
    monkeypatch.setitem(main._maint_cache, "expires", 0.0)       # cache expired

    first = main._maintenance_active()
    second = main._maintenance_active()

    assert first[0] is True and first[4] == "locked", "must not fail open during maintenance"
    assert second[0] is True
    assert calls["n"] == 1, "a failed check must back off, not retry the DB on every request"
