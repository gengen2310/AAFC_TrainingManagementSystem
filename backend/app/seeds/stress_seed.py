"""Stress-test seed. Generates Wings/Squadrons/facilitators/parade-nights/sessions/
audit at configurable scale, then times a few representative queries.

Defaults are modest so it runs in CI quickly. For the spec's national targets:
    SCALE=full python -m app.seeds.stress_seed
(That generates 10 wings, 250 squadrons, ~25k cadets, ~5k facilitators,
~20k parade nights, ~100k sessions, ~50k audit rows. Use PostgreSQL — SQLite
will be slow at that volume.)
"""
import os, time, random
from datetime import date, timedelta
from ..database import SessionLocal, reset_db
from ..models import (NationalEntity, Wing, Squadron, Facilitator, ParadeNight,
                      Session, Cadet, AuditLog)

SCALE = os.environ.get("SCALE", "small")
PROFILES = {
    # wings, sqns_per_wing, facs_per_sqn, pn_per_sqn, sess_per_pn, cadets_per_sqn
    "small": (2, 5, 4, 6, 3, 10),
    "medium": (4, 15, 8, 20, 3, 40),
    "full": (10, 25, 20, 80, 5, 100),
}


def run():
    wings_n, sqn_n, fac_n, pn_n, sess_n, cadet_n = PROFILES.get(SCALE, PROFILES["small"])
    print(f"Stress seed profile={SCALE}: {wings_n} wings x {sqn_n} sqns ...")
    reset_db()
    db = SessionLocal()
    nat = NationalEntity(); db.add(nat); db.commit()
    t0 = time.time()
    statuses = ["delivered", "planned", "not_delivered", "cancelled", "delivered_with_issue"]
    sess_total = audit_total = 0
    for wi in range(wings_n):
        w = Wing(national_id=nat.id, code=f"{wi+1}WG", name=f"{wi+1} Wing",
                 short_name=f"{wi+1}WG", timezone="Australia/Perth")
        db.add(w); db.commit()
        for si in range(sqn_n):
            s = Squadron(wing_id=w.id, code=f"{wi+1}{si:02d}", name=f"Sqn {wi+1}{si:02d}",
                         short_name=f"{wi+1}{si:02d}SQN", default_parade_day="Friday",
                         default_start_time="18:00", default_end_time="22:00")
            db.add(s); db.commit()
            facs = []
            for fi in range(fac_n):
                f = Facilitator(squadron_id=s.id, wing_id=w.id, last_name=f"Fac{fi}", current_rank="CIV", type="Staff")
                db.add(f); facs.append(f)
            db.commit()
            for ci in range(cadet_n):
                db.add(Cadet(squadron_id=s.id, service_number=f"{wi}{si}{ci:03d}", rank="CDT",
                             first_name="C", last_name=f"{ci}", phase="Initial",
                             attendance_percentage=random.randint(50, 100)))
            base = date(2026, 2, 1)
            for pi in range(pn_n):
                pn = ParadeNight(squadron_id=s.id, wing_id=w.id, date=str(base + timedelta(days=pi * 7)),
                                 term="T1", session_count=sess_n, published_status=True)
                db.add(pn); db.commit()
                for pe in range(sess_n):
                    f = random.choice(facs)
                    db.add(Session(parade_night_id=pn.id, squadron_id=s.id, period_number=pe + 1,
                                   phase_at_time="B. Initial", facilitator_id=f.id,
                                   facilitator_display_name_at_time=f.last_name,
                                   status=random.choice(statuses), expected_attendance=15))
                    sess_total += 1
                db.add(AuditLog(action="seed", object_type="parade_night", object_id=pn.id,
                                squadron_id=s.id, wing_id=w.id)); audit_total += 1
            db.commit()
    secs = time.time() - t0
    print(f"Seeded {sess_total} sessions, {audit_total} audit rows in {secs:.1f}s")

    # Representative perf checks
    t = time.time(); db.query(Session).filter(Session.status == "not_delivered").count()
    print(f"  not-delivered count query: {(time.time()-t)*1000:.0f} ms")
    t = time.time(); db.query(ParadeNight).count()
    print(f"  parade-night count query: {(time.time()-t)*1000:.0f} ms")
    db.close()


if __name__ == "__main__":
    run()
