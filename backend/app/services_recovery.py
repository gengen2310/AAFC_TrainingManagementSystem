"""Account recovery: eligibility, one-time tokens, address masking.

Spec: docs/superpowers/specs/2026-08-29-account-recovery-design.md

Two rules hold everywhere in this module:
  - the raw token is never stored, logged, or returned to anyone but the
    address it was mailed to;
  - eligibility never distinguishes itself to the caller. Every reason an
    account cannot recover produces the same outward response, so this module
    reports a plain bool and the router says the same thing either way.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import secrets

from sqlalchemy.orm import Session as DBSession

from .database import utcnow
from .models import RecoveryToken, User

# Roles that may hold a recovery channel at all. A recovery email is REQUIRED
# for system_admin (enforced at account creation) and offered to the others.
# Deliberately excludes sqn_general, viewers and cadets: storing an address for
# every account is more personal data for less benefit, and those users are
# already recoverable by their own squadron admin.
RECOVERY_ROLES = frozenset({"system_admin", "national_admin", "wing_admin", "sqn_admin"})

RESET_TTL_MINUTES = 20
VERIFY_TTL_MINUTES = 60 * 24


def hash_token(raw: str) -> str:
    """SHA-256, deliberately not passlib.

    An access code is short, user-chosen and guessable, so it needs a slow
    salted KDF. A recovery token is 256 bits of `secrets` output, where a slow
    hash buys nothing -- and a salted hash could not be looked up by value at
    all, which is the operation this table exists to serve.
    """
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_recovery_eligible(u: User | None) -> bool:
    """Whether self-service recovery may proceed for this account.

    Archived and disabled accounts are excluded: they were deliberately taken
    out of use, and letting one re-admit itself would make archiving unreliable
    as a removal. An administrator restores first.
    """
    return bool(
        u is not None
        and not u.is_archived
        and u.active_status
        and u.role in RECOVERY_ROLES
        and u.recovery_email
        and u.recovery_email_verified_at is not None
    )


def mint_token(db: DBSession, user: User, purpose: str,
               ttl_minutes: int, ip: str | None) -> str:
    """Issue a single-use token and return the RAW value to the caller once.

    Any outstanding unconsumed token of the same purpose is consumed first, so
    requesting a second link invalidates the first: two live reset links for one
    account is one more than the account can justify.
    """
    now = utcnow()
    for old in (db.query(RecoveryToken)
                  .filter(RecoveryToken.user_id == user.id,
                          RecoveryToken.purpose == purpose,
                          RecoveryToken.consumed_at.is_(None))
                  .all()):
        old.consumed_at = now

    raw = secrets.token_urlsafe(32)
    # SessionLocal is autoflush=False, so a pending mutation is invisible to the
    # next query on the same session. Flush explicitly or an invalidated token
    # keeps working.
    db.add(RecoveryToken(
        user_id=user.id,
        token_hash=hash_token(raw),
        purpose=purpose,
        expires_at=now + _dt.timedelta(minutes=ttl_minutes),
        created_ip=ip,
    ))
    db.flush()
    return raw


def consume_token(db: DBSession, raw: str, purpose: str) -> User | None:
    """Resolve a raw token to its user and mark it used, or return None.

    One return value for every failure -- unknown, expired, already consumed,
    wrong purpose -- so a caller cannot turn this into an oracle.
    """
    if not raw:
        return None
    row = (db.query(RecoveryToken)
             .filter(RecoveryToken.token_hash == hash_token(raw),
                     RecoveryToken.purpose == purpose,
                     RecoveryToken.consumed_at.is_(None))
             .first())
    if row is None:
        return None

    expires = row.expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=_dt.timezone.utc)
    if expires is not None and expires <= utcnow():
        return None

    row.consumed_at = utcnow()
    # Flush before returning. SessionLocal sets autoflush=False, so without this
    # the token stays unconsumed for the rest of the session and a single-use
    # token can be redeemed twice -- which is the whole property this function
    # exists to guarantee.
    db.flush()
    return db.get(User, row.user_id)


def mask_email(addr: str | None) -> str | None:
    """g••••••••@example.com -- enough to recognise, not enough to retype."""
    if not addr or "@" not in addr:
        return None
    local, _, domain = addr.partition("@")
    head = local[0] if local else ""
    return f"{head}{'•' * max(len(local) - 1, 1)}@{domain}"
