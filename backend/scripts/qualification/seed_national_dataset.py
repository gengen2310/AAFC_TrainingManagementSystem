"""Seed a national-scale qualification dataset (LOCAL databases only).

Default shape (all adjustable by flags):
  6 Wings x 10 Squadrons = 60 Squadrons
  170 cadets per Squadron            = 10,200 cadets (+ class memberships)
  15 facilitators per Squadron       = 900
  1 planning year / Squadron, 40 parade nights x 6 periods = 14,400 sessions
  5 training classes per Squadron, 600 Service Desk tickets, 30,000 audit rows
  Accounts: per Squadron sqn_admin + sqn_general, per Wing wing_admin +
  wing_viewer, plus national_admin / national_viewer / system_admin.

Access codes are deterministic so the load driver can sign in:
  QA<sqn>ADM / QA<sqn>GEN, QA<wing>ADM / QA<wing>VWR, QANATADM / QANATVWR / QASYSADM

Run against a database already migrated with `alembic upgrade head`:
  ENVIRONMENT=test DATABASE_URL=postgresql://...@127.0.0.1:.../db \
    python -m scripts.qualification.seed_national_dataset

Refuses to run unless ENVIRONMENT is development/test AND the database host is
local -- it must never touch staging or production.
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time
import uuid
from datetime import date, timedelta
from urllib.parse import urlparse

sys.path.insert(0, ".")

from app.config import settings  # noqa: E402
from app.database import SessionLocal, utcnow  # noqa: E402
from app.models import (  # noqa: E402
    AccessCode, AuditLog, Cadet, Facilitator, NationalEntity, ParadeNight, Squadron, User, Wing,
)
from app.models import Session as TrainingSession  # noqa: E402
from app.models.planning import PlanningYear  # noqa: E402
from app.security import hash_code  # noqa: E402

GROUPS = [("orientation", "ORI", "A. Orientation"), ("initial", "INI", "B. Initial"),
          ("junior", "JNR", "C. Junior"), ("intermediate", "INT", "D. Intermediate"),
          ("senior", "SNR", "E. Senior")]


def _refuse_unless_local() -> None:
    env = (settings.ENVIRONMENT or "").lower()
    host = urlparse(settings.DATABASE_URL.replace("+psycopg2", "")).hostname or ""
    local = settings.DATABASE_URL.startswith("sqlite") or host in ("127.0.0.1", "localhost", "::1")
    if env not in ("development", "test") or not local:
        sys.exit(f"REFUSED: qualification seeding needs ENVIRONMENT development/test and a local DB "
                 f"(got ENVIRONMENT={env!r}, host={host!r}).")


def _uid() -> str:
    return str(uuid.uuid4())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--wings", type=int, default=6)
    ap.add_argument("--squadrons-per-wing", type=int, default=10)
    ap.add_argument("--cadets-per-squadron", type=int, default=170)
    ap.add_argument("--facilitators-per-squadron", type=int, default=15)
    ap.add_argument("--nights", type=int, default=40)
    ap.add_argument("--periods", type=int, default=6)
    ap.add_argument("--tickets", type=int, default=600)
    ap.add_argument("--audit-rows", type=int, default=30000)
    ap.add_argument("--year", type=int, default=date.today().year)
    args = ap.parse_args()
    _refuse_unless_local()
    rng = random.Random(20261004)
    t0 = time.time()
    db = SessionLocal()
    try:
        from app.models import ServiceTicket, TrainingClass, CadetClassMembership
        hashes: dict[str, str] = {}

        def code(c: str) -> str:
            if c not in hashes:
                hashes[c] = hash_code(c)
            return hashes[c]

        def account(display, role, code_plain, **scope):
            u = User(id=_uid(), display_name=display, role=role, active_status=True, **scope)
            db.add(u)
            db.flush()          # no ORM relationship orders users before access_codes
            db.add(AccessCode(id=_uid(), user_id=u.id, code_hash=code(code_plain), active_status=True))
            return u

        nat = NationalEntity(id=_uid(), name="QA National HQ", short_name="QANAT")
        db.add(nat)
        db.flush()
        account("QA National Admin", "national_admin", "QANATADM", national_id=nat.id)
        account("QA National Viewer", "national_viewer", "QANATVWR", national_id=nat.id)
        account("QA System Admin", "system_admin", "QASYSADM", national_id=nat.id)
        db.commit()

        counts = dict(wings=0, squadrons=0, cadets=0, facilitators=0, nights=0, sessions=0, classes=0)
        start = date(args.year, 2, 2)
        for w in range(args.wings):
            wcode = f"Q{w + 1}W"
            wing = Wing(id=_uid(), national_id=nat.id, code=wcode, name=f"QA Wing {w + 1}", short_name=wcode,
                        timezone="Australia/Perth", active_status=True)
            db.add(wing)
            db.flush()
            account(f"{wcode} Wing Admin", "wing_admin", f"QA{wcode}ADM", wing_id=wing.id, national_id=nat.id)
            account(f"{wcode} Wing Viewer", "wing_viewer", f"QA{wcode}VWR", wing_id=wing.id, national_id=nat.id)
            counts["wings"] += 1
            for q in range(args.squadrons_per_wing):
                scode = f"{9 - w % 9}{w:01d}{q:02d}"[:4]
                sqn = Squadron(id=_uid(), wing_id=wing.id, code=scode, name=f"{scode} QA Squadron",
                               short_name=scode, active_status=True)
                db.add(sqn)
                db.flush()
                account(f"{scode} Admin", "sqn_admin", f"QA{scode}ADM", squadron_id=sqn.id, wing_id=wing.id)
                account(f"{scode} General", "sqn_general", f"QA{scode}GEN", squadron_id=sqn.id, wing_id=wing.id)
                py = PlanningYear(id=_uid(), unit_id=sqn.id, wing_id=wing.id, year=args.year,
                                  name=f"{scode} Training Year {args.year}", active_status=True)
                db.add(py)
                db.flush()
                classes = []
                for i, (grp, stage, _) in enumerate(GROUPS):
                    tc = TrainingClass(id=_uid(), squadron_id=sqn.id, training_year_id=py.id,
                                       display_name=f"{stage} {args.year}", stage_code=stage,
                                       class_number=i + 1)   # unique per squadron + year
                    db.add(tc)
                    classes.append(tc)
                facs = [Facilitator(id=_uid(), squadron_id=sqn.id, wing_id=wing.id,
                                    first_name=f"Fac{f}", last_name=f"{scode}Staff", type="Staff")
                        for f in range(args.facilitators_per_squadron)]
                db.add_all(facs)
                db.flush()
                cadets = []
                for c in range(args.cadets_per_squadron):
                    cad = Cadet(id=_uid(), squadron_id=sqn.id, service_number=f"{scode}{c:05d}",
                                first_name=f"Cadet{c}", last_name=f"{scode}Unit",
                                attendance_percentage=rng.uniform(40, 100), active_status=True)
                    cadets.append(cad)
                db.add_all(cadets)
                db.flush()
                db.add_all([CadetClassMembership(id=_uid(), cadet_id=cad.id, training_class_id=classes[i % 5].id)
                            for i, cad in enumerate(cadets)])
                for n in range(args.nights):
                    pn = ParadeNight(id=_uid(), squadron_id=sqn.id, wing_id=wing.id, planning_year_id=py.id,
                                     date=(start + timedelta(days=7 * n)).isoformat(), is_active=True)
                    db.add(pn)
                    db.flush()
                    for period in range(1, args.periods + 1):
                        grp = GROUPS[(period - 1) % 5][0]
                        db.add(TrainingSession(id=_uid(), parade_night_id=pn.id, squadron_id=sqn.id,
                                               period_number=period, cadet_group=grp,
                                               custom_title=f"{grp.title()} P{period}",
                                               facilitator_id=rng.choice(facs).id, status="planned"))
                    counts["nights"] += 1
                    counts["sessions"] += args.periods
                db.commit()
                counts["squadrons"] += 1
                counts["cadets"] += len(cadets)
                counts["facilitators"] += len(facs)
                counts["classes"] += len(classes)
            print(f"  wing {wcode}: {counts['squadrons']} squadrons, {counts['cadets']} cadets", flush=True)

        sqns = db.query(Squadron).filter(Squadron.code.like("_%")).all()
        qa_sqns = [s for s in sqns if s.name.endswith("QA Squadron")]
        for i in range(args.tickets):
            s = rng.choice(qa_sqns)
            db.add(ServiceTicket(id=_uid(), rank="CDT", first_name=f"Req{i}", last_name="Ticket",
                                 email=f"req{i}@example.invalid", squadron_id=s.id, wing_id=s.wing_id,
                                 unit_name=s.name, category="other",
                                 description=f"Qualification ticket {i} with enough text to be realistic.",
                                 status=rng.choice(["open", "in_progress", "resolved"])))
        db.commit()
        now = utcnow()
        batch = []
        for i in range(args.audit_rows):
            s = qa_sqns[i % len(qa_sqns)]
            batch.append(AuditLog(id=_uid(), timestamp=now - timedelta(minutes=i), role="sqn_admin",
                                  scope="squadron", squadron_id=s.id, wing_id=s.wing_id,
                                  object_type="session", object_id=_uid(), action="update"))
            if len(batch) == 5000:
                db.add_all(batch); db.commit(); batch = []
        db.add_all(batch); db.commit()
        counts.update(tickets=args.tickets, audit_rows=args.audit_rows)
        print("SEEDED", counts, f"in {time.time() - t0:.0f}s")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
