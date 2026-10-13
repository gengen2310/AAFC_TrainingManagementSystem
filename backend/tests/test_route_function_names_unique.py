"""R13: two routes in one router module must not share a Python function name.

The second definition silently rebinds the module attribute (both routes still
work, but anything importing the name gets the wrong one) and FastAPI derives
OpenAPI operation ids from the name. training.py had two
`apply_parade_night_template` functions (PATCH /parade-nights/{id}/template and
POST /parade-night-templates/{tid}/apply/{pnid}).
"""
import importlib
import pkgutil
from collections import Counter

import app.routers as routers_pkg
from fastapi.routing import APIRoute


def _modules():
    for m in pkgutil.iter_modules(routers_pkg.__path__):
        mod = importlib.import_module(f"app.routers.{m.name}")
        router = getattr(mod, "router", None)
        if router is not None:
            yield m.name, router


def test_route_function_names_are_unique_within_each_router_module():
    checked = 0
    dupes = {}
    for name, router in _modules():
        # One function on several paths (backward-compatible aliases, e.g.
        # /parade-dates/... next to /parade-nights/...) is a single endpoint.
        endpoints = {id(r.endpoint): r.endpoint for r in router.routes if isinstance(r, APIRoute)}
        names = Counter(fn.__name__ for fn in endpoints.values())
        checked += sum(names.values())
        clash = sorted(n for n, c in names.items() if c > 1)
        if clash:
            dupes[name] = clash
    assert checked > 300, f"only {checked} endpoint functions enumerated; the check would be vacuous"
    assert dupes == {}, dupes
