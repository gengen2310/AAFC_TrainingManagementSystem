"""SQLAlchemy 2.x engine, session and declarative base.

UUID primary keys are stored as 36-char strings so the same models run on
SQLite (local demo) and PostgreSQL (production) without change.
"""
import uuid
from datetime import datetime, timezone
from collections.abc import Generator

from sqlalchemy import create_engine, String, DateTime, Boolean
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase, Mapped, mapped_column

from .config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if _is_sqlite else {}

# Production runs on Railway-native Postgres, not a Supabase Session Pooler
# (GAP-18 fix, 2026-08 -- see deployment/backup-dr.md and config.py's
# DB_POOL_SIZE comment for the full history, including a real incident where
# sizing reasoned from the older, stale Supabase-pooler premise blew past the
# real ceiling). The real, load-tested ceiling is Postgres's own
# max_connections=100 (docs/release/qualification_gap_register.md GAP-28/29).
# Pool size is configurable per-environment (DB_POOL_SIZE / DB_POOL_MAX_OVERFLOW /
# DB_POOL_TIMEOUT) — the 5/2/30 defaults below are conservative and safe; do not
# raise them without checking current `workers x (pool_size + max_overflow)`
# against the target environment's actual max_connections.
def build_pool_kwargs(is_sqlite: bool, pool_size: int, max_overflow: int, pool_timeout: int) -> dict:
    """Pure function (no I/O, no globals) so pool sizing logic is unit-testable
    without a real Postgres connection — SQLite (local dev/tests) never receives
    pool kwargs since SQLAlchemy's SQLite driver doesn't support pooling params."""
    if is_sqlite:
        return {}
    return {
        "pool_size": pool_size,
        "max_overflow": max_overflow,
        "pool_timeout": pool_timeout,
        "pool_recycle": 1800,
    }


_pool_kwargs = build_pool_kwargs(
    _is_sqlite, settings.DB_POOL_SIZE, settings.DB_POOL_MAX_OVERFLOW, settings.DB_POOL_TIMEOUT
)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
    future=True,
    **_pool_kwargs,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(value: datetime | None) -> str | None:
    """ISO 8601 with a "Z" suffix, for routers that build response dicts by hand.

    UTCDateTime hands back aware UTC values, so a bare .isoformat() spells the
    zone "+00:00" while Pydantic and the encoder registered in main.py spell it
    "Z". Both are correct and both parse, but one API should not use two
    spellings for the same instant.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class UTCDateTime(TypeDecorator):
    """A DateTime column that always hands Python a timezone-aware UTC value.

    utcnow() has always returned an aware datetime, so the intent throughout this
    codebase is "everything is UTC". A plain DateTime column silently broke that
    on the way back out: SQLite and a non-timezone PostgreSQL column both drop
    tzinfo, so a value written as aware was read back naive. FastAPI and Pydantic
    then serialised it with no zone marker, and browsers parse a zone-less
    timestamp as LOCAL time -- eight hours out in Perth, which moved dates onto
    the wrong day either side of midnight.

    Storage format is unchanged: values are still written as naive UTC, exactly
    as before, so this needs no migration and reads existing rows correctly --
    they were already naive UTC by convention. Only the Python-side value gains
    its tzinfo back.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            # A naive value reaching the database is UTC by this codebase's
            # convention; store it unchanged rather than guessing a timezone.
            return value
        return value.astimezone(timezone.utc).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class UUIDMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, onupdate=utcnow)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class SoftDeleteMixin:
    """Records are archived, never hard-deleted (history preservation)."""
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401 — ensure models are registered
    Base.metadata.create_all(bind=engine)


class DestructiveResetRefused(RuntimeError):
    """Raised when reset_db() refuses to drop and recreate the schema."""


def check_destructive_reset_allowed(
    *, environment: str, database_url: str, protected_fingerprints: set[str], allow_destructive_seed: str,
) -> None:
    """Pure guard for reset_db() — no globals, no I/O, fully unit-testable.

    Refuses (raises DestructiveResetRefused) when:
      1. environment is 'production'/'prod' — absolute, no override.
      2. database_url's hostname fingerprint matches a protected database —
         absolute, no override, and independent of `environment` because
         production's own ENVIRONMENT variable was found set to "staging" in
         practice (see docs/beta/11_defect_register.md), so ENVIRONMENT alone
         is not a sufficient guard.
      3. database_url is not SQLite and ALLOW_DESTRUCTIVE_SEED != "true".
    SQLite targets (local dev, the test suite) are always allowed — they are
    inherently local, ephemeral, and never shared/production.
    """
    import hashlib
    import urllib.parse

    if environment.strip().lower() in ("production", "prod"):
        raise DestructiveResetRefused(
            "Refusing to reset the database: ENVIRONMENT is 'production'. "
            "This operation is never permitted against a production-labelled environment."
        )

    if database_url.startswith("sqlite"):
        return

    hostname = urllib.parse.urlparse(database_url).hostname or ""
    fingerprint = hashlib.sha256(hostname.encode()).hexdigest()
    if fingerprint in protected_fingerprints:
        raise DestructiveResetRefused(
            "Refusing to reset the database: DATABASE_URL host matches a "
            "protected database fingerprint, regardless of ENVIRONMENT."
        )
    if allow_destructive_seed.strip().lower() != "true":
        raise DestructiveResetRefused(
            "Refusing to reset a non-SQLite database: set ALLOW_DESTRUCTIVE_SEED=true "
            "explicitly to confirm this is a disposable database (e.g. staging)."
        )


def reset_db() -> None:
    """Drop and recreate every table — for fresh local/CI databases ONLY.

    This is unconditionally destructive (DROP + CREATE, bypassing Alembic
    entirely) and is called by the demo/stress seed scripts. See
    check_destructive_reset_allowed() for the safety guard.
    """
    import os
    from . import models  # noqa: F401

    check_destructive_reset_allowed(
        environment=settings.ENVIRONMENT,
        database_url=settings.DATABASE_URL,
        protected_fingerprints=settings.protected_db_host_fingerprints,
        allow_destructive_seed=os.environ.get("ALLOW_DESTRUCTIVE_SEED", ""),
    )

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
