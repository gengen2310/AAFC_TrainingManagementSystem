"""Application configuration, driven entirely by environment variables.

No secrets are hard-coded. For production, set SECRET_KEY/JWT_SECRET to strong
random values and DATABASE_URL to the PostgreSQL DSN.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # SQLite for local demo; PostgreSQL DSN for production.
    DATABASE_URL: str = "sqlite:///./aafc_tms.db"
    REDIS_URL: str = "redis://localhost:6379/0"

    # SQLAlchemy connection pool sizing (Postgres only; ignored for SQLite).
    # As of 2026-08 (GAP-18 fix, see deployment/backup-dr.md), production runs on
    # Railway-native Postgres, not a Supabase Session Pooler -- an earlier version
    # of this comment cited a stale "15 total connections" Supabase pooler cap as
    # the rationale, which no longer applies. The real, load-tested ceiling is
    # Postgres's own max_connections=100 (docs/release/qualification_gap_register.md
    # GAP-28/GAP-29) -- GAP-29 documents a real incident where someone raised
    # workers/pool sizes reasoning from the old (already-stale-then) per-service
    # mental model and blew past that ceiling (12 workers x (16+2) = 216 > 100),
    # producing a >50% server error rate on staging before being reverted. These
    # defaults (2 workers x (5+2) = 14 total) are conservative and safe under the
    # real ceiling; do not raise them without checking current
    # `workers x (pool_size + max_overflow)` against Postgres's actual
    # max_connections for the target environment.
    DB_POOL_SIZE: int = 5
    DB_POOL_MAX_OVERFLOW: int = 2
    DB_POOL_TIMEOUT: int = 30

    # Secrets — MUST be overridden in production via environment.
    # Dev defaults are ≥32 bytes to satisfy HS256 key-length requirements during local testing.
    # These values MUST be replaced with cryptographically random secrets in production.
    SECRET_KEY: str = "dev-only-change-me-in-production-aafc"
    JWT_SECRET: str = "dev-only-change-me-jwt-secret-aafc-tms"
    JWT_ALG: str = "HS256"
    ACCESS_TOKEN_TTL_MIN: int = 30
    REFRESH_TOKEN_TTL_MIN: int = 60 * 12

    # Cookie / CORS
    COOKIE_NAME: str = "aafc_session"
    COOKIE_SECURE: bool = False          # set True in production (HTTPS)
    COOKIE_SAMESITE: str = "lax"
    FRONTEND_ORIGIN: str = "http://localhost:5173"
    CORS_ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080,http://localhost:8000"

    # Login protection
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_WINDOW_SEC: int = 300
    LOGIN_LOCKOUT_SEC: int = 900

    # General API rate limiting (non-login endpoints, per-IP, in-memory sliding window)
    API_RATE_LIMIT: int = 300       # requests allowed per window
    API_RATE_WINDOW_SEC: int = 60   # window length in seconds

    # Uploads / exports
    UPLOAD_MAX_MB: int = 5
    EXPORT_DIR: str = "./exports"
    BACKUP_DIR: str = "./backups"

    TRAINING_YEAR: int = 2026

    # URL for the Planning Workspace frontend (served separately).
    # Set this env var in each Railway environment. Empty string = no link shown.
    PLANNING_WORKSPACE_URL: str = ""

    # Defense in depth for reset_db()/seed_all(): SHA-256 fingerprints (of the
    # DATABASE_URL hostname only — never the credentials) of databases that
    # must never be destructively reset, regardless of what ENVIRONMENT says.
    # This exists because production's ENVIRONMENT was found set to "staging"
    # in practice — see docs/beta/11_defect_register.md — so ENVIRONMENT alone
    # is not a sufficient guard. Comma-separated; extend via env var without
    # a code change if another protected database is added.
    PROTECTED_DB_HOST_FINGERPRINTS: str = (
        "48de339b89ad325c27447d39c07b2ee3d56ebc155d46e517bc820b520a70c943"
    )

    @property
    def protected_db_host_fingerprints(self) -> set[str]:
        return {f.strip() for f in self.PROTECTED_DB_HOST_FINGERPRINTS.split(",") if f.strip()}

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def is_prod(self) -> bool:
        return self.ENVIRONMENT.lower() in ("production", "prod")

    def validate_for_production(self) -> list[str]:
        """Return a list of fatal misconfigurations when ENVIRONMENT=production.

        Fail closed: the app refuses to start in production with dev secrets, insecure
        cookies, an unset/over-permissive CORS origin, or a SQLite database.
        """
        problems: list[str] = []
        if not self.is_prod:
            return problems
        dev_prefixes = ("dev-only-", "changeme")

        def _is_dev(v: str) -> bool:
            return not v or any(v.startswith(p) for p in dev_prefixes) or len(v) < 32

        if _is_dev(self.SECRET_KEY):
            problems.append("SECRET_KEY must be a strong value (>=32 chars) in production.")
        if _is_dev(self.JWT_SECRET):
            problems.append("JWT_SECRET must be a strong value (>=32 chars) in production.")
        if not self.COOKIE_SECURE:
            problems.append("COOKIE_SECURE must be true in production (HTTPS).")
        origins = self.cors_origins
        if not origins:
            problems.append("CORS_ALLOWED_ORIGINS must list the real frontend origin in production.")
        if any(o == "*" for o in origins):
            problems.append("CORS_ALLOWED_ORIGINS must not be '*' in production.")
        if any("localhost" in o or "127.0.0.1" in o for o in origins):
            problems.append("CORS_ALLOWED_ORIGINS must not include localhost in production.")
        if self.DATABASE_URL.startswith("sqlite"):
            problems.append("DATABASE_URL must be PostgreSQL in production, not SQLite.")
        return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
