#!/usr/bin/env python3
"""Generate the SQL that resolves duplicate ACTIVE planning years. READ-ONLY.

Reads a database and writes a reviewable .sql file to stdout. It never executes
anything and never prints the connection string. Deciding whether to run the
output is a data decision -- this only removes the tedium and the transcription
errors from preparing it.

Rows are ARCHIVED (active_status = false), never deleted: archiving is this
system's normal way to retire a planning year, archived rows do not participate
in the partial unique index from migration d1e4f8a03b27, and it is reversible.

A group is only resolved automatically when exactly ONE of its rows has
dependents. Groups where none do, or where more than one does, are printed as
comments for a person to decide -- both were hit in practice on 2026-08-23.

    TARGET_ENV=production DATABASE_URL=... python3 tools/data-quality/planning_year_resolution_sql.py \
      > docs/remediation/rem134_resolve_production.sql
"""
import os
from collections import defaultdict
from sqlalchemy import create_engine, text

env = os.environ["TARGET_ENV"]
e = create_engine(os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1))
c = e.connect(); c.exec_driver_sql("SET TRANSACTION READ ONLY")

# training_classes does not exist in production, which is behind on migrations.
has_tc = bool(list(c.exec_driver_sql(
    "SELECT 1 FROM information_schema.tables WHERE table_name='training_classes'")))
tc_expr = ("(SELECT count(*) FROM training_classes tc WHERE tc.training_year_id = py.id)"
           if has_tc else "0")

rows = list(c.exec_driver_sql(f"""
  SELECT py.id, py.year, py.name, py.created_at, s.code,
         (SELECT count(*) FROM parade_dates pd WHERE pd.planning_year_id = py.id),
         (SELECT count(*) FROM holiday_periods hp WHERE hp.planning_year_id = py.id),
         {tc_expr}
  FROM planning_years py JOIN squadrons s ON s.id = py.unit_id
  WHERE py.active_status = true AND (py.unit_id, py.year) IN (
    SELECT unit_id, year FROM planning_years
    WHERE unit_id IS NOT NULL AND active_status = true
    GROUP BY unit_id, year HAVING count(*) > 1)
  ORDER BY s.code, py.year, py.created_at"""))

g = defaultdict(list)
for r in rows:
    g[(r[4], r[1])].append(r)

def dependents(r):
    return r[5] + r[6] + r[7]

keep, archive, none_have, many_have = [], [], [], []
for k, grp in sorted(g.items()):
    with_data = [r for r in grp if dependents(r)]
    if len(with_data) == 1:
        keep.append((k, with_data[0]))
        archive += [(k, r) for r in grp if r[0] != with_data[0][0]]
    elif not with_data:
        none_have.append((k, grp))
    else:
        many_have.append((k, grp, with_data))

P = print
P(f"-- REM-134 planning-year resolution — {env.upper()}")
P(f"-- {len(rows)} active rows across {len(g)} duplicate group(s).")
P(f"-- training_classes table present in this environment: {has_tc}")
P("--")
P("-- Nothing here deletes anything. Rows are ARCHIVED (active_status = false),")
P("-- which is this system's normal way to retire a planning year, and archived")
P("-- rows do not participate in the partial unique index that migration")
P("-- d1e4f8a03b27 creates. Archiving is reversible; deletion would not be.")
P("--")
P("-- Dependent counts below are parade_dates + holiday_periods" + (" + training_classes." if has_tc else "."))

if keep:
    P("--")
    P("-- RESOLVED AUTOMATICALLY — exactly one row in the group carries data, so")
    P("-- the choice is not a judgement call. Kept:")
    for (code, year), r in keep:
        P(f"--   {code} {year}  {r[0]}  pd={r[5]} hp={r[6]} tc={r[7]}  {str(r[2])[:34]}")

if none_have:
    P("--")
    P("-- NOT HANDLED — no row in these groups carries any data, so there is no")
    P("-- basis for preferring one. Ask which name is intended, keep that one,")
    P("-- archive the rest by hand:")
    for (code, year), grp in none_have:
        for r in grp:
            P(f"--   {code} {year}  {r[0]}  created {str(r[3])[:10]}  {str(r[2])[:34]}")

if many_have:
    P("--")
    P("-- NOT HANDLED — MORE THAN ONE row in these groups carries data. Archiving")
    P("-- either one hides real records, so this needs a person who knows what the")
    P("-- squadron actually ran. Consider moving the dependents onto the row you")
    P("-- intend to keep before archiving the other.")
    for (code, year), grp, wd in many_have:
        for r in grp:
            mark = "  <-- has data" if dependents(r) else ""
            P(f"--   {code} {year}  {r[0]}  pd={r[5]} hp={r[6]} tc={r[7]}  {str(r[2])[:30]}{mark}")

P("")
if not archive:
    P("-- Nothing can be archived automatically in this environment.")
else:
    P("BEGIN;")
    P("")
    P("UPDATE planning_years SET active_status = false, updated_at = now()")
    P("WHERE id IN (")
    for i, ((code, year), r) in enumerate(archive):
        comma = "," if i < len(archive) - 1 else ""
        P(f"    '{r[0]}'{comma}   -- {code} {year}, no dependents, created {str(r[3])[:10]}")
    P(");")
    P(f"-- expect: UPDATE {len(archive)}")
    P("")
    P("-- Verify BEFORE committing. Both queries must return zero rows.")
    P("SELECT unit_id, year, count(*) FROM planning_years")
    P("WHERE unit_id IS NOT NULL AND active_status = true")
    P("GROUP BY unit_id, year HAVING count(*) > 1;")
    P("")
    P("SELECT py.id FROM planning_years py")
    P("WHERE py.active_status = false AND EXISTS (")
    P("  SELECT 1 FROM parade_dates pd WHERE pd.planning_year_id = py.id);")
    P("-- ^ nothing archived here should own parade dates")
    P("")
    P("COMMIT;   -- or ROLLBACK; if either check returned rows")
c.close(); e.dispose()
