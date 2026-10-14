"""The training/planning service modules are domain helpers, not HTTP code.

Stabilisation Phase 3 (C5, 2026-10-11) moved 53 module-level helpers verbatim
out of routers/training.py (8,088 -> 7,542 lines) and routers/planning.py
(6,280 -> 5,746 lines) into services_training_{conflicts,serialisers,
reference_tags,activities,imports}.py and services_planning_{conflicts,
serialisers,io}.py. Parity: every GET route on both routers, as eight seeded
principals (656 responses), is unchanged -- see
test_training_planning_extraction_parity.py.

This keeps the boundary the dashboard split set (test_dashboard_services_
boundary.py): no HTTP framework, no authorization policy and no import back
into a router -- the dependency direction is routers -> services -> models.
Helpers that answer with an HTTPException or decide scope stay in the router.
"""
import ast
import pathlib

import pytest

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
MODULES = sorted([*APP.glob("services_training_*.py"), *APP.glob("services_planning_*.py")])
FORBIDDEN = ("fastapi", "starlette", "permissions", "dependencies", "routers")


def test_the_split_modules_exist():
    assert {m.stem for m in MODULES} == {
        "services_training_conflicts", "services_training_serialisers",
        "services_training_reference_tags", "services_training_activities",
        "services_training_imports",
        "services_planning_conflicts", "services_planning_serialisers", "services_planning_io"}


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.stem)
def test_no_http_authorization_or_router_imports(path):
    tree = ast.parse(path.read_text())
    bad = []
    for node in ast.walk(tree):  # walks function-local imports too
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
        elif isinstance(node, ast.Import):
            mod = ",".join(a.name for a in node.names)
        else:
            continue
        if any(f in mod.split(".") or mod.startswith(f) for f in FORBIDDEN):
            bad.append(f"line {node.lineno}: {mod}")
    assert not bad, f"{path.name} imports {bad}"


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.stem)
def test_no_http_exception_raised(path):
    """A helper that answers with an HTTP status belongs in the router."""
    names = {n.id for n in ast.walk(ast.parse(path.read_text())) if isinstance(n, ast.Name)}
    assert "HTTPException" not in names
