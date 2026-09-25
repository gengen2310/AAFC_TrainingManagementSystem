#!/usr/bin/env python3
"""Lightweight guardrails for the AAFC TMS visual design contract."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DESIGN = ROOT / "DESIGN.md"
PW_TOKENS = ROOT / "frontend/src/styles/tokens.css"
PW_SRC = ROOT / "frontend/src"
MAIN = ROOT / "connected-frontend/index.html"

REQUIRED_WORDING = (
    "mandatory visual design contract",
    "New or modified UI must comply",
    "explicit review and documented justification",
    "ultimate brand authority",
    "WCAG re-validation",
)
REQUIRED_THEME_CONTEXTS = (
    ':root {',
    'html[data-theme="dark"]',
    'html[data-theme="hc"]',
    "@media (prefers-contrast: more)",
)
REQUIRED_SEMANTIC_TOKENS = (
    "--success-tint-bg",
    "--danger-tint-bg",
    "--warning-tint-bg",
    "--info-tint-bg",
    "--success-on-tint",
    "--danger-on-tint",
    "--warning-on-tint",
    "--info-on-tint",
)


def main() -> int:
    errors: list[str] = []
    design = DESIGN.read_text()
    tokens = PW_TOKENS.read_text()
    main_html = MAIN.read_text()

    errors.extend(
        f"DESIGN.md is missing mandatory wording: {phrase!r}"
        for phrase in REQUIRED_WORDING
        if phrase not in design
    )
    errors.extend(
        f"Planning token file is missing required context: {context!r}"
        for context in REQUIRED_THEME_CONTEXTS
        if context not in tokens
    )
    errors.extend(
        f"Planning token file is missing semantic token: {token}"
        for token in REQUIRED_SEMANTIC_TOKENS
        if token not in tokens
    )

    if re.search(r"html\s*\{[^}]*font-size\s*:\s*\d+px", main_html, re.IGNORECASE | re.DOTALL):
        errors.append("Main TMS must not set a pixel font-size on html")
    if re.search(r"html\s*\{[^}]*font-size\s*:\s*\d+px", tokens, re.IGNORECASE | re.DOTALL):
        errors.append("Planning Workspace must not set a pixel font-size on html")

    unsafe = [
        path
        for path in PW_SRC.rglob("*")
        if path.suffix in {".ts", ".tsx"}
        and "dangerouslySetInnerHTML" in path.read_text()
    ]
    if unsafe:
        errors.append(
            "Review required before using dangerouslySetInnerHTML: "
            + ", ".join(str(path.relative_to(ROOT)) for path in unsafe)
        )

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("OK — DESIGN.md contract and frontend guardrails are present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
