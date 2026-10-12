"""D19 (2026-10-12): a database outage must never abort a response mid-flight.

Found in the national-scale failure drill (PostgreSQL stopped under 100
users): get_db's teardown called Session.close(), whose rollback raised
OperationalError ("server closed the connection unexpectedly") after the
response had started, so Starlette could not send an error response and
dropped the connection (8 times; the client saw 3 requests with no HTTP
response). Teardown now invalidates the dead connection instead of raising.
"""
import pytest
from sqlalchemy.exc import OperationalError

import app.database as database


class _DeadSession:
    def __init__(self):
        self.invalidated = False

    def close(self):
        raise OperationalError("ROLLBACK", {}, Exception("server closed the connection unexpectedly"))

    def invalidate(self):
        self.invalidated = True


def test_teardown_survives_a_database_that_went_away(monkeypatch):
    dead = _DeadSession()
    monkeypatch.setattr(database, "SessionLocal", lambda: dead)
    gen = database.get_db()
    assert next(gen) is dead
    gen.close()                       # must not raise
    assert dead.invalidated


def test_other_teardown_errors_still_surface(monkeypatch):
    class _Broken(_DeadSession):
        def close(self):
            raise ValueError("a programming error, not an outage")
    monkeypatch.setattr(database, "SessionLocal", lambda: _Broken())
    gen = database.get_db()
    next(gen)
    with pytest.raises(ValueError):
        gen.close()
