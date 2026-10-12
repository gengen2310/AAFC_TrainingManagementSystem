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

## 2026-10-12 rehearsal at `24be3e1` (code identical to freeze `ea12454`)

`alembic heads` → **one head**, `63c110addb63` (v76). Script: empty DB → `upgrade head` →
`downgrade a4e9507a9c51` (production's v64) → `upgrade head`.

| Engine | upgrade head | downgrade → v64 | upgrade head |
|---|---|---|---|
| PostgreSQL 16 (throwaway local cluster) | ok | ok | ok |
| SQLite | ok | ok | ok |

Proves the schema path both ways; the data path v64 → head is proven separately on restored
production data by the restore workflow (runs 37909713246, 37910351762; to be repeated at the
final SHA).

**Downgrade is lossy below v70/v71 — rollback must not rely on it:**
- v70 `downgrade` drops `service_tickets.assigned_to_user_id` (account-backed assignments).
- v71 drops `users.must_change_code` (pending forced first-login rotations would be lost,
  re-exposing administrator-issued initial codes).
- v73/v74 drop transient tables (idempotency keys, rate-limit buckets): harmless.
- v76 converts naive UTC ↔ timestamptz without loss.

Rollback policy for the release runbook: roll back **application code only** (redeploy the
prior image; additive schema stays), or restore the pre-deploy backup; never `alembic
downgrade` production below v72 except with an owner-approved data-loss acceptance.

## Restore drill at `0c0aadb` (2026-10-12, run 38221096962, `workflow_dispatch`)

Latest encrypted production backup → decrypted → restored into an ephemeral PostgreSQL 18
→ restored revision `a4e9507a9c51` (v64) → `alembic upgrade head` ran all 15 pending
migrations to `63c110addb63` (v76) → **23/23 database checks passed** (row counts incl.
users 22, parade_nights 154, sessions 86, facilitators 97), **all 77 model tables present**,
**9/9 authenticated application reads** against restored data (health 18 squadrons;
`/api/facilitators?unit_id=<busiest>` 23 items = 23 restored rows). The last scheduled run on
`main` (38181254881, 2026-10-11) failed only at verification, by construction (D6): main's
workflow compares the restored v64 with main's head instead of upgrading first. It clears when
this branch merges.
