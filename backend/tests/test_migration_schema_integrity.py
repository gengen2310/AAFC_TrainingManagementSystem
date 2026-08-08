"""Static check: every model using TimestampMixin must have created_by/updated_by
somewhere in the real Alembic migration chain for its table.

Why this exists: local dev (init_db()) and the whole pytest suite (seed_all's
reset_db()) both build the schema directly from SQLAlchemy metadata, bypassing
Alembic entirely -- so a model can declare a column via TimestampMixin that its
own creation migration never actually adds, and every test in this suite will
still pass, because the metadata-built table always has it. Only a real
Postgres database built purely through `alembic upgrade head` (production, and
any staging environment that was never reseeded via seed_all()) exposes the
drift, as an UndefinedColumn crash on the very first query that touches the
table. This exact bug class has hit production four times now: planning_notices
(fixed v35), curriculum_phases + facilitator_type_tags (fixed v47),
planning_facilitator_leave (fixed v44), and squadron_event_status +
wing_event_curriculum_links + activity_local_hides (fixed v45). This test
performs the same audit that found the v44/v45 gaps, so the fifth instance is
caught here instead of in a live incident.
"""
import os
import re

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(REPO_ROOT, "app", "models")
VERSIONS_DIR = os.path.join(REPO_ROOT, "alembic", "versions")

_REQUIRED_COLUMNS = ("created_by", "updated_by")


def _timestamp_mixin_tables() -> dict[str, str]:
    tables = {}
    for fn in os.listdir(MODELS_DIR):
        if not fn.endswith(".py"):
            continue
        content = open(os.path.join(MODELS_DIR, fn)).read()
        for m in re.finditer(
            r'class (\w+)\(Base,\s*([^)]*)\):\s*\n'
            r'(?:\s*""".*?"""\s*\n)?'
            r'\s*__tablename__\s*=\s*["\'](\w+)["\']',
            content, re.DOTALL,
        ):
            cls, bases, table = m.group(1), m.group(2), m.group(3)
            if "TimestampMixin" in bases:
                tables[table] = cls
    return tables


def _migration_files() -> dict[str, str]:
    files = {}
    for fn in sorted(os.listdir(VERSIONS_DIR)):
        if fn.endswith(".py"):
            files[fn] = open(os.path.join(VERSIONS_DIR, fn)).read()
    return files


def _table_has_column_at_creation(content: str, table: str, column: str) -> tuple[bool, bool]:
    """Returns (found_creation, has_column) for op.create_table(table, ...)."""
    m = re.search(
        r'op\.create_table\(\s*["\']' + re.escape(table) + r'["\'](.*?)\n    \)',
        content, re.DOTALL,
    )
    if not m:
        return False, False
    return True, column in m.group(1)


def test_every_timestampmixin_table_has_created_by_and_updated_by_in_migrations():
    """For every TimestampMixin model, created_by and updated_by must appear
    either in the table's own op.create_table() migration, or be addable by
    finding both the table name and the column name together in some other
    migration file (an ALTER/add_column patch). A model with neither is a real
    gap: a database built purely through the migration chain will crash on the
    first ORM query against that table."""
    tables = _timestamp_mixin_tables()
    assert len(tables) > 40, (
        f"Only found {len(tables)} TimestampMixin models -- the class-detection regex "
        "in this test likely broke and stopped matching; fix the regex before trusting "
        "a 'no gaps found' result from this test."
    )

    files = _migration_files()
    missing: list[str] = []

    for table, cls in sorted(tables.items()):
        creation_file = None
        creation_has = {"created_by": False, "updated_by": False}
        for fn, content in files.items():
            found, _ = _table_has_column_at_creation(content, table, "created_by")
            if found:
                creation_file = fn
                for col in _REQUIRED_COLUMNS:
                    _, has = _table_has_column_at_creation(content, table, col)
                    creation_has[col] = has
                break

        for col in _REQUIRED_COLUMNS:
            if creation_file and creation_has[col]:
                continue
            added_later = any(
                fn != creation_file and table in content and col in content
                for fn, content in files.items()
            )
            if not added_later:
                missing.append(f"{table} ({cls}): missing '{col}' -- not at creation"
                               f"{' (creation migration not found)' if not creation_file else ''}"
                               ", and no other migration adds it")

    assert not missing, (
        "TimestampMixin tables missing created_by/updated_by in the real migration "
        "chain (will crash with UndefinedColumn against a purely-migrated Postgres "
        "database, e.g. production):\n" + "\n".join(missing)
    )
