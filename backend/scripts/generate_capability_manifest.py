"""Regenerate the current-state capability manifest from live app/model introspection.

Used by the whole-system product hardening program's capability-preservation
discipline (.claude/rules/capability-preservation.md) to snapshot the real
route/model surface before and after major changes -- not a one-off, run it
again whenever a "before" snapshot is needed.

Usage: cd backend && source .venv/bin/activate && python scripts/generate_capability_manifest.py
"""
import json
import subprocess
from pathlib import Path

from app.main import app
from app.database import Base


def collect_routes() -> list[str]:
    routes: set[str] = set()
    for included in app.routes:
        original = getattr(included, "original_router", None)
        if original is None:
            continue
        for route in getattr(original, "routes", []):
            methods = getattr(route, "methods", None)
            path = getattr(route, "path", None)
            if methods and path:
                for method in sorted(set(methods) - {"HEAD", "OPTIONS"}):
                    routes.add(f"{method} {path}")
    return sorted(routes)


def collect_tables() -> list[str]:
    return sorted(Base.metadata.tables.keys())


def git_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()


def main() -> None:
    manifest = {
        "generated_from": "live introspection (app.routes + Base.metadata.tables), not regex",
        "commit": git_sha(),
        "note": (
            "Route/table names are exhaustive (introspected from the running "
            "FastAPI app and SQLAlchemy metadata, not parsed from source text), "
            "so this will not miss a route hidden behind unusual formatting the "
            "way an earlier regex-based pass could. Per-role/per-scope "
            "button-and-action-level frontend detail is still a separate, "
            "manual pass -- not captured here."
        ),
        "total_routes": None,
        "routes": collect_routes(),
        "total_tables": None,
        "tables": collect_tables(),
    }
    manifest["total_routes"] = len(manifest["routes"])
    manifest["total_tables"] = len(manifest["tables"])

    out = Path(__file__).resolve().parents[2] / "docs" / "product-review" / "capability_manifest_current.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {out} -- {manifest['total_routes']} routes, {manifest['total_tables']} tables")


if __name__ == "__main__":
    main()
