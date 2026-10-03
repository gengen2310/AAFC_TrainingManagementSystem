#!/usr/bin/env python3
"""Architecture regression guard for the AAFC TMS stabilisation phase.

This is a ratchet, not a style checker:
- the connected Main TMS monolith may shrink, but may not silently grow;
- router-local direct role branching may be reduced, but may not increase.

Intentional baseline increases require an explicit baseline edit and PR rationale.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = Path(__file__).with_name("architecture-baseline.json")
DIRECT_ROLE_RE = re.compile(r"\bp\.role\s*(?:==|!=|in\b|not\s+in\b)")
NAMED_FUNCTION_RE = re.compile(r"\bfunction\s+[A-Za-z_$][\w$]*\s*\(")

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

    expected=baseline["router_direct_role_checks"]
    router_dir=ROOT/"backend"/"app"/"routers"
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
    print(f" - router-local direct role checks: {total} (ratcheted, no increase)")
    return 0

if __name__=="__main__":
    sys.exit(main())
