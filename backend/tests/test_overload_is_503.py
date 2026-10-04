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
