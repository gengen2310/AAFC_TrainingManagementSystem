"""Regression coverage for maintenance-cache expiry concurrency.

The cache exists specifically to avoid a database checkout on every request.
At an expiry boundary, many simultaneous requests must collapse to one refresh
rather than recreating pool exhaustion every ten seconds.
"""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import threading
import time

import app.main as main


def test_expired_maintenance_cache_refreshes_database_once(monkeypatch):
    opens = 0
    count_lock = threading.Lock()

    values = {
        "maintenance_mode": "off",
        "maintenance_message": "Maintenance",
        "maintenance_block_reads": "false",
        "maintenance_block_logins": "false",
        "maintenance_pending_until": None,
    }

    class FakeSession:
        def __enter__(self):
            nonlocal opens
            with count_lock:
                opens += 1
            # Keep the first refresher inside the critical section long enough
            # for the remaining workers to reach the same expired boundary.
            time.sleep(0.05)
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, _model, key):
            value = values.get(key)
            return None if value is None else SimpleNamespace(value=value)

    monkeypatch.setattr(main, "SessionLocal", FakeSession)
    main._maint_cache.update({
        "active": False,
        "msg": "",
        "block_reads": False,
        "block_logins": False,
        "pending_until": None,
        "expires": 0.0,
    })

    try:
        with ThreadPoolExecutor(max_workers=20) as pool:
            results = list(pool.map(lambda _n: main._maintenance_active(), range(20)))

        assert opens == 1, f"expected one DB refresh at expiry, got {opens}"
        assert all(r == results[0] for r in results)
        assert results[0][0] is False
        assert results[0][4] == "normal"
    finally:
        # Do not leave the synthetic cache fresh for unrelated tests.
        main._maint_cache["expires"] = 0.0
