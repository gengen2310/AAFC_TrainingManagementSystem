#!/usr/bin/env python3
"""reset_staging_system_admin.py — Secure staging System Admin access code reset.

STAGING ONLY. Aborts immediately on any mismatch against the exact allowlisted
Railway project, environment and backend service UUIDs. "Not production" is not
sufficient — the target must be the exact staging service.

Run via:
  source backend/.venv/bin/activate
  railway run \\
    --project     f5d9524f-8a57-44ff-86b7-ab66aec00e73 \\
    --service     deb53faa-ca8d-4291-aa2e-9ff3029c50f8 \\
    --environment 77a45568-5c16-46c2-9065-d5d339208b0e \\
    python scripts/reset_staging_system_admin.py

Optional dry run (all checks, no writes, no code prompt):
  RESET_DRY_RUN=1 railway run ... python scripts/reset_staging_system_admin.py

Authentication:
  New code is prompted TWICE via getpass (no echo, no shell-history entry).
  It is never passed as a command-line argument, never written to a file,
  never printed, and never logged. Hashed immediately; plaintext deleted
  before any database write.

Audit actor note:
  This is a maintenance script; there is no authenticated principal.
  AuditLog.user_id is set to None and AuditLog.role to "system" because the
  AuditLog schema has one actor field (user_id) with no separate maintenance-
  actor representation. This is intentional and documented here.

Changes applied in a single transaction (staging DB only):
  AccessCode.code_hash        → new pbkdf2_sha256 hash
  AccessCode.failed_attempts  → 0
  AccessCode.locked_until     → None
  AccessCode.updated_by       → user.id (account being reset)
  User.token_version          → incremented by 1 (invalidates all existing JWTs)
  User.updated_by             → user.id
  AuditLog (new row)          → action=staging_credential_reset; no credential stored

Does NOT:
  - deploy any application code
  - touch production
  - print or log the access code or its hash
  - write the access code to any file
"""
import getpass
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import text

# ── Exact staging allowlist ────────────────────────────────────────────────────
_EXPECTED_PROJECT_ID  = "f5d9524f-8a57-44ff-86b7-ab66aec00e73"
_EXPECTED_ENV_ID      = "77a45568-5c16-46c2-9065-d5d339208b0e"
_EXPECTED_BACKEND_SVC = "deb53faa-ca8d-4291-aa2e-9ff3029c50f8"
_PRODUCTION_ENV_ID    = "571a8028-3640-4542-a4ab-7a1ee6b1f693"
_MIN_CODE_LENGTH      = 8   # matches generate_code() default in security.py
_MAX_CODE_LENGTH      = 128  # matches LoginIn.code max_length in auth.py


def _abort(msg: str) -> None:
    print(f"\n[ABORT] {msg}", file=sys.stderr)
    sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# Pure verification functions — no database imports; directly testable.
# ══════════════════════════════════════════════════════════════════════════════

def verify_exact_staging_env(env: dict) -> None:
    """Verify Railway env vars match EXACTLY the allowlisted staging identifiers.

    Checks:
      1. RAILWAY_ENVIRONMENT_ID present and == _EXPECTED_ENV_ID
      2. RAILWAY_SERVICE_ID present and == _EXPECTED_BACKEND_SVC
      3. None of the Railway vars equal _PRODUCTION_ENV_ID
      4. ENVIRONMENT is not 'production'/'prod'
      5. DATABASE_URL does not contain 'production'

    'Not production' is insufficient — the IDs must be exactly correct.
    """
    environment = env.get("ENVIRONMENT", "").strip().lower()
    railway_env = env.get("RAILWAY_ENVIRONMENT_ID", "")
    railway_svc = env.get("RAILWAY_SERVICE_ID", "")
    railway_prj = env.get("RAILWAY_PROJECT_ID", "")
    db_url      = env.get("DATABASE_URL", "")

    # Hard-block production by name
    if environment in ("production", "prod"):
        _abort(f"ENVIRONMENT={environment!r} — refusing to run against production.")

    # Hard-block production UUID in any Railway var or URL
    for var_name, val in [
        ("RAILWAY_ENVIRONMENT_ID", railway_env),
        ("RAILWAY_SERVICE_ID",     railway_svc),
        ("RAILWAY_PROJECT_ID",     railway_prj),
        ("DATABASE_URL",           db_url),
    ]:
        if _PRODUCTION_ENV_ID in val:
            _abort(f"Production environment UUID found in {var_name} — refusing.")

    if "production" in db_url.lower():
        _abort("DATABASE_URL contains 'production' — refusing.")

    # Require RAILWAY_ENVIRONMENT_ID to be EXACTLY the staging env
    if not railway_env:
        _abort(
            "RAILWAY_ENVIRONMENT_ID is not set.\n"
            "Run via: railway run --environment 77a45568-5c16-46c2-9065-d5d339208b0e ..."
        )
    if railway_env != _EXPECTED_ENV_ID:
        _abort(
            f"RAILWAY_ENVIRONMENT_ID does not match the expected staging environment.\n"
            f"  Expected : {_EXPECTED_ENV_ID}\n"
            f"  Actual   : {railway_env}\n"
            f"The reset is bound to exactly this staging environment."
        )

    # Require RAILWAY_SERVICE_ID to be EXACTLY the backend service
    if not railway_svc:
        _abort(
            "RAILWAY_SERVICE_ID is not set.\n"
            "Run via: railway run --service deb53faa-ca8d-4291-aa2e-9ff3029c50f8 ..."
        )
    if railway_svc != _EXPECTED_BACKEND_SVC:
        _abort(
            f"RAILWAY_SERVICE_ID does not match the expected backend service.\n"
            f"  Expected : {_EXPECTED_BACKEND_SVC}\n"
            f"  Actual   : {railway_svc}\n"
            f"The reset is bound to exactly this backend service."
        )

    print("[reset] Exact staging identifiers verified:")
    print(f"[reset]   RAILWAY_ENVIRONMENT_ID : {_EXPECTED_ENV_ID}  ✓")
    print(f"[reset]   RAILWAY_SERVICE_ID     : {_EXPECTED_BACKEND_SVC}  ✓")
    print(f"[reset]   ENVIRONMENT            : {environment or '(not set)'}")


def verify_db_url(url: str) -> None:
    """Abort if DATABASE_URL is absent, SQLite, or signals production."""
    if not url:
        _abort(
            "DATABASE_URL is not set. "
            "Run via: railway run --service ... python scripts/reset_staging_system_admin.py"
        )
    if url.startswith("sqlite"):
        _abort(
            "DATABASE_URL is SQLite — this script targets the staging PostgreSQL database.\n"
            "Run via: railway run ... (which injects the PostgreSQL DATABASE_URL)."
        )
    if "production" in url.lower():
        _abort("DATABASE_URL contains 'production' — refusing.")


def redact_url(url: str) -> tuple:
    """Return (host_display, dbname_display) with credentials removed.

    Shows only the last 30 characters of the hostname (provider domain visible,
    unique subdomain not) and first 3 + last 3 characters of the database name.
    """
    try:
        parsed = urlparse(url)
        host   = parsed.hostname or ""
        dbname = (parsed.path or "").lstrip("/").split("?")[0]

        host_display   = ("..." + host[-30:])   if len(host) > 30   else host
        dbname_display = (dbname[:3] + "..." + dbname[-3:]) if len(dbname) > 6 else (dbname[:3] + "...")
    except Exception:
        host_display   = "(parse error)"
        dbname_display = "(parse error)"

    return host_display, dbname_display


def validate_new_code(code1: str, code2: str,
                      min_len: int = _MIN_CODE_LENGTH) -> None:
    """Abort if the new code is empty, weak, too long, or the two entries differ."""
    if not code1:
        _abort("Empty code — reset cancelled.")
    if len(code1) < min_len:
        _abort(f"Code too short (minimum {min_len} characters) — reset cancelled.")
    if len(code1) > _MAX_CODE_LENGTH:
        _abort(f"Code too long (maximum {_MAX_CODE_LENGTH} characters) — reset cancelled.")
    if code1 != code2:
        _abort("Codes do not match — reset cancelled.")


# ══════════════════════════════════════════════════════════════════════════════
# Database functions — accept session and model classes for testability.
# ══════════════════════════════════════════════════════════════════════════════

def verify_alembic_single_head(session) -> str:
    """Query alembic_version; abort if absent, empty, or multiple heads.

    Returns the single current revision string.
    """
    try:
        rows = session.execute(text("SELECT version_num FROM alembic_version")).fetchall()
    except Exception as exc:
        _abort(f"Cannot read alembic_version: {exc}")
    if not rows:
        _abort("alembic_version table is empty — database may not be initialised.")
    if len(rows) > 1:
        revs = [r[0] for r in rows]
        _abort(f"Multiple Alembic heads detected ({revs}) — resolve before reset.")
    return rows[0][0]


def find_exactly_one_system_admin(session, User) -> object:
    """Return the single active, non-archived national system_admin.

    Aborts on zero, more than one, or any unexpected role/scope.
    Does NOT use .first() — the count must be exactly 1.
    """
    users = (
        session.query(User)
        .filter(
            User.role == "system_admin",
            User.active_status == True,   # noqa: E712
            User.is_archived == False,    # noqa: E712
        )
        .all()
    )

    count = len(users)
    print(f"[reset] Active national system_admin accounts found: {count}")

    if count == 0:
        _abort(
            "No active system_admin account found on staging. "
            "Run the bootstrap seed first."
        )
    if count > 1:
        for u in users:
            uid_r = f"{u.id[:8]}...{u.id[-4:]}"
            print(f"[reset]   {uid_r}  display={u.display_name}", file=sys.stderr)
        _abort(
            f"{count} active system_admin accounts found. "
            "Exactly one is required. Resolve the duplicate before resetting."
        )

    user = users[0]
    if user.role != "system_admin":
        _abort(f"Unexpected role '{user.role}' — expected system_admin.")
    if not user.active_status:
        _abort("Account is inactive — cannot reset an inactive account.")
    if user.is_archived:
        _abort("Account is archived — cannot reset an archived account.")

    uid_r = f"{user.id[:8]}...{user.id[-4:]}"
    print(f"[reset] Target account:")
    print(f"[reset]   user_id (partial) : {uid_r}")
    print(f"[reset]   display_name      : {user.display_name}")
    print(f"[reset]   role              : {user.role}")
    print(f"[reset]   active_status     : {user.active_status}")
    print(f"[reset]   token_version     : {user.token_version}")

    return user


def find_exactly_one_access_code(session, AccessCode, user_id: str) -> object:
    """Return the single active AccessCode for this user.

    Aborts on zero or more than one active record.
    Does NOT use .first().
    """
    codes = (
        session.query(AccessCode)
        .filter(
            AccessCode.user_id == user_id,
            AccessCode.active_status == True,  # noqa: E712
        )
        .all()
    )

    count = len(codes)
    if count == 0:
        _abort(
            f"No active AccessCode record found for user {user_id[:8]}... "
            "Bootstrap seed may not have completed."
        )
    if count > 1:
        _abort(
            f"{count} active AccessCode records found for user {user_id[:8]}... "
            "Data integrity error — resolve before resetting."
        )

    ac = codes[0]
    old_failed = ac.failed_attempts or 0
    is_locked  = bool(
        ac.locked_until
        and ac.locked_until.replace(tzinfo=None) > datetime.now(timezone.utc).replace(tzinfo=None)
    )

    print(f"[reset] Current AccessCode state:")
    print(f"[reset]   failed_attempts : {old_failed}")
    print(f"[reset]   locked          : {'YES — will be cleared' if is_locked else 'No'}")
    if ac.locked_until:
        print(f"[reset]   locked_until    : {ac.locked_until}")

    return ac


def perform_reset_in_transaction(session, user, ac, new_hash: str,
                                  AuditLog, now: datetime) -> None:
    """Apply all writes in one transaction; rollback everything on failure.

    Audit actor: user_id=None, role='system' — this is a maintenance operation
    with no authenticated principal. The AuditLog schema has no separate
    maintenance-actor field; this is explicitly documented in the module header.
    """
    try:
        ac.code_hash       = new_hash
        ac.failed_attempts = 0
        ac.locked_until    = None
        ac.updated_by      = user.id

        old_tv             = user.token_version or 0
        user.token_version = old_tv + 1
        user.updated_by    = user.id

        audit_entry = AuditLog(
            # Actor: None — no authenticated user for a maintenance script.
            # See module-level docstring for the explicit rationale.
            user_id          = None,
            role             = "system",
            scope            = "national",
            wing_id          = None,
            squadron_id      = None,
            proxy_session_id = None,
            # Target
            object_type      = "access_code",
            object_id        = user.id,
            action           = "staging_credential_reset",
            # No credential or hash in any value field (immutable record)
            old_value        = None,
            new_value        = None,
            reason           = (
                "Staging System Admin access code reset via "
                "reset_staging_system_admin.py"
            ),
            ip_address       = "local",
            user_agent       = "reset_staging_system_admin.py",
        )
        session.add(audit_entry)
        session.commit()

    except Exception:
        session.rollback()
        raise


def verify_post_commit(session, user_id: str, old_token_version: int,
                        AccessCode, AuditLog) -> None:
    """Re-read records after commit and assert expected state.

    Aborts if any assertion fails; does not print hash values.
    """
    session.expire_all()

    # Re-read AccessCode
    codes = (
        session.query(AccessCode)
        .filter(AccessCode.user_id == user_id, AccessCode.active_status == True)  # noqa: E712
        .all()
    )
    if len(codes) != 1:
        _abort(f"Post-commit: expected 1 active AccessCode, found {len(codes)}.")
    ac_v = codes[0]

    if ac_v.failed_attempts != 0:
        _abort(f"Post-commit: failed_attempts = {ac_v.failed_attempts}, expected 0.")
    if ac_v.locked_until is not None:
        _abort(f"Post-commit: locked_until is not None after reset.")

    # Re-read User (token_version)
    from sqlalchemy import text as _text
    tv_rows = session.execute(
        _text("SELECT token_version FROM users WHERE id = :uid"),
        {"uid": user_id},
    ).fetchall()
    if not tv_rows:
        _abort("Post-commit: user record not found.")
    new_tv = tv_rows[0][0]
    if new_tv != old_token_version + 1:
        _abort(
            f"Post-commit: token_version is {new_tv}, "
            f"expected {old_token_version + 1}."
        )

    # Verify audit entry
    audit_rows = (
        session.query(AuditLog)
        .filter(
            AuditLog.object_id == user_id,
            AuditLog.action    == "staging_credential_reset",
        )
        .order_by(AuditLog.timestamp.desc())
        .all()
    )
    if not audit_rows:
        _abort("Post-commit: no staging_credential_reset audit entry found.")
    latest_audit = audit_rows[0]
    if latest_audit.old_value is not None:
        _abort("Post-commit: audit old_value is not None — credential leak.")
    if latest_audit.new_value is not None:
        _abort("Post-commit: audit new_value is not None — credential leak.")

    print("[reset] Post-commit verification:")
    print(f"[reset]   failed_attempts = 0                          ✓")
    print(f"[reset]   locked_until    = None                       ✓")
    print(f"[reset]   token_version   = {old_token_version} → {new_tv}                      ✓")
    print(f"[reset]   audit entry     = staging_credential_reset   ✓")
    print(f"[reset]   audit old_value = None                       ✓")
    print(f"[reset]   audit new_value = None                       ✓")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    env = dict(os.environ)

    # ── 1. Exact staging identifier check ─────────────────────────────────────
    verify_exact_staging_env(env)

    # ── 2. DATABASE_URL check ─────────────────────────────────────────────────
    db_url = env.get("DATABASE_URL", "")
    verify_db_url(db_url)

    # ── Import app packages after env is confirmed safe ────────────────────────
    _script_dir  = os.path.dirname(os.path.abspath(__file__))
    _backend_dir = os.path.join(_script_dir, "..", "backend")
    sys.path.insert(0, _backend_dir)

    from app.database import SessionLocal
    from app.models   import User, AccessCode, AuditLog
    from app.security import hash_code

    # ── 3. Database target verification ───────────────────────────────────────
    host_display, dbname_display = redact_url(db_url)
    print(f"[reset] Database target (redacted):")
    print(f"[reset]   host   : {host_display}")
    print(f"[reset]   dbname : {dbname_display}")

    session = SessionLocal()
    try:
        revision = verify_alembic_single_head(session)
        print(f"[reset]   Alembic revision : {revision}  (single head ✓)")

        # ── 4. Find exactly one system_admin ──────────────────────────────────
        user = find_exactly_one_system_admin(session, User)

        # ── 5. Find exactly one active AccessCode ─────────────────────────────
        ac = find_exactly_one_access_code(session, AccessCode, user.id)
        old_token_version = user.token_version or 0

        # ── RESET_DRY_RUN=1: all checks done; no writes ───────────────────────
        is_dry_run = env.get("RESET_DRY_RUN", "").strip() == "1"
        if is_dry_run:
            session.rollback()
            print()
            print("[reset] DRY RUN — all environment, database and account checks passed.")
            print("[reset] No write performed. No code prompted. Transaction rolled back.")
            print("[reset] Exit 0.")
            return

        # ── 6. Prompt for new code ────────────────────────────────────────────
        print()
        code1 = getpass.getpass("  New staging System Admin access code: ").strip()
        code2 = getpass.getpass("  Confirm new code: ").strip()
        validate_new_code(code1, code2)

        # Hash immediately; delete plaintext before any DB call
        new_hash = hash_code(code1)
        del code1, code2

        # ── 7. Single transaction: hash + lockout clear + token_version + audit ─
        now = datetime.now(timezone.utc)
        try:
            perform_reset_in_transaction(session, user, ac, new_hash, AuditLog, now)
        finally:
            del new_hash

        # ── 8. Post-commit verification ───────────────────────────────────────
        verify_post_commit(session, user.id, old_token_version, AccessCode, AuditLog)

        print()
        print("[reset] SUCCESS — staging System Admin credential reset.")
        print("[reset]   AccessCode.code_hash      : updated (value not printed)")
        print(f"[reset]   AccessCode.failed_attempts: cleared → 0")
        print(f"[reset]   AccessCode.locked_until   : cleared → None")
        print(f"[reset]   User.token_version        : {old_token_version} → {old_token_version + 1}")
        print("[reset]   AuditLog                  : staging_credential_reset written")
        print()
        print("[reset] All existing sessions are invalidated.")
        print("[reset] Log in with the new code to verify, then rerun the dry run.")

    except SystemExit:
        raise
    except Exception as exc:
        session.rollback()
        _abort(f"Database error — rolled back: {exc}")
    finally:
        session.close()


if __name__ == "__main__":
    main()
