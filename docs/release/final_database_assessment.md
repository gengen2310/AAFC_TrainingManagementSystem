# Final Database & Migration Assessment (Stage 8)

Tested against a real local PostgreSQL 18 instance (matching production's
`ghcr.io/railwayapp-templates/postgres-ssl:18` image — the same version GAP-16 was
originally about, so version-matching mattered here, not just "some Postgres"), not
SQLite. Backend test suite itself remains SQLite-only by design (`conftest.py`
hardcodes it) — this stage exists specifically to cover what that suite structurally
cannot.

## Migration chain — clean, both directions

- **Upgrade from blank database**: all 34 migrations ran cleanly,
  `` → `z1a2b3c4d5e6` (current head), zero errors. Resulting schema: 58 tables
  (57 model classes + `alembic_version`, reconciling exactly with Stage 1's model
  count).
- **Downgrade, full chain**: `alembic downgrade base` walked all 34 migrations
  in reverse, zero errors — every migration in this repo has a working `downgrade()`,
  not just an `upgrade()`. Confirmed by running it, not by reading the migration
  files and assuming symmetry.
- **Round-trip**: down to base, back up to head — final state verified identical
  (`alembic current` → `z1a2b3c4d5e6 (head)` again).
- **Partial round-trip** (`-3` then back to head) also verified separately before the
  full-chain test, as a faster sanity check.

## Functional verification against the resulting real-Postgres schema

Seeded (`ALLOW_DESTRUCTIVE_SEED=true`, required and correctly enforced — `reset_db()`
refuses to run against a non-SQLite database otherwise, a real safety feature
confirmed working, not just documented) and ran the app against it live:

| Check | Result |
|---|---|
| `GET /api/health/ready` | `{"status":"ready","squadrons":16}` — correct seeded count |
| Login (`system_admin`) | 200 |
| `GET /api/squadrons` | 200, 16 rows |
| `GET /api/curriculum` | 200, 13 rows |
| `GET /api/system/audit-summary` | 200 |
| `POST /api/accounts` (write path) | 200, row created |
| `POST /api/facilitators` with a JSONB list field (`subject_areas`, the v28 migration's TEXT→JSONB conversion) | 200; **verified the actual persisted value via a follow-up GET** (`['Drill', 'Aviation']`) rather than trusting the create response, which doesn't echo the field at all — an initial read of the create response looked like a data-loss bug and was traced to a test-script assumption, not a real defect |

## Outcome

No migration or Postgres-specific defect found. The migration chain is
production-representative-version-tested in both directions, and core read/write/
JSONB functionality is confirmed working against real Postgres, not just SQLite.

## Not yet done in this pass

- Query-plan / index review (`EXPLAIN ANALYZE` on the highest-traffic queries) —
  the `supabase` skill's intended use for this stage, not yet invoked.
- Connection-pool sizing sanity check against real Postgres under load — deferred
  to Stage 10 (performance/load), where pool behavior actually matters.
- No second-database backward-compatibility check (e.g., does the current migration
  chain also apply cleanly to a Postgres version older than 18, such as production's
  exact minor version) — assumed adequate given the image tag pins major version 18
  only, matching what's actually deployed.
