"""Security primitives: access-code hashing, JWT tokens, login rate limiting.

Hashing uses PBKDF2-SHA256 via passlib (no external C deps). For production
consider argon2. Tokens are signed JWTs delivered in an HTTP-only cookie.
"""
import secrets
import time
import jwt
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext

from .config import settings

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
    payload = {"sub": sub, "iat": now, "exp": now + timedelta(minutes=ttl), **extra}
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
