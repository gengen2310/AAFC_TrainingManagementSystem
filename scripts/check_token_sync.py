#!/usr/bin/env python3
"""
check_token_sync.py — verify shared/tokens.css variables are present
in connected-frontend/index.html between the sync markers.

Usage:
    python scripts/check_token_sync.py

Exit code 0 = all shared token names found in connected-frontend.
Exit code 1 = one or more names missing.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent

SHARED = ROOT / "shared" / "tokens.css"
CF = ROOT / "connected-frontend" / "index.html"

SYNC_START = "/* shared/tokens.css sync begin"
SYNC_END = "/* shared/tokens.css sync end */"

def extract_var_names(css: str) -> set[str]:
    return set(re.findall(r"--[\w-]+(?=\s*:)", css))

def extract_cf_sync_block(html: str) -> str:
    i = html.find(SYNC_START)
    j = html.find(SYNC_END, i)
    if i == -1 or j == -1:
        sys.exit("ERROR: sync markers not found in connected-frontend/index.html")
    return html[i:j + len(SYNC_END)]

def main() -> None:
    shared_css = SHARED.read_text()
    cf_html = CF.read_text()

    shared_names = extract_var_names(shared_css)
    cf_block = extract_cf_sync_block(cf_html)
    cf_names = extract_var_names(cf_block)

    missing = shared_names - cf_names
    extra = cf_names - shared_names

    ok = True
    if missing:
        print("MISSING from connected-frontend (add to sync block):")
        for n in sorted(missing):
            print(f"  {n}")
        ok = False
    if extra:
        print("EXTRA in connected-frontend sync block (not in shared source):")
        for n in sorted(extra):
            print(f"  {n}  (ok if CF-only token; move to shared if both frontends need it)")

    if ok:
        print(f"OK — all {len(shared_names)} shared token names present in connected-frontend sync block.")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
