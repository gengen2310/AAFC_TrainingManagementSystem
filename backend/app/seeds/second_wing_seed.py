"""Second Wing synthetic seed — Level B pilot readiness (staging only).

Creates a second Wing (e.g. 1WG) with two synthetic squadrons and one account
per role (wing_admin, sqn_admin, sqn_general) under that wing. Generates
synthetic access codes and prints them to stdout for capture by the operator.

Idempotent: skips any entity that already exists.

SAFETY:
- Rejected if ENVIRONMENT == 'production' or 'prod'.
- Uses synthetic data only. No real cadet, personal, or operational data.
- Printed access codes are one-time output. They are hashed in the DB;
  the plaintext is never stored.

Usage (from backend/ directory):
    source .venv/bin/activate
    ENVIRONMENT=staging DATABASE_URL=<staging-url> \\
      python -m app.seeds.second_wing_seed

Optional env vars:
    WING2_CODE      Wing code (default: 1WG)
    WING2_NAME      Wing name (default: 1 Wing HQ)
    SQN2A_CODE      First squadron code (default: 101)
    SQN2A_NAME      First squadron name (default: 101 Squadron AAFC)
    SQN2B_CODE      Second squadron code (default: 102)
    SQN2B_NAME      Second squadron name (default: 102 Squadron AAFC)
"""
import os
import sys

from ..database import SessionLocal
from ..models import NationalEntity, Wing, Squadron, User, AccessCode
from ..security import generate_code, hash_code


def second_wing_seed() -> None:
    env = os.environ.get("ENVIRONMENT", "development").lower()
    if env in ("production", "prod"):
        print("[second_wing_seed] REFUSED: cannot run against production environment.",
              file=sys.stderr)
        sys.exit(1)

    wing_code  = os.environ.get("WING2_CODE",  "1WG")
    wing_name  = os.environ.get("WING2_NAME",  "1 Wing HQ")
    sqn_a_code = os.environ.get("SQN2A_CODE",  "101")
    sqn_a_name = os.environ.get("SQN2A_NAME",  "101 Squadron AAFC")
    sqn_b_code = os.environ.get("SQN2B_CODE",  "102")
    sqn_b_name = os.environ.get("SQN2B_NAME",  "102 Squadron AAFC")

    db = SessionLocal()
    codes_out = []
    try:
        nat = db.query(NationalEntity).first()
        if not nat:
            print("[second_wing_seed] No NationalEntity found. Run migrations and staging_seed first.",
                  file=sys.stderr)
            sys.exit(1)

        # ── Wing ────────────────────────────────────────────────────────────────
        wing = db.query(Wing).filter(Wing.code == wing_code,
                                     Wing.is_archived == False).first()  # noqa: E712
        if wing:
            print(f"[second_wing_seed] Wing {wing_code} already exists — skipping Wing create.",
                  file=sys.stderr)
        else:
            wing = Wing(
                national_id=nat.id,
                code=wing_code,
                name=wing_name,
                short_name=wing_code,
                active_status=True,
            )
            db.add(wing)
            db.flush()
            print(f"[second_wing_seed] Created Wing: {wing_code}", file=sys.stderr)

        # ── Squadrons ────────────────────────────────────────────────────────────
        sqns = []
        for code, name in [(sqn_a_code, sqn_a_name), (sqn_b_code, sqn_b_name)]:
            sqn = db.query(Squadron).filter(Squadron.code == code,
                                            Squadron.wing_id == wing.id,
                                            Squadron.is_archived == False).first()  # noqa: E712
            if sqn:
                print(f"[second_wing_seed] Squadron {code} already exists — skipping.", file=sys.stderr)
            else:
                sqn = Squadron(
                    wing_id=wing.id,
                    code=code,
                    name=name,
                    short_name=f"{code} SQN",
                    unit_type="standard_squadron",
                    active_status=True,
                )
                db.add(sqn)
                db.flush()
                print(f"[second_wing_seed] Created Squadron: {code} under {wing_code}", file=sys.stderr)
            sqns.append(sqn)

        sqn_a, sqn_b = sqns[0], sqns[1]

        # ── Accounts ─────────────────────────────────────────────────────────────
        account_specs = [
            {"role": "wing_admin",   "display_name": f"{wing_code} Wing Admin",
             "wing_id": wing.id, "squadron_id": None},
            {"role": "sqn_admin",    "display_name": f"{sqn_a.code} SQN Admin",
             "wing_id": wing.id, "squadron_id": sqn_a.id},
            {"role": "sqn_general",  "display_name": f"{sqn_a.code} SQN General",
             "wing_id": wing.id, "squadron_id": sqn_a.id},
            {"role": "sqn_admin",    "display_name": f"{sqn_b.code} SQN Admin",
             "wing_id": wing.id, "squadron_id": sqn_b.id},
        ]

        for spec in account_specs:
            q = db.query(User).filter(
                User.role == spec["role"],
                User.is_archived == False,  # noqa: E712
            )
            if spec["squadron_id"]:
                q = q.filter(User.squadron_id == spec["squadron_id"])
            else:
                q = q.filter(User.wing_id == spec["wing_id"],
                             User.squadron_id == None)  # noqa: E711
            existing = q.first()

            if existing:
                print(f"[second_wing_seed] {spec['role']} for {spec['display_name']} already exists — skipping.",
                      file=sys.stderr)
                continue

            plain = generate_code()
            code_hash = hash_code(plain)
            del plain  # keep reference to avoid re-use
            # Re-generate for the output list after hashing
            plain = generate_code()
            code_hash = hash_code(plain)

            u = User(
                display_name=spec["display_name"],
                role=spec["role"],
                national_id=nat.id,
                wing_id=spec["wing_id"],
                squadron_id=spec["squadron_id"],
                active_status=True,
            )
            db.add(u)
            db.flush()

            db.add(AccessCode(
                user_id=u.id,
                code_hash=code_hash,
                active_status=True,
            ))

            codes_out.append({
                "role": spec["role"],
                "display_name": spec["display_name"],
                "code": plain,
            })
            plain = None  # type: ignore[assignment]  # clear reference immediately

        db.commit()
    finally:
        db.close()

    if codes_out:
        print("\n=== SECOND WING SYNTHETIC ACCESS CODES ===", flush=True)
        print("Record these now — they will NOT be shown again.\n", flush=True)
        for entry in codes_out:
            print(f"  [{entry['role']}] {entry['display_name']}: {entry['code']}", flush=True)
        print("\nAll codes hashed in database. Plaintext not stored.", flush=True)
        print("==========================================\n", flush=True)
    else:
        print("[second_wing_seed] No new accounts created (all already exist).", file=sys.stderr)


if __name__ == "__main__":
    second_wing_seed()
