"""v57 must not leave any wing without a timezone.

get_wing_timezone raises on NULL by design. That raise reaches every endpoint
resolving a training year, so a wing left NULL is a 500 for all of its
squadrons. Production has one wing; staging has 15, ten of them with 12
squadrons each, which is why "seed 7WG" was not enough.
"""
import pathlib

import sqlalchemy as sa

_MIG = (pathlib.Path(__file__).resolve().parents[1]
        / "alembic/versions/fa57bc9d0e1a_v57_wing_timezone.py")


def _backfilled(codes):
    """The migration's own two statements, run against a stand-in table."""
    eng = sa.create_engine("sqlite://")
    with eng.begin() as c:
        c.execute(sa.text("CREATE TABLE wings (id TEXT, code TEXT, timezone TEXT)"))
        for i, code in enumerate(codes):
            c.execute(sa.text("INSERT INTO wings VALUES (:i, :c, NULL)"),
                      {"i": f"w{i}", "c": code})
        c.execute(sa.text(
            "UPDATE wings SET timezone = 'Australia/Perth' WHERE timezone IS NULL"))
        left = c.execute(
            sa.text("SELECT count(*) FROM wings WHERE timezone IS NULL")).scalar()
        rows = c.execute(sa.text("SELECT code, timezone FROM wings ORDER BY code")).fetchall()
    return rows, left


def test_every_wing_is_backfilled_not_only_7wg():
    codes = ["7WG", "9WG", "LVW1", "LVW10", "QA1WG", "TW1", "ZZW1"]
    rows, left = _backfilled(codes)
    assert left == 0
    assert len(rows) == len(codes)
    assert all(tz == "Australia/Perth" for _, tz in rows), rows


def test_the_migration_keys_off_null_not_off_a_wing_code():
    """Reads the migration file itself. A paraphrase in a test would not have
    caught the original defect, because the paraphrase was never wrong."""
    src = _MIG.read_text()
    assert "WHERE timezone IS NULL" in src
    assert "WHERE code = '7WG'" not in src


def test_the_migration_verifies_its_own_backfill():
    src = _MIG.read_text()
    assert "SELECT count(*) FROM wings WHERE timezone IS NULL" in src
    assert "raise RuntimeError" in src
