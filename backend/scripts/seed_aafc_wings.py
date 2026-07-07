"""Idempotent: ensure all AAFC Wing records exist.

7 Wing (Western Australia) and its squadrons are already seeded by seed_all.
This script adds Wing records for Wings 1–6 and 8 so the login selector
can show all wings nationally. Squadron records for other wings can be
added later as those units are onboarded.

Run via:
  railway run --service aafc-tms-backend python -m scripts.seed_aafc_wings
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.organisations import NationalEntity, Wing

# (code, name, short_name)
AAFC_WINGS = [
    ("1WG", "1 Wing — New South Wales North",             "1WG"),
    ("2WG", "2 Wing — New South Wales South / ACT",       "2WG"),
    ("3WG", "3 Wing — Victoria",                          "3WG"),
    ("4WG", "4 Wing — Queensland",                        "4WG"),
    ("5WG", "5 Wing — South Australia / Northern Territory", "5WG"),
    ("6WG", "6 Wing — Tasmania",                          "6WG"),
    ("7WG", "7 Wing — Western Australia",                 "7WG"),   # already exists; will be skipped
    ("8WG", "8 Wing — Australian Capital Territory",      "8WG"),
]


def run():
    with SessionLocal() as db:
        nat = db.query(NationalEntity).first()
        if not nat:
            print("ERROR: No NationalEntity found. Run the main seed first.")
            sys.exit(1)

        existing = {w.code: w for w in db.query(Wing).filter(Wing.is_archived == False).all()}
        added = 0
        updated = 0

        for code, name, short in AAFC_WINGS:
            if code in existing:
                # Update name/short_name if they have changed
                w = existing[code]
                if w.name != name or w.short_name != short:
                    w.name = name
                    w.short_name = short
                    updated += 1
                    print(f"  UPDATE {code} — {name}")
                else:
                    print(f"  SKIP   {code} (exists, unchanged)")
                continue
            w = Wing(national_id=nat.id, code=code, name=name, short_name=short, active_status=True)
            db.add(w)
            added += 1
            print(f"  ADD    {code} — {name}")

        db.commit()
        print(f"\nDone: {added} wing(s) added, {updated} updated.")


if __name__ == "__main__":
    run()
