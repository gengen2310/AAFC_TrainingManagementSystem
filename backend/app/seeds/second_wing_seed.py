"""Second Wing synthetic seed — Level B pilot readiness (staging only).

Creates a second Wing with two synthetic squadrons, one account per role
(wing_admin, sqn_admin, sqn_general) under that wing, and an initial
PlanningYear with standard Canadian school-holiday periods.

Idempotent: skips any entity that already exists.
Supports dry-run mode: set DRY_RUN=1 to preview without writing.

SAFETY:
- Rejected if ENVIRONMENT == 'production' or 'prod'.
- Uses synthetic data only. No real cadet, personal, or operational data.
- Printed access codes are one-time output. They are hashed in the DB;
  the plaintext is never stored beyond this invocation's local scope.
- Audit log entries are written with user_id=None, tagged
  action="staging_onboarding" for traceability.

Usage (from backend/ directory):
    source .venv/bin/activate
    ENVIRONMENT=staging DATABASE_URL=<staging-url> \\
      python -m app.seeds.second_wing_seed

Dry-run (no DB writes):
    DRY_RUN=1 ENVIRONMENT=staging DATABASE_URL=<staging-url> \\
      python -m app.seeds.second_wing_seed

Configuration env vars (all optional):
    WING2_CODE          Wing code (default: 1WG)
    WING2_NAME          Wing name (default: 1 Wing HQ)
    WING2_SHORT         Wing short name (default: WING2_CODE value)
    SQN2A_CODE          First squadron code (default: 101)
    SQN2A_NAME          First squadron name (default: 101 Squadron AAFC)
    SQN2A_PARADE_DAY    First squadron default parade day (default: Thursday)
    SQN2A_START_TIME    First squadron start time HH:MM (default: 18:30)
    SQN2A_END_TIME      First squadron end time HH:MM (default: 21:30)
    SQN2B_CODE          Second squadron code (default: 102)
    SQN2B_NAME          Second squadron name (default: 102 Squadron AAFC)
    SQN2B_PARADE_DAY    Second squadron default parade day (default: Thursday)
    SQN2B_START_TIME    Second squadron start time HH:MM (default: 18:30)
    SQN2B_END_TIME      Second squadron end time HH:MM (default: 21:30)
    PLANNING_YEAR       Planning year to create (default: current calendar year)
    DRY_RUN             Set to 1 to preview without writing (default: 0)
"""
import os
import sys
import json
from datetime import date, timedelta

from ..database import SessionLocal
from ..models import NationalEntity, Wing, Squadron, User, AccessCode
from ..models.planning import PlanningYear, HolidayPeriod
from ..services import audit
from ..security import generate_code, hash_code


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> date:
    """Return the nth occurrence of weekday (Mon=0 ... Sun=6) in the given month."""
    first = date(year, month, 1)
    # Days until first occurrence of weekday
    delta = (weekday - first.weekday()) % 7
    return first + timedelta(days=delta + (n - 1) * 7)


def _last_weekday_before(year: int, month: int, day: int, weekday: int) -> date:
    """Last occurrence of weekday at or before month/day."""
    d = date(year, month, day)
    delta = (d.weekday() - weekday) % 7
    return d - timedelta(days=delta)


def standard_canadian_school_holidays(year: int) -> list[dict]:
    """Approximate Canadian school-holiday periods for a given calendar year.

    These are approximate; the Wing SOCAD should review and adjust via the
    Planning Workspace → Holidays tab before the planning year is finalised.
    """
    holidays = []

    # Christmas / New Year break: Dec 20 of prior year → Jan 5 of this year
    holidays.append({
        "name": "Christmas & New Year Break",
        "start_date": f"{year - 1}-12-20",
        "end_date": f"{year}-01-05",
        "holiday_type": "school_holiday",
        "affects_parade": True,
    })

    # March Break: 3rd week of March (Mon–Fri)
    march_break_start = _nth_weekday_of_month(year, 3, 0, 3)  # 3rd Monday of March
    holidays.append({
        "name": "March Break",
        "start_date": march_break_start.isoformat(),
        "end_date": (march_break_start + timedelta(days=4)).isoformat(),
        "holiday_type": "school_holiday",
        "affects_parade": True,
    })

    # Victoria Day: last Monday before May 25
    victoria_day = _last_weekday_before(year, 5, 25, 0)
    holidays.append({
        "name": "Victoria Day",
        "start_date": victoria_day.isoformat(),
        "end_date": victoria_day.isoformat(),
        "holiday_type": "statutory_holiday",
        "affects_parade": True,
    })

    # Summer break: July 1 → August 31
    holidays.append({
        "name": "Summer Break",
        "start_date": f"{year}-07-01",
        "end_date": f"{year}-08-31",
        "holiday_type": "school_holiday",
        "affects_parade": True,
    })

    # Thanksgiving: 2nd Monday of October
    thanksgiving = _nth_weekday_of_month(year, 10, 0, 2)
    holidays.append({
        "name": "Thanksgiving",
        "start_date": thanksgiving.isoformat(),
        "end_date": thanksgiving.isoformat(),
        "holiday_type": "statutory_holiday",
        "affects_parade": True,
    })

    # Remembrance Day: November 11
    holidays.append({
        "name": "Remembrance Day",
        "start_date": f"{year}-11-11",
        "end_date": f"{year}-11-11",
        "holiday_type": "statutory_holiday",
        "affects_parade": True,
    })

    # Christmas break: Dec 20 → Dec 31 of this year (rest carried to next year's Jan block)
    holidays.append({
        "name": "Christmas Break",
        "start_date": f"{year}-12-20",
        "end_date": f"{year}-12-31",
        "holiday_type": "school_holiday",
        "affects_parade": True,
    })

    return holidays


def second_wing_seed() -> None:
    env = os.environ.get("ENVIRONMENT", "development").lower()
    if env in ("production", "prod"):
        print("[second_wing_seed] REFUSED: cannot run against production environment.",
              file=sys.stderr)
        sys.exit(1)

    dry_run = os.environ.get("DRY_RUN", "0") in ("1", "true", "yes")

    wing_code   = os.environ.get("WING2_CODE",  "1WG")
    wing_name   = os.environ.get("WING2_NAME",  "1 Wing HQ")
    wing_short  = os.environ.get("WING2_SHORT", wing_code)

    sqn_a_code  = os.environ.get("SQN2A_CODE",         "101")
    sqn_a_name  = os.environ.get("SQN2A_NAME",         "101 Squadron AAFC")
    sqn_a_pday  = os.environ.get("SQN2A_PARADE_DAY",   "Thursday")
    sqn_a_start = os.environ.get("SQN2A_START_TIME",   "18:30")
    sqn_a_end   = os.environ.get("SQN2A_END_TIME",     "21:30")

    sqn_b_code  = os.environ.get("SQN2B_CODE",         "102")
    sqn_b_name  = os.environ.get("SQN2B_NAME",         "102 Squadron AAFC")
    sqn_b_pday  = os.environ.get("SQN2B_PARADE_DAY",   "Thursday")
    sqn_b_start = os.environ.get("SQN2B_START_TIME",   "18:30")
    sqn_b_end   = os.environ.get("SQN2B_END_TIME",     "21:30")

    plan_year   = int(os.environ.get("PLANNING_YEAR", str(date.today().year)))

    if dry_run:
        print("=== DRY RUN — no database writes will occur ===\n")

    report: dict = {
        "dry_run": dry_run,
        "wing": {"code": wing_code, "name": wing_name},
        "squadrons": [],
        "accounts": [],
        "planning_years": [],
    }

    db = SessionLocal()
    codes_out: list[dict] = []
    try:
        nat = db.query(NationalEntity).first()
        if not nat:
            if dry_run:
                print("[second_wing_seed] WARNING: No NationalEntity in DB — dry-run will show "
                      "what would be created but cannot check existing state.", file=sys.stderr)
            else:
                print("[second_wing_seed] No NationalEntity found. Run migrations first.",
                      file=sys.stderr)
                sys.exit(1)

        # ── Wing ────────────────────────────────────────────────────────────────
        wing = None if not nat else db.query(Wing).filter(
            Wing.code == wing_code, Wing.is_archived == False).first()  # noqa: E712
        if wing:
            print(f"[second_wing_seed] Wing {wing_code!r} already exists — skipping create.",
                  file=sys.stderr)
            report["wing"]["status"] = "existing"
        else:
            report["wing"]["status"] = "would_create" if dry_run else "created"
            if not dry_run:
                wing = Wing(
                    national_id=nat.id,
                    code=wing_code, name=wing_name, short_name=wing_short,
                    active_status=True,
                )
                db.add(wing)
                db.flush()
                audit(db, None, object_type="wing", object_id=wing.id,
                      action="staging_onboarding",
                      new={"code": wing_code, "name": wing_name, "source": "second_wing_seed"},
                      commit=False)
                print(f"[second_wing_seed] Created Wing: {wing_code}", file=sys.stderr)

        # ── Squadrons ────────────────────────────────────────────────────────────
        sqn_specs = [
            (sqn_a_code, sqn_a_name, sqn_a_pday, sqn_a_start, sqn_a_end),
            (sqn_b_code, sqn_b_name, sqn_b_pday, sqn_b_start, sqn_b_end),
        ]
        sqns: list = []
        for code, name, pday, start_t, end_t in sqn_specs:
            sqn_report = {"code": code, "name": name}
            if dry_run:
                sqn_report["status"] = "would_create_or_skip"
                sqns.append(None)
                report["squadrons"].append(sqn_report)
                continue

            sqn = db.query(Squadron).filter(
                Squadron.code == code,
                Squadron.wing_id == (wing.id if wing else ""),
                Squadron.is_archived == False,  # noqa: E712
            ).first()
            if sqn:
                print(f"[second_wing_seed] Squadron {code!r} already exists — skipping.",
                      file=sys.stderr)
                sqn_report["status"] = "existing"
            else:
                sqn = Squadron(
                    wing_id=wing.id,
                    code=code, name=name, short_name=f"{code} SQN",
                    unit_type="standard_squadron",
                    default_parade_day=pday,
                    default_start_time=start_t,
                    default_end_time=end_t,
                    default_session_count=3,
                    active_status=True,
                )
                db.add(sqn)
                db.flush()
                audit(db, None, object_type="squadron", object_id=sqn.id,
                      action="staging_onboarding",
                      new={"code": code, "name": name, "wing": wing_code,
                           "parade_day": pday, "source": "second_wing_seed"},
                      commit=False)
                sqn_report["status"] = "created"
                print(f"[second_wing_seed] Created Squadron: {code} under {wing_code}",
                      file=sys.stderr)
            sqns.append(sqn)
            report["squadrons"].append(sqn_report)

        sqn_a, sqn_b = sqns[0], sqns[1]

        # ── Accounts ─────────────────────────────────────────────────────────────
        account_specs = [
            {"role": "wing_admin",  "display_name": f"{wing_code} Wing Admin",
             "wing_id": wing.id if wing else None, "squadron_id": None},
            {"role": "sqn_admin",   "display_name": f"{sqn_a_code} SQN Admin",
             "wing_id": wing.id if wing else None, "squadron_id": sqn_a.id if sqn_a else None},
            {"role": "sqn_general", "display_name": f"{sqn_a_code} SQN General",
             "wing_id": wing.id if wing else None, "squadron_id": sqn_a.id if sqn_a else None},
            {"role": "sqn_admin",   "display_name": f"{sqn_b_code} SQN Admin",
             "wing_id": wing.id if wing else None, "squadron_id": sqn_b.id if sqn_b else None},
        ] if not dry_run else [
            {"role": "wing_admin",  "display_name": f"{wing_code} Wing Admin"},
            {"role": "sqn_admin",   "display_name": f"{sqn_a_code} SQN Admin"},
            {"role": "sqn_general", "display_name": f"{sqn_a_code} SQN General"},
            {"role": "sqn_admin",   "display_name": f"{sqn_b_code} SQN Admin"},
        ]

        for spec in account_specs:
            acct_report = {"role": spec["role"], "display_name": spec["display_name"]}
            if dry_run:
                acct_report["status"] = "would_create_or_skip"
                report["accounts"].append(acct_report)
                continue

            q = db.query(User).filter(User.role == spec["role"],
                                      User.is_archived == False)  # noqa: E712
            if spec["squadron_id"]:
                q = q.filter(User.squadron_id == spec["squadron_id"])
            else:
                q = q.filter(User.wing_id == spec["wing_id"],
                             User.squadron_id == None)  # noqa: E711
            if q.first():
                print(f"[second_wing_seed] {spec['role']} {spec['display_name']!r} already exists — skipping.",
                      file=sys.stderr)
                acct_report["status"] = "existing"
                report["accounts"].append(acct_report)
                continue

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
            db.add(AccessCode(user_id=u.id, code_hash=code_hash, active_status=True))

            codes_out.append({"role": spec["role"], "display_name": spec["display_name"],
                              "code": plain})
            plain = ""  # clear after use; hash is already separate

            acct_report["status"] = "created"
            report["accounts"].append(acct_report)

        # ── Planning Year + Holidays ─────────────────────────────────────────────
        holidays = standard_canadian_school_holidays(plan_year)
        for sqn, sqn_code_local in [(sqn_a, sqn_a_code), (sqn_b, sqn_b_code)]:
            py_report = {"squadron": sqn_code_local, "year": plan_year}
            if dry_run:
                py_report["status"] = "would_create_or_skip"
                py_report["holidays_count"] = len(holidays)
                report["planning_years"].append(py_report)
                continue
            if sqn is None:
                py_report["status"] = "skipped_no_squadron"
                report["planning_years"].append(py_report)
                continue

            existing_py = db.query(PlanningYear).filter(
                PlanningYear.unit_id == sqn.id,
                PlanningYear.year == plan_year,
            ).first()
            if existing_py:
                py_report["status"] = "existing"
                print(f"[second_wing_seed] PlanningYear {plan_year} for {sqn_code_local} already exists — skipping.",
                      file=sys.stderr)
            else:
                py = PlanningYear(
                    unit_id=sqn.id,
                    wing_id=wing.id,
                    year=plan_year,
                    name=f"{plan_year} Training Year",
                    active_status=True,
                )
                db.add(py)
                db.flush()
                for h in holidays:
                    db.add(HolidayPeriod(
                        planning_year_id=py.id,
                        name=h["name"],
                        start_date=h["start_date"],
                        end_date=h["end_date"],
                        holiday_type=h["holiday_type"],
                        affects_parade=h["affects_parade"],
                    ))
                audit(db, None, object_type="planning_year", object_id=py.id,
                      action="staging_onboarding",
                      new={"year": plan_year, "squadron": sqn_code_local,
                           "holidays": len(holidays), "source": "second_wing_seed"},
                      commit=False)
                py_report["status"] = "created"
                py_report["holidays_count"] = len(holidays)
                print(f"[second_wing_seed] Created PlanningYear {plan_year} for {sqn_code_local} "
                      f"with {len(holidays)} holidays.", file=sys.stderr)
            report["planning_years"].append(py_report)

        if not dry_run:
            db.commit()

    finally:
        db.close()

    # ── Output ───────────────────────────────────────────────────────────────────
    if codes_out and not dry_run:
        print("\n=== SECOND WING SYNTHETIC ACCESS CODES ===", flush=True)
        print("Record these now — they will NOT be shown again.\n", flush=True)
        for entry in codes_out:
            print(f"  [{entry['role']}] {entry['display_name']}: {entry['code']}", flush=True)
        print("\nAll codes hashed in database. Plaintext not stored.", flush=True)
        print("==========================================\n", flush=True)
    elif not codes_out and not dry_run:
        print("[second_wing_seed] No new accounts created (all already exist).", file=sys.stderr)

    print("\n=== ONBOARDING REPORT ===")
    print(json.dumps(report, indent=2))
    print("=========================\n")

    if dry_run:
        print("[second_wing_seed] Dry run complete — no changes were made.", file=sys.stderr)


if __name__ == "__main__":
    second_wing_seed()
