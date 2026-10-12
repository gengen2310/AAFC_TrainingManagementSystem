"""Container start-up migration step (replaces a bare `alembic upgrade head`).

D23 (2026-10-12): the entrypoint ran `alembic upgrade head` under `set -e`.
After a release's migrations have run, redeploying the PREVIOUS build failed at
start-up ("Can't locate revision identified by '<newer head>'") and the
container crash-looped, so an application-only rollback was impossible.

- No alembic_version yet, or a revision this code knows: upgrade to head,
  exactly as before. A migration failure exits non-zero and stops start-up.
- A revision this code does NOT know: the database is ahead of the code,
  i.e. this build was deployed as a rollback. Do not migrate (there is
  nothing this code could do), say so loudly, and let start-up continue.
  Whether this build's code is safe against the newer schema is the rollback
  runbook's question (additive migrations are; see MIGRATION_EVIDENCE.md).

Run from backend/: `python -m scripts.migrate_or_hold`.
"""
from __future__ import annotations

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
        print(f"[migrate] DATABASE IS AHEAD OF THIS CODE: revision(s) {unknown} are not in this "
              f"build's migrations (head {script.get_current_head()}). This build was deployed as a "
              "rollback. NOT migrating; starting against the newer schema.", flush=True)
        return 0

    print(f"[migrate] database at {sorted(current) or 'no revision'}; upgrading to "
          f"{script.get_current_head()}", flush=True)
    command.upgrade(cfg, "head")
    return 0


if __name__ == "__main__":
    sys.exit(main())
