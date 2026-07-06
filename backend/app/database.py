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


def reset_db() -> None:
    from . import models  # noqa: F401
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
