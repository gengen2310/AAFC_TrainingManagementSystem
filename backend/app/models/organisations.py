"""Organisation hierarchy (National → Wing → Squadron → Flight), users, access codes."""
from sqlalchemy import String, Integer, ForeignKey, Boolean, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from ..database import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, UTCDateTime


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
    # IANA zone, e.g. "Australia/Perth". Squadrons deliberately cannot override:
    # a wing is the smallest unit that spans a timezone in practice.
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
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
    # External URL, not a binary upload -- Railway's filesystem is ephemeral per
    # deployment (.claude/rules/deployment.md) and this codebase has no object
    # storage (S3/CDN) configured anywhere (remediation program Section 7,
    # Stage 4). Validated as http(s) at the API boundary; None means "use the
    # default crest" (frontend concern, not stored here).
    crest_url: Mapped[str | None] = mapped_column(String(500))
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
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class AccessCode(Base, UUIDMixin, TimestampMixin):
    """Hashed access code → user. The plaintext code is never stored or returned.

    updated_at / updated_by (from TimestampMixin) record the last reset date and actor.
    failed_attempts / locked_until support per-account lockout (see auth.py).
    """
    __tablename__ = "access_codes"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    code_hash: Mapped[str] = mapped_column(String(255), index=True)
    active_status: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class IpLoginAttempt(Base):
    """DB-backed per-IP login rate-limit state.

    Replaces the in-memory _attempts/_lockouts dicts in security.py, which do not
    survive across gunicorn workers. One row per unique client IP — upserted on each
    failed login, cleared on success.
    """
    __tablename__ = "ip_login_attempts"
    ip: Mapped[str] = mapped_column(String(45), primary_key=True)  # IPv6 max 45 chars
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    window_start: Mapped[datetime] = mapped_column(UTCDateTime)
    locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class IpApiRequest(Base):
    """DB-backed per-IP general API rate-limit state (DEF-10).

    Replaces the in-memory _api_hits dict in security.py for non-development
    environments, making the 300 req/60 s limit accurate across all gunicorn
    workers.  One row per unique client IP — upserted on each non-exempt API
    request and reset by the system_admin reset-rate-limits endpoint.
    """
    __tablename__ = "ip_api_requests"
    ip: Mapped[str] = mapped_column(String(45), primary_key=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    window_start: Mapped[datetime] = mapped_column(UTCDateTime)


class UserApiRequest(Base):
    """DB-backed per-account general API rate-limit state (DEF-11).

    Complements IpApiRequest: where the per-IP check guards against large-scale
    flooding from one source address, this check ensures a single authenticated
    account cannot monopolise the service even when many accounts share the same
    Railway edge IP.  One row per user_id — upserted inside get_principal after
    the JWT is validated, so only authenticated requests count.
    """
    __tablename__ = "user_api_requests"
    user_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    window_start: Mapped[datetime] = mapped_column(UTCDateTime)


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
