# Migration pre-flight — staging and production, 2026-08-23

Production is **23 migrations** behind this branch (`f6a7b8c9d0e1` → `d1e4f8a03b27`);
staging is 4 behind (`0ae75ee5aed6`). Both were audited read-only with
`tools/data-quality/migration_preflight.py`.

**Conclusion: duplicate active planning years are the only blocker in either
environment.** Everything else in the chain is a no-op against real data.

## Why this needed asking

Of the 23 pending migrations, 8 do more than create tables. Three of those are
genuinely dangerous on paper:

| Revision | What it does |
|---|---|
| `5cf6d7e8f9a0` | drops `custom_phases` — docstring calls it "dead" |
| `9997f6527ef4` | drops `planning_locations` and `scheduled_sessions` — "inert" |
| `b4c5d6e7f8a9` | `DELETE FROM session_audience WHERE id NOT IN (SELECT MIN(id) …)` |

"Dead" and "inert" were written about the development database. Whether they hold
for production is a question about production.

An earlier version of this analysis flagged 20 of 23 migrations as destructive.
That was wrong: it matched `op.drop_table` inside every `downgrade()`, which every
migration has. The classification now parses `upgrade()` only.

## Results

| Check | Production | Staging |
|---|---|---|
| alembic revision | `f6a7b8c9d0e1` | `0ae75ee5aed6` |
| `custom_phases` rows dropped | 0 (table empty) | table already absent |
| `planning_locations` rows dropped | 0 (table empty) | already absent |
| `scheduled_sessions` rows dropped | 0 (table empty) | already absent |
| `session_audience` rows deleted by the dedupe | table absent — created later in the same chain, so empty when the DELETE runs | 0 of 47 |
| `parade_dates` orphan links nulled | 0 of 146 | 0 of 63 |
| `planning_conflicts` orphans nulled | 0 of 24 | 0 of 9 |
| **duplicate active planning-year groups** | **4 — blocks** | **1 — blocks** |

The three "dead"/"inert" tables really are empty in production, so those drops
destroy nothing. The `session_audience` dedupe is harmless because the table does
not exist in production yet — it is created earlier in the same chain and is empty
when the DELETE runs. Both orphan cleanups match zero rows.

## What to do

1. Resolve the duplicate active planning years using
   `docs/remediation/rem134_resolve_production.sql` and `…_staging.sql`. These
   archive, never delete. Production resolves 3 of 4 groups automatically; the
   708 group and all of staging need a human to choose.
2. Re-run this pre-flight immediately before deploying. The table above is a
   point-in-time snapshot; a clean result today says nothing about a database
   that has been written to since.
3. Deploy staging first. It is only 4 migrations behind and exercises the same
   chain tail.

## Not covered

Migration *correctness* against production data beyond the checks above — for
instance whether `update_block_type_taxonomy` (`821e2a4bc3e6`) maps every
`block_type` value present in production. It rewrites `timing_blocks` rows by id
and was written against the development dataset.
