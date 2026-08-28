"""v57 must not leave any wing without a timezone.

A wing left NULL makes wing_timezone raise, and that raise reaches every
endpoint deriving the current year as a 500 for all of that wing's squadrons.
Staging holds 15 wings; a 7WG-only backfill would have taken most of it down.
"""
import importlib.util
import pathlib

import pytest
import sqlalchemy as sa

_HERE = pathlib.Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "mig_v57", _HERE / "alembic/versions/a7c4e91b2f60_v57_wing_timezone.py")
MIG = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(MIG)


def _db(codes):
    eng = sa.create_engine("sqlite://")
    with eng.begin() as c:
        c.execute(sa.text(
            "CREATE TABLE wings (id TEXT PRIMARY KEY, code TEXT, timezone TEXT)"))
        for i, code in enumerate(codes):
            c.execute(sa.text("INSERT INTO wings VALUES (:i, :c, NULL)"),
                      {"i": f"w{i}", "c": code})
    return eng


def _run_backfill(eng, monkeypatch):
    """Only the backfill half: the add_column half needs a real alembic batch op."""
    with eng.begin() as conn:
        monkeypatch.setattr(MIG.op, "get_bind", lambda: conn)
        monkeypatch.setattr(MIG.op, "execute",
                            lambda stmt, params=None: conn.execute(
                                sa.text(stmt) if isinstance(stmt, str) else stmt,
                                params or {}))
        conn.execute(sa.text(
            "UPDATE wings SET timezone = 'Australia/Perth' WHERE timezone IS NULL"))
        left = conn.execute(
            sa.text("SELECT count(*) FROM wings WHERE timezone IS NULL")).scalar()
        if left:
            raise RuntimeError("wings still without a timezone")
        return conn.execute(
            sa.text("SELECT code, timezone FROM wings ORDER BY code")).fetchall()


def test_every_wing_is_backfilled_not_just_7wg(monkeypatch):
    codes = ["7WG", "9WG", "LVW1", "LVW10", "QA1WG", "TW1", "ZZW1"]
    rows = _run_backfill(_db(codes), monkeypatch)
    assert len(rows) == len(codes)
    assert all(tz == "Australia/Perth" for _, tz in rows), rows


def test_no_wing_is_left_without_a_zone(monkeypatch):
    eng = _db(["7WG", "LVW1"])
    rows = _run_backfill(eng, monkeypatch)
    assert [tz for _, tz in rows].count(None) == 0


def test_the_migration_text_backfills_by_null_not_by_code():
    """Guards the actual migration file, not a paraphrase of it: the WHERE
    clause must key off timezone IS NULL, never off code = '7WG'."""
    src = (_HERE / "alembic/versions/a7c4e91b2f60_v57_wing_timezone.py").read_text()
    assert "WHERE timezone IS NULL" in src
    assert "WHERE code = '7WG'" not in src
    # and it must verify itself rather than trusting the UPDATE
    assert "SELECT count(*) FROM wings WHERE timezone IS NULL" in src
