"""Tests for reset_db()'s destructive-reset guard (DEFECT-002).

seed_all()/stress_seed.py call reset_db(), which unconditionally does
DROP ALL + CREATE ALL — appropriate for a fresh local/CI database, but a
real hazard if ever pointed at a database containing real data.

These test the pure check_destructive_reset_allowed() function directly
with explicit arguments — no monkeypatching of settings/env vars and no
module reloading, so this file cannot pollute global engine/session state
for the rest of the suite (module-reload based tests were tried first and
found to do exactly that: 95 unrelated failures across the suite).
"""
import hashlib

import pytest

from app.database import DestructiveResetRefused, check_destructive_reset_allowed


PROTECTED_HOSTNAME = "db.protected-example.supabase.co"
PROTECTED_FINGERPRINT = hashlib.sha256(PROTECTED_HOSTNAME.encode()).hexdigest()


def test_refuses_when_environment_is_production():
    with pytest.raises(DestructiveResetRefused, match="production"):
        check_destructive_reset_allowed(
            environment="production",
            database_url="sqlite:///./anything.db",
            protected_fingerprints=set(),
            allow_destructive_seed="",
        )


def test_refuses_when_environment_is_prod_abbreviation():
    with pytest.raises(DestructiveResetRefused):
        check_destructive_reset_allowed(
            environment="prod",
            database_url="postgresql://user:pass@some-host:5432/db",
            protected_fingerprints=set(),
            allow_destructive_seed="true",
        )


def test_refuses_protected_hostname_even_if_not_labelled_production():
    """Regression guard for the exact incident found in this repo: production's
    own ENVIRONMENT variable was set to 'staging', so ENVIRONMENT alone cannot
    be trusted — the hostname fingerprint check must catch it independently."""
    with pytest.raises(DestructiveResetRefused, match="protected"):
        check_destructive_reset_allowed(
            environment="staging",  # deliberately NOT "production"
            database_url=f"postgresql://user:pass@{PROTECTED_HOSTNAME}:5432/postgres",
            protected_fingerprints={PROTECTED_FINGERPRINT},
            allow_destructive_seed="true",  # even with the flag set — still refused
        )


def test_refuses_non_sqlite_without_explicit_allow():
    with pytest.raises(DestructiveResetRefused, match="ALLOW_DESTRUCTIVE_SEED"):
        check_destructive_reset_allowed(
            environment="staging",
            database_url="postgresql://user:pass@some-other-host.example.com:5432/postgres",
            protected_fingerprints=set(),
            allow_destructive_seed="",
        )


def test_allows_non_sqlite_with_explicit_allow_and_unprotected_host():
    check_destructive_reset_allowed(
        environment="staging",
        database_url="postgresql://user:pass@some-other-host.example.com:5432/postgres",
        protected_fingerprints=set(),
        allow_destructive_seed="true",
    )  # must not raise


def test_allows_sqlite_without_any_flag():
    """The existing test suite and local dev both rely on this working
    unchanged — SQLite is inherently local/disposable."""
    check_destructive_reset_allowed(
        environment="test",
        database_url="sqlite:///./aafc_tms.db",
        protected_fingerprints={PROTECTED_FINGERPRINT},
        allow_destructive_seed="",
    )  # must not raise — SQLite is exempt regardless of flags
