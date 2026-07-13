"""SQLAlchemy 2.x engine, session and declarative base.

UUID primary keys are stored as 36-char strings so the same models run on
SQLite (local demo) and PostgreSQL (production) without change.
"""
import uuid
from datetime import datetime, timezone
from collections.abc import Generator

from sqlalchemy import create_engine, String, DateTime, Boolean
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase, Mapped, mapped_column

from .config import settings

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if _is_sqlite else {}

# Supabase Session Pooler caps connections at 15.  With 2 gunicorn workers
# each pool must stay under 8 (7 + 1 pre-ping headroom = 14 total < 15).
# Switch DATABASE_URL to port 6543 (Transaction Pooler) for higher concurrency.
_pool_kwargs = (
    {}
    if _is_sqlite
    else {"pool_size": 5, "max_overflow": 2, "pool_timeout": 30, "pool_recycle": 1800}
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


def new_uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class UUIDMixin:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
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
