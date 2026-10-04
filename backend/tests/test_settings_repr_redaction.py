"""Settings must never render secrets when printed, logged or shown in a traceback.

pydantic's default repr() lists every field, so `log.info(settings)`, an f-string,
or a traceback that captures locals would print the JWT signing key, the session
secret, the SMTP password and the database password.
"""
from app.config import Settings

SECRET_FIELDS = {
    "SECRET_KEY": "s3cret-key-value-for-repr-test-000000000",
    "JWT_SECRET": "jwt-signing-value-for-repr-test-00000000",
    "SMTP_PASS": "smtp-password-value-for-repr-test",
    "DATABASE_URL": "postgresql://tms:db-password-value-for-repr-test@db.example:5432/tms",
    "REDIS_URL": "redis://:redis-password-value-for-repr-test@cache.example:6379/0",
}
NEEDLES = ["s3cret-key-value", "jwt-signing-value", "smtp-password-value",
           "db-password-value", "redis-password-value"]


def _settings() -> Settings:
    return Settings(_env_file=None, **SECRET_FIELDS)


def test_repr_and_str_do_not_contain_secret_values():
    s = _settings()
    for rendered in (repr(s), str(s), f"{s}", f"{s!r}"):
        for needle in NEEDLES:
            assert needle not in rendered, f"{needle} leaked into {rendered[:80]}..."


def test_secret_values_are_still_readable_by_the_application():
    s = _settings()
    for name, value in SECRET_FIELDS.items():
        assert getattr(s, name) == value


def test_non_secret_settings_still_appear_for_diagnostics():
    rendered = repr(_settings())
    assert "ENVIRONMENT=" in rendered and "DB_POOL_SIZE=" in rendered
