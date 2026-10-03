# Timestamp model and production verification runbook

## The model (authoritative)

- Every application timestamp is stored as **naive UTC** (`timestamp without
  time zone`). `app.database.UTCDateTime` writes naive UTC and hands Python an
  aware UTC `datetime`; the API serialises it with a `Z` suffix.
- Date-only values (parade dates etc.) are plain strings/dates and are not
  timestamps.
- After migration **v76 (`63c110addb63`)** there are **0** `timestamp with time
  zone` columns. Verified on PostgreSQL 18: `alembic check` reports no
  differences.

## What v76 changed and why it is safe

Six columns had been created as `timestamptz` (the same drift v69 fixed for two
other tables): `activity_type_tags.created_at/updated_at`,
`training_area_capability_tags.created_at/updated_at`,
`parade_night_timing_snapshots.created_at`,
`session_assistant_facilitators.created_at`.

`ALTER … TYPE timestamp USING col AT TIME ZONE 'UTC'` converts each stored
**instant** to its exact UTC wall-clock value, independent of the session
`TimeZone`. Proven locally: a value written as 09:30 under an
`Australia/Perth` session keeps the same epoch (1780277400) through upgrade and
downgrade, stored as `01:30` UTC. The migration therefore cannot make any
stored value wrong, and reads return the same instants as before.

## The one external check (owner, read-only)

What the migration cannot know is whether **historical** rows in those six
columns were written while the database session `TimeZone` was not UTC. A
naive value inserted into `timestamptz` is interpreted in the session zone, so
such rows would already hold a shifted instant (v76 preserves, not repairs,
them). Run these **read-only** queries against production before or after the
release:

```sql
-- 1. The server/database/role default zone (expect UTC or Etc/UTC).
SHOW TimeZone;
SELECT datname, setconfig FROM pg_db_role_setting
  JOIN pg_database d ON d.oid = setdatabase;            -- any per-DB override

-- 2. Cross-check: assistant rows were created in the same request as their
--    session's update, which lives in a naive-UTC column. A consistent
--    offset of whole hours (e.g. 8h) means historical writes were shifted.
SELECT round(extract(epoch FROM (saf.created_at - s.updated_at)) / 3600) AS hours,
       count(*)
FROM session_assistant_facilitators saf
JOIN sessions s ON s.id = saf.session_id
GROUP BY 1 ORDER BY 2 DESC LIMIT 5;
```

Interpretation: if (1) is `UTC`/`Etc/UTC` and (2) clusters at `0` (within the
request duration), nothing further is needed. If (2) clusters at a non-zero
whole number of hours, the historical rows in these six columns need a one-off,
reviewed correction of that offset; open an issue with the query output.

Railway's official PostgreSQL images default to `Etc/UTC`, and the production
restore test (run 37132802899, 2026-10-03) restored and upgraded production
data cleanly, but neither proves the historical session zone; only the queries
above do.
