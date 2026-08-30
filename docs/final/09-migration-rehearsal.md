# Part 93 — migration rehearsal against PostgreSQL

**Date:** 2026-08-30 · **Harness:** `backend/scripts/rehearse_migrations.py`

## What the programme assumed, and what is actually there

The programme brief records "only 1 of 27 production-path migrations rehearsed".
The chain holds **70 migrations**, not 27. It is linear — a single head
(`f2c8e51d7a93`), no branches, no orphans; the harness asserts this and would
refuse to run otherwise.

Of the 70: 12 carry data logic (`UPDATE` / `INSERT` / `DELETE`), 6 carry a
self-check that raises on a failed backfill, and the rest are DDL only.

## Why PostgreSQL, and why the test suite could not have caught this

The suite builds its schema with `create_all` on SQLite and never runs the
migration chain. SQLite cannot run it: an early migration alters constraints,
which the SQLite dialect refuses outright. So a fully green suite says nothing
about whether a deploy will migrate — which is exactly how a branch that
removed already-applied migrations took staging down on 2026-08-28.

## Result

| check | result |
|---|---|
| forward, base → head | **70 / 70** |
| per-migration reversibility | **67 / 70** identical schema; 3 declared irreversible |
| full down, head → base | **70 / 70** |
| re-upgrade, base → head | schema **identical** to the first pass |

Before this work the chain **could not be walked backwards at all** — it stopped
after 54 of 70.

## Defects found and fixed

All four were invisible to the test suite and would only ever have surfaced
during a rollback, which is the worst possible moment to discover them.

**1. `v53 drop_inert_planning_tables` — recreated two tables at the wrong shape.**
Its downgrade drops `planning_locations` and `scheduled_sessions` and recreates
them from the v11 column list, ignoring every column added in between. It
omitted `scheduled_sessions.archived_at` (added by v26) and
`planning_locations.updated_by`, and relaxed four `NOT NULL` columns to
nullable. The chain then broke **27 migrations later**, at v26's own downgrade:
`column "archived_at" does not exist`. The failure names v26, but v26 is
correct and symmetric — the fault is entirely v53's.

**2. `v55 schema_integrity_fixes` — dropped an index it did not create.**
Its upgrade does `CREATE INDEX IF NOT EXISTS ix_pnto_parade_night_id`, a no-op
because v8 already created it. Its downgrade dropped that index unconditionally
and added a unique constraint that never existed pre-v55. v8's downgrade then
failed. Verified by fingerprinting `pg_indexes` either side of v55: the
round trip is now identity.

**3. `821e2a4bc3e6 update_block_type_taxonomy` — dropped another migration's
columns, and their data.** Same pattern as (2), but worse: its upgrade adds
`service_desk_email_configs.created_by` / `updated_by` only when absent (a
no-op — v45 created them), while its downgrade dropped them unconditionally.
Any rollback past this point destroyed the attribution data in those columns.

**4. `v40 drop_dead_custom_phases_table` — recreated `custom_phases` at its
original shape**, missing the `created_by` / `updated_by` columns the timestamp
patches had added and relaxing `created_at` / `updated_at` to nullable.

Every replacement shape was measured from a real database built through the
chain to the revision immediately before the migration, never inferred from
reading the migration files.

## Declared irreversible, by design

Three migrations have a deliberate no-op downgrade, documented in each file:
`v44` (`planning_facilitator_leave.updated_by`), `v45` (TimestampMixin columns
on `activity_local_hides` and `squadron_event_status`) and `v46`
(`parade_nights.version`). Each adds a column the ORM now requires
unconditionally, so a symmetric `drop_column` would re-break every
environment's queries on rollback — reintroducing the defect the migration
exists to fix.

They are listed in `DECLARED_IRREVERSIBLE` in the harness so they stay visible
in the report rather than being silently tolerated. An **undeclared** asymmetry
fails the run.

## The check that matters, and its blind spot

The per-migration check compares the schema after a downgrade against the
schema recorded when the chain first passed through that revision on the way
up — not merely against the migration's own before/after.

That distinction is what catches this class of bug. v53's own down→up cycle is
self-consistent even when broken, because at v53 the tables do not exist; the
damage only shows against the state v52 actually had. An earlier version of
this harness compared only the migration's own round trip and **missed the v53
defect entirely** — it was caught by the full-chain walk instead.

## Running it

```
python backend/scripts/rehearse_migrations.py          # all three checks
python backend/scripts/rehearse_migrations.py --quick  # skip the per-migration pass
```

Needs a local PostgreSQL and `createdb` rights. It creates and drops its own
scratch database and never touches an existing one.

## Data paths

`scripts/rehearse_data_migrations.py` covers the second half of Part 93.

Of the 12 data-bearing migrations, **nine seed their own reference data**, so the
empty-database walk does exercise them. That is measured, not assumed — after a
full chain run on an empty database:

| table | rows |
|---|---|
| `curriculum_items` | 214 |
| `curriculum_elements` | 15 |
| `session_status_reason_tags` | 10 |
| `curriculum_phases` | 8 |
| `training_area_capability_tags` | 8 |
| `activity_type_tags` | 3 |

**Three transform rows only a real installation has**, so on an empty database
their `UPDATE`/`DELETE` match nothing and the chain walk proves nothing about
them. Each is now rehearsed against representative rows, at the migration's own
parent revision, with a control row that must *not* change:

| migration | exercised | result |
|---|---|---|
| `v54 a3b4c5d6e7f8` | dangling `parade_dates.parade_night_id` nulled; valid one kept | ok |
| `v55 b4c5d6e7f8a9` | `session_audience` de-duplicated; dangling `planning_conflicts.scheduled_session_id` nulled; valid one kept | ok |
| `821e 821e2a4bc3e6` | all six `block_type` remappings, `is_instructional_period` recomputed both ways, `service_desk_email_configs` NULL timestamps backfilled | ok |

Verified non-vacuous by sabotage. Breaking v54's `WHERE` clause so it matches
nothing makes the migration itself fail with the exact foreign-key violation a
production deploy would hit; corrupting one entry in 821e's type map is caught
by the block assertions.

### Finding: v55's de-duplication is unreachable on the canonical chain

`v49` (`af4a8639bc3a`) already made `(session_id, training_class_id)` unique, so
duplicates cannot exist by the time `v55` runs, and its `DELETE` can never match
a row. `v55` then adds `uq_session_audience_pair` — a **second unique constraint
on the same column pair**, which the canonical schema now carries alongside
`uq_session_audience_session_class`.

Neither is a correctness fault: the data ends up right either way. The cost is a
redundant index on every write to that table, and dead defensive code that reads
as though it is protecting something.

The rehearsal exercises the `DELETE` path deliberately, by dropping the v49
constraint first. That reproduces a database which reached v54 without it —
created by `create_all` rather than migrated, which is the population v55 was
written to repair.

Left as-is rather than fixed: removing a constraint from a shipped migration
rewrites history for every environment that has already applied it, which is a
worse risk than a redundant index. Recorded here for a future consolidation.

## Not covered
- **Volume.** The data cases use a handful of rows each: enough to prove the
  transformation is correct, not enough to say what it costs. A backfill that is
  right on six rows can still time out on six hundred thousand.
- **A production-shaped dump.** No production data has been copied, per the
  standing constraint. Row counts, and the time the data migrations take
  against them, remain unmeasured.
- **The SQLite downgrade branches.** `v55` and others branch on dialect. Only
  the PostgreSQL branch — the production path — is exercised here.
