"""Read-only audit for cross-squadron references written before the tenancy fix.

Sessions denormalise a curriculum item, facilitators and a training area. Until
2026-09-02 those ids were resolved with a bare db.get() on every write path, with
no comparison between the referenced row's squadron and the session's. The fix
closes the door; it does not clean up anything that walked through it. This finds
what did.

SELECT only. It opens no transaction that writes, and it is safe to run against
any environment. It does not print the connection string.

    DATABASE_URL=... python scripts/audit_cross_tenant_refs.py
    python scripts/audit_cross_tenant_refs.py --self-test   # prove it can detect

--self-test builds a throwaway SQLite database, seeds two squadrons, writes one
deliberately bad row per category, and asserts every check fires. A query that
returns zero is indistinguishable from a query that is broken, so the zero is
only worth reporting after the query has been shown to find something.
"""
from __future__ import annotations

import os
import sys

# Each check: (label, what a hit means, SQL). Every query returns
# (session_id, squadron_id, referenced_id, referenced_squadron).
CHECKS = [
    ("audience_class", "session targets a TrainingClass owned by another squadron", """
        SELECT s.id, s.squadron_id, tc.id, tc.squadron_id
        FROM session_audience sa
        JOIN sessions s          ON s.id = sa.session_id
        JOIN training_classes tc ON tc.id = sa.training_class_id
        WHERE tc.squadron_id <> s.squadron_id
    """),
    ("facilitator", "session references another squadron's facilitator", """
        SELECT s.id, s.squadron_id, f.id, f.squadron_id
        FROM sessions s JOIN facilitators f ON f.id = s.facilitator_id
        WHERE f.squadron_id <> s.squadron_id
    """),
    ("assistant_facilitator", "assistant facilitator belongs to another squadron", """
        SELECT s.id, s.squadron_id, f.id, f.squadron_id
        FROM sessions s JOIN facilitators f ON f.id = s.assistant_facilitator_id
        WHERE f.squadron_id <> s.squadron_id
    """),
    ("backup_facilitator", "backup facilitator belongs to another squadron", """
        SELECT s.id, s.squadron_id, f.id, f.squadron_id
        FROM sessions s JOIN facilitators f ON f.id = s.backup_facilitator_id
        WHERE f.squadron_id <> s.squadron_id
    """),
    ("training_area", "session references another squadron's training area", """
        SELECT s.id, s.squadron_id, ta.id, ta.squadron_id
        FROM sessions s JOIN training_areas ta ON ta.id = s.training_area_id
        WHERE ta.squadron_id <> s.squadron_id
    """),
    # Curriculum is inheritable, so ownership is the wrong test. Only a
    # SQUADRON-owned item belonging to a different squadron is wrong; national
    # items are shared by design and wing items are checked separately below.
    ("curriculum_squadron", "session uses another squadron's local curriculum item", """
        SELECT s.id, s.squadron_id, ci.id, ci.squadron_id
        FROM sessions s JOIN curriculum_items ci ON ci.id = s.curriculum_item_id
        WHERE ci.owning_level = 'squadron' AND ci.squadron_id <> s.squadron_id
    """),
    ("curriculum_wing", "session uses a wing-owned item from a different wing", """
        SELECT s.id, s.squadron_id, ci.id, ci.wing_id
        FROM sessions s
        JOIN squadrons sq        ON sq.id = s.squadron_id
        JOIN curriculum_items ci ON ci.id = s.curriculum_item_id
        WHERE ci.owning_level = 'wing' AND ci.wing_id <> sq.wing_id
    """),
]


# How much data each check actually looked at. "0 findings" describes what was
# examined; a reader hears it as describing the system. On an empty table the two
# are very different statements, so the counts are printed beside the result.
COVERAGE = [
    ("sessions",                  "SELECT COUNT(*) FROM sessions"),
    ("  with a facilitator",      "SELECT COUNT(*) FROM sessions WHERE facilitator_id IS NOT NULL"),
    ("  with an assistant",       "SELECT COUNT(*) FROM sessions WHERE assistant_facilitator_id IS NOT NULL"),
    ("  with a backup",           "SELECT COUNT(*) FROM sessions WHERE backup_facilitator_id IS NOT NULL"),
    ("  with a training area",    "SELECT COUNT(*) FROM sessions WHERE training_area_id IS NOT NULL"),
    ("  with a curriculum item",  "SELECT COUNT(*) FROM sessions WHERE curriculum_item_id IS NOT NULL"),
    ("session_audience rows",     "SELECT COUNT(*) FROM session_audience"),
    ("squadrons",                 "SELECT COUNT(*) FROM squadrons"),
    ("training_classes",          "SELECT COUNT(*) FROM training_classes"),
    ("facilitators",              "SELECT COUNT(*) FROM facilitators"),
    ("training_areas",            "SELECT COUNT(*) FROM training_areas"),
    ("curriculum_items",          "SELECT COUNT(*) FROM curriculum_items"),
    ("  squadron-owned",          "SELECT COUNT(*) FROM curriculum_items WHERE owning_level = 'squadron'"),
    ("  wing-owned",              "SELECT COUNT(*) FROM curriculum_items WHERE owning_level = 'wing'"),
]


def coverage(conn) -> list[tuple[str, int]]:
    cur = conn.cursor()
    out = []
    for label, sql in COVERAGE:
        cur.execute(sql)
        out.append((label, cur.fetchone()[0]))
    return out


def run(conn) -> dict[str, list]:
    findings = {}
    cur = conn.cursor()
    for name, _meaning, sql in CHECKS:
        cur.execute(sql)
        findings[name] = cur.fetchall()
    return findings


def report(findings: dict[str, list], cov: list[tuple[str, int]] | None = None) -> int:
    total = sum(len(v) for v in findings.values())
    if cov:
        print("\ncoverage — what the checks were run against\n")
        for label, n in cov:
            print(f"  {label:<26} {n:>7}")
    width = max(len(n) for n, _, _ in CHECKS)
    print(f"\ncross-tenant reference audit — {len(CHECKS)} checks\n")
    for name, meaning, _ in CHECKS:
        rows = findings[name]
        flag = "ok  " if not rows else "HIT "
        print(f"  {flag} {name:<{width}}  {len(rows):>5}   {meaning}")
        for sid, ssq, rid, rsq in rows[:5]:
            print(f"          session {sid}  (sqn {ssq})  ->  {rid}  (sqn/wing {rsq})")
        if len(rows) > 5:
            print(f"          ... and {len(rows) - 5} more")
    print(f"\n  total cross-tenant references: {total}")
    return total


def self_test() -> int:
    """Prove each check can fire before trusting a zero from any of them."""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE squadrons (id TEXT PRIMARY KEY, wing_id TEXT);
        CREATE TABLE sessions (id TEXT PRIMARY KEY, squadron_id TEXT,
            curriculum_item_id TEXT, facilitator_id TEXT,
            assistant_facilitator_id TEXT, backup_facilitator_id TEXT,
            training_area_id TEXT);
        CREATE TABLE facilitators (id TEXT PRIMARY KEY, squadron_id TEXT);
        CREATE TABLE training_areas (id TEXT PRIMARY KEY, squadron_id TEXT);
        CREATE TABLE training_classes (id TEXT PRIMARY KEY, squadron_id TEXT);
        CREATE TABLE session_audience (session_id TEXT, training_class_id TEXT);
        CREATE TABLE curriculum_items (id TEXT PRIMARY KEY, owning_level TEXT,
            squadron_id TEXT, wing_id TEXT);

        INSERT INTO squadrons VALUES ('sq703','wgA'), ('sq705','wgB');
        -- one clean session and one poisoned session, same shape
        INSERT INTO sessions VALUES ('sOK','sq703','ciNAT','fOK','fOK','fOK','taOK');
        INSERT INTO sessions VALUES ('sBAD','sq703','ciSQN705','f705','f705','f705','ta705');
        INSERT INTO facilitators VALUES ('fOK','sq703'), ('f705','sq705');
        INSERT INTO training_areas VALUES ('taOK','sq703'), ('ta705','sq705');
        INSERT INTO training_classes VALUES ('tcOK','sq703'), ('tc705','sq705');
        INSERT INTO session_audience VALUES ('sOK','tcOK'), ('sBAD','tc705');
        INSERT INTO curriculum_items VALUES
            ('ciNAT','national',NULL,NULL),
            ('ciSQN705','squadron','sq705',NULL),
            ('ciWGB','wing',NULL,'wgB');
    """)
    conn.commit()

    findings = run(conn)
    failures = [n for n, _, _ in CHECKS if not findings[n]]
    # curriculum_wing needs its own poisoned row: sBAD already carries a
    # squadron-owned item, so point a third session at wing B's item.
    c.execute("INSERT INTO sessions VALUES ('sWING','sq703','ciWGB',NULL,NULL,NULL,NULL)")
    conn.commit()
    findings = run(conn)
    failures = [n for n, _, _ in CHECKS if not findings[n]]

    print("self-test — every check must fire on a deliberately poisoned database")
    for name, _, _ in CHECKS:
        print(f"  {'FIRED' if findings[name] else 'SILENT'}  {name}  ({len(findings[name])} row(s))")
    if failures:
        print(f"\n  SELF-TEST FAILED — these checks cannot detect their own bug: {failures}")
        return 1

    # and the clean session must never be implicated
    implicated = {row[0] for rows in findings.values() for row in rows}
    if "sOK" in implicated:
        print("\n  SELF-TEST FAILED — a clean session was reported as cross-tenant")
        return 1
    print(f"\n  SELF-TEST PASSED — {len(CHECKS)} checks fire, clean rows untouched")
    return 0


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()

    # Railway's DATABASE_URL uses postgres.railway.internal, which resolves only
    # inside their network. From a workstation the public proxy URL is the one
    # that connects, so prefer it when present.
    url = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set. Run under `railway run` so it is injected "
              "into the environment rather than passed on the command line.")
        return 2

    if url.startswith("postgres"):
        import psycopg2  # noqa
        conn = psycopg2.connect(url)
        conn.set_session(readonly=True, autocommit=True)
    else:
        import sqlite3
        conn = sqlite3.connect(url.replace("sqlite:///", ""))

    # Never print the URL. Host only, so the operator can confirm the target.
    target = url.split("@")[-1].split("/")[0] if "@" in url else "local sqlite"
    print(f"target: {target}")
    return 0 if report(run(conn), coverage(conn)) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
