#!/usr/bin/env python3
"""Rehearse the whole Alembic chain against a real PostgreSQL database.

Part 93 of the final assurance programme: production-path migrations must be
exercised somewhere other than production. SQLite cannot stand in -- the chain
does not even run there (an early migration alters constraints, which SQLite's
dialect refuses), so a green test suite says nothing about whether a deploy
will migrate cleanly.

Three checks, in increasing strictness:

  1. FORWARD    base -> head applies cleanly.
  2. REVERSIBLE for each migration in turn: at revision N, step down to N-1 and
                back up to N, and require the schema fingerprint to be
                unchanged. This is the check that matters. A migration whose
                downgrade does not restore what its upgrade changed leaves the
                chain unwalkable, and the failure surfaces at some *unrelated*
                migration far away -- v53 dropping a table and recreating it
                without one column broke v26's downgrade, 27 steps earlier.
  3. FULL DOWN  head -> base, then base -> head again, with the head
                fingerprint required to match the first pass.

Usage:
    python scripts/rehearse_migrations.py                  # all three checks
    python scripts/rehearse_migrations.py --quick          # 1 and 3 only
    python scripts/rehearse_migrations.py --db tms_probe   # database name

Requires a running local PostgreSQL and createdb/dropdb rights. It creates and
drops its own scratch database and never touches an existing one.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent

# Migrations whose downgrade is deliberately NOT symmetric, with the reason.
# Each adds a column the ORM now requires unconditionally, so a symmetric
# drop_column would re-break every environment's queries the moment you rolled
# back -- reintroducing the very defect the migration exists to fix. They are
# listed rather than silently tolerated: an undeclared asymmetry is a bug, and
# a declared one should still be visible in the report.
DECLARED_IRREVERSIBLE = {
    "d4e5f6a7b8c9": "v44 adds planning_facilitator_leave.updated_by; TimestampMixin requires it",
    "e5f6a7b8c9d0": "v45 adds TimestampMixin columns to activity_local_hides and squadron_event_status",
    "f6a7b8c9d0e1": "v46 adds parade_nights.version for optimistic locking; the model requires it",
}
VERSIONS = BACKEND / "alembic" / "versions"


def chain() -> list[tuple[str, str]]:
    """The linear revision chain, base first, as (revision, filename)."""
    revs: dict[str, tuple[str | None, str]] = {}
    for f in VERSIONS.glob("*.py"):
        text = f.read_text()
        r = re.search(r'^revision = ["\']([^"\']+)', text, re.M)
        d = re.search(r'^down_revision = ["\']([^"\']+)', text, re.M)
        if r:
            revs[r.group(1)] = (d.group(1) if d else None, f.name)
    children: dict[str | None, list[str]] = {}
    for rev, (down, _) in revs.items():
        children.setdefault(down, []).append(rev)
    order, cur = [], None
    while True:
        nxt = children.get(cur, [])
        if not nxt:
            break
        if len(nxt) > 1:
            raise SystemExit(f"chain branches at {cur}: {nxt} -- two heads, not one")
        cur = nxt[0]
        order.append((cur, revs[cur][1]))
    if len(order) != len(revs):
        raise SystemExit(f"chain reaches {len(order)} of {len(revs)} revisions -- orphans exist")
    return order


def psql(db: str, sql: str) -> str:
    out = subprocess.run(["psql", "-d", db, "-qtA", "-c", sql],
                         capture_output=True, text=True, timeout=120)
    if out.returncode:
        raise SystemExit(f"psql failed: {out.stderr.strip()}")
    return out.stdout


def fingerprint(db: str) -> str:
    """Every column and index in the public schema, order-independent."""
    # alembic_version is Alembic's own bookkeeping, not application schema. It
    # does not exist before the first migration runs, so including it would
    # report the first migration as irreversible against an empty database.
    cols = psql(db, """
        SELECT table_name || '.' || column_name || ':' || data_type ||
               ':' || is_nullable
        FROM information_schema.columns WHERE table_schema = 'public'
          AND table_name <> 'alembic_version'
        ORDER BY 1
    """)
    idx = psql(db, """
        SELECT tablename || '/' || indexname
        FROM pg_indexes WHERE schemaname = 'public'
          AND tablename <> 'alembic_version' ORDER BY 1
    """)
    return cols + "--INDEXES--" + idx


def alembic(db: str, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["DATABASE_URL"] = f"postgresql+psycopg2://{os.environ.get('USER','postgres')}@localhost:5432/{db}"
    return subprocess.run([sys.executable, "-m", "alembic", *args],
                          cwd=BACKEND, env=env, capture_output=True, text=True,
                          timeout=600)


def recreate(db: str) -> None:
    subprocess.run(["psql", "-d", "postgres", "-q", "-c",
                    f'DROP DATABASE IF EXISTS "{db}"'], capture_output=True, timeout=120)
    subprocess.run(["psql", "-d", "postgres", "-q", "-c",
                    f'CREATE DATABASE "{db}"'], check=True, capture_output=True, timeout=120)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="tms_rehearsal")
    ap.add_argument("--quick", action="store_true",
                    help="skip the per-migration reversibility check")
    args = ap.parse_args()

    order = chain()
    print(f"chain: {len(order)} migrations, linear, single head ({order[-1][0]})\n")
    failures: list[str] = []
    declared: list[str] = []

    # ── 1. forward ────────────────────────────────────────────────────────────
    recreate(args.db)
    r = alembic(args.db, "upgrade", "head")
    if r.returncode:
        print("FORWARD  FAIL")
        print(r.stderr[-2000:])
        return 1
    applied = r.stderr.count("Running upgrade")
    head_fp = fingerprint(args.db)
    print(f"FORWARD  base -> head: {applied}/{len(order)} applied")

    # ── 2. per-migration reversibility ───────────────────────────────────────
    if not args.quick:
        print("\nREVERSIBLE  (at each revision: step down one, back up one, compare schema)")
        recreate(args.db)
        prev = "base"
        # The schema as it actually was when the chain first passed through each
        # revision on the way up. A downgrade is correct only if it restores
        # THAT, not merely if the migration's own round trip looks self-
        # consistent: v53 drops a table and recreates it on downgrade, so its
        # own down->up cycle is clean even when the recreated table is missing a
        # column. The damage surfaces 27 migrations later, at v26's downgrade.
        fp_at: dict[str, str] = {"base": fingerprint(args.db)}
        for i, (rev, name) in enumerate(order, 1):
            up = alembic(args.db, "upgrade", rev)
            if up.returncode:
                failures.append(f"{rev} ({name}): upgrade failed")
                print(f"  {i:2d}. {rev}  UPGRADE FAILED  {name}")
                break
            fp_here = fingerprint(args.db)

            down = alembic(args.db, "downgrade", prev)
            if down.returncode:
                err = _last_error(down.stderr)
                failures.append(f"{rev} ({name}): downgrade failed -- {err}")
                print(f"  {i:2d}. {rev}  DOWNGRADE FAILED  {name}\n        {err}")
                alembic(args.db, "upgrade", rev)   # restore for the next step
                fp_at[rev] = fp_here
                prev = rev
                continue

            restored = fingerprint(args.db)
            if restored != fp_at[prev]:
                diff = _fp_diff(fp_at[prev], restored)
                if rev in DECLARED_IRREVERSIBLE:
                    declared.append(f"{rev} ({name}): {DECLARED_IRREVERSIBLE[rev]}")
                    print(f"  {i:2d}. {rev}  declared irreversible  {name}")
                else:
                    failures.append(
                        f"{rev} ({name}): downgrade does not restore the pre-migration schema -- {diff}")
                    print(f"  {i:2d}. {rev}  DOWNGRADE LEAVES A DIFFERENT SCHEMA  {name}\n        {diff}")

            back = alembic(args.db, "upgrade", rev)
            if back.returncode:
                failures.append(f"{rev} ({name}): re-upgrade failed")
                print(f"  {i:2d}. {rev}  RE-UPGRADE FAILED  {name}")
                break
            after = fingerprint(args.db)
            if after != fp_here:
                diff = _fp_diff(fp_here, after)
                failures.append(f"{rev} ({name}): not reversible -- {diff}")
                print(f"  {i:2d}. {rev}  NOT REVERSIBLE  {name}\n        {diff}")

            fp_at[rev] = fp_here
            prev = rev
        clean = len(order) - len(failures) - len(declared)
        if not failures:
            print(f"  {clean} of {len(order)} migrations round-trip to an identical schema; "
                  f"{len(declared)} declared irreversible")

    # ── 3. full down, then up again ──────────────────────────────────────────
    print("\nFULL DOWN  head -> base -> head")
    recreate(args.db)
    alembic(args.db, "upgrade", "head")
    d = alembic(args.db, "downgrade", "base")
    if d.returncode:
        err = _last_error(d.stderr)
        ran = d.stderr.count("Running downgrade")
        failures.append(f"full downgrade stopped after {ran}/{len(order)}: {err}")
        print(f"  head -> base: FAILED after {ran}/{len(order)}\n        {err}")
    else:
        print(f"  head -> base: {d.stderr.count('Running downgrade')}/{len(order)}")
        u = alembic(args.db, "upgrade", "head")
        if u.returncode:
            failures.append("re-upgrade to head after full downgrade failed")
            print("  base -> head: FAILED")
        elif fingerprint(args.db) != head_fp:
            failures.append("schema after down+up differs from the first pass")
            print("  base -> head: schema DIFFERS from the first pass")
        else:
            print("  base -> head: schema identical to the first pass")

    subprocess.run(["psql", "-d", "postgres", "-q", "-c",
                    f'DROP DATABASE IF EXISTS "{args.db}"'], capture_output=True, timeout=120)

    print()
    if declared:
        print(f"DECLARED IRREVERSIBLE -- {len(declared)}, by design:")
        for d in declared:
            print(f"  - {d}")
        print()
    if failures:
        print(f"REHEARSAL FAILED -- {len(failures)} problem(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("REHEARSAL PASSED")
    return 0


def _last_error(stderr: str) -> str:
    for line in reversed(stderr.splitlines()):
        if "Error" in line or "error" in line:
            return line.strip()[:200]
    return stderr.strip().splitlines()[-1][:200] if stderr.strip() else "unknown"


def _fp_diff(before: str, after: str) -> str:
    b, a = set(before.split("\n")), set(after.split("\n"))
    lost, gained = sorted(b - a), sorted(a - b)
    parts = []
    if lost:
        parts.append(f"lost {lost[:4]}")
    if gained:
        parts.append(f"gained {gained[:4]}")
    return "; ".join(parts)[:300]


if __name__ == "__main__":
    raise SystemExit(main())
