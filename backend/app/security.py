"""Security primitives: access-code hashing, JWT tokens, login rate limiting.

Hashing uses PBKDF2-SHA256 via passlib (no external C deps). For production
consider argon2. Tokens are signed JWTs delivered in an HTTP-only cookie.
"""
import secrets
import time
import uuid
import jwt
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from typing import TYPE_CHECKING

from .config import settings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session as DBSession

_pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


# Unambiguous alphabet: no 0/O, 1/I/L confusion
_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_code(length: int = 8) -> str:
    """Generate a cryptographically random, human-typeable access code.

    The code is returned as plaintext exactly once (to the caller) and must be
    hashed before storage. It is never retrievable after that point.
    """
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(length))


def hash_code(code: str) -> str:
    return _pwd.hash(code)


def verify_code(code: str, code_hash: str) -> bool:
    try:
        return _pwd.verify(code, code_hash)
    except Exception:
        return False


def create_token(sub: str, extra: dict, ttl_min: int | None = None,
                 token_version: int = 0) -> str:
    ttl = ttl_min or settings.ACCESS_TOKEN_TTL_MIN
    now = datetime.now(timezone.utc)
    payload = {"sub": sub, "iat": now, "exp": now + timedelta(minutes=ttl),
               "jti": str(uuid.uuid4()), "tv": token_version, **extra}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except jwt.PyJWTError:
        return None


# ── Simple in-memory login rate limiter / lockout ──
# Production: replace with Redis (REDIS_URL) so limits hold across workers.
_attempts: dict[str, list[float]] = {}
_lockouts: dict[str, float] = {}


def login_blocked(key: str) -> bool:
    until = _lockouts.get(key)
    if until and time.time() < until:
        return True
    if until and time.time() >= until:
        _lockouts.pop(key, None)
        _attempts.pop(key, None)
    return False


def record_login_failure(key: str) -> None:
    now = time.time()
    window = settings.LOGIN_WINDOW_SEC
    arr = [t for t in _attempts.get(key, []) if now - t < window]
    arr.append(now)
    _attempts[key] = arr
    if len(arr) >= settings.LOGIN_MAX_ATTEMPTS:
        _lockouts[key] = now + settings.LOGIN_LOCKOUT_SEC


def record_login_success(key: str) -> None:
    _attempts.pop(key, None)
    _lockouts.pop(key, None)


def reset_rate_limiter() -> None:
    _attempts.clear()
    _lockouts.clear()


# ── Per-IP general API rate limiter (non-login endpoints) ───────────────────
# In-memory sliding window. Same caveat as above: replace with Redis for
# true distribution across gunicorn workers in production.
_api_hits: dict[str, list[float]] = {}


def check_api_rate(ip: str) -> bool:
    """Return True if the IP has exceeded the API rate limit (caller must 429)."""
    now = time.time()
    window = settings.API_RATE_WINDOW_SEC
    hits = [t for t in _api_hits.get(ip, []) if now - t < window]
    hits.append(now)
    _api_hits[ip] = hits
    return len(hits) > settings.API_RATE_LIMIT


def reset_api_rate_limiter() -> None:
    _api_hits.clear()


# ── Idempotency-key deduplication (in-memory, single-worker) ────────────────
# Same caveat as the rate limiters above: per-worker only, not shared across
# gunicorn workers -- replace with Redis for true distribution in production.
# Protects against a genuine network-level retry (client times out, resends
# the same request) creating a duplicate write. Client-side button-disable
# already covers the common double-click case; this covers the case that
# doesn't -- a request the client believes failed but the server actually
# completed.
_idempotency_cache: dict[str, tuple[float, int, dict]] = {}
_IDEMPOTENCY_TTL_SEC = 300


def idempotency_get(key: str) -> tuple[int, dict] | None:
    """Return the cached (status_code, body) for this key if present and unexpired."""
    entry = _idempotency_cache.get(key)
    if not entry:
        return None
    expires_at, status_code, body = entry
    if time.time() > expires_at:
        _idempotency_cache.pop(key, None)
        return None
    return status_code, body


def idempotency_set(key: str, status_code: int, body: dict) -> None:
    _idempotency_cache[key] = (time.time() + _IDEMPOTENCY_TTL_SEC, status_code, body)


def reset_idempotency_cache() -> None:
    _idempotency_cache.clear()


# ── DB-backed per-IP rate limiter (works across gunicorn workers) ──────────────
# Replaces the in-memory dicts above for production use. Uses IpLoginAttempt
# table so state is shared across all workers.

def login_blocked_db(key: str, db: "DBSession") -> bool:
    from .models import IpLoginAttempt
    row = db.get(IpLoginAttempt, key)
    if not row:
        return False
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    locked = row.locked_until
    if locked is None:
        return False
    # strip tz if stored as naive (SQLite stores naive datetimes)
    locked_naive = locked.replace(tzinfo=None) if locked.tzinfo else locked
    if locked_naive > now:
        return True
    # Lock expired — reset
    row.attempt_count = 0
    row.locked_until = None
    db.commit()
    return False


def record_login_failure_db(key: str, db: "DBSession") -> None:
    from .models import IpLoginAttempt
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    row = db.get(IpLoginAttempt, key)
    if not row:
        row = IpLoginAttempt(ip=key, attempt_count=0, window_start=now)
        db.add(row)
    window_start = row.window_start
    if window_start and window_start.tzinfo:
        window_start = window_start.replace(tzinfo=None)
    elapsed = (now - window_start).total_seconds() if window_start else settings.LOGIN_WINDOW_SEC + 1
    if elapsed > settings.LOGIN_WINDOW_SEC:
        row.attempt_count = 0
        row.window_start = now
    row.attempt_count += 1
    if row.attempt_count >= settings.LOGIN_MAX_ATTEMPTS:
        row.locked_until = now + timedelta(seconds=settings.LOGIN_LOCKOUT_SEC)
    db.commit()


def record_login_success_db(key: str, db: "DBSession") -> None:
    from .models import IpLoginAttempt
    row = db.get(IpLoginAttempt, key)
    if row:
        row.attempt_count = 0
        row.locked_until = None
        db.commit()


# ── DB-backed general API rate limiter (DEF-10) ────────────────────────────
# Replaces the in-memory _api_hits for non-development environments so the
# 300 req/60 s limit is accurate across all gunicorn workers.

def check_api_rate_db(ip: str, db: "DBSession") -> bool:
    """Return True if the IP has exceeded the API rate limit (caller must 429).

    Uses a sliding window: counts how many seconds have elapsed since
    window_start; resets the counter when the window expires.
    """
    from .models import IpApiRequest
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    window = settings.API_RATE_WINDOW_SEC
    row = db.get(IpApiRequest, ip)
    if not row:
        row = IpApiRequest(ip=ip, request_count=0, window_start=now)
        db.add(row)
    ws = row.window_start
    if ws and ws.tzinfo:
        ws = ws.replace(tzinfo=None)
    elapsed = (now - ws).total_seconds() if ws else window + 1
    if elapsed > window:
        row.request_count = 0
        row.window_start = now
    row.request_count += 1
    over_limit = row.request_count > settings.API_RATE_LIMIT
    db.commit()
    return over_limit


def reset_api_rate_limiter_db(db: "DBSession") -> None:
    """Clear all DB-backed API rate-limit rows (used by system_admin reset endpoint)."""
    from .models import IpApiRequest
    db.query(IpApiRequest).delete()
    db.commit()


# ── DB-backed per-account API rate limiter (DEF-11) ───────────────────────────
# Complements check_api_rate_db: where the per-IP check catches flooding from
# one source address, this check prevents a single authenticated account from
# monopolising the service regardless of IP (important when all users share the
# same Railway edge IP, as confirmed by REM-125).

def check_user_api_rate_db(user_id: str, db: "DBSession") -> bool:
    """Return True if the user account has exceeded the API rate limit (caller must 429)."""
    from .models import UserApiRequest
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    window = settings.API_RATE_WINDOW_SEC
    row = db.get(UserApiRequest, user_id)
    if not row:
        row = UserApiRequest(user_id=user_id, request_count=0, window_start=now)
        db.add(row)
    ws = row.window_start
    if ws and ws.tzinfo:
        ws = ws.replace(tzinfo=None)
    elapsed = (now - ws).total_seconds() if ws else window + 1
    if elapsed > window:
        row.request_count = 0
        row.window_start = now
    row.request_count += 1
    over_limit = row.request_count > settings.API_RATE_LIMIT
    db.commit()
    return over_limit


def reset_user_api_rate_limiter_db(db: "DBSession") -> None:
    """Clear all DB-backed per-account API rate-limit rows."""
    from .models import UserApiRequest
    db.query(UserApiRequest).delete()
    db.commit()
