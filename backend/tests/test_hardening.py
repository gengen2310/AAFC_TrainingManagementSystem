"""Tests for the pre-deployment hardening: JWT refresh and production config fail-closed."""
from conftest import login
from app.config import Settings


def test_refresh_with_valid_token_issues_new_token(client):
    h = login(client, "ADMIN703")
    r = client.post("/api/auth/refresh", headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("token")
    # The new token still authenticates.
    h2 = {"Authorization": f"Bearer {body['token']}"}
    assert client.get("/api/auth/me", headers=h2).status_code == 200


def test_refresh_without_token_rejected(client):
    assert client.post("/api/auth/refresh").status_code == 401


def test_production_config_fails_closed_on_dev_secrets():
    s = Settings(ENVIRONMENT="production", SECRET_KEY="dev-only-change-me",
                 JWT_SECRET="dev-only-change-me-too", COOKIE_SECURE=False,
                 CORS_ALLOWED_ORIGINS="http://localhost:5173",
                 DATABASE_URL="sqlite:///./x.db")
    problems = s.validate_for_production()
    # Every insecure default should be reported.
    joined = " ".join(problems).lower()
    assert any("secret_key" in p.lower() for p in problems)
    assert any("jwt_secret" in p.lower() for p in problems)
    assert "cookie_secure" in joined
    assert "localhost" in joined or "cors" in joined
    assert "sqlite" in joined


def test_production_config_passes_when_hardened():
    s = Settings(ENVIRONMENT="production",
                 SECRET_KEY="x" * 40, JWT_SECRET="y" * 40, COOKIE_SECURE=True,
                 CORS_ALLOWED_ORIGINS="https://tms.example.org",
                 DATABASE_URL="postgresql://u:p@db:5432/tms")
    assert s.validate_for_production() == []


def test_development_config_is_not_blocked():
    s = Settings(ENVIRONMENT="development")
    assert s.validate_for_production() == []
