"""Break-glass: reset one System Administrator's access code from the operator side.

WHEN TO USE THIS
    Only when normal recovery is impossible: no other System Administrator can
    sign in, AND email recovery is unavailable (no verified address, or mail
    delivery is broken).

WHAT MAKES IT SAFE
    There is no hard-coded secret, nothing committed to git, and no HTTP route.
    The authority is deployment access: whoever can run a command against the
    production service can do this, and nobody else. That is deliberately the
    same authority that could already read the database.

USAGE
    railway run --service <backend> -- \\
        python -m scripts.breakglass_reset_sa --user-code SYSADMIN --i-understand

The new code is printed ONCE to stdout and never stored in plaintext.
"""
from __future__ import annotations

import argparse
import sys

sys.path.insert(0, ".")

from app.database import SessionLocal, utcnow          # noqa: E402
from app.models import AccessCode, User                # noqa: E402
from app.security import generate_code, hash_code      # noqa: E402
from app.services import audit                         # noqa: E402


def reset_system_admin(db, display_name: str) -> tuple[str, str]:
    """Reset one named system_admin. Returns (user_id, new_plaintext_code).

    Refuses anything that is not an active, non-archived system_admin: this
    tool exists to restore the last administrator, not to mint new authority.
    """
    matches = (db.query(User)
                 .filter(User.display_name == display_name,
                         User.role == "system_admin")
                 .all())
    if not matches:
        raise SystemExit(f"No system_admin found with display_name {display_name!r}.")
    if len(matches) > 1:
        raise SystemExit(
            f"{len(matches)} system_admins share display_name {display_name!r}. "
            f"Refusing to guess which one to reset.")

    u = matches[0]
    if u.is_archived:
        raise SystemExit(f"{display_name!r} is archived. Restore it first.")

    new_code = generate_code(12)
    for ac in db.query(AccessCode).filter(AccessCode.user_id == u.id).all():
        ac.active_status = False
        ac.failed_attempts = 0        # clear any lockout that helped cause this
        ac.locked_until = None
    db.add(AccessCode(user_id=u.id, code_hash=hash_code(new_code), active_status=True))

    u.active_status = True
    u.token_version = (u.token_version or 0) + 1   # kill every existing session
    db.flush()

    # principal=None: no authenticated user performed this. The audit row says
    # so rather than attributing it to whoever happened to be in the database.
    audit(db, None, object_type="user", object_id=u.id, action="breakglass_reset",
          new={"at": utcnow().isoformat(), "by": "operator (deployment access)"})
    db.commit()
    return u.id, new_code


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--user-code", required=True,
                    help="display_name of the system_admin to reset")
    ap.add_argument("--i-understand", action="store_true",
                    help="required: confirms this replaces a live credential")
    args = ap.parse_args()

    if not args.i_understand:
        print("Refusing to run without --i-understand. This replaces a live "
              "access code and signs out every existing session for that "
              "account.", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        uid, code = reset_system_admin(db, args.user_code)
    finally:
        db.close()

    print("\nBreak-glass reset complete.")
    print(f"  account:   {args.user_code}  ({uid})")
    print(f"  new code:  {code}")
    print("\nShown once. It is stored only as a hash. Sign in and change it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
