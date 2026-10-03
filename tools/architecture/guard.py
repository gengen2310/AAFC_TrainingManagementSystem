#!/usr/bin/env python3
"""Architecture regression guard for the AAFC TMS stabilisation phase.

This is a ratchet, not a style checker:
- the connected Main TMS monolith may shrink, but may not silently grow;
- router-local direct role branching may be reduced, but may not increase.

Intentional baseline increases require an explicit baseline edit and PR rationale.
"""
from __future__ import annotations
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = Path(__file__).with_name("architecture-baseline.json")
DIRECT_ROLE_RE = re.compile(r"\bp\.role\s*(?:==|!=|in\b|not\s+in\b)")
NAMED_FUNCTION_RE = re.compile(r"\bfunction\s+[A-Za-z_$][\w$]*\s*\(")


def router_imports(text: str, router_names: set[str], self_name: str) -> set[str]:
    """Sibling router modules imported by this router source, in any form.

    Parsed with ast, so only real import statements count (never strings or
    comments), at any indentation. Covers `from .x import`, `from . import x`,
    `from ..routers(.x) import`, `from app.routers(.x) import`, `import app.routers.x`.
    A regex once used here could not match any import at all (see test_guard.py).
    """
    found: set[str] = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if node.level == 1:
                pkg_names = [mod] if mod else [a.name for a in node.names]
            elif node.level == 2 and (mod == "routers" or mod.startswith("routers.")):
                pkg_names = [mod.split(".", 1)[1]] if "." in mod else [a.name for a in node.names]
            elif node.level == 0 and (mod == "app.routers" or mod.startswith("app.routers.")):
                pkg_names = [mod.split(".")[2]] if mod.count(".") >= 2 else [a.name for a in node.names]
            else:
                continue
            found.update(n.split(".")[0] for n in pkg_names)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.startswith("app.routers."):
                    found.add(a.name.split(".")[2])
    return {n for n in found if n in router_names and n != self_name}

def main() -> int:
    baseline=json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    failures=[]
    cfg=baseline["connected_frontend"]
    path=ROOT/cfg["path"]
    text=path.read_text(encoding="utf-8")
    byte_count=len(text.encode("utf-8"))
    line_count=len(text.splitlines())
    fn_count=len(NAMED_FUNCTION_RE.findall(text))
    if byte_count>cfg["max_bytes"]:
        failures.append(f"{cfg['path']} grew to {byte_count:,} bytes (baseline max {cfg['max_bytes']:,}).")
    if line_count>cfg["max_lines"]:
        failures.append(f"{cfg['path']} grew to {line_count:,} lines (baseline max {cfg['max_lines']:,}).")
    if fn_count>cfg["max_named_function_declarations"]:
        failures.append(
            f"{cfg['path']} now has {fn_count} named functions "
            f"(baseline max {cfg['max_named_function_declarations']}). Extract instead of growing the monolith."
        )

    # Router-to-router coupling is another form of hidden shared state.
    # Existing dependency edges are allowed while we extract them, but new
    # router dependencies must be rejected in favour of permissions/services.
    router_dir=ROOT/"backend"/"app"/"routers"
    router_names={p.stem for p in router_dir.glob("*.py")}
    expected_edges=baseline.get("router_cross_imports", {})
    actual_edges={}
    for file in sorted(router_dir.glob("*.py")):
        rel=file.relative_to(ROOT).as_posix()
        deps=sorted(router_imports(file.read_text(encoding="utf-8"), router_names, file.stem))
        if deps:
            actual_edges[rel]=deps
        allowed=set(expected_edges.get(rel, []))
        unexpected=sorted(set(deps)-allowed)
        if unexpected:
            failures.append(
                f"{rel} added router-to-router import(s): {', '.join(unexpected)}. "
                "Move reusable logic into permissions/services/domain modules instead."
            )

    expected=baseline["router_direct_role_checks"]
    seen=set()
    for file in sorted(router_dir.glob("*.py")):
        rel=file.relative_to(ROOT).as_posix()
        count=len(DIRECT_ROLE_RE.findall(file.read_text(encoding="utf-8")))
        allowed=int(expected.get(rel,0))
        seen.add(rel)
        if count>allowed:
            failures.append(
                f"{rel} has {count} direct p.role checks (baseline max {allowed}). "
                "Put authorization/scope policy in backend/app/permissions.py or a named permission helper."
            )
    missing=sorted(set(expected)-seen)
    if missing:
        failures.append("Baseline lists removed routers: "+", ".join(missing))

    if failures:
        print("ARCHITECTURE GUARD: FAIL")
        for item in failures:
            print(" - "+item)
        return 1

    total=sum(
        len(DIRECT_ROLE_RE.findall((ROOT/rel).read_text(encoding="utf-8")))
        for rel in expected if (ROOT/rel).exists()
    )
    print("ARCHITECTURE GUARD: PASS")
    print(f" - connected frontend: {byte_count:,} bytes, {line_count:,} lines, {fn_count} named functions")
    edge_count=sum(len(v) for v in actual_edges.values())
    print(f" - router-to-router dependency edges: {edge_count} (ratcheted, no increase)")
    print(f" - router-local direct role checks: {total} (ratcheted, no increase)")
    return 0

if __name__=="__main__":
    sys.exit(main())
