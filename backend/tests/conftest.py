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
# K-001: raise the in-memory API rate limit in test mode so the timing test's
# 244-iteration loop (plus login and bulk-schedule preamble) never trips the
# 300-req/60s default. The login-spike tests have their own DB-backed rate limiter
# that is independent of this setting.
os.environ["API_RATE_LIMIT"] = "10000"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app                    # noqa: E402
from app.main import _5xx_times             # noqa: E402
from app.seeds.seed_all import seed_all     # noqa: E402
from app.security import reset_rate_limiter, reset_api_rate_limiter, reset_api_rate_limiter_db, reset_user_api_rate_limiter_db # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.models import IpLoginAttempt, IpApiRequest, UserApiRequest, AccessCode, PlanningYear  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _seed():
    seed_all()
    # v64 backfill: the test DB is created from SQLAlchemy metadata (not Alembic),
    # so the migration's INSERT is never run. Replicate it here so SAF-aware tests
    # find the expected rows without having to skip.
    import uuid
    import sqlalchemy as sa
    db = SessionLocal()
    try:
        rows = db.execute(sa.text(
            "SELECT id, assistant_facilitator_id FROM sessions "
            "WHERE assistant_facilitator_id IS NOT NULL AND is_archived = 0"
        )).fetchall()
        for row in rows:
            db.execute(sa.text(
                "INSERT OR IGNORE INTO session_assistant_facilitators "
                "(id, session_id, user_id, created_at) "
                "VALUES (:id, :sid, :uid, CURRENT_TIMESTAMP)"
            ), {"id": str(uuid.uuid4()), "sid": row[0], "uid": row[1]})
        db.commit()
    finally:
        db.close()
    yield


# K-001: autouse reset that runs before EVERY test, not just those that use the
# `client` fixture. This covers tests that call security functions directly via
# _db() (e.g. test_rate_limiting.py) and tests that check for unmaterialised
# future planning years (test_year_context.py).
@pytest.fixture(autouse=True)
def _reset_shared_state():
    # In-process state reset.
    reset_rate_limiter()
    reset_api_rate_limiter()
    _5xx_times.clear()
    # K-001: alembic.command.upgrade/stamp calls fileConfig('alembic.ini') which sets
    # disable_existing_loggers=True by default, silencing any logger not listed in
    # alembic.ini's [loggers] keys (including "security"). Re-enable it before each test.
    import logging
    logging.getLogger("security").disabled = False

    db = SessionLocal()
    try:
        db.query(IpLoginAttempt).delete()
        reset_api_rate_limiter_db(db)
        reset_user_api_rate_limiter_db(db)
        for ac in db.query(AccessCode).all():
            ac.failed_attempts = 0
            ac.locked_until = None
        # K-001 year context: delete PlanningYear rows for near-future years
        # materialised by other tests via ensure_year_context or direct API calls.
        # Safe range: above the seed's 2026 year, below the test-year-counter floor
        # (5000). Rows in this range are test artefacts, not seed data.
        db.query(PlanningYear).filter(
            PlanningYear.year >= 2027,
            PlanningYear.year < 5000,
        ).delete()
        db.commit()
    finally:
        db.close()

    yield


@pytest.fixture()
def client():
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
