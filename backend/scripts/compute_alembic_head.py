"""Compute the single Alembic head from a directory of migration files.

Used by the backup restore-test workflows (see
.github/workflows/test-restore-postgresql-production.yml and
test-restore-postgresql-staging.yml) to verify a restored database's schema
revision against the *actual* current migration chain, instead of a
hardcoded value that goes stale after every new migration.

Deliberately does not import Alembic/SQLAlchemy — it only needs to parse the
`revision`/`down_revision` assignments out of each versions/*.py file, so it
runs in a bare CI container with nothing but the standard library installed.
"""
import glob
import re
import sys


class MultipleHeadsError(Exception):
    def __init__(self, heads: set[str]):
        self.heads = heads
        super().__init__(f"Expected exactly one Alembic head, found {len(heads)}: {sorted(heads)}")


class NoMigrationsError(Exception):
    pass


def parse_revisions(versions_dir: str) -> dict[str, str | None]:
    """Return {revision: down_revision} for every migration file in versions_dir."""
    revisions: dict[str, str | None] = {}
    for path in glob.glob(f"{versions_dir}/*.py"):
        text = open(path).read()
        rev_m = re.search(r"^revision\s*=\s*['\"]([^'\"]+)['\"]", text, re.M)
        down_m = re.search(r"^down_revision\s*=\s*(.+)$", text, re.M)
        if not rev_m:
            continue
        rev = rev_m.group(1)
        down_raw = down_m.group(1).strip() if down_m else "None"
        down = None if down_raw == "None" else re.sub(r"^['\"]|['\"]$", "", down_raw)
        revisions[rev] = down
    return revisions


def compute_head(versions_dir: str) -> str:
    """Return the single Alembic head revision id.

    Raises NoMigrationsError if no migration files are found, or
    MultipleHeadsError if the chain has branched (more than one revision
    that nothing else points to as its down_revision).
    """
    revisions = parse_revisions(versions_dir)
    if not revisions:
        raise NoMigrationsError(f"No Alembic migration files found under {versions_dir}")

    all_revs = set(revisions.keys())
    referenced = {v for v in revisions.values() if v}
    heads = all_revs - referenced

    if len(heads) != 1:
        raise MultipleHeadsError(heads)

    return heads.pop()


if __name__ == "__main__":
    versions_dir = sys.argv[1] if len(sys.argv) > 1 else "alembic/versions"
    try:
        head = compute_head(versions_dir)
    except (NoMigrationsError, MultipleHeadsError) as e:
        print(f"::error::{e}", file=sys.stderr)
        sys.exit(1)
    print(head)
