"""Per-worker request cap: overload queues or fails fast instead of deadlocking.

National qualification found a pool/thread deadlock: FastAPI runs a sync
dependency (get_principal holds a DB connection) and the sync endpoint as
separate threadpool jobs, so a request holds its connection while waiting for
a thread. Under overload the 7 connections were held by requests waiting for
threads and the 40 threads by requests waiting for connections; the worker
stayed wedged (health timing out) even after load stopped, with 7 sessions
"idle in transaction" in PostgreSQL.

Capping in-flight requests per worker at the pool size means every admitted
request can get its connection; the rest wait asynchronously (no thread, no
connection) and get 503 server_busy if the wait exceeds the queue timeout.
"""
import asyncio

import httpx
import pytest
import sqlalchemy.exc

from app import main
from app.config import settings
from app.main import app

_gate: asyncio.Event | None = None


async def _slow():
    await _gate.wait()
    return {"ok": True}


def _pool_timeout():
    raise sqlalchemy.exc.TimeoutError("QueuePool limit of size 5 overflow 2 reached")


@pytest.fixture
def routes():
    app.add_api_route("/api/__test_slow", _slow, methods=["GET"])
    app.add_api_route("/api/__test_pool_timeout_mw", _pool_timeout, methods=["GET"])
    yield
    app.router.routes = [r for r in app.router.routes
                         if getattr(r, "path", "") not in ("/api/__test_slow", "/api/__test_pool_timeout_mw")]


async def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def test_requests_beyond_the_cap_wait_then_get_503(routes, monkeypatch):
    monkeypatch.setattr(settings, "REQUEST_CONCURRENCY", 1)
    monkeypatch.setattr(settings, "REQUEST_QUEUE_TIMEOUT_SEC", 0.2)
    main.reset_request_slots()

    async def scenario():
        global _gate
        _gate = asyncio.Event()
        async with await _client() as c:
            first = asyncio.create_task(c.get("/api/__test_slow"))
            await asyncio.sleep(0.05)                      # first now holds the only slot
            second = await c.get("/api/__test_slow")       # waits 0.2 s, then 503
            _gate.set()
            return (await first), second
    first, second = asyncio.run(scenario())
    main.reset_request_slots()
    assert first.status_code == 200
    assert second.status_code == 503 and second.json()["error"] == "server_busy"
    assert int(second.headers["Retry-After"]) > 0


def test_a_queued_request_runs_when_a_slot_frees(routes, monkeypatch):
    monkeypatch.setattr(settings, "REQUEST_CONCURRENCY", 1)
    monkeypatch.setattr(settings, "REQUEST_QUEUE_TIMEOUT_SEC", 5)
    main.reset_request_slots()

    async def scenario():
        global _gate
        _gate = asyncio.Event()
        async with await _client() as c:
            first = asyncio.create_task(c.get("/api/__test_slow"))
            await asyncio.sleep(0.05)
            second = asyncio.create_task(c.get("/api/__test_slow"))
            await asyncio.sleep(0.05)
            _gate.set()                                     # first finishes, second admitted
            return await first, await second
    a, b = asyncio.run(scenario())
    main.reset_request_slots()
    assert a.status_code == 200 and b.status_code == 200


def test_health_is_never_queued(routes, monkeypatch):
    monkeypatch.setattr(settings, "REQUEST_CONCURRENCY", 1)
    monkeypatch.setattr(settings, "REQUEST_QUEUE_TIMEOUT_SEC", 0.1)
    main.reset_request_slots()

    async def scenario():
        global _gate
        _gate = asyncio.Event()
        async with await _client() as c:
            busy = asyncio.create_task(c.get("/api/__test_slow"))
            await asyncio.sleep(0.05)
            h = await c.get("/api/health")
            _gate.set()
            await busy
            return h
    h = asyncio.run(scenario())
    main.reset_request_slots()
    assert h.status_code == 200


def test_pool_timeout_raised_below_the_handlers_is_503_not_500(routes):
    main.reset_request_slots()

    async def scenario():
        async with await _client() as c:
            return await c.get("/api/__test_pool_timeout_mw")
    r = asyncio.run(scenario())
    assert r.status_code == 503 and r.json()["error"] == "server_busy"
