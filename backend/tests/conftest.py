"""Pytest fixtures: isolated SQLite DB, seeded data, and an authenticated client."""
import itertools
import os
import tempfile
import pytest

# Use a throwaway SQLite file before importing the app/config.
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET"] = "test-secret"
os.environ["SECRET_KEY"] = "test-secret"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app                    # noqa: E402
from app.seeds.seed_all import seed_all     # noqa: E402
from app.security import reset_rate_limiter, reset_api_rate_limiter, reset_api_rate_limiter_db, reset_user_api_rate_limiter_db # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.models import IpLoginAttempt, IpApiRequest, UserApiRequest, AccessCode  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _seed():
    seed_all()
    yield


@pytest.fixture()
def client():
    reset_rate_limiter()
    reset_api_rate_limiter()
    # Clear DB-backed lockout state so tests are isolated
    db = SessionLocal()
    try:
        db.query(IpLoginAttempt).delete()
        reset_api_rate_limiter_db(db)      # DEF-10: clear DB-backed per-IP API rate limit rows
        reset_user_api_rate_limiter_db(db) # DEF-11: clear DB-backed per-account API rate limit rows
        # Reset per-account lockout fields on all access codes
        for ac in db.query(AccessCode).all():
            ac.failed_attempts = 0
            ac.locked_until = None
        db.commit()
    finally:
        db.close()
    # Dispose pooled connections so the next request sees fresh DB state
    engine.dispose()
    return TestClient(app)


# REM-134: a unit may hold one planning year per year number, enforced by
# POST /api/planning/years. The suite seeds once per session and never resets
# between tests, so any helper with a fixed year collided with itself on its
# second call -- and with the seed, which already gives 703 the year 2026.
# Tests that do not care which year they get should ask for one.
#
# Allocated years start at 5000 -- above every literal the suite uses (the
# highest is 2999) and above the seed's 2026, so an allocated year can never
# collide with a hand-written one. POST /api/planning/years does not constrain
# the year, so there is no ceiling to work around. Step 3 leaves the two years
# after each allocation free, which rollover tests need: they create a source
# year and roll it over to source+1.
_test_year_counter = itertools.count(5000, 3)


def next_test_year() -> int:
    """An unused planning year, unique for the life of the test session."""
    return next(_test_year_counter)


def login(client, code):
    r = client.post("/api/auth/login", json={"code": code})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}
