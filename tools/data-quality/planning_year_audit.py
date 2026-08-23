#!/usr/bin/env python3
"""Report duplicate and implausible planning years. READ-ONLY -- changes nothing.

Written 2026-08-22 after the dev database was found holding 118 planning years
for one squadron, including year 7253 and year 2064 thirty-three times over.
Migration b4c1f7d92e08 adds the missing unique index on (unit_id, year), and it
REFUSES to run if duplicates already exist -- duplicate years own parade nights
and sessions, so choosing which copy survives is an operational decision. This
script is what you run to make that decision.

Works against SQLite (a file path) and PostgreSQL (a URL), because the databases
that actually need checking before a deploy are Postgres:

    python3 tools/data-quality/planning_year_audit.py backend/aafc_tms.db
    python3 tools/data-quality/planning_year_audit.py "postgresql://..."
    railway run --environment staging -- python3 tools/data-quality/planning_year_audit.py

With no argument it reads DATABASE_URL from the environment, then falls back to
the local SQLite file. It never prints the connection string.
"""
import os
import sys
from collections import defaultdict


class _Conn:
    """Minimal read-only wrapper so one code path serves SQLite and PostgreSQL."""

    def __init__(self, target: str):
        self.is_url = "://" in target
        if self.is_url:
            from sqlalchemy import create_engine
            # PostgreSQL only. A read-only session so a mistake here cannot write.
            url = target.replace("postgres://", "postgresql://", 1)
            self._engine = create_engine(url, pool_pre_ping=True)
            self._conn = self._engine.connect()
            self._conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            self.label = "PostgreSQL"
        else:
            import sqlite3
            self._conn = sqlite3.connect(f"file:{target}?mode=ro", uri=True)
            self.label = f"SQLite {target}"

    def query(self, sql):
        if self.is_url:
            return list(self._conn.exec_driver_sql(sql))
        return list(self._conn.execute(sql))

    def close(self):
        self._conn.close()
        if self.is_url:
            self._engine.dispose()


def main(target):
    db = _Conn(target)
    print(f"source: {db.label}\n")

    rows = db.query(
        "SELECT id, unit_id, year, name, active_status, created_at FROM planning_years")
    print(f"planning_years rows: {len(rows)}")
    if not rows:
        # An empty result and a broken query look identical in a report. Say so.
        print("  NOTE: the table is empty. If that is unexpected, the connection is\n"
              "  probably pointing somewhere other than you think.")
    print()

    by_unit_year = defaultdict(list)
    for r in rows:
        by_unit_year[(r[1], r[2])].append(r)

    # unit_id is NULL for wing and national years, and the unique index treats
    # NULLs as distinct, so those rows are not constrained and not reported.
    dupes = {k: v for k, v in by_unit_year.items() if len(v) > 1 and k[0] is not None}
    print(f"duplicate (unit_id, year) groups: {len(dupes)}")
    extra = sum(len(v) - 1 for v in dupes.values())
    print(f"  rows beyond the first in each group: {extra}")
    if dupes:
        print("  MIGRATION b4c1f7d92e08 WILL REFUSE TO RUN until these are resolved.")
    for (unit, year), grp in sorted(dupes.items(), key=lambda kv: -len(kv[1]))[:8]:
        print(f"  year {year}: {len(grp)} rows  (unit {str(unit)[:8]}\u2026)")
        for r in grp[:3]:
            print(f"      {str(r[0])[:8]}\u2026  {'active ' if r[4] else 'archived'}  {str(r[3])[:44]}")
        if len(grp) > 3:
            print(f"      \u2026 {len(grp)-3} more")

    nulls = sum(1 for k, v in by_unit_year.items() if k[0] is None for _ in v)
    print(f"\nwing/national years (unit_id NULL, never constrained): {nulls}")

    # a training year far from any plausible operating year
    THIS_YEAR = 2026
    implausible = [r for r in rows if not (THIS_YEAR - 10 <= r[2] <= THIS_YEAR + 10)]
    print(f"years outside {THIS_YEAR-10}-{THIS_YEAR+10}: {len(implausible)}")
    for r in sorted(implausible, key=lambda r: -r[2])[:10]:
        print(f"  {r[2]}  {'active ' if r[4] else 'archived'}  {str(r[3])[:52]}")

    # what still references a row before anything is deleted
    print("\nreferencing rows (delete nothing without checking these):")
    ids = {r[0] for r in rows}
    for tbl, col in [("parade_dates", "planning_year_id"),
                     ("holiday_periods", "planning_year_id"),
                     ("training_classes", "training_year_id")]:
        try:
            n = sum(1 for (v,) in db.query(f"SELECT {col} FROM {tbl}") if v in ids)
            print(f"  {tbl}.{col}: {n} rows point at a planning year")
        except Exception as e:
            print(f"  {tbl}: {type(e).__name__}: {str(e)[:90]}")

    db.close()
    return 1 if dupes else 0


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target = sys.argv[1]
    elif os.environ.get("DATABASE_URL"):
        target = os.environ["DATABASE_URL"]
    else:
        target = "backend/aafc_tms.db"
    sys.exit(main(target))
