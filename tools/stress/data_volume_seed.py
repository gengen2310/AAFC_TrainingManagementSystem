#!/usr/bin/env python3
"""Data volume seeder — generates larger-than-demo data sets for performance testing.

WARNING: Run only against a TEST database, never production.
Creates additional wings, squadrons, users, curriculum items and parade nights
to test system behaviour under volume.

Usage:
    cd backend
    DATABASE_URL=sqlite:///./test_volume.db python ../tools/stress/data_volume_seed.py

Options:
    --wings N       Number of extra wings to create (default: 3)
    --sqns-per-wing N  Squadrons per wing (default: 5)
    --users-per-sqn N  Users per squadron (default: 3)
    --curriculum N  Curriculum items per squadron (default: 50)
"""
import argparse
import sys
import os
import uuid

# Must be run from backend/ directory or with PYTHONPATH set
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

try:
    from app.database import get_db, Base, engine
    from app.models import Wing, Squadron, User, AccessCode, NationalEntity, CurriculumItem
    from app.security import hash_code
    from sqlalchemy.orm import Session
except ImportError as e:
    print(f"Import error: {e}")
    print("Run from backend/ directory: DATABASE_URL=sqlite:///./test_volume.db python ../tools/stress/data_volume_seed.py")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wings", type=int, default=3)
    parser.add_argument("--sqns-per-wing", type=int, default=5)
    parser.add_argument("--users-per-sqn", type=int, default=3)
    parser.add_argument("--curriculum", type=int, default=50)
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        nat = db.query(NationalEntity).first()
        if not nat:
            nat = NationalEntity(name="AAFC National", code="NAT")
            db.add(nat)
            db.flush()

        total_users = 0
        total_sqns = 0
        total_curr = 0

        for wi in range(args.wings):
            wing = Wing(
                name=f"Test Wing {wi+1}",
                code=f"TW{wi+1}",
                national_id=nat.id,
            )
            db.add(wing)
            db.flush()

            for si in range(args.sqns_per_wing):
                sqn = Squadron(
                    name=f"Test Sqn {wi+1}-{si+1}",
                    code=f"T{wi+1}{si+1:02d}",
                    wing_id=wing.id,
                    unit_type="squadron",
                )
                db.add(sqn)
                db.flush()
                total_sqns += 1

                for ui in range(args.users_per_sqn):
                    role = "sqn_admin" if ui == 0 else "sqn_general"
                    u = User(
                        display_name=f"User {wi+1}-{si+1}-{ui+1}",
                        role=role,
                        squadron_id=sqn.id,
                        wing_id=wing.id,
                        national_id=nat.id,
                    )
                    db.add(u)
                    db.flush()
                    code = f"TST{wi+1}{si+1:02d}{ui+1}"
                    db.add(AccessCode(user_id=u.id, code_hash=hash_code(code)))
                    total_users += 1

                for ci in range(args.curriculum):
                    item = CurriculumItem(
                        squadron_id=sqn.id,
                        scope="local",
                        title=f"Vol Test Mission {ci+1} — Wing {wi+1} SQN {si+1}",
                        phase_code="PO",
                        level="proficiency",
                        duration_minutes=60,
                        part_count=1,
                    )
                    db.add(item)
                    total_curr += 1

        db.commit()
        print(f"\nVolume seed complete:")
        print(f"  Wings created    : {args.wings}")
        print(f"  Squadrons created: {total_sqns}")
        print(f"  Users created    : {total_users}")
        print(f"  Curriculum items : {total_curr}")
        print()
        print("  WARNING: This data is for performance testing only.")
        print("  Do not use this script against a production or demo database.")


if __name__ == "__main__":
    main()
