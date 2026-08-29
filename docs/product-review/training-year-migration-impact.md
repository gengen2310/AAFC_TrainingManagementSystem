# Training Year — migration impact

Date: 2026-08-29

Two migrations ship with the context model. One of them caused a staging
outage before it was corrected; that is documented here in full, because the
lesson is worth more than the fix.

## 1. `v57` — `a7c4e91b2f60` — `wings.timezone`

Adds a nullable `String(64)` column and backfills **every existing wing** to
`Australia/Perth`, then verifies its own work:

```sql
UPDATE wings SET timezone = 'Australia/Perth' WHERE timezone IS NULL;
SELECT count(*) FROM wings WHERE timezone IS NULL;   -- must be 0, else raise
```

**Why `WHERE timezone IS NULL` and not `WHERE code = '7WG'`.** The first draft
backfilled 7WG only, on the reasoning that production has exactly one wing.
True of production, false of staging: staging holds **15** wings, ten of them
with 12 squadrons each. `wing_timezone()` raises on NULL by design, and that
raise reaches every endpoint resolving a year — `setup/status`, the year
listing, `year-context`, and every year-scoped write. A 7WG-only backfill would
have 500'd roughly 120 squadrons the moment the deploy completed.

Caught by querying staging before deploying rather than by reading the diff.

**Not silent defaulting.** The fail-loudly rule governs *runtime date
arithmetic*, where a wrong zone is invisible. This is a one-time decision for
rows that predate the column and have no other source of truth: the value is
written to the row, visible and editable, and a wing not actually in Perth can
be corrected. There is deliberately **no** `server_default`, so a new wing still
gets its zone explicitly from `timezone_for_new_wing()`.

Reversible: `downgrade()` drops the column.

## 2. `v58` — `d5f81a3c9e27` — renumber 708

708's only live container is numbered 2027 while holding all 15 of its parade
dates in 2026. The dates are authoritative, so the container is renumbered.
**This is the only place a year integer changes, and it changes because a human
decided it on 2026-08-28 — never by inference.**

The guard refuses unless the row is in exactly the state that decision was made
about:

```
year == 2027  AND  dates == 15  AND  dates outside 2026 == 0
```

Anything else raises. A missing row returns silently, so dev, test and fresh
deploys are untouched.

| environment | effect |
|---|---|
| local / test | no-op — row absent |
| **staging** | **no-op — row absent** (`row_present = 0`, verified 2026-08-28) |
| production | performs the renumber on the next production deploy |

**Still owed before production:** running
`tools/data-quality/year_container_audit.py` against a restored production dump
and rehearsing this migration forward and back on a disposable PostgreSQL
(plan Task 8, steps 2 and 4). Not done — §58 forbids altering production data.
Because staging's row is absent, staging has **not** exercised this migration.

## 3. The staging outage, 2026-08-28

Worth recording in full.

**What happened.** `main` briefly carried a competing chain
(`fa57bc9d0e1a → b3e9c1f7a2d4 → e3693a06b1bd`) from the superseded model, and
that chain had already been deployed to staging — the database was stamped at
`e3693a06b1bd`. Reverting it and deploying the context model removed those
files. The container could not locate the revision its own database claimed to
be at:

```
ERROR [alembic.util.messaging] Can't locate revision identified by 'e3693a06b1bd'
```

It crash-looped. The deploy script caught it at backend gate 3 and hard-failed,
exactly as designed.

**Root cause.** The data preconditions were checked carefully — the 708 row,
duplicate active years, wing timezones — and `alembic_version` was not.
**Merging a branch that deletes already-applied migrations is a rollback, not a
fast-forward,** and the deployed schema revision is the single fact that says
so.

**Recovery.** The three superseded migrations' own `downgrade()` bodies were
replayed as SQL through the `railway connect Postgres` proxy — rehearsed inside
a transaction ending in `ROLLBACK`, checked, then re-run with `COMMIT` — and
`alembic_version` re-stamped to `e2f3a4b5c6d7`, the revision both chains share.
The crash-looping container then migrated cleanly onto the context chain by
itself on its next restart.

**The check that now comes first:**

```sql
SELECT version_num FROM alembic_version;
```

against every environment being deployed to, before merging anything that
removes a migration file.

## 4. Both chains claimed the same parent

`fa57bc9d0e1a` and `a7c4e91b2f60` both declared
`down_revision = "e2f3a4b5c6d7"`. Merged naively that is two Alembic heads and
`alembic upgrade head` fails outright — before any of the above could even be
reached. The revert collapsed it back to a single chain:

```
e2f3a4b5c6d7 → a7c4e91b2f60 (v57) → d5f81a3c9e27 (v58, head)
```

`scripts/deploy-staging.sh`'s `REQUIRED_ALEMBIC_HEAD` had to move with it; it
had been left pointing at `e3693a06b1bd`, a revision the revert deletes.
