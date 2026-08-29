"""Account recovery: recovery email, tokens, forgot/reset (spec 2026-08-29)."""
from app.database import SessionLocal
from app.models import User


def test_user_carries_recovery_email_fields():
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.role == "system_admin").first()
        assert u is not None
        assert u.recovery_email is None
        assert u.recovery_email_verified_at is None
        assert u.recovery_email_updated_at is None
        assert u.recovery_email_updated_by is None
    finally:
        db.close()


# --- Task 2: token service ---------------------------------------------------
import datetime as dt
import pytest
from app.database import utcnow
from app.models import RecoveryToken
from app.services_recovery import (
    RECOVERY_ROLES, consume_token, hash_token, is_recovery_eligible, mint_token,
)


def _sa(db):
    return db.query(User).filter(User.role == "system_admin").first()


def test_the_raw_token_is_never_stored():
    db = SessionLocal()
    try:
        raw = mint_token(db, _sa(db), "reset", 20, None)
        db.flush()
        stored = db.query(RecoveryToken).filter(
            RecoveryToken.token_hash == hash_token(raw)).first()
        assert stored is not None
        assert raw not in stored.token_hash
        assert len(stored.token_hash) == 64          # sha256 hex
    finally:
        db.rollback(); db.close()


def test_a_token_is_single_use():
    db = SessionLocal()
    try:
        u = _sa(db)
        raw = mint_token(db, u, "reset", 20, None)
        db.flush()
        assert consume_token(db, raw, "reset").id == u.id
        assert consume_token(db, raw, "reset") is None, "a consumed token must not work twice"
    finally:
        db.rollback(); db.close()


def test_an_expired_token_is_rejected():
    db = SessionLocal()
    try:
        raw = mint_token(db, _sa(db), "reset", 20, None)
        db.flush()
        row = db.query(RecoveryToken).filter(
            RecoveryToken.token_hash == hash_token(raw)).first()
        row.expires_at = utcnow() - dt.timedelta(minutes=1)
        db.flush()
        assert consume_token(db, raw, "reset") is None
    finally:
        db.rollback(); db.close()


def test_a_newer_token_supersedes_an_older_one():
    db = SessionLocal()
    try:
        u = _sa(db)
        old = mint_token(db, u, "reset", 20, None)
        db.flush()
        new = mint_token(db, u, "reset", 20, None)
        db.flush()
        assert consume_token(db, old, "reset") is None, "minting a new token must kill the old"
        assert consume_token(db, new, "reset").id == u.id
    finally:
        db.rollback(); db.close()


def test_a_token_minted_for_one_purpose_does_not_work_for_another():
    db = SessionLocal()
    try:
        raw = mint_token(db, _sa(db), "verify_email", 60, None)
        db.flush()
        assert consume_token(db, raw, "reset") is None
    finally:
        db.rollback(); db.close()


def test_unknown_token_returns_none():
    db = SessionLocal()
    try:
        assert consume_token(db, "not-a-real-token", "reset") is None
    finally:
        db.close()


def test_eligibility_requires_a_verified_address_and_a_live_privileged_account():
    db = SessionLocal()
    try:
        u = _sa(db)
        assert is_recovery_eligible(u) is False, "no address yet"
        u.recovery_email = "sa@example.com"
        assert is_recovery_eligible(u) is False, "unverified address is not a channel"
        u.recovery_email_verified_at = utcnow()
        assert is_recovery_eligible(u) is True
        u.active_status = False
        assert is_recovery_eligible(u) is False, "disabled accounts must not self-recover"
        u.active_status = True
        u.is_archived = True
        assert is_recovery_eligible(u) is False, "archived accounts must not self-recover"
        u.is_archived = False
        u.role = "sqn_general"
        assert is_recovery_eligible(u) is False, "non-privileged roles are out of scope"
        assert "system_admin" in RECOVERY_ROLES
    finally:
        db.rollback(); db.close()
