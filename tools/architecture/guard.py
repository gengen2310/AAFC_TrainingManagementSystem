#!/usr/bin/env python3
"""Architecture regression guard for the AAFC TMS stabilisation phase.

This is intentionally a ratchet, not a style checker:
- the connected frontend monolith may shrink, but may not silently grow;
- router-local direct role branching may be reduced, but may not increase.

If an intentional product/security change genuinely requires raising a baseline,
update architecture-baseline.json in the same PR and explain why in the PR body.
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


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def main() -> int:
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    failures: list[str] = []

    # 1) Connected frontend monolith ratchet.
    frontend_cfg = baseline["connected_frontend"]
    frontend_path = ROOT / frontend_cfg["path"]
    text = frontend_path.read_text(encoding="utf-8")
    byte_count = len(text.encode("utf-8"))
    line_count = len(text.splitlines())
    fn_count = len(NAMED_FUNCTION_RE.findall(text))

    if byte_count > frontend_cfg["max_bytes"]:
        fail(
            f"{frontend_cfg['path']} grew to {byte_count:,} bytes "
            f"(baseline max {frontend_cfg['max_bytes']:,}). "
            "During stabilisation the monolith must shrink or stay flat.",
            failures,
        )
    if line_count > frontend_cfg["max_lines"]:
        fail(
            f"{frontend_cfg['path']} grew to {line_count:,} lines "
            f"(baseline max {frontend_cfg['max_lines']:,}).",
            failures,
        )
    if fn_count > frontend_cfg["max_named_function_declarations"]:
        fail(
            f"{frontend_cfg['path']} now has {fn_count} named function declarations "
            f"(baseline max {frontend_cfg['max_named_function_declarations']}). "
            "Put new behaviour behind an extracted/module boundary instead.",
            failures,
        )

    # 2) Backend permission-source-of-truth ratchet.
    # permissions.py is the authority. Routers may retain legacy role branching
    # for now, but the count cannot increase. New routers therefore start at 0.
    router_dir = ROOT / "backend" / "app" / "routers"
    expected = baseline["router_direct_role_checks"]
    seen: set[str] = set()

    for path in sorted(router_dir.glob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        source = path.read_text(encoding="utf-8")
        count = len(DIRECT_ROLE_RE.findall(source))
        allowed = int(expected.get(rel, 0))
        seen.add(rel)
        if count > allowed:
            fail(
                f"{rel} has {count} direct p.role checks (baseline max {allowed}). "
                "Move the authorization/scoping rule into backend/app/permissions.py "
                "or a named permission helper instead of adding router-local policy.",
                failures,
            )

    missing = sorted(set(expected) - seen)
    if missing:
        fail(
            "Baseline lists router files that no longer exist: " + ", ".join(missing) + ". "
            "Remove their entries from the baseline as part of the same refactor.",
            failures,
        )

    if failures:
        print("ARCHITECTURE GUARD: FAIL")
        for item in failures:
            print(f" - {item}")
        return 1

    total_role_checks = sum(
        len(DIRECT_ROLE_RE.findall((ROOT / rel).read_text(encoding="utf-8")))
        for rel in expected
        if (ROOT / rel).exists()
    )
    print("ARCHITECTURE GUARD: PASS")
    print(
        f" - connected frontend: {byte_count:,} bytes, {line_count:,} lines, "
        f"{fn_count} named functions"
    )
    print(f" - router-local direct role checks: {total_role_checks} (ratcheted, no increase)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
