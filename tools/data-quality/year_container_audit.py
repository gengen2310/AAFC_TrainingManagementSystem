"""Report every PlanningYear against the calendar years of its own children.

READ-ONLY. Run before any year migration. Instruction §40-41: no migration may
silently reinterpret a row, and ambiguity stops and asks rather than guessing.

Exit code is 1 when any container's year integer disagrees with the dates it
holds, so this can gate a deploy step.

    python tools/data-quality/year_container_audit.py --dsn "$DISPOSABLE_DSN"

Never point --dsn at production for anything but a read; the tool issues no
writes, but a production connection string in shell history is its own problem.
"""
import argparse

SQL = """
SELECT s.code AS sqn, py.id, py.year, py.name, py.active_status,
       count(pd.id)                          AS dates,
       min(substr(pd.parade_date,1,4))       AS first_child_year,
       max(substr(pd.parade_date,1,4))       AS last_child_year
FROM planning_years py
LEFT JOIN squadrons s ON s.id = py.unit_id
LEFT JOIN parade_dates pd ON pd.planning_year_id = py.id
GROUP BY s.code, py.id, py.year, py.name, py.active_status
ORDER BY s.code, py.year;
"""


def audit(rows) -> tuple[list[str], int]:
    """Pure, so it is testable without a database."""
    flagged, total = [], 0
    for sqn, _id, year, name, _active, dates, first, last in rows:
        total += 1
        if dates and (str(year) != first or str(year) != last):
            flagged.append(
                f"MISMATCH {sqn} year={year} name={name!r} "
                f"dates={dates} children={first}..{last} id={_id}"
            )
    return flagged, total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dsn", required=True)
    args = ap.parse_args()

    # psycopg3 if present, else psycopg2 -- which is what this project actually
    # ships. Importing only psycopg3 made this tool fail on the project's own
    # dependencies, at exactly the moment an operator reaches for it: immediately
    # before a production year migration.
    try:
        import psycopg                      # psycopg 3
        connect = psycopg.connect
    except ModuleNotFoundError:
        import psycopg2                     # what requirements.txt installs
        connect = psycopg2.connect

    conn = connect(args.dsn)
    try:
        with conn.cursor() as cur:
            cur.execute(SQL)
            rows = cur.fetchall()
    finally:
        conn.close()

    flagged, total = audit(rows)
    for line in flagged:
        print(line)
    print(f"\n{len(flagged)} of {total} container(s) disagree with their dates")
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
