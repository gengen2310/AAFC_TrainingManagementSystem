"""Staging seeder — identical org structure to seed_all but with cryptographically random access codes.

Codes are printed to stdout ONCE on first run and stored only as hashes.
They cannot be retrieved again. Retrieve them from the deployment logs immediately after first startup.

Usage (one-off, run only when DB is empty):
    PYTHONPATH=. python -m app.seeds.staging_seed
"""
import secrets
import sys
from datetime import date, datetime, timezone

from ..database import SessionLocal
from ..models import (
    NationalEntity, Wing, Squadron, User, AccessCode,
    CurriculumItem, PlanningYear,
)
from ..security import hash_code


_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no I, O, 0, 1 — typeable


def _random_code() -> str:
    """Generate a strong, human-typeable access code: XXXX-XXXX-XXXX-XXXX"""
    return "-".join(
        "".join(secrets.choice(_ALPHABET) for _ in range(4))
        for _ in range(4)
    )


_UNITS = [
    ("701", "701 Squadron — Bullsbrook",           "701SQN"),
    ("702", "702 Squadron — Cannington",            "702SQN"),
    ("703", "703 Squadron — City of Fremantle",     "703SQN"),
    ("704", "704 Squadron — Madeley",               "704SQN"),
    ("705", "705 Squadron — City of Albany",        "705SQN"),
    ("707", "707 Squadron — Mandurah",              "707SQN"),
    ("708", "708 Squadron — Rockingham",            "708SQN"),
    ("709", "709 Squadron — Kalgoorlie-Boulder",    "709SQN"),
    ("710", "710 Squadron — Bunbury",               "710SQN"),
    ("711", "711 Squadron — City of Greater Geraldton", "711SQN"),
    ("712", "712 Squadron — City of Belmont",       "712SQN"),
    ("713", "713 Squadron — Cannington (RAAFA)",    "713SQN"),
    ("714", "714 Squadron — Karrakatta",            "714SQN"),
    ("715", "715 Squadron — City of Belmont (Fri)", "715SQN"),
    ("721", "721 Squadron — Madeley",               "721SQN"),
    ("723", "723 Squadron — Joondalup",             "723SQN"),
]


def staging_seed() -> None:
    db = SessionLocal()
    try:
        if db.query(User).count() > 0:
            print("staging_seed: users already exist — skipping (use rotate_access_codes.py to rotate).",
                  file=sys.stderr)
            return

        # ── Org structure ──────────────────────────────────────────────────
        nat = NationalEntity(name="AAFC National Headquarters", short_name="NATIONAL")
        db.add(nat)
        db.flush()

        wing = Wing(national_id=nat.id, code="7WG",
                    name="7 Wing (Western Australia)", short_name="7WG")
        db.add(wing)
        db.flush()

        codes_out: list[tuple[str, str, str]] = []  # (role, display_name, code)

        def _add_user(display_name: str, role: str, **kw) -> User:
            u = User(display_name=display_name, role=role, **kw)
            db.add(u)
            db.flush()
            code = _random_code()
            db.add(AccessCode(user_id=u.id, code_hash=hash_code(code)))
            codes_out.append((role, display_name, code))
            return u

        # Wing-level users
        _add_user("7 Wing Admin",   "wing_admin",   wing_id=wing.id, national_id=nat.id)
        _add_user("7 Wing Viewer",  "wing_viewer",  wing_id=wing.id, national_id=nat.id)

        # Squadron users
        for unit_code, name, short in _UNITS:
            s = Squadron(
                wing_id=wing.id, code=unit_code, unit_number=unit_code,
                name=name, short_name=short, active_status=True,
            )
            db.add(s)
            db.flush()
            _add_user(f"{unit_code} Admin",   "sqn_admin",   wing_id=wing.id, squadron_id=s.id)
            _add_user(f"{unit_code} General", "sqn_general", wing_id=wing.id, squadron_id=s.id)

        # National-level users
        _add_user("National Admin",  "national_admin",  national_id=nat.id)
        _add_user("National Viewer", "national_viewer", national_id=nat.id)
        _add_user("System Admin",    "system_admin",    national_id=nat.id)
        _add_user("Auditor",         "auditor",         national_id=nat.id)

        # Minimal curriculum
        ITEMS = [
            ("GEN-001", "Drill and Ceremonial",              "mandatory", "national"),
            ("GEN-002", "Aerospace",                         "mandatory", "national"),
            ("GEN-003", "Leadership",                        "mandatory", "national"),
            ("GEN-004", "Fitness and Sports",                "mandatory", "national"),
            ("GEN-005", "Survival Training",                 "elective",  "national"),
            ("GEN-006", "Music",                             "elective",  "national"),
            ("GEN-007", "Biathlon",                          "elective",  "national"),
            ("GEN-008", "Aviation",                          "elective",  "national"),
            ("GEN-009", "Community Service",                 "mandatory", "national"),
            ("GEN-010", "Effective Speaking",                "elective",  "national"),
            ("GEN-011", "First Aid",                         "elective",  "national"),
            ("GEN-012", "Summer Training Preparation",       "elective",  "national"),
            ("GEN-013", "Cadet Exchange Program Orientation","elective",  "national"),
        ]
        for code_c, title, cat, lvl in ITEMS:
            db.add(CurriculumItem(
                code=code_c, title=title, category=cat,
                owning_level=lvl, active_status=True,
                national_id=nat.id,
            ))

        db.commit()

        # ── Print codes to stdout (visible in deployment logs) ───────────────
        print()
        print("=" * 70)
        print("STAGING ACCESS CODES — retrieve now, these will NOT be shown again")
        print("=" * 70)
        print(f"{'ROLE':<22} {'DISPLAY NAME':<30} ACCESS CODE")
        print("-" * 70)
        for role, display, code in sorted(codes_out, key=lambda x: x[0]):
            print(f"{role:<22} {display:<30} {code}")
        print("=" * 70)
        print()
        print(f"Seeded: {len(codes_out)} users, {len(_UNITS)} squadrons, 7 Wing, National HQ.")
        print("Codes are stored as hashes only. Rotate via rotate_access_codes.py when needed.")
        print()

    finally:
        db.close()


if __name__ == "__main__":
    staging_seed()
