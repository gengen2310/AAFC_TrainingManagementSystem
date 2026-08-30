"""One-time recovery tokens.

The raw token is never stored. `token_hash` is SHA-256 of it -- not a passlib
hash: a 256-bit random token needs no slow KDF, and a salted hash could not be
looked up by value at all.
"""
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base, UUIDMixin, TimestampMixin, UTCDateTime


class RecoveryToken(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "recovery_tokens"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), index=True)
    purpose: Mapped[str] = mapped_column(String(20), index=True)   # reset | verify_email
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    consumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
