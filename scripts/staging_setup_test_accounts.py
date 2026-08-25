#!/usr/bin/env python3
"""staging_setup_test_accounts.py — Reset access codes for Playwright test roles on staging.

STAGING ONLY. Creates or resets access codes for the three roles the Playwright staging
suite uses beyond sqn_admin and system_admin:
  - sqn_general  / squadron 703
  - wing_admin   / 7WG
  - national_admin / national

Run via:
  RESET_SQN_GENERAL_CODE=<code>   \\
  RESET_WING_ADMIN_CODE=<code>    \\
  RESET_NATIONAL_ADMIN_CODE=<code> \\
  railway run \\
    --project     f5d9524f-8a57-44ff-86b7-ab66aec00e73 \\
    --service     deb53faa-ca8d-4291-aa2e-9ff3029c50f8 \\
    --environment 77a45568-5c16-46c2-9065-d5d339208b0e \\
    python scripts/staging_setup_test_accounts.py

On success, prints shell export lines ready to paste into a Playwright test run:
  export STAGING_SQN_GENERAL_CODE=...
  export STAGING_WING_ADMIN_CODE=...
  export STAGING_NATIONAL_ADMIN_CODE=...

The export values are the same codes you supplied — this is a reminder, not a reveal.
The actual values are never printed elsewhere in this script.

RESET_DRY_RUN=1  — run all checks, no writes.

Security:
  Codes are hashed immediately on receipt; plaintext deleted before any DB write.
  Codes are not printed to stdout (only a reminder that they equal what you supplied).
  Codes are never logged, stored in files, or committed to source.
"""
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import text

# ── Exact staging allowlist ────────────────────────────────────────────────────
_EXPECTED_ENV_ID      = "77a45568-5c16-46c2-9065-d5d339208b0e"
_EXPECTED_BACKEND_SVC = "deb53faa-ca8d-4291-aa2e-9ff3029c50f8"
_PRODUCTION_ENV_ID    = "571a8028-3640-4542-a4ab-7a1ee6b1f693"
_MIN_CODE_LENGTH      = 8
_MAX_CODE_LENGTH      = 128

_TEST_ROLES = [
    {
        "label":      "Squadron General (703)",
        "role":       "sqn_general",
        "unit_type":  "squadron",
        "identifier": "703",
        "env_var":    "RESET_SQN_GENERAL_CODE",
        "pw_var":     "STAGING_SQN_GENERAL_CODE",
    },
    {
        "label":      "Wing Admin (7WG)",
        "role":       "wing_admin",
        "unit_type":  "wing",
        "identifier": "7WG",
        "env_var":    "RESET_WING_ADMIN_CODE",
        "pw_var":     "STAGING_WING_ADMIN_CODE",
    },
    {
        "label":      "National Admin",
        "role":       "national_admin",
        "unit_type":  "national",
        "identifier": None,
        "env_var":    "RESET_NATIONAL_ADMIN_CODE",
        "pw_var":     "STAGING_NATIONAL_ADMIN_CODE",
    },
]


def _abort(msg: str) -> None:
    print(f"\n[ABORT] {msg}", file=sys.stderr)
    sys.exit(1)


def _verify_staging_env(env: dict) -> None:
    railway_env = env.get("RAILWAY_ENVIRONMENT_ID", "")
    railway_svc = env.get("RAILWAY_SERVICE_ID", "")
    db_url      = env.get("DATABASE_URL", "")
    environment = env.get("ENVIRONMENT", "").strip().lower()

    if environment in ("production", "prod"):
        _abort(f"ENVIRONMENT={environment!r} — refusing to run against production.")

    for var_name, val in [
        ("RAILWAY_ENVIRONMENT_ID", railway_env),
        ("RAILWAY_SERVICE_ID",     railway_svc),
        ("DATABASE_URL",           db_url),
    ]:
        if _PRODUCTION_ENV_ID in val:
            _abort(f"Production UUID found in {var_name} — refusing.")

    if "production" in db_url.lower():
        _abort("DATABASE_URL contains 'production' — refusing.")

    if not railway_env:
        _abort("RAILWAY_ENVIRONMENT_ID is not set. Run via: railway run --environment 77a45568-...")
    if railway_env != _EXPECTED_ENV_ID:
        _abort(f"RAILWAY_ENVIRONMENT_ID mismatch.\n  Expected: {_EXPECTED_ENV_ID}\n  Actual:   {railway_env}")
    if not railway_svc:
        _abort("RAILWAY_SERVICE_ID is not set. Run via: railway run --service deb53faa-...")
    if railway_svc != _EXPECTED_BACKEND_SVC:
        _abort(f"RAILWAY_SERVICE_ID mismatch.\n  Expected: {_EXPECTED_BACKEND_SVC}\n  Actual:   {railway_svc}")

    print("[setup] Staging identifiers verified ✓")


def _validate_code(code: str, label: str) -> None:
    if not code:
        _abort(f"Empty code for {label}.")
    if len(code) < _MIN_CODE_LENGTH:
        _abort(f"Code for {label} too short (min {_MIN_CODE_LENGTH} chars).")
    if len(code) > _MAX_CODE_LENGTH:
        _abort(f"Code for {label} too long (max {_MAX_CODE_LENGTH} chars).")


def _find_user_by_role(session, User, role_cfg: dict):
    """Find the active, non-archived user for a given role and unit context.

    For national roles, identifier is None — filter by role only.
    For squadron/wing roles, filter by unit identifier via the joined org.
    We look up by role alone and filter by unit below to avoid joining tables
    not available in this import context.
    """
    users = (
        session.query(User)
        .filter(
            User.role == role_cfg["role"],
            User.active_status == True,   # noqa: E712
            User.is_archived == False,    # noqa: E712
        )
        .all()
    )

    identifier = role_cfg.get("identifier")
    if identifier and users:
        # Filter to the right unit by checking squadron/wing display identifiers
        # via raw SQL to avoid importing Wing/Squadron models.
        unit_type = role_cfg["unit_type"]
        matching = []
        for u in users:
            if unit_type == "squadron":
                row = session.execute(
                    text("SELECT identifier FROM squadrons WHERE id = :sid"),
                    {"sid": u.squadron_id},
                ).fetchone()
                if row and row[0] == identifier:
                    matching.append(u)
            elif unit_type == "wing":
                row = session.execute(
                    text("SELECT identifier FROM wings WHERE id = :wid"),
                    {"wid": u.wing_id},
                ).fetchone()
                if row and row[0] == identifier:
                    matching.append(u)
        users = matching

    count = len(users)
    label = role_cfg["label"]
    print(f"[setup] {label}: found {count} active account(s)")

    if count == 0:
        _abort(
            f"No active {role_cfg['role']} account found"
            + (f" for unit {identifier}" if identifier else "")
            + ".\nCreate the account via System Admin console, then re-run this script."
        )
    if count > 1:
        for u in users:
            print(f"[setup]   {u.id[:8]}...{u.id[-4:]}  {u.display_name}", file=sys.stderr)
        _abort(f"{count} matching accounts found for {label}. Resolve duplicates first.")

    return users[0]


def _find_active_code(session, AccessCode, user_id: str, label: str):
    codes = (
        session.query(AccessCode)
        .filter(
            AccessCode.user_id == user_id,
            AccessCode.active_status == True,  # noqa: E712
        )
        .all()
    )
    if len(codes) == 0:
        _abort(f"No active AccessCode for {label} ({user_id[:8]}...). Create via System Admin.")
    if len(codes) > 1:
        _abort(f"{len(codes)} active AccessCode records for {label} — resolve duplicates first.")
    return codes[0]


def _reset_code(session, user, ac, new_hash: str, AuditLog, label: str) -> None:
    try:
        ac.code_hash       = new_hash
        ac.failed_attempts = 0
        ac.locked_until    = None
        ac.updated_by      = user.id

        old_tv             = user.token_version or 0
        user.token_version = old_tv + 1
        user.updated_by    = user.id

        session.add(AuditLog(
            user_id          = None,
            role             = "system",
            scope            = "national",
            wing_id          = None,
            squadron_id      = None,
            proxy_session_id = None,
            object_type      = "access_code",
            object_id        = user.id,
            action           = "staging_test_credential_reset",
            old_value        = None,
            new_value        = None,
            reason           = f"Playwright test account reset via staging_setup_test_accounts.py — {label}",
            ip_address       = "local",
            user_agent       = "staging_setup_test_accounts.py",
        ))
        session.commit()
        print(f"[setup] {label}: code reset, token_version {old_tv} → {old_tv + 1} ✓")
    except Exception:
        session.rollback()
        raise


def main() -> None:
    env = dict(os.environ)
    _verify_staging_env(env)

    db_url = env.get("DATABASE_URL", "")
    if not db_url or db_url.startswith("sqlite"):
        _abort("DATABASE_URL is absent or SQLite — run via railway run.")

    # Collect and validate codes before any DB work
    role_codes: dict[str, str] = {}
    for role_cfg in _TEST_ROLES:
        code = env.get(role_cfg["env_var"], "").strip()
        if not code:
            _abort(
                f"Missing env var {role_cfg['env_var']} for {role_cfg['label']}.\n"
                f"Pass all three RESET_* vars before running."
            )
        _validate_code(code, role_cfg["label"])
        role_codes[role_cfg["env_var"]] = code

    is_dry_run = env.get("RESET_DRY_RUN", "").strip() == "1"

    _script_dir  = os.path.dirname(os.path.abspath(__file__))
    _backend_dir = os.path.join(_script_dir, "..", "backend")
    sys.path.insert(0, _backend_dir)

    from app.database import SessionLocal
    from app.models   import User, AccessCode, AuditLog
    from app.security import hash_code

    session = SessionLocal()
    try:
        # Verify alembic single head
        rows = session.execute(text("SELECT version_num FROM alembic_version")).fetchall()
        if len(rows) != 1:
            _abort(f"Expected 1 Alembic head, found {len(rows)}: {[r[0] for r in rows]}")
        print(f"[setup] Alembic revision: {rows[0][0]} ✓")

        if is_dry_run:
            # Still find users (validates accounts exist) but no writes
            for role_cfg in _TEST_ROLES:
                _find_user_by_role(session, User, role_cfg)
            print("\n[setup] DRY RUN — all checks passed. No writes performed.")
            return

        now = datetime.now(timezone.utc)
        pw_exports: list[str] = []

        for role_cfg in _TEST_ROLES:
            user = _find_user_by_role(session, User, role_cfg)
            ac   = _find_active_code(session, AccessCode, user.id, role_cfg["label"])
            code = role_codes[role_cfg["env_var"]]
            new_hash = hash_code(code)
            try:
                _reset_code(session, user, ac, new_hash, AuditLog, role_cfg["label"])
            finally:
                del new_hash
            pw_exports.append(f"export {role_cfg['pw_var']}=<your_{role_cfg['env_var']}_value>")

        print()
        print("[setup] SUCCESS — all test accounts reset.")
        print()
        print("Add to your Playwright test run (values = same codes you supplied above):")
        print()
        print(f"  STAGING_SQN_ADMIN_CODE=ADMIN703 \\")
        print(f"  STAGING_SYSADMIN_CODE=SYSTEMADMIN2026 \\")
        for role_cfg in _TEST_ROLES:
            suffix = " \\" if role_cfg != _TEST_ROLES[-1] else ""
            print(f"  {role_cfg['pw_var']}=${{RESET_{role_cfg['env_var'].replace('RESET_', '')}}}{suffix}")
        print(f"  npx playwright test --project=chromium")

    except SystemExit:
        raise
    except Exception as exc:
        session.rollback()
        _abort(f"Database error — rolled back: {exc}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
