"""The v58 renumber migration's guard, and the audit tool's pure core.

The guard is what stops a one-off data decision from being applied to a
database it was not made about. Verified in all three states: absent, wrong,
and exactly as decided.
"""
import importlib.util
import pathlib

import pytest
import sqlalchemy as sa

_HERE = pathlib.Path(__file__).resolve().parents[1]


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


MIG = _load(_HERE / "alembic/versions/d5f81a3c9e27_v58_renumber_708_year.py",
            "mig_v58")
AUDIT = _load(_HERE.parent / "tools/data-quality/year_container_audit.py",
              "year_container_audit")


def _db(rows_708=None, year=2027):
    """An in-memory stand-in holding just what the guard inspects."""
    eng = sa.create_engine("sqlite://")
    with eng.begin() as c:
        c.execute(sa.text("CREATE TABLE planning_years (id TEXT, year INT, name TEXT)"))
        c.execute(sa.text("CREATE TABLE parade_dates (planning_year_id TEXT, parade_date TEXT)"))
        if rows_708 is not None:
            c.execute(sa.text("INSERT INTO planning_years VALUES (:i, :y, 'x')"),
                      {"i": MIG.TARGET, "y": year})
            for d in rows_708:
                c.execute(sa.text("INSERT INTO parade_dates VALUES (:i, :d)"),
                          {"i": MIG.TARGET, "d": d})
    return eng


def _run(eng, monkeypatch):
    with eng.begin() as conn:
        monkeypatch.setattr(MIG.op, "get_bind", lambda: conn)

        # The double takes ONE argument, matching Alembic's real op.execute.
        # It previously accepted an optional params dict, which the real API
        # does not -- so `op.execute(text, params)` passed here and raised
        # TypeError against a real database. A double more permissive than the
        # API it stands in for hides exactly the bug it should catch.
        monkeypatch.setattr(MIG.op, "execute", lambda stmt: conn.execute(stmt))
        MIG.upgrade()
        return conn.execute(sa.text(
            "SELECT year, name FROM planning_years WHERE id = :i"),
            {"i": MIG.TARGET}).first()


def test_guard_is_a_noop_where_the_row_does_not_exist(monkeypatch):
    """Dev, test, and a fresh deploy must not be affected at all."""
    eng = _db(rows_708=None)
    assert _run(eng, monkeypatch) is None


def test_guard_refuses_when_the_state_differs(monkeypatch):
    """14 dates, not the 15 the decision was made about -- refuse."""
    eng = _db(rows_708=[f"2026-0{(i % 9) + 1}-0{(i % 9) + 1}" for i in range(14)])
    with pytest.raises(RuntimeError, match="Refusing to renumber"):
        _run(eng, monkeypatch)


def test_guard_refuses_when_a_date_is_outside_2026(monkeypatch):
    dates = [f"2026-0{(i % 9) + 1}-0{(i % 9) + 1}" for i in range(14)] + ["2027-01-06"]
    eng = _db(rows_708=dates)
    with pytest.raises(RuntimeError, match="Refusing to renumber"):
        _run(eng, monkeypatch)


def test_guard_renumbers_only_the_exact_decided_state(monkeypatch):
    dates = [f"2026-0{(i % 9) + 1}-0{(i % 9) + 1}" for i in range(15)]
    eng = _db(rows_708=dates)
    assert _run(eng, monkeypatch) == (2026, "2026 Training Year")


def test_audit_flags_a_container_whose_year_disagrees_with_its_dates():
    rows = [
        ("708", "id-708", 2027, "2026 Training Year → 2027", True, 15, "2026", "2026"),
        ("703", "id-703", 2026, "2026 Training Year", True, 12, "2026", "2026"),
        ("704", "id-704", 2027, "2027 Training Year", True, 0, None, None),
    ]
    flagged, total = AUDIT.audit(rows)
    assert total == 3
    assert len(flagged) == 1
    assert "708" in flagged[0] and "year=2027" in flagged[0]


def test_audit_does_not_flag_an_empty_future_container():
    """A materialised year with no dates yet is normal under this model."""
    flagged, _ = AUDIT.audit([("704", "id", 2028, "2028 Training Year", True, 0, None, None)])
    assert flagged == []
