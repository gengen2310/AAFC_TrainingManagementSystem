#!/usr/bin/env python3
"""Phase B pre-migration audit.

Run from repo root:
    python scripts/phase_b_audit.py

Reads the DB at DATABASE_URL (env) or backend/aafc_tms.db.
Exit code 0 = all clear; 1 = blockers found.
"""
import os, sys, sqlite3

DB = os.environ.get("DATABASE_URL") or "backend/aafc_tms.db"
if DB.startswith("postgresql"):
    try:
        import psycopg2
        conn = psycopg2.connect(DB)
    except ImportError:
        print("ERROR: psycopg2 not installed; activate backend/.venv first", file=sys.stderr)
        sys.exit(2)
    cursor = conn.cursor()
    placeholder = "%s"
else:
    conn = sqlite3.connect(DB.removeprefix("sqlite:///"))
    cursor = conn.cursor()
    placeholder = "?"

# 1. Orphan nights — no linked parade_date row at all
cursor.execute("""
    SELECT pn.id, pn.squadron_id, pn.date, pn.training_year
    FROM parade_nights pn
    LEFT JOIN parade_dates pd ON pd.parade_night_id = pn.id
    WHERE pd.id IS NULL
      AND pn.is_archived = 0
    ORDER BY pn.squadron_id, pn.date
""")
orphans = cursor.fetchall()

# 2. Linked nights whose parade_date has no planning_year_id
cursor.execute("""
    SELECT pn.id, pn.squadron_id, pn.date, pd.id as pd_id, pd.planning_year_id
    FROM parade_nights pn
    JOIN parade_dates pd ON pd.parade_night_id = pn.id
    WHERE pd.planning_year_id IS NULL
      AND pn.is_archived = 0
    ORDER BY pn.squadron_id, pn.date
""")
null_year = cursor.fetchall()

# 3. Nights with multiple linked parade_date rows (integrity violation)
cursor.execute("""
    SELECT pn.id, pn.squadron_id, pn.date, COUNT(pd.id) as n
    FROM parade_nights pn
    JOIN parade_dates pd ON pd.parade_night_id = pn.id
    WHERE pn.is_archived = 0
    GROUP BY pn.id HAVING COUNT(pd.id) > 1
    ORDER BY pn.squadron_id, pn.date
""")
duplicates = cursor.fetchall()

# 4. Notices pointing at a parade_date with no night
cursor.execute("""
    SELECT n.id, n.parade_date_id, pd.parade_night_id
    FROM planning_notices n
    JOIN parade_dates pd ON pd.id = n.parade_date_id
    WHERE pd.parade_night_id IS NULL
""")
notice_orphans = cursor.fetchall()

conn.close()

blockers = []

print("=" * 60)
print("Phase B Pre-migration Audit")
print("=" * 60)

if orphans:
    print(f"\n[BLOCKER] {len(orphans)} active parade_nights with NO linked parade_date:")
    for row in orphans:
        print(f"  squadron={row[1]}  date={row[2]}  night_id={row[0]}  training_year={row[3]}")
    blockers.extend(orphans)
else:
    print("\n[OK] No orphan parade_nights (all have a linked parade_date).")

if null_year:
    print(f"\n[BLOCKER] {len(null_year)} nights whose linked parade_date has NULL planning_year_id:")
    for row in null_year:
        print(f"  squadron={row[1]}  date={row[2]}  night_id={row[0]}  parade_date_id={row[3]}")
    blockers.extend(null_year)
else:
    print("[OK] All linked parade_dates have a planning_year_id.")

if duplicates:
    print(f"\n[BLOCKER] {len(duplicates)} nights with MULTIPLE linked parade_dates:")
    for row in duplicates:
        print(f"  squadron={row[1]}  date={row[2]}  night_id={row[0]}  count={row[3]}")
    blockers.extend(duplicates)
else:
    print("[OK] No nights with duplicate parade_date links.")

if notice_orphans:
    print(f"\n[WARN] {len(notice_orphans)} PlanningNotices point at a parade_date with no night:")
    for row in notice_orphans:
        print(f"  notice_id={row[0]}  parade_date_id={row[1]}")
else:
    print("[OK] All PlanningNotices link to a parade_date that has a night.")

print()
if blockers:
    print(f"RESULT: {len(blockers)} blocker(s) — resolve before running the migration.")
    sys.exit(1)
else:
    print("RESULT: All preconditions met. Safe to run the migration.")
    sys.exit(0)
