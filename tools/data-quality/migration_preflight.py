#!/usr/bin/env python3
"""Pre-flight the pending Alembic migrations against a real database. READ-ONLY.

Answers one question: if `alembic upgrade head` ran against this database right
now, what would it destroy, and what would stop it?

Written 2026-08-23 after finding production 23 migrations behind. Three of those
migrations drop tables described in their own docstrings as "dead" or "inert",
and one runs a de-duplicating DELETE. Those descriptions were written about the
development database; whether they hold for production is a question about
production, and it has to be asked before the deploy rather than after.

Opens a READ ONLY transaction and never prints the connection string.

    TARGET_ENV=production DATABASE_URL=... python3 tools/data-quality/migration_preflight.py

Point-in-time only. Re-run it immediately before deploying -- a clean result
today says nothing about a database that has been written to since.
"""
import os
from sqlalchemy import create_engine
env = os.environ["TARGET_ENV"]
e = create_engine(os.environ["DATABASE_URL"].replace("postgres://","postgresql://",1))
c = e.connect(); c.exec_driver_sql("SET TRANSACTION READ ONLY")
def exists(t): return bool(list(c.exec_driver_sql(f"SELECT 1 FROM information_schema.tables WHERE table_name='{t}'")))
def count(t):  return list(c.exec_driver_sql(f"SELECT count(*) FROM {t}"))[0][0]
rev = list(c.exec_driver_sql("SELECT version_num FROM alembic_version"))[0][0]
print(f"--- {env.upper()}  (alembic {rev}) ---")
blockers = []
for t, why in [("custom_phases","v40 drops it"),("planning_locations","v53 drops it"),("scheduled_sessions","v53 drops it")]:
    if exists(t):
        n = count(t)
        print(f"  drop {t:20} {n:6} rows" + ("   <-- WOULD DESTROY DATA" if n else "   (empty)"))
        if n: blockers.append(f"{t} holds {n} rows")
    else:
        print(f"  drop {t:20} already absent")
if exists("session_audience"):
    tot = count("session_audience")
    keep = list(c.exec_driver_sql("SELECT count(*) FROM (SELECT MIN(id) FROM session_audience GROUP BY session_id, training_class_id) x"))[0][0]
    print(f"  v55 dedupe session_audience: {tot} rows, {tot-keep} would be DELETED")
    if tot-keep: blockers.append(f"session_audience dedupe deletes {tot-keep}")
else:
    print("  v55 dedupe session_audience: table absent, created later in the chain (empty when it runs)")
if exists("parade_dates") and exists("parade_nights"):
    o = list(c.exec_driver_sql("SELECT count(*) FROM parade_dates WHERE parade_night_id IS NOT NULL AND parade_night_id NOT IN (SELECT id FROM parade_nights)"))[0][0]
    print(f"  v54 orphan parade_dates links nulled: {o} of {count('parade_dates')}")
if exists("planning_conflicts"):
    o = list(c.exec_driver_sql("SELECT count(*) FROM planning_conflicts WHERE scheduled_session_id IS NOT NULL AND scheduled_session_id NOT IN (SELECT id FROM sessions)"))[0][0]
    print(f"  v55 orphan planning_conflicts nulled: {o} of {count('planning_conflicts')}")
d = list(c.exec_driver_sql("SELECT count(*) FROM (SELECT unit_id, year FROM planning_years WHERE unit_id IS NOT NULL AND active_status = true GROUP BY unit_id, year HAVING count(*) > 1) x"))[0][0]
print(f"  REM-134 duplicate ACTIVE year groups: {d}" + ("   <-- BLOCKS THE MIGRATION" if d else ""))
if d: blockers.append(f"{d} duplicate active planning-year group(s)")
print(f"  => {'BLOCKED: ' + '; '.join(blockers) if blockers else 'clear to migrate'}")
c.close(); e.dispose()
