#!/usr/bin/env python3
"""test_reset_staging.py — Unit tests for reset_staging_system_admin.py.

All 17 tests use only the pure-function surface of the reset script; no database
connection is required. The two mock-based tests (T16, T17) use unittest.mock to
stub SQLAlchemy sessions and the User model — they do NOT hit any database.

Run from the repo root:
  python scripts/test_reset_staging.py
Or with pytest:
  pytest scripts/test_reset_staging.py -v

Exit 0 if all 17 pass. Exit 1 on first failure.
"""
import sys
import os
import types
import unittest

# ── Make the script importable without executing main() ───────────────────────
# Insert scripts/ into sys.path so we can import the module directly.
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _SCRIPTS_DIR)

# Stub out backend/ imports that the module performs inside main() so that
# importing the module at test time does not fail if the venv is absent.
# The pure functions under test do not use these imports.
_STUB = types.ModuleType
for _name in ("app", "app.database", "app.models", "app.security"):
    sys.modules.setdefault(_name, _STUB(_name))
sys.modules["app"].database   = _STUB("app.database")
sys.modules["app"].models     = _STUB("app.models")
sys.modules["app"].security   = _STUB("app.security")
sys.modules["app.database"].SessionLocal = None
sys.modules["app.models"].User       = None
sys.modules["app.models"].AccessCode = None
sys.modules["app.models"].AuditLog   = None
sys.modules["app.security"].hash_code = lambda x: f"hash({x})"

import reset_staging_system_admin as rsa

# Known constants
_ENV_ID = "77a45568-5c16-46c2-9065-d5d339208b0e"
_SVC_ID = "deb53faa-ca8d-4291-aa2e-9ff3029c50f8"
_PROD_ENV = "571a8028-3640-4542-a4ab-7a1ee6b1f693"
_VALID_PG_URL = "postgresql://user:pass@db.staging.railway.internal/aafc_staging_db"


def _staging_env(**overrides) -> dict:
    """Return a minimal valid staging env dict with optional overrides."""
    base = {
        "RAILWAY_ENVIRONMENT_ID": _ENV_ID,
        "RAILWAY_SERVICE_ID":     _SVC_ID,
        "RAILWAY_PROJECT_ID":     "f5d9524f-8a57-44ff-86b7-ab66aec00e73",
        "ENVIRONMENT":            "staging",
        "DATABASE_URL":           _VALID_PG_URL,
    }
    base.update(overrides)
    return {k: v for k, v in base.items() if v is not None}


class TestVerifyExactStagingEnv(unittest.TestCase):
    """T1–T8: verify_exact_staging_env() — env-var guard."""

    # T1
    def test_valid_staging_env_passes(self):
        """All correct staging IDs → no SystemExit."""
        rsa.verify_exact_staging_env(_staging_env())

    # T2
    def test_missing_railway_environment_id_aborts(self):
        """RAILWAY_ENVIRONMENT_ID absent → SystemExit."""
        env = _staging_env()
        env.pop("RAILWAY_ENVIRONMENT_ID")
        with self.assertRaises(SystemExit):
            rsa.verify_exact_staging_env(env)

    # T3
    def test_wrong_railway_environment_id_aborts(self):
        """RAILWAY_ENVIRONMENT_ID set but not the exact staging UUID → SystemExit."""
        with self.assertRaises(SystemExit):
            rsa.verify_exact_staging_env(
                _staging_env(RAILWAY_ENVIRONMENT_ID="aaaaaaaa-0000-0000-0000-000000000000")
            )

    # T4
    def test_production_uuid_in_railway_environment_id_aborts(self):
        """RAILWAY_ENVIRONMENT_ID is the production env UUID → SystemExit."""
        with self.assertRaises(SystemExit):
            rsa.verify_exact_staging_env(
                _staging_env(RAILWAY_ENVIRONMENT_ID=_PROD_ENV)
            )

    # T5
    def test_missing_railway_service_id_aborts(self):
        """RAILWAY_SERVICE_ID absent → SystemExit."""
        env = _staging_env()
        env.pop("RAILWAY_SERVICE_ID")
        with self.assertRaises(SystemExit):
            rsa.verify_exact_staging_env(env)

    # T6
    def test_wrong_railway_service_id_aborts(self):
        """RAILWAY_SERVICE_ID set but not the exact backend-service UUID → SystemExit."""
        with self.assertRaises(SystemExit):
            rsa.verify_exact_staging_env(
                _staging_env(RAILWAY_SERVICE_ID="bbbbbbbb-1111-1111-1111-111111111111")
            )

    # T7
    def test_environment_production_aborts(self):
        """ENVIRONMENT=production → SystemExit regardless of Railway IDs."""
        with self.assertRaises(SystemExit):
            rsa.verify_exact_staging_env(_staging_env(ENVIRONMENT="production"))

    # T8
    def test_database_url_contains_production_aborts(self):
        """DATABASE_URL containing 'production' → SystemExit."""
        with self.assertRaises(SystemExit):
            rsa.verify_exact_staging_env(
                _staging_env(DATABASE_URL="postgresql://host/production_db")
            )


class TestVerifyDbUrl(unittest.TestCase):
    """T9–T11: verify_db_url() — URL pre-flight check."""

    # T9
    def test_empty_url_aborts(self):
        """Empty DATABASE_URL → SystemExit."""
        with self.assertRaises(SystemExit):
            rsa.verify_db_url("")

    # T10
    def test_sqlite_url_aborts(self):
        """SQLite URL → SystemExit (staging must use PostgreSQL)."""
        with self.assertRaises(SystemExit):
            rsa.verify_db_url("sqlite:///./aafc_tms.db")

    # T11
    def test_valid_postgres_url_passes(self):
        """Valid PostgreSQL URL with no 'production' substring → no SystemExit."""
        rsa.verify_db_url(_VALID_PG_URL)


class TestRedactUrl(unittest.TestCase):
    """T12–T13: redact_url() — credential stripping."""

    # T12
    def test_short_host_and_dbname_partially_redacted(self):
        """Short hostname and dbname → host shows as-is, dbname truncated."""
        url = "postgresql://user:pass@shorthost/db"
        host_display, dbname_display = rsa.redact_url(url)
        self.assertNotIn("user", host_display)
        self.assertNotIn("pass", host_display)
        self.assertNotIn("user", dbname_display)
        self.assertNotIn("pass", dbname_display)
        # Short host (≤30 chars) should be returned as-is
        self.assertIn("shorthost", host_display)
        # Short dbname (≤6 chars): first 3 + "..."
        self.assertTrue(dbname_display.endswith("..."))

    # T13
    def test_long_host_truncated_to_last_30_chars(self):
        """Long hostname → only last 30 chars shown, with leading '...'."""
        long_host = "aaa" * 20 + ".railway.internal"
        url = f"postgresql://user:pass@{long_host}/staging_database_name"
        host_display, dbname_display = rsa.redact_url(url)
        self.assertTrue(host_display.startswith("..."))
        self.assertLessEqual(len(host_display.lstrip(".")), 30)
        self.assertIn("...", dbname_display)


class TestValidateNewCode(unittest.TestCase):
    """T14–T17: validate_new_code() — input validation."""

    # T14
    def test_matching_codes_of_sufficient_length_pass(self):
        """Two identical codes meeting the minimum length → no SystemExit."""
        rsa.validate_new_code("SecureCode123!", "SecureCode123!")

    # T15
    def test_mismatched_codes_abort(self):
        """Code and confirmation that differ → SystemExit."""
        with self.assertRaises(SystemExit):
            rsa.validate_new_code("SecureCode123!", "DifferentCode!")

    # T16
    def test_too_short_code_aborts(self):
        """Code shorter than minimum length → SystemExit."""
        short = "abc"
        with self.assertRaises(SystemExit):
            rsa.validate_new_code(short, short)

    # T17
    def test_empty_code_aborts(self):
        """Empty code → SystemExit (caught before length check)."""
        with self.assertRaises(SystemExit):
            rsa.validate_new_code("", "")


class TestFindExactlyOneSystemAdmin(unittest.TestCase):
    """T18–T19: find_exactly_one_system_admin() — uniqueness assertion.

    Uses unittest.mock.MagicMock to stub the SQLAlchemy session; no database
    connection is made.
    """

    def _make_session(self, users: list):
        """Return a mock session whose query().filter().all() yields `users`."""
        from unittest.mock import MagicMock
        mock_query   = MagicMock()
        mock_filter  = MagicMock()
        mock_filter.all.return_value = users
        mock_query.filter.return_value = mock_filter
        session = MagicMock()
        session.query.return_value = mock_query
        return session

    def _make_user(self, **kwargs):
        """Return a minimal mock user with valid staging attributes."""
        from unittest.mock import MagicMock
        u = MagicMock()
        u.id            = kwargs.get("id",            "aabbccdd-0000-0000-0000-000000000001")
        u.role          = kwargs.get("role",          "system_admin")
        u.active_status = kwargs.get("active_status", True)
        u.is_archived   = kwargs.get("is_archived",   False)
        u.display_name  = kwargs.get("display_name",  "System Admin")
        u.token_version = kwargs.get("token_version", 0)
        return u

    def _make_user_class(self):
        """Return a MagicMock acting as a SQLAlchemy User model class.

        SQLAlchemy column attribute access (User.role, User.active_status, etc.)
        returns an InstrumentedAttribute which is consumed by session.query().filter().
        MagicMock accepts any attribute access and returns a new Mock, satisfying
        the same contract without requiring a real database model.
        """
        from unittest.mock import MagicMock
        return MagicMock()

    # T18 — zero users → abort
    def test_zero_system_admins_aborts(self):
        """No active system_admin found → SystemExit."""
        session = self._make_session([])
        User    = self._make_user_class()
        with self.assertRaises(SystemExit):
            rsa.find_exactly_one_system_admin(session, User)

    # T19 — two users → abort
    def test_two_system_admins_aborts(self):
        """Two active system_admin accounts found → SystemExit (ambiguous target)."""
        users   = [self._make_user(), self._make_user(id="aabbccdd-0000-0000-0000-000000000002")]
        session = self._make_session(users)
        User    = self._make_user_class()
        with self.assertRaises(SystemExit):
            rsa.find_exactly_one_system_admin(session, User)


# ── Runner ─────────────────────────────────────────────────────────────────────

def _run() -> None:
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()
    for cls in [
        TestVerifyExactStagingEnv,
        TestVerifyDbUrl,
        TestRedactUrl,
        TestValidateNewCode,
        TestFindExactlyOneSystemAdmin,
    ]:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    if not result.wasSuccessful():
        sys.exit(1)


if __name__ == "__main__":
    _run()
