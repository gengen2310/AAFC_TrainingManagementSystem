"""Organisation hierarchy (National → Wing → Squadron → Flight), users, access codes."""
from sqlalchemy import String, Integer, ForeignKey, Boolean, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from ..database import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin


class NationalEntity(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "national_entities"
    name: Mapped[str] = mapped_column(String(120), default="AAFC National Headquarters")
    short_name: Mapped[str] = mapped_column(String(40), default="NATIONAL")


class Wing(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "wings"
    national_id: Mapped[str] = mapped_column(ForeignKey("national_entities.id"), index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)   # e.g. "7WG"
    name: Mapped[str] = mapped_column(String(120))
    short_name: Mapped[str] = mapped_column(String(40))
    active_status: Mapped[bool] = mapped_column(Boolean, default=True)
    squadrons: Mapped[list["Squadron"]] = relationship(back_populates="wing")


UNIT_TYPES = frozenset({
    "standard_squadron", "specialist_squadron", "specialist_flight", "support_unit",
})


class Squadron(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "squadrons"
    wing_id: Mapped[str] = mapped_column(ForeignKey("wings.id"), index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # e.g. "703"
    unit_number: Mapped[str | None] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(160))
    short_name: Mapped[str] = mapped_column(String(40))
    # unit_type distinguishes standard squadron from specialist squadron, specialist flight,
    # and support unit. All use the same account/tenancy model as a standard squadron.
    unit_type: Mapped[str] = mapped_column(String(40), default="standard_squadron", index=True)
    address: Mapped[str | None] = mapped_column(String(255))
    default_parade_day: Mapped[str | None] = mapped_column(String(20))
    default_start_time: Mapped[str | None] = mapped_column(String(10))
    default_end_time: Mapped[str | None] = mapped_column(String(10))
    default_session_count: Mapped[int] = mapped_column(Integer, default=3)
    active_status: Mapped[bool] = mapped_column(Boolean, default=True)
    wing: Mapped["Wing"] = relationship(back_populates="squadrons")


class Flight(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """A local Squadron grouping only. Not a separate tenant or permission scope.

    Flight assignment filters local display and reporting; it never expands access.
    A user assigned to A Flight still belongs entirely to the Squadron.
    """
    __tablename__ = "flights"
    squadron_id: Mapped[str] = mapped_column(ForeignKey("squadrons.id"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    active_status: Mapped[bool] = mapped_column(Boolean, default=True)


class User(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """A user/principal. In prototype mode a user is an access code holder.

    role drives RBAC. scope columns drive tenancy (which org the user belongs to).
    flight_id is optional and applies only to squadron-scoped users; it is a
    local display grouping and does NOT expand or restrict permissions.
    """
    __tablename__ = "users"
    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(40), index=True)
    national_id: Mapped[str | None] = mapped_column(ForeignKey("national_entities.id"), nullable=True, index=True)
    wing_id: Mapped[str | None] = mapped_column(ForeignKey("wings.id"), nullable=True, index=True)
    squadron_id: Mapped[str | None] = mapped_column(ForeignKey("squadrons.id"), nullable=True, index=True)
    flight_id: Mapped[str | None] = mapped_column(ForeignKey("flights.id"), nullable=True, index=True)
    active_status: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class AccessCode(Base, UUIDMixin, TimestampMixin):
    """Hashed access code → user. The plaintext code is never stored or returned.

    updated_at / updated_by (from TimestampMixin) record the last reset date and actor.
    """
    __tablename__ = "access_codes"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    code_hash: Mapped[str] = mapped_column(String(255), index=True)
    active_status: Mapped[bool] = mapped_column(Boolean, default=True)


class ProxySession(Base, UUIDMixin, TimestampMixin):
    """Records a Wing→Squadron Proxy or National→(Wing/Squadron) Delegated Intervention."""
    __tablename__ = "proxy_sessions"
    actor_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    actor_role: Mapped[str] = mapped_column(String(40))
    mode: Mapped[str] = mapped_column(String(40), default="proxy")  # proxy | delegated_intervention
    acting_wing_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    acting_squadron_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
