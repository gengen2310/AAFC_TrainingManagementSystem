"""One ACTIVE timing override per parade night -- enforced by the migrated schema.

v55 meant to replace the full UNIQUE(parade_night_id) on
parade_night_timing_overrides with a partial unique index (active rows only),
so "set or replace" -- archive the active override, insert the new one --
works. But its PostgreSQL branch dropped a constraint name that never existed
(the default ..._parade_night_id_key; v8 named it uq_pnto_parade_night_id), and
migration 821e later dropped the partial index on every dialect. Result:
PostgreSQL (production) kept the FULL unique, so replacing a night's override
failed with a duplicate-key error; SQLite had no uniqueness at all. The test
suite builds its schema with create_all, so it could never see either.

This runs the real migration chain and checks the rule on the result.
"""
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def migrated(tmp_path):
    # A subprocess: alembic/env.py reads the URL from app settings, which this
    # test process already loaded for the suite's own database.
    url = f"sqlite:///{tmp_path / 'chain.sqlite'}"
    env = {**os.environ, "DATABASE_URL": url, "ENVIRONMENT": "test"}
    r = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                       env=env, capture_output=True, text=True, cwd=BACKEND)
    assert r.returncode == 0, r.stderr[-2000:]
    eng = create_engine(url)
    yield eng
    eng.dispose()


def _insert(conn, night, archived, oid=None):
    conn.execute(text(
        "INSERT INTO parade_night_timing_overrides "
        "(id, parade_night_id, timing_template_id, reason, is_archived, created_at, updated_at) "
        "VALUES (:id, :n, 'tpl', 'r', :a, '2026-01-01', '2026-01-01')"),
        {"id": oid or str(uuid.uuid4()), "n": night, "a": archived})


def test_replace_flow_succeeds_on_the_migrated_schema(migrated):
    with migrated.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        _insert(c, "night-1", False, "ov1")
        c.execute(text("UPDATE parade_night_timing_overrides SET is_archived = 1 WHERE id = 'ov1'"))
        _insert(c, "night-1", False, "ov2")            # the replacement
        _insert(c, "night-1", True)                     # more archived history is fine


def test_two_active_overrides_for_one_night_are_rejected(migrated):
    with pytest.raises(IntegrityError):
        with migrated.begin() as c:
            c.execute(text("PRAGMA foreign_keys=OFF"))
            _insert(c, "night-2", False)
            _insert(c, "night-2", False)
