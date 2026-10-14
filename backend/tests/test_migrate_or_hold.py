"""D23 (2026-10-12): a rolled-back backend must start against a newer schema.

The container entrypoint ran `alembic upgrade head` under `set -e`. Once a
release's migrations have run, redeploying the PREVIOUS build fails at
start-up ("Can't locate revision identified by '<newer head>'") and the
container crash-loops, so the runbook's application-only rollback was
impossible (proven locally against the previous release, 431d5f9).
scripts/migrate_or_hold.py replaces that step: a fresh or older database is
upgraded as before; a database at a revision this code does not know (the
rollback case) is left untouched with a loud warning and start-up continues.
A genuine migration failure still fails start-up.
"""
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
PY = sys.executable


def _run(db, *args, extra_env=None):
    env = {k: v for k, v in os.environ.items() if k != "ALLOW_SCHEMA_AHEAD"}
    env.update({"DATABASE_URL": f"sqlite:///{db}", "ENVIRONMENT": "test", **(extra_env or {})})
    return subprocess.run([PY, *args], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=300)


def _rev(db):
    con = sqlite3.connect(db)
    try:
        return [r[0] for r in con.execute("SELECT version_num FROM alembic_version")]
    finally:
        con.close()


def _head():
    return subprocess.run([PY, "scripts/compute_alembic_head.py", "alembic/versions"], cwd=BACKEND,
                          capture_output=True, text=True, check=True).stdout.strip()


def test_a_fresh_database_is_upgraded_to_head():
    with tempfile.TemporaryDirectory() as tmp:
        db = f"{tmp}/fresh.db"
        r = _run(db, "-m", "scripts.migrate_or_hold")
        assert r.returncode == 0, r.stdout + r.stderr
        assert _rev(db) == [_head()]


def test_an_older_database_is_upgraded_to_head():
    with tempfile.TemporaryDirectory() as tmp:
        db = f"{tmp}/old.db"
        assert _run(db, "-m", "alembic", "upgrade", "a4e9507a9c51").returncode == 0
        r = _run(db, "-m", "scripts.migrate_or_hold")
        assert r.returncode == 0, r.stdout + r.stderr
        assert _rev(db) == [_head()]


def _ahead_db(tmp):
    db = f"{tmp}/ahead.db"
    assert _run(db, "-m", "alembic", "upgrade", "head").returncode == 0
    con = sqlite3.connect(db)
    con.execute("UPDATE alembic_version SET version_num = 'f0f0f0f0f0f0'")   # a later (or diverged) head
    con.commit()
    con.close()
    return db


def test_a_database_ahead_of_this_code_is_held_only_when_a_rollback_is_declared():
    """ALLOW_SCHEMA_AHEAD=1 (set by the operator on a rollback deploy) holds:
    no migration, start-up continues."""
    with tempfile.TemporaryDirectory() as tmp:
        db = _ahead_db(tmp)
        r = _run(db, "-m", "scripts.migrate_or_hold", extra_env={"ALLOW_SCHEMA_AHEAD": "1"})
        assert r.returncode == 0, r.stdout + r.stderr
        assert "AHEAD" in (r.stdout + r.stderr)
        assert _rev(db) == ["f0f0f0f0f0f0"]                    # untouched


def test_an_unknown_revision_without_a_declared_rollback_fails_start_up():
    """Without the flag an unknown revision may be a diverged branch rather than
    a rollback; starting against a schema missing this build's own migrations
    would be worse than not starting (security review, 2026-10-12)."""
    with tempfile.TemporaryDirectory() as tmp:
        db = _ahead_db(tmp)
        r = _run(db, "-m", "scripts.migrate_or_hold")
        assert r.returncode != 0
        assert "ALLOW_SCHEMA_AHEAD" in (r.stdout + r.stderr)
        assert _rev(db) == ["f0f0f0f0f0f0"]
