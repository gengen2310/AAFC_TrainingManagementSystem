# Migration and restore evidence — production readiness 2026-10-09

| Item | Value |
|---|---|
| Production DB revision (restored) | `a4e9507a9c51` (v64) |
| Repository head on this branch | `63c110addb63` (v76) — `alembic heads` single head |
| Migrations a production deploy will apply | **15** (`b7f3c2e1d098` K-006 … `63c110addb63`) |
| Backup used | `postgresql-production-backup-20261008_225958` (artifact 11583977958), 152 KB encrypted / 337,405 B dump, SHA-256 `962e0f86…c8f4` verified |
| Restore run on `704cf5b` | 37909713246 — success (reported 14 pending: D7) |
| Restore run on `a98f7ae` | **37910351762 — success**: 15 reported = 15 executed; 23/23 data checks; 77 model tables present; 9/9 authenticated reads incl. facilitators scoped to busiest squadron = 23 restored rows |
| Nightly production backup | green (e.g. 37856864407, 2026-10-08) |

## D6 — why scheduled restore runs on `main` fail (root cause)

`main`'s copy of the restore test requires restored head == repo head. Production
is deliberately held at v64 while `main` is ahead, so every weekly run since
2026-09-13 failed (latest 37238968630: `got 'a4e9507a9c51', expected
'7f61608fa538'`; `session_audiences` missing). Not a backup failure. The branch's
version restores, upgrades to head on the real data, then verifies. `main` stays
red until this branch's workflow is merged.

## Data observations on real production data (upgrade rehearsal)

- K-006: 0 SessionAudience rows created, 69 skipped. Production has 0 training
  classes; legacy `cadet_group` sessions are the designed path (D8, not a defect).
- Restored counts: users 22, squadrons 18, sessions 86, parade_nights 154,
  facilitators 97, curriculum_items 214, planning_years 23, audit_logs 878.

## Local migration rehearsal (2026-10-09, migrations as of `8ecd2cd`)

Throwaway databases, removed afterwards. Sequence: empty -> head -> downgrade to the
production revision `a4e9507a9c51` -> head (the rollback-then-redeploy path).

| Engine | empty -> head | head -> prod rev | prod rev -> head | errors |
|---|---|---|---|---|
| SQLite (fresh file) | 89 upgrades | 15 downgrades | 15 upgrades | none |
| PostgreSQL 18.4 (scratch cluster, port 5499, pid verified) | 89 upgrades | 15 downgrades | 15 upgrades | none |

`alembic heads`: single head `63c110addb63`. To repeat at the final SHA if any
migration is added after `8ecd2cd` (none planned).
