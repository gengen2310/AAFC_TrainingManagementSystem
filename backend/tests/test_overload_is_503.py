"""Database pool exhaustion is overload, not an internal error.

National qualification (250 users, 2 workers, production pool 5+2 per worker)
produced 178 x 500 "internal_error": every one was sqlalchemy.exc.TimeoutError
("QueuePool limit of size 5 overflow 2 reached") after the 30 s pool wait.
Clients and monitoring must see that as capacity -- 503 with Retry-After --
so retries back off and alerts point at sizing, not at a code defect.
"""
import sqlalchemy.exc

from app.main import app


def _boom():
    raise sqlalchemy.exc.TimeoutError("QueuePool limit of size 5 overflow 2 reached")


def test_pool_timeout_returns_503_with_retry_after(client):
    app.add_api_route("/api/__test_pool_timeout", _boom, methods=["GET"])
    try:
        r = client.get("/api/__test_pool_timeout")
        assert r.status_code == 503, r.text
        assert r.json()["error"] == "server_busy"
        assert int(r.headers["Retry-After"]) > 0
    finally:
        app.router.routes = [rt for rt in app.router.routes if getattr(rt, "path", "") != "/api/__test_pool_timeout"]


def _db_down():
    raise sqlalchemy.exc.OperationalError(
        "SELECT 1", {}, Exception('connection to server at "127.0.0.1", port 5432 failed: Connection refused'))


def test_database_unreachable_returns_503_not_500(client):
    """Failure drill: stopping PostgreSQL for 15 s under load returned 466 x 500
    internal_error. An unreachable database is unavailability -- 503 + Retry-After
    -- and the pool recovered by itself once PostgreSQL returned."""
    app.add_api_route("/api/__test_db_down", _db_down, methods=["GET"])
    try:
        r = client.get("/api/__test_db_down")
        assert r.status_code == 503, r.text
        assert r.json()["error"] == "database_unavailable"
        assert int(r.headers["Retry-After"]) > 0
        assert "127.0.0.1" not in r.text and "Connection refused" not in r.text, "no internals in the response"
    finally:
        app.router.routes = [rt for rt in app.router.routes if getattr(rt, "path", "") != "/api/__test_db_down"]
