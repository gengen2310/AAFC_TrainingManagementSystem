"""A worker must not keep refusing writes after maintenance has been turned off.

Each worker caches the maintenance state for 10 s. Turning maintenance off
invalidates the cache only in the worker that served the request, so every
other worker kept answering 503 for up to 10 s (observed in the national
qualification drill). Now, before refusing, the gate re-reads the state if its
copy is more than REVALIDATE_BEFORE_REFUSAL_SEC old: the lag drops to <= 1 s,
normal traffic (cache says off) never pays for it, and refusals during a real
maintenance window add at most one read per second per worker (single-flight).
"""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import threading
import time

import app.main as main
from tests.conftest import login

LOCKED = dict(active=True, msg="Locked for test", block_reads=False, block_logins=False, pending_until=None)


def _seed_cache(*, age: float, ttl_left: float = 8.0, **state):
    now = time.monotonic()
    main._maint_cache.update(state, fetched_at=now - age, expires=now + ttl_left)


def test_a_stale_locked_copy_does_not_refuse_a_write_once_maintenance_is_off(client):
    hdr = login(client, "ADMIN703")
    _seed_cache(age=5.0, **LOCKED)                     # another worker turned maintenance off 5 s ago
    try:
        r = client.post("/api/subject-area-tags", json={"display_name": f"Reval {time.time_ns()}"}, headers=hdr)
        assert not (r.status_code == 503 and r.json().get("error") == "maintenance_mode"), r.text
    finally:
        main._maint_cache["expires"] = 0.0


class _FakeDB:
    def __init__(self, values, counter):
        self.values, self.counter = values, counter

    def __call__(self):
        return self

    def __enter__(self):
        with self.counter["lock"]:
            self.counter["opens"] += 1
        time.sleep(0.05)
        return self

    def __exit__(self, *a):
        return False

    def get(self, _model, key):
        v = self.values.get(key)
        return None if v is None else SimpleNamespace(value=v)


OFF = {"maintenance_mode": "off", "maintenance_message": "m", "maintenance_block_reads": "false",
       "maintenance_block_logins": "false", "maintenance_pending_until": None}


def test_a_fresh_copy_is_trusted_without_a_database_read(monkeypatch):
    counter = {"opens": 0, "lock": threading.Lock()}
    monkeypatch.setattr(main, "SessionLocal", _FakeDB(OFF, counter))
    _seed_cache(age=0.2, **LOCKED)
    try:
        assert main._confirm_maintenance_before_refusal()[0] is True
        assert counter["opens"] == 0
    finally:
        main._maint_cache["expires"] = 0.0


def test_concurrent_refusals_revalidate_once(monkeypatch):
    counter = {"opens": 0, "lock": threading.Lock()}
    monkeypatch.setattr(main, "SessionLocal", _FakeDB(OFF, counter))
    _seed_cache(age=5.0, **LOCKED)
    try:
        with ThreadPoolExecutor(max_workers=20) as pool:
            results = list(pool.map(lambda _n: main._confirm_maintenance_before_refusal(), range(20)))
        assert counter["opens"] == 1, counter["opens"]
        assert all(r[0] is False for r in results)
    finally:
        main._maint_cache["expires"] = 0.0


class _DownDB(_FakeDB):
    """A database that is unreachable: every checkout attempt fails."""

    def __enter__(self):
        with self.counter["lock"]:
            self.counter["opens"] += 1
        raise ConnectionError("database unavailable")


class _Clock:
    def __init__(self):
        self.now = time.monotonic()

    def monotonic(self):
        return self.now


def test_refusals_during_a_database_outage_honour_the_failure_backoff(monkeypatch):
    # Locked, copy older than the revalidation age, database down. The first
    # refusal tries one re-read; every refusal inside the 2 s backoff must keep
    # the last known state instead of queueing on another failing checkout.
    counter = {"opens": 0, "lock": threading.Lock()}
    monkeypatch.setattr(main, "SessionLocal", _DownDB(OFF, counter))
    _seed_cache(age=5.0, ttl_left=-1.0, **LOCKED)
    try:
        results = [main._confirm_maintenance_before_refusal() for _ in range(20)]
        assert counter["opens"] == 1, counter["opens"]
        assert all(r[0] is True for r in results)          # still locked: last known state
    finally:
        main._maint_cache["expires"] = 0.0


def test_refusals_re_read_once_the_failure_backoff_has_passed(monkeypatch):
    counter = {"opens": 0, "lock": threading.Lock()}
    clock = _Clock()
    monkeypatch.setattr(main, "_time", clock)
    monkeypatch.setattr(main, "SessionLocal", _DownDB(OFF, counter))
    _seed_cache(age=5.0, ttl_left=-1.0, **LOCKED)
    main._maint_cache.update(fetched_at=clock.now - 5.0, expires=clock.now - 1.0)
    try:
        main._confirm_maintenance_before_refusal()
        assert counter["opens"] == 1
        clock.now += 2.5                                    # backoff (2 s) elapsed
        monkeypatch.setattr(main, "SessionLocal", _FakeDB(OFF, counter))
        assert main._confirm_maintenance_before_refusal()[0] is False
        assert counter["opens"] == 2
    finally:
        main._maint_cache["expires"] = 0.0
