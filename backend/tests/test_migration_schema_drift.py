"""Regression test for a recurring class of defect: a table created by a
migration is missing a column its SQLAlchemy model declares (most often
TimestampMixin's `updated_by`, added to the mixin after some tables' create
migrations were already written and copy-pasted from each other).

This has happened at least 4 times across this project's history:
  - v24 patched it for the original planning tables
  - v40 patched it for subject_area_tags (v39's create migration missed it)
  - v47 patched it for curriculum_phases (v42) and facilitator_type_tags (v45)

Every instance was invisible to the full backend test suite because local/CI
tests build their schema directly from the SQLAlchemy models
(`Base.metadata.create_all()` via `seed_all.py`'s `reset_db()`), bypassing
Alembic entirely -- so a migration that forgets a column never gets caught
until a real Postgres environment (staging/production) runs the actual
migration chain and someone calls the affected endpoint. Confirmed live on
staging via GET /api/curriculum/phases and GET /api/facilitator-type-tags,
both 500ing with psycopg2.errors.UndefinedColumn -- and cross-checked against
a full `information_schema.columns` audit of every table on staging Postgres
(59 tables; only these two, plus one pre-existing-by-design non-issue, showed
any drift), which this test's static approach is calibrated against.

Parses every migration file's AST (not regex -- migration formatting varies
enough that a regex scan produced false positives against tables already
confirmed correct on live Postgres) looking for op.create_table(...),
op.add_column(...), and `with op.batch_alter_table(...) as batch_op:` /
batch_op.add_column(...) calls, and unions every column name found per table
across the whole migration history (order doesn't matter -- only whether some
migration adds each column, matching how Alembic actually accumulates state).
"""
import ast
from pathlib import Path

import pytest

from app.database import TimestampMixin
from app import models
import inspect

_VERSIONS_DIR = Path(__file__).parent.parent / "alembic" / "versions"

# TimestampMixin's own columns -- every model using it must have all of these
# somewhere in its table's cumulative migration history.
_MIXIN_COLUMNS = {"created_at", "updated_at", "created_by", "updated_by"}


def _timestamp_mixin_tables() -> dict[str, str]:
    """tablename -> model class name, for every model using TimestampMixin."""
    out = {}
    for name in dir(models):
        obj = getattr(models, name)
        if inspect.isclass(obj) and issubclass(obj, TimestampMixin) and hasattr(obj, "__tablename__"):
            out[obj.__tablename__] = name
    return out


def _const_str(node: ast.AST) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _column_name_from_call(call: ast.Call) -> str | None:
    """sa.Column('name', ...) -> 'name'."""
    if call.args:
        return _const_str(call.args[0])
    return None


def _module_level_string_lists(tree: ast.Module) -> dict[str, list[str]]:
    """`_NEED_BOTH = ['a', 'b', 'c']` at module level -> {'_NEED_BOTH': ['a','b','c']}
    -- resolves the exact pattern v24 uses (`for table in _NEED_BOTH:
    op.add_column(table, ...)`) so a loop-driven multi-table patch is
    attributed to every table it actually touches, not silently dropped."""
    out: dict[str, list[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.List):
            names = [_const_str(e) for e in node.value.elts]
            if all(names) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                out[node.targets[0].id] = names  # type: ignore[arg-type]
    return out


def _for_loop_add_column_tables(tree: ast.Module, string_lists: dict[str, list[str]]) -> dict[str, set[str]]:
    """`for table in _NEED_BOTH: op.add_column(table, sa.Column('x', ...))`
    -- resolve the loop variable to every table name in the iterated list."""
    per_table: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.For) or not isinstance(node.target, ast.Name):
            continue
        loop_var = node.target.id
        tables: list[str] | None = None
        if isinstance(node.iter, ast.Name) and node.iter.id in string_lists:
            tables = string_lists[node.iter.id]
        elif isinstance(node.iter, ast.List):
            names = [_const_str(e) for e in node.iter.elts]
            if all(names):
                tables = names  # type: ignore[assignment]
        if not tables:
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute) \
                    and inner.func.attr == "add_column" and len(inner.args) >= 2 \
                    and isinstance(inner.args[0], ast.Name) and inner.args[0].id == loop_var:
                col_call = inner.args[1]
                if isinstance(col_call, ast.Call) and isinstance(col_call.func, ast.Attribute) \
                        and col_call.func.attr == "Column":
                    name = _column_name_from_call(col_call)
                    if name:
                        for t in tables:
                            per_table.setdefault(t, set()).add(name)
    return per_table


# Confirmed correct on live staging Postgres via a direct information_schema.columns
# audit (2026-08-05, this gate's own verification -- see docs/beta/32) but not
# attributable by this static scan to any migration in the current versions/
# directory. Most likely explanation: a manual ALTER TABLE was applied directly
# to the database outside the migration system at some point (a process gap
# worth flagging, not a live defect) -- or a migration file was later removed/
# squashed after being applied. Either way, re-verify with the same live query
# before trusting this list again if the migration history changes.
_CONFIRMED_FINE_NOT_STATICALLY_TRACEABLE = {
    "activity_local_hides",
    "squadron_event_status",
    "wing_event_curriculum_links",
    "planning_facilitator_leave",
}


def _columns_ever_added_per_table() -> dict[str, set[str]]:
    per_table: dict[str, set[str]] = {}

    for path in sorted(_VERSIONS_DIR.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except SyntaxError:
            continue

        string_lists = _module_level_string_lists(tree)
        for table, cols in _for_loop_add_column_tables(tree, string_lists).items():
            per_table.setdefault(table, set()).update(cols)

        for node in ast.walk(tree):
            # op.create_table('name', sa.Column(...), sa.Column(...), ...)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "create_table" and node.args:
                table = _const_str(node.args[0])
                if table is None:
                    continue
                cols = set()
                for arg in node.args[1:]:
                    if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute) \
                            and arg.func.attr == "Column":
                        name = _column_name_from_call(arg)
                        if name:
                            cols.add(name)
                per_table.setdefault(table, set()).update(cols)

            # Bare op.add_column('table', sa.Column('name', ...))
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "add_column" and len(node.args) >= 2:
                table = _const_str(node.args[0])
                col_call = node.args[1]
                if table and isinstance(col_call, ast.Call) and isinstance(col_call.func, ast.Attribute) \
                        and col_call.func.attr == "Column":
                    name = _column_name_from_call(col_call)
                    if name:
                        per_table.setdefault(table, set()).add(name)

            # with op.batch_alter_table('table') as batch_op: ... batch_op.add_column(sa.Column('name', ...))
            elif isinstance(node, ast.With):
                table = None
                for item in node.items:
                    call = item.context_expr
                    if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) \
                            and call.func.attr == "batch_alter_table" and call.args:
                        table = _const_str(call.args[0])
                if table:
                    for inner in ast.walk(node):
                        if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute) \
                                and inner.func.attr == "add_column" and inner.args:
                            col_call = inner.args[0]
                            if isinstance(col_call, ast.Call) and isinstance(col_call.func, ast.Attribute) \
                                    and col_call.func.attr == "Column":
                                name = _column_name_from_call(col_call)
                                if name:
                                    per_table.setdefault(table, set()).add(name)

    return per_table


@pytest.mark.parametrize(
    "tablename,model_name",
    [(t, m) for t, m in sorted(_timestamp_mixin_tables().items())
     if t not in _CONFIRMED_FINE_NOT_STATICALLY_TRACEABLE],
)
def test_timestamp_mixin_columns_present_in_migration_history(tablename, model_name):
    added = _columns_ever_added_per_table()
    cols = added.get(tablename)
    assert cols is not None, (
        f"{model_name} ({tablename}) uses TimestampMixin but no migration's "
        f"create_table/add_column mentions this table at all -- either the "
        f"table was never migrated, or this scan's AST patterns need updating."
    )
    missing = _MIXIN_COLUMNS - cols
    assert not missing, (
        f"{model_name} ({tablename}): migration history never adds column(s) "
        f"{sorted(missing)} that TimestampMixin declares. This is the exact "
        f"defect class fixed by v24/v40/v47 -- add a migration with "
        f"batch_alter_table('{tablename}') adding the missing column(s), "
        f"nullable=True (existing rows have no historical value to backfill)."
    )
