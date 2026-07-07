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


def create_token(sub: str, extra: dict, ttl_min: int | None = None) -> str:
    ttl = ttl_min or settings.ACCESS_TOKEN_TTL_MIN
    now = datetime.now(timezone.utc)
    payload = {"sub": sub, "iat": now, "exp": now + timedelta(minutes=ttl),
               "jti": str(uuid.uuid4()), **extra}
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
