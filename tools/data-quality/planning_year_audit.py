#!/usr/bin/env python3
"""Report duplicate and implausible planning years. READ-ONLY -- changes nothing.

Written 2026-08-22 after the dev database was found holding 118 planning years
for one squadron, including year 7253 and year 2064 thirty-three times over.
There is no uniqueness constraint on (unit_id, year), and the plain create
endpoint has no duplicate check -- only /rollover does (409).

Run against a copy first. Deciding what to do with the rows this prints is a
data decision, not a code one.

    python3 tools/data-quality/planning_year_audit.py backend/aafc_tms.db
"""
import sys, sqlite3
from collections import defaultdict

def main(path):
    db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    rows = list(db.execute(
        "SELECT id, unit_id, year, name, active_status, created_at FROM planning_years"))
    print(f"planning_years rows: {len(rows)}\n")

    by_unit_year = defaultdict(list)
    for r in rows:
        by_unit_year[(r[1], r[2])].append(r)

    dupes = {k: v for k, v in by_unit_year.items() if len(v) > 1}
    print(f"duplicate (unit_id, year) groups: {len(dupes)}")
    extra = sum(len(v) - 1 for v in dupes.values())
    print(f"  rows beyond the first in each group: {extra}")
    for (unit, year), grp in sorted(dupes.items(), key=lambda kv: -len(kv[1]))[:8]:
        print(f"  year {year}: {len(grp)} rows  (unit {unit[:8]}…)")
        for r in grp[:3]:
            print(f"      {r[0][:8]}…  {'active ' if r[4] else 'archived'}  {str(r[3])[:44]}")
        if len(grp) > 3:
            print(f"      … {len(grp)-3} more")

    # a training year far from any plausible operating year
    THIS_YEAR = 2026
    implausible = [r for r in rows if not (THIS_YEAR - 10 <= r[2] <= THIS_YEAR + 10)]
    print(f"\nyears outside {THIS_YEAR-10}-{THIS_YEAR+10}: {len(implausible)}")
    for r in sorted(implausible, key=lambda r: -r[2])[:10]:
        print(f"  {r[2]}  {'active ' if r[4] else 'archived'}  {str(r[3])[:52]}")

    # what still references a row before anything is deleted
    print("\nreferencing rows (delete nothing without checking these):")
    for tbl, col in [("parade_dates", "planning_year_id"),
                     ("holiday_periods", "planning_year_id"),
                     ("training_classes", "training_year_id")]:
        try:
            ids = {r[0] for r in rows}
            n = 0
            for (v,) in db.execute(f"SELECT {col} FROM {tbl}"):
                if v in ids:
                    n += 1
            print(f"  {tbl}.{col}: {n} rows point at a planning year")
        except sqlite3.OperationalError as e:
            print(f"  {tbl}: {e}")
    db.close()

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "backend/aafc_tms.db")
