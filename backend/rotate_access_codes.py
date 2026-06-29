"""Rotate ALL access codes to strong random values for production cut-over.

The seeded demo codes (ADMIN703, 703SQN2026, ADMIN7WG, NATIONAL2026, ...) MUST NOT be used with
real data. This tool replaces every active access code with a strong random one, writes the new codes
to a private file you hand out securely, and never prints them to stdout in full.

Usage:
    python rotate_access_codes.py --out ../secret_codes_2026.csv
    python rotate_access_codes.py --dry-run        # show how many would change, change nothing

The output CSV (user_id,role,new_code) is sensitive: distribute over a secure channel, then delete.
It is git-ignored by name pattern; never commit it.
"""
import argparse
import csv
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
        db.commit()
        with open(args.out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["user_id", "role", "new_code"])
            w.writerows(rows)
        print(f"Rotated {len(rows)} access codes. New codes written to {args.out!r}.")
        print("SECURITY: distribute securely, then DELETE this file. Codes are not recoverable once deleted.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
