#!/usr/bin/env python3
"""Rehearse the data-transforming migrations against representative rows.

Part 93, second half. scripts/rehearse_migrations.py walks the chain on an
EMPTY database, which proves the DDL applies but moves no user rows. Twelve
migrations carry data logic; nine of them seed their own reference data, so the
empty-database walk does exercise them (measurable: after a full chain run
curriculum_items holds 214 rows, session_status_reason_tags 10, and so on).

Three transform rows that only a real installation has, so on an empty database
their UPDATE/DELETE match nothing and the walk proves nothing about them:

    v54  a3b4c5d6e7f8  NULLs parade_dates.parade_night_id when it dangles
    v55  b4c5d6e7f8a9  de-duplicates session_audience; NULLs dangling
                       planning_conflicts.scheduled_session_id
    821e 821e2a4bc3e6  remaps the timing_blocks block_type taxonomy and
                       recomputes is_instructional_period from it

Each case below builds the chain to the migration's parent, inserts rows that
exercise BOTH the path that should change and a control that must not, runs the
one migration, and asserts on what actually changed. A case that changed
nothing is reported as a failure, not a pass -- a rehearsal that matches no
rows is the thing this script exists to prevent.

Usage:  python scripts/rehearse_data_migrations.py [--db NAME]

Needs a local PostgreSQL and createdb rights. Creates and drops its own scratch
database; no production data is copied or required.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent


def sh(db: str, sql: str, fetch: bool = False) -> str:
    r = subprocess.run(["psql", "-d", db, "-qtA", "-v", "ON_ERROR_STOP=1", "-c", sql],
                       capture_output=True, text=True, timeout=180)
    if r.returncode:
        raise SystemExit(f"psql failed:\n{sql}\n{r.stderr.strip()}")
    return r.stdout.strip()


def alembic(db: str, *args: str) -> None:
    env = dict(os.environ)
    env["DATABASE_URL"] = (
        f"postgresql+psycopg2://{os.environ.get('USER','postgres')}@localhost:5432/{db}")
    r = subprocess.run([sys.executable, "-m", "alembic", *args],
                       cwd=BACKEND, env=env, capture_output=True, text=True, timeout=600)
    if r.returncode:
        raise SystemExit(f"alembic {' '.join(args)} failed:\n{r.stderr[-1500:]}")


def recreate(db: str) -> None:
    subprocess.run(["psql", "-d", "postgres", "-q", "-c", f'DROP DATABASE IF EXISTS "{db}"'],
                   capture_output=True, timeout=120)
    subprocess.run(["psql", "-d", "postgres", "-q", "-c", f'CREATE DATABASE "{db}"'],
                   check=True, capture_output=True, timeout=120)


ORG = """
INSERT INTO national_entities (id,name,short_name,created_at,updated_at)
  VALUES ('nat1','Nat','NAT',now(),now());
INSERT INTO wings (id,national_id,code,name,short_name,active_status,is_archived,created_at,updated_at)
  VALUES ('wing1','nat1','WG1','Wing 1','WG1',true,false,now(),now());
INSERT INTO squadrons (id,wing_id,code,name,short_name,default_session_count,active_status,is_archived,created_at,updated_at)
  VALUES ('sqn1','wing1','001','Sqn 1','001',3,true,false,now(),now());
"""


# ── v54 ───────────────────────────────────────────────────────────────────────
def case_v54(db: str) -> list[str]:
    recreate(db)
    alembic(db, "upgrade", "9997f6527ef4")          # parent of v54
    sh(db, ORG)
    sh(db, """
    INSERT INTO planning_years (id,unit_id,year,name,created_at,updated_at)
      VALUES ('py1','sqn1',2026,'2026',now(),now());
    INSERT INTO parade_nights (id,squadron_id,wing_id,training_year,date,session_count,
                               parade_type,published_status,readiness_score,closeout_status,
                               created_at,updated_at,is_archived)
      VALUES ('pn_real','sqn1','wing1',2026,'2026-05-01',3,'standard',false,0,'open',
              now(),now(),false);
    INSERT INTO parade_dates (id,planning_year_id,parade_date,unit_id,parade_night_id,created_at,updated_at)
      VALUES ('pd_dangling','py1','2026-05-08','sqn1','pn_DOES_NOT_EXIST',now(),now()),
             ('pd_valid','py1','2026-05-01','sqn1','pn_real',now(),now()),
             ('pd_null','py1','2026-05-15','sqn1',NULL,now(),now());
    """)
    before = sh(db, "SELECT count(*) FROM parade_dates WHERE parade_night_id='pn_DOES_NOT_EXIST'")
    alembic(db, "upgrade", "a3b4c5d6e7f8")
    problems = []
    if before != "1":
        problems.append(f"v54 fixture did not create a dangling row (found {before})")
    if sh(db, "SELECT coalesce(parade_night_id,'NULL') FROM parade_dates WHERE id='pd_dangling'") != "NULL":
        problems.append("v54 left a dangling parade_night_id in place")
    if sh(db, "SELECT parade_night_id FROM parade_dates WHERE id='pd_valid'") != "pn_real":
        problems.append("v54 nulled a VALID parade_night_id")
    return problems


# ── v55 ───────────────────────────────────────────────────────────────────────
def case_v55(db: str) -> list[str]:
    recreate(db)
    alembic(db, "upgrade", "a3b4c5d6e7f8")          # parent of v55
    sh(db, ORG)
    sh(db, """
    INSERT INTO planning_years (id,unit_id,year,name,created_at,updated_at)
      VALUES ('py1','sqn1',2026,'2026',now(),now());
    INSERT INTO parade_nights (id,squadron_id,wing_id,training_year,date,session_count,
                               parade_type,published_status,readiness_score,closeout_status,
                               created_at,updated_at,is_archived)
      VALUES ('pn1','sqn1','wing1',2026,'2026-05-01',3,'standard',false,0,'open',
              now(),now(),false);
    INSERT INTO sessions (id,parade_night_id,squadron_id,period_number,status,
                          follow_up_required,created_at,updated_at,is_archived)
      VALUES ('s_real','pn1','sqn1',1,'planned',false,now(),now(),false);
    -- training_stage_id points at curriculum_phases, which v42 seeded upstream.
    INSERT INTO training_classes (id,squadron_id,training_year_id,training_stage_id,
                                  display_name,created_at,updated_at)
      SELECT 'tc1','sqn1','py1',id,'Class 1',now(),now()
        FROM curriculum_phases ORDER BY id LIMIT 1;
    -- v49 already made (session_id, training_class_id) unique, so duplicates
    -- CANNOT exist on the canonical chain and v55's de-duplication can never
    -- match a row there. It still matters for a database that reached v54
    -- without that constraint -- created by create_all rather than migrated,
    -- which is exactly the population v55 was written to repair. Drop the
    -- constraint to reproduce that state and exercise the code path for real.
    ALTER TABLE session_audience DROP CONSTRAINT uq_session_audience_session_class;
    INSERT INTO session_audience (id,session_id,training_class_id,created_at,updated_at)
      VALUES ('aaa_keep','s_real','tc1',now(),now()),
             ('zzz_drop','s_real','tc1',now(),now());
    -- dangling conflict reference: must be nulled
    INSERT INTO planning_conflicts (id,conflict_type,severity,message,is_resolved,scheduled_session_id,created_at,updated_at)
      VALUES ('c_dangling','x','warn','m',false,'s_DOES_NOT_EXIST',now(),now()),
             ('c_valid','x','warn','m',false,'s_real',now(),now());
    """)
    dupes = sh(db, "SELECT count(*) FROM session_audience WHERE session_id='s_real'")
    alembic(db, "upgrade", "b4c5d6e7f8a9")
    problems = []
    if dupes != "2":
        problems.append(f"v55 fixture did not create duplicate audience rows (found {dupes})")
    kept = sh(db, "SELECT string_agg(id,',' ORDER BY id) FROM session_audience WHERE session_id='s_real'")
    if kept != "aaa_keep":
        problems.append(f"v55 de-duplication kept the wrong rows: {kept!r}, expected 'aaa_keep'")
    if sh(db, "SELECT coalesce(scheduled_session_id,'NULL') FROM planning_conflicts WHERE id='c_dangling'") != "NULL":
        problems.append("v55 left a dangling scheduled_session_id in place")
    if sh(db, "SELECT scheduled_session_id FROM planning_conflicts WHERE id='c_valid'") != "s_real":
        problems.append("v55 nulled a VALID scheduled_session_id")
    # After repairing the duplicates v55 must leave the pair protected again.
    if sh(db, "SELECT count(*) FROM pg_constraint "
              "WHERE conrelid='session_audience'::regclass AND contype='u'") == "0":
        problems.append("v55 de-duplicated but left the pair unprotected")
    return problems


# ── 821e ──────────────────────────────────────────────────────────────────────
def case_821e(db: str) -> list[str]:
    recreate(db)
    alembic(db, "upgrade", "3197cd57cd98")          # parent of 821e
    sh(db, ORG)
    sh(db, """
    INSERT INTO timing_templates (id,squadron_id,name,effective_from,is_default,active_status,is_archived,created_at,updated_at)
      VALUES ('tt1','sqn1','T','2026-01-01',true,true,false,now(),now());
    INSERT INTO timing_blocks (id,timing_template_id,display_order,block_name,block_type,is_instructional_period,created_at,updated_at)
      VALUES ('b_admin','tt1',1,'Roll Call','roll_call',false,now(),now()),
             ('b_flight','tt1',2,'Flight Period','flight_period',false,now(),now()),
             ('b_instr','tt1',3,'Period 1','instructional_period',true,now(),now()),
             ('b_break','tt1',4,'Break','break',false,now(),now()),
             ('b_custom','tt1',5,'Custom','custom',true,now(),now()),
             ('b_keep','tt1',6,'Arrival','arrival',false,now(),now());
    -- service_desk row with NULL timestamps: the migration backfills then SETs NOT NULL
    INSERT INTO service_desk_email_configs (id,wing_id,scope,notification_email,created_at,updated_at)
      VALUES ('sd1','wing1','wing','sd@example.test',NULL,NULL);
    """)
    alembic(db, "upgrade", "821e2a4bc3e6")
    problems = []
    # Postgres renders a boolean as 'true'/'false' when concatenated with ||.
    expected = {
        "b_admin": ("admin", "false"),
        "b_flight": ("training_period", "true"),   # was NOT instructional; taxonomy makes it so
        "b_instr": ("training_period", "true"),
        "b_break": ("drinks_break", "false"),
        "b_custom": ("other", "false"),            # was instructional; taxonomy clears it
        "b_keep": ("arrival", "false"),            # type unchanged by the map
    }
    for bid, (btype, ip) in expected.items():
        got = sh(db, f"SELECT block_type||'|'||is_instructional_period FROM timing_blocks WHERE id='{bid}'")
        if got != f"{btype}|{ip}":
            problems.append(f"821e block {bid}: got {got!r}, expected '{btype}|{ip}'")
    nulls = sh(db, "SELECT count(*) FROM service_desk_email_configs WHERE created_at IS NULL OR updated_at IS NULL")
    if nulls != "0":
        problems.append(f"821e left {nulls} service_desk row(s) with NULL timestamps")
    return problems


CASES = [
    ("v54  a3b4c5d6e7f8  parade_dates.parade_night_id", case_v54),
    ("v55  b4c5d6e7f8a9  session_audience / planning_conflicts", case_v55),
    ("821e 821e2a4bc3e6  timing_blocks taxonomy", case_821e),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="tms_data_rehearsal")
    args = ap.parse_args()

    print(f"data-path rehearsal: {len(CASES)} migrations that transform rows "
          f"an empty database does not have\n")
    all_problems: list[str] = []
    for label, fn in CASES:
        # A hard failure in one case must not hide the cases after it: alembic
        # and psql helpers raise SystemExit, which would otherwise abort the run
        # at the first problem and report the rest as untested.
        try:
            problems = fn(args.db)
        except SystemExit as exc:
            problems = [str(exc).strip().splitlines()[-1][:200] if str(exc) else "aborted"]
        print(f"  {'FAIL' if problems else 'ok  '}  {label}")
        for p in problems:
            print(f"          {p}")
        all_problems.extend(problems)

    subprocess.run(["psql", "-d", "postgres", "-q", "-c",
                    f'DROP DATABASE IF EXISTS "{args.db}"'], capture_output=True, timeout=120)
    print()
    if all_problems:
        print(f"DATA REHEARSAL FAILED -- {len(all_problems)} problem(s)")
        return 1
    print("DATA REHEARSAL PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
