# Uncommitted Migration Quarantine

This directory holds Alembic migration files that were written but deliberately
excluded from the live migration chain.

## Why quarantine rather than delete?

Migrations in this directory represent planned schema changes that were
**deferred** — not abandoned. Keeping them here:

- Prevents another developer inadvertently writing the same migration
- Documents the intended future schema change and its `down_revision` at the
  time it was written
- Makes it easy to revive the migration when the right time comes (update
  `down_revision` to the then-current head and move the file into
  `backend/alembic/versions/`)

## Files

| File | Purpose | Deferred reason |
|---|---|---|
| `w8x9y0z1a2b3_v35_program_type.py` | Rename `CurriculumItem.core_status` values `core→foundation`, `additional→extension` to match the user-facing terminology | Alembic head had moved forward before this migration landed; the connected-frontend CSV import mapper and backend code already handle both spellings via normalisation; DB rename deferred to Level B cleanup |

## Reviving a quarantined migration

1. Run `cd backend && alembic heads` to get the current head revision.
2. Update `down_revision` in the quarantined file to that value.
3. Move the file into `backend/alembic/versions/`.
4. Run `alembic upgrade head` to apply.
5. Update any code that writes the old value to write the new value instead.
6. Remove the file from this directory.
