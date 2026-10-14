"""The dashboard metric modules are pure read-side computation.

routers/dashboard.py (2,966 lines) was split on 2026-10-05: the 53 metric
helpers moved verbatim into services_dashboard_{common,readiness,delivery,
curriculum,facilitators,adoption}.py; the router keeps HTTP handling, scope
resolution and chart assembly (824 lines). Parity was proven by snapshotting
all 75 dashboard responses (5 roles x 5 routes x 3 windows) before and after:
byte-identical.

This keeps the boundary: no HTTP and no authorization in these modules --
callers resolve scope first -- and no import back into a router.
"""
import ast
import pathlib

import pytest

APP = pathlib.Path(__file__).resolve().parents[1] / "app"
MODULES = sorted(APP.glob("services_dashboard_*.py"))
FORBIDDEN = ("fastapi", "starlette", "permissions", "dependencies", "routers")


def test_the_split_modules_exist():
    assert {m.stem for m in MODULES} == {
        "services_dashboard_common", "services_dashboard_readiness", "services_dashboard_delivery",
        "services_dashboard_curriculum", "services_dashboard_facilitators", "services_dashboard_adoption"}


@pytest.mark.parametrize("path", MODULES, ids=lambda p: p.stem)
def test_no_http_authorization_or_router_imports(path):
    tree = ast.parse(path.read_text())
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
        elif isinstance(node, ast.Import):
            mod = ",".join(a.name for a in node.names)
        else:
            continue
        if any(f in mod.split(".") or mod.startswith(f) for f in FORBIDDEN):
            bad.append(f"line {node.lineno}: {mod}")
    assert not bad, f"{path.name} imports {bad}"
