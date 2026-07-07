"""Idempotent: ensure all 7 Wing squadron records exist.

Does NOT create users or access codes. Squadron records are org data only;
accounts are created separately by system_admin. Safe to run multiple times.

Run via:
  railway run --service aafc-tms-backend python -m scripts.seed_7wg_squadrons
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.organisations import Wing, Squadron

# (code, name, short_name, address, parade_day, start, end, sessions)
SEVEN_WING_SQUADRONS = [
    ("701", "701 Squadron — Bullsbrook",              "701SQN", "Great Northern Highway, Bullsbrook WA 6084",                          "Friday",    "18:00", "22:00", 3),
    ("702", "702 Squadron — Cannington",              "702SQN", "Gate 3, 1-5 Station Street, Cannington WA 6107",                      "Wednesday", "18:00", "21:30", 3),
    ("703", "703 Squadron — City of Fremantle",       "703SQN", "Leeuwin Barracks, Riverside Road, East Fremantle WA 6158",            "Friday",    "18:00", "22:00", 3),
    ("704", "704 Squadron — Madeley",                 "704SQN", "Kingsway Regional Sporting Complex, Madeley WA 6065",                 "Friday",    "18:00", "22:00", 3),
    ("705", "705 Squadron — City of Albany",          "705SQN", "Cnr Spencer St and Serpentine Rd, Albany WA 6330",                    "Wednesday", "17:20", "21:15", 2),
    ("707", "707 Squadron — Mandurah",                "707SQN", "Coodanup Drive, Coodanup WA 6210",                                    "Wednesday", "18:15", "22:00", 3),
    ("708", "708 Squadron — Rockingham",              "708SQN", "127 Dixon Road, Rockingham WA 6168",                                  "Friday",    "18:15", "22:00", 3),
    ("709", "709 Squadron — Kalgoorlie-Boulder",      "709SQN", "23 Cheetham Street, Kalgoorlie WA 6430",                             "Monday",    "17:45", "21:30", 2),
    ("710", "710 Squadron — Bunbury",                 "710SQN", "Cnr Wilson Rd and Proffit St, Bunbury WA 6230",                       "Friday",    "18:00", "21:30", 2),
    ("711", "711 Squadron — City of Greater Geraldton","711SQN","189 Lester Avenue, Geraldton WA 6530",                               "Monday",    "17:30", "21:00", 2),
    ("712", "712 Squadron — City of Belmont",         "712SQN", "Palmer Barracks, Beavis Drive, South Guildford WA 6055",              "Wednesday", "17:45", "21:30", 3),
    ("713", "713 Squadron — Cannington",              "713SQN", "Cannington Exhibition Centre, Gate 3 Station St, Cannington WA 6107", "Friday",    "18:00", "22:30", 3),
    ("714", "714 Squadron — Karrakatta",              "714SQN", "Irwin Barracks, Stubbs Terrace, Karrakatta WA 6010",                  "Friday",    "18:00", "22:00", 3),
    ("715", "715 Squadron — City of Belmont",         "715SQN", "Palmer Barracks, Beavis Drive, South Guildford WA 6055",              "Friday",    "18:30", "22:00", 3),
    ("721", "721 Squadron — Madeley",                 "721SQN", "Cnr Hartman Drive and Sporting Drive, Madeley WA 6065",               "Wednesday", "18:30", "21:30", 2),
    ("723", "723 Squadron — Joondalup",               "723SQN", "63 McLarty Avenue, Joondalup WA 6027",                                "Wednesday", "18:30", "21:30", 2),
]


def run():
    with SessionLocal() as db:
        wing = db.query(Wing).filter(Wing.code == "7WG").first()
        if not wing:
            print("ERROR: 7WG Wing not found. Run seed_aafc_wings first.")
            sys.exit(1)

        existing = {s.code for s in db.query(Squadron).filter(Squadron.wing_id == wing.id).all()}
        added = 0
        skipped = 0

        for code, name, short, addr, day, st, et, sc in SEVEN_WING_SQUADRONS:
            if code in existing:
                print(f"  SKIP  {code} — {name}")
                skipped += 1
                continue
            sqn = Squadron(
                wing_id=wing.id,
                code=code,
                unit_number=code,
                name=name,
                short_name=short,
                address=addr,
                default_parade_day=day,
                default_start_time=st,
                default_end_time=et,
                default_session_count=sc,
                active_status=True,
            )
            db.add(sqn)
            added += 1
            print(f"  ADD   {code} — {name}")

        db.commit()
        print(f"\nDone: {added} squadron(s) added, {skipped} skipped.")
        print("No users or access codes were created.")


if __name__ == "__main__":
    run()
