"""Staging bootstrap seeder.

Creates a single system_admin account using the access code supplied via the
STAGING_BOOTSTRAP_SYSADMIN_CODE environment variable. Idempotent: does nothing
if a system_admin already exists.

No access codes, credentials or secrets are ever written to stdout, stderr,
application logs or the database in plaintext. The bootstrap code is hashed
immediately on read; the plaintext reference is deleted before any DB call.

All accounts other than system_admin are provisioned through the System
Console after first login. Org structure (Wings, Squadrons) is also created
through the System Console — this seed creates only the minimum needed to
log in.

Lifecycle:
  1. Set STAGING_BOOTSTRAP_SYSADMIN_CODE in Render before first deploy.
  2. On first container start the seed runs, hashes the code, creates the user.
  3. Log in to the System Console with that code.
  4. Reset the code via System Console → your account (one-time display).
  5. Remove STAGING_BOOTSTRAP_SYSADMIN_CODE from the Render environment.
  6. Redeploy — subsequent starts skip this seed entirely.
"""
import os
import sys

from ..database import SessionLocal
from ..models import NationalEntity, User, AccessCode
from ..security import hash_code


def staging_seed() -> None:
    bootstrap_code = os.environ.get("STAGING_BOOTSTRAP_SYSADMIN_CODE", "").strip()
    if not bootstrap_code:
        print("[staging_seed] STAGING_BOOTSTRAP_SYSADMIN_CODE not set — skipping bootstrap.",
              file=sys.stderr)
        return

    db = SessionLocal()
    try:
        if db.query(User).filter_by(role="system_admin").count() > 0:
            print("[staging_seed] system_admin already exists — skipping (idempotent).",
                  file=sys.stderr)
            return

        # Hash immediately; explicitly delete the plaintext variable before
        # any database interaction so it cannot appear in ORM query logs.
        code_hash = hash_code(bootstrap_code)
        del bootstrap_code

        nat = db.query(NationalEntity).first()
        if nat is None:
            nat = NationalEntity(name="AAFC National Headquarters", short_name="NATIONAL")
            db.add(nat)
            db.flush()

        sysadmin = User(
            display_name="System Admin",
            role="system_admin",
            national_id=nat.id,
            active_status=True,
        )
        db.add(sysadmin)
        db.flush()

        db.add(AccessCode(user_id=sysadmin.id, code_hash=code_hash))
        db.commit()

        print("[staging_seed] Bootstrap complete: system_admin account created.",
              file=sys.stderr)
        print("[staging_seed] Log in, reset the code via System Console, then remove",
              file=sys.stderr)
        print("[staging_seed] STAGING_BOOTSTRAP_SYSADMIN_CODE from the Render environment.",
              file=sys.stderr)
    finally:
        db.close()


if __name__ == "__main__":
    staging_seed()
