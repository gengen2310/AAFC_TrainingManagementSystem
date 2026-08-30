#!/usr/bin/env python3
"""Compare the migrated schema against the ORM's own metadata.

The test suite builds its schema with Base.metadata.create_all() from the
models. Production builds it by running the migration chain. Nothing checks
that those two agree, so any divergence is invisible to every test by
construction: the tests cannot produce a row that only the migrated schema
permits.

This builds both on PostgreSQL and diffs every column's type and nullability.

The divergence is a ratchet, not a gate. There are known differences that
predate this check and are not worth the risk of a mass ALTER on a live
database -- nullable created_at/updated_at, mostly. What must not happen is the
set growing. BASELINE is the count when this check was introduced; the script
fails if the count rises above it, and tells you to lower BASELINE when you
bring it down.

Usage:  python scripts/schema_parity.py [--list] [--baseline N]

Needs a local PostgreSQL and createdb rights. Creates and drops its own two
scratch databases.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent

# Divergences remaining after v62 closed the eight boolean flags. Lower this
# whenever you close more; never raise it.
BASELINE = 60

COLUMN_QUERY = (
    "SELECT table_name||'.'||column_name||E'\\t'||data_type||' null='||is_nullable "
    "FROM information_schema.columns "
    "WHERE table_schema='public' AND table_name<>'alembic_version' ORDER BY 1"
)


def psql(db: str, sql: str) -> list[str]:
    r = subprocess.run(["psql", "-d", db, "-qtA", "-c", sql],
                       capture_output=True, text=True, timeout=180)
    if r.returncode:
        raise SystemExit(f"psql failed: {r.stderr.strip()}")
    return [ln for ln in r.stdout.splitlines() if ln.strip()]


def recreate(db: str) -> None:
    subprocess.run(["psql", "-d", "postgres", "-q", "-c", f'DROP DATABASE IF EXISTS "{db}"'],
                   capture_output=True, timeout=120)
    subprocess.run(["psql", "-d", "postgres", "-q", "-c", f'CREATE DATABASE "{db}"'],
                   check=True, capture_output=True, timeout=120)


def url(db: str) -> str:
    return f"postgresql+psycopg2://{os.environ.get('USER','postgres')}@localhost:5432/{db}"


def build_migrated(db: str) -> None:
    recreate(db)
    env = dict(os.environ); env["DATABASE_URL"] = url(db)
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                       cwd=BACKEND, env=env, capture_output=True, text=True, timeout=900)
    if r.returncode:
        raise SystemExit(f"alembic upgrade failed:\n{r.stderr[-1500:]}")


def build_orm(db: str) -> None:
    recreate(db)
    env = dict(os.environ); env["DATABASE_URL"] = url(db)
    r = subprocess.run(
        [sys.executable, "-c",
         "from app.database import Base, engine\n"
         "import app.models  # noqa: F401\n"
         "Base.metadata.create_all(engine)"],
        cwd=BACKEND, env=env, capture_output=True, text=True, timeout=900)
    if r.returncode:
        raise SystemExit(f"create_all failed:\n{r.stderr[-1500:]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="print every divergence")
    ap.add_argument("--baseline", type=int, default=BASELINE)
    args = ap.parse_args()

    build_migrated("tms_parity_mig")
    build_orm("tms_parity_orm")
    mig = dict(ln.split("\t", 1) for ln in psql("tms_parity_mig", COLUMN_QUERY))
    orm = dict(ln.split("\t", 1) for ln in psql("tms_parity_orm", COLUMN_QUERY))

    only_mig = sorted(set(mig) - set(orm))
    only_orm = sorted(set(orm) - set(mig))
    differ = sorted(c for c in set(mig) & set(orm) if mig[c] != orm[c])

    print(f"migrated columns: {len(mig)}   ORM columns: {len(orm)}")
    print(f"  only in migrated schema: {len(only_mig)}")
    print(f"  only in ORM metadata:    {len(only_orm)}")
    print(f"  differing definition:    {len(differ)}  (baseline {args.baseline})")

    if args.list:
        for c in only_mig:
            print(f"    migrated-only  {c}  {mig[c]}")
        for c in only_orm:
            print(f"    ORM-only       {c}  {orm[c]}")
        for c in differ:
            print(f"    differs        {c}\n        migrated: {mig[c]}\n        ORM     : {orm[c]}")

    for db in ("tms_parity_mig", "tms_parity_orm"):
        subprocess.run(["psql", "-d", "postgres", "-q", "-c", f'DROP DATABASE IF EXISTS "{db}"'],
                       capture_output=True, timeout=120)

    print()
    if only_mig or only_orm:
        print("SCHEMA PARITY FAILED -- a column exists on only one side. "
              "That is a missing migration or a missing model field, not a tolerable drift.")
        return 1
    if len(differ) > args.baseline:
        print(f"SCHEMA PARITY FAILED -- divergence grew to {len(differ)}, "
              f"above the baseline of {args.baseline}. Run with --list to see them.")
        return 1
    if len(differ) < args.baseline:
        print(f"SCHEMA PARITY PASSED -- divergence is down to {len(differ)}. "
              f"Lower BASELINE in this script to {len(differ)} to lock the gain in.")
        return 0
    print(f"SCHEMA PARITY PASSED -- {len(differ)} known divergences, none new.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
