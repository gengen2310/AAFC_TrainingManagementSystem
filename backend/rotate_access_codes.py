"""Rotate ALL access codes to strong random values for production cut-over.

The seeded demo codes (ADMIN703, 703SQN2026, ADMIN7WG, NATIONAL2026, ...) MUST NOT be used with
real data. This tool replaces every active access code with a strong random one, writes the new codes
to a private file you hand out securely, and never prints them to stdout in full.

Usage:
    python rotate_access_codes.py --out ../secret_codes_2026.csv
    python rotate_access_codes.py --dry-run        # show how many would change, change nothing

The output CSV (user_id,role,new_code) is sensitive: distribute over a secure channel, then delete.
It is git-ignored by name pattern (secret_codes*.csv) -- a pattern that was
missing from .gitignore until 2026-09-02, so this sentence was false for as
long as it had been written. Never commit it.
"""
import argparse
import csv
import os
import secrets
import string

from app.database import SessionLocal
from app.models import User, AccessCode
from app.security import hash_code


def _strong_code(role: str) -> str:
    # Human-typeable but strong: 4 groups of 4 from an unambiguous alphabet.
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no I,O,0,1
    body = "-".join("".join(secrets.choice(alphabet) for _ in range(4)) for _ in range(4))
    return body


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="secret_codes.csv", help="where to write the new codes (sensitive)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        codes = db.query(AccessCode).all()
        if args.dry_run:
            print(f"[dry-run] {len(codes)} access codes would be rotated. No changes made.")
            return
        rows = []
        for ac in codes:
            user = db.get(User, ac.user_id)
            role = getattr(user, "role", "unknown")
            new_code = _strong_code(role)
            ac.code_hash = hash_code(new_code)
            rows.append((ac.user_id, role, new_code))
        # ORDER IS THE SAFETY PROPERTY. This used to commit first and write the
        # CSV afterwards, so a crash in between rotated every code in the
        # database while the only copy of the new codes died with the process --
        # an unrecoverable lockout of every account, because the hashes are
        # one-way and the plaintext existed nowhere else.
        #
        # That is not hypothetical. On 2026-09-02 a rotation of 1249 codes was
        # killed by a 10-minute timeout partway through; it happened to die
        # during hashing rather than after the commit, which is the only reason
        # staging still had working credentials.
        #
        # Written and fsynced BEFORE the commit, the two failure modes become:
        #   crash before commit -> codes unchanged, CSV may be stale: delete and retry
        #   crash after commit  -> codes changed, CSV on disk and complete
        # Neither loses access. A stale CSV is confusing; a lost one is fatal.
        with open(args.out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["user_id", "role", "new_code"])
            w.writerows(rows)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(args.out, 0o600)
        print(f"New codes written to {args.out!r} ({len(rows)} rows). Committing…")
        db.commit()
        print(f"Rotated {len(rows)} access codes.")
        print("SECURITY: distribute securely, then DELETE this file. Codes are not recoverable once deleted.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
