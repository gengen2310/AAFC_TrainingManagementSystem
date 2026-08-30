"""Tests for scripts/compute_alembic_head.py — the restore-test workflows'
dynamic migration-head detection (replaces a previously hardcoded value that
went stale after every new migration; see DEFECT in docs/beta/11_defect_register.md).
"""
import textwrap

import pytest

from scripts.compute_alembic_head import (
    MultipleHeadsError,
    NoMigrationsError,
    compute_head,
    parse_revisions,
)


def _write_migration(tmp_path, filename: str, revision: str, down_revision: str | None):
    down_literal = "None" if down_revision is None else f"'{down_revision}'"
    (tmp_path / filename).write_text(textwrap.dedent(f"""
        revision = '{revision}'
        down_revision = {down_literal}
    """))


def test_computes_the_real_repo_head():
    """Sanity check against the actual repository migration chain.

    Update this value whenever a new migration is added — that's expected
    maintenance for a direct sanity check, and it fails loudly with a clear
    diff (unlike the workflow-level hardcoding this script replaced, which
    failed silently and was found stale by ~9 migrations in production)."""
    head = compute_head("alembic/versions")
    assert head == "f2c8e51d7a93"


def test_single_linear_chain(tmp_path):
    _write_migration(tmp_path, "a.py", "aaa", None)
    _write_migration(tmp_path, "b.py", "bbb", "aaa")
    _write_migration(tmp_path, "c.py", "ccc", "bbb")
    assert compute_head(str(tmp_path)) == "ccc"


def test_no_migrations_raises(tmp_path):
    with pytest.raises(NoMigrationsError):
        compute_head(str(tmp_path))


def test_branched_chain_raises(tmp_path):
    """Two migrations both claim the same down_revision — a branch, not a chain."""
    _write_migration(tmp_path, "a.py", "aaa", None)
    _write_migration(tmp_path, "b1.py", "bbb1", "aaa")
    _write_migration(tmp_path, "b2.py", "bbb2", "aaa")
    with pytest.raises(MultipleHeadsError) as exc_info:
        compute_head(str(tmp_path))
    assert exc_info.value.heads == {"bbb1", "bbb2"}


def test_parse_revisions_ignores_non_migration_files(tmp_path):
    (tmp_path / "__init__.py").write_text("")
    _write_migration(tmp_path, "a.py", "aaa", None)
    revisions = parse_revisions(str(tmp_path))
    assert revisions == {"aaa": None}
