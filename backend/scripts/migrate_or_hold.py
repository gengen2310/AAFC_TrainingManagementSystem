"""Container start-up migration step (replaces a bare `alembic upgrade head`).

D23 (2026-10-12): the entrypoint ran `alembic upgrade head` under `set -e`.
After a release's migrations have run, redeploying the PREVIOUS build failed at
start-up ("Can't locate revision identified by '<newer head>'") and the
container crash-looped, so an application-only rollback was impossible.

- No alembic_version yet, or a revision this code knows: upgrade to head,
  exactly as before. A migration failure exits non-zero and stops start-up.
- A revision this code does NOT know: either the database is ahead of the
  code (this build was deployed as a rollback) or it is on a diverged branch.
  Only the operator knows which, so holding requires ALLOW_SCHEMA_AHEAD=1 on
  the service (set for the rollback deploy, removed afterwards). With it: do
  not migrate, say so loudly, start. Without it: fail start-up, as before --
  starting a diverged build against a schema missing its own migrations would
  be worse than not starting (security review, 2026-10-12).

Run from backend/: `python -m scripts.migrate_or_hold`.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine

BACKEND = Path(__file__).resolve().parents[1]


def main() -> int:
    from app.config import normalize_database_url, settings

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    engine = create_engine(normalize_database_url(settings.DATABASE_URL))
    try:
        with engine.connect() as conn:
            current = set(MigrationContext.configure(conn).get_current_heads())
    finally:
        engine.dispose()

    known = {rev.revision for rev in script.walk_revisions()}
    unknown = sorted(current - known)
    if unknown:
        if os.environ.get("ALLOW_SCHEMA_AHEAD") != "1":
            print(f"[migrate] REFUSING TO START: database revision(s) {unknown} are not in this build's "
                  f"migrations (head {script.get_current_head()}). If this is a deliberate rollback to an "
                  "older build, set ALLOW_SCHEMA_AHEAD=1 on this service; otherwise this build is on a "
                  "diverged branch.", flush=True)
            return 1
        print(f"[migrate] DATABASE IS AHEAD OF THIS CODE: revision(s) {unknown} are not in this "
              f"build's migrations (head {script.get_current_head()}). ALLOW_SCHEMA_AHEAD=1: rollback "
              "declared. NOT migrating; starting against the newer schema.", flush=True)
        return 0

    print(f"[migrate] database at {sorted(current) or 'no revision'}; upgrading to "
          f"{script.get_current_head()}", flush=True)
    command.upgrade(cfg, "head")
    return 0


if __name__ == "__main__":
    sys.exit(main())
