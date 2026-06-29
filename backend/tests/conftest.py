"""Pytest fixtures: isolated SQLite DB, seeded data, and an authenticated client."""
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
from app.security import reset_rate_limiter # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _seed():
    seed_all()
    yield


@pytest.fixture()
def client():
    reset_rate_limiter()
    return TestClient(app)


def login(client, code):
    r = client.post("/api/auth/login", json={"code": code})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    return {"Authorization": f"Bearer {token}"}
