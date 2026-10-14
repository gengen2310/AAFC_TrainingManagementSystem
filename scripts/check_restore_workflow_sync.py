#!/usr/bin/env python3
"""
check_restore_workflow_sync.py -- keep the staging restore test identical to
the production one, apart from a declared list of environment differences.

Why: the two workflows were hand-maintained copies. Production gained four
fixes (restore with --clean, revision-in-graph check instead of an exact-head
check, an upgrade rehearsal on the restored data, ORM-derived table check and
authenticated API reads) that staging never received, so a staging restore
still failed on the old exact-head check whenever main had a migration
staging had not deployed.

The staging file keeps its own header comment (everything before the first
top-level `name:` line). Everything after it must equal the production body
with SUBSTITUTIONS applied. Each substitution must match exactly once, so a
change to the production file that invalidates one fails loudly here instead
of drifting silently.

Usage:
    python scripts/check_restore_workflow_sync.py           # check (CI)
    python scripts/check_restore_workflow_sync.py --write   # regenerate staging body

Exit code 0 = in sync. Exit code 1 = drift or a stale substitution.
"""
import difflib
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PROD = ROOT / ".github" / "workflows" / "test-restore-postgresql.yml"
STAGING = ROOT / ".github" / "workflows" / "test-restore-postgresql-staging.yml"

SUBSTITUTIONS = [
    ("name: PostgreSQL Restore Test — Production — Weekly\n",
     "name: PostgreSQL Restore Test — Staging — Manual\n"),
    # Staging is manual-only; production also runs weekly.
    ("on:\n  schedule:\n    - cron: '0 19 * * 0'   # Monday 03:00 AWST (UTC+8) = Sunday 19:00 UTC\n  workflow_dispatch:\n",
     "on:\n  workflow_dispatch:\n"),
    ("group: postgresql-restore-test-production\n",
     "group: postgresql-restore-test-staging\n"),
    ("    name: Decrypt, restore, verify\n",
     "    name: Decrypt, restore, verify (staging)\n"),
    ('startswith("postgresql-production-backup-")',
     'startswith("postgresql-staging-backup-")'),
    ("No production backup artifacts found",
     "No staging backup artifacts found"),
    ("Run the backup workflow first: Actions → PostgreSQL Backup — Production — Daily → Run workflow",
     "Run the backup workflow first: Actions → PostgreSQL Backup — Staging — Manual → Run workflow"),
    ('print(f"Restored (production) revision: {rev}")',
     'print(f"Restored (staging) revision:    {rev}")'),
    ("- name: Rehearse production upgrade on restored data (alembic upgrade head)",
     "- name: Rehearse staging upgrade on restored data (alembic upgrade head)"),
    ("authenticated reads succeeded against restored production data.",
     "authenticated reads succeeded against restored staging data."),
    ('echo "Restore test SKIPPED — no backup artifact available."',
     'echo "Restore test SKIPPED — no staging backup artifact available."'),
    ('echo "  Actions → PostgreSQL Backup — Production — Daily → Run workflow"',
     'echo "  Actions → PostgreSQL Backup — Staging — Manual → Run workflow"'),
]


def split_header(text: str) -> tuple[str, str]:
    i = text.find("\nname:")
    if i == -1:
        raise SystemExit("no top-level `name:` line")
    return text[: i + 1], text[i + 1 :]


def expected_staging_body(prod_text: str) -> str:
    _, body = split_header(prod_text)
    for old, new in SUBSTITUTIONS:
        n = body.count(old)
        if n != 1:
            raise SystemExit(f"stale substitution (matches {n} times, expected 1): {old!r}")
        body = body.replace(old, new)
    return body


def main(argv: list[str]) -> int:
    want = expected_staging_body(PROD.read_text(encoding="utf-8"))
    header, have = split_header(STAGING.read_text(encoding="utf-8"))
    if "--write" in argv:
        STAGING.write_text(header + want, encoding="utf-8")
        print(f"wrote {STAGING.relative_to(ROOT)}")
        return 0
    if have == want:
        print("staging restore workflow is in sync with production.")
        return 0
    sys.stdout.writelines(difflib.unified_diff(
        want.splitlines(keepends=True), have.splitlines(keepends=True),
        "expected (from production)", "test-restore-postgresql-staging.yml", n=1))
    print("\nFAIL: staging restore workflow has drifted from production. "
          "Fix production, then run: python scripts/check_restore_workflow_sync.py --write")
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
