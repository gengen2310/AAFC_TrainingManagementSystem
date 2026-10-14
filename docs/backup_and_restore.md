# Backup and Restore

This document describes the current AAFC TMS backup model. The old pilot-era
SQLite copy procedure is retained only for local development; production is
PostgreSQL.

## Production source of truth

Production backup automation is defined in
`.github/workflows/backup-postgresql.yml`.

The workflow:

- runs daily at 02:00 AWST and can also be dispatched manually;
- uses the dedicated `PROD_DATABASE_BACKUP_URL` direct/session PostgreSQL
  connection, not the application's transaction-pooler URL;
- refuses the known staging host and refuses port 6543;
- dumps only the application's `public` schema in PostgreSQL custom format;
- computes a SHA-256 checksum before encryption;
- GPG-encrypts both the dump and checksum;
- stores only the encrypted files as a GitHub Actions artifact, retained for
  30 days. **The repository is public, so these artifacts are not private:**
  any signed-in GitHub user can download the encrypted files. Confidentiality
  rests entirely on the GPG encryption (4096-bit RSA public key committed at
  `.github/backup-public-key.asc`; the private key and passphrase exist only as
  the Actions secrets `BACKUP_GPG_PRIVATE_KEY` / `BACKUP_GPG_PASSPHRASE` and
  have never been committed -- verified across the full git history on
  2026-10-03). See "Known risks" below;
- deletes plaintext temporary files even when the workflow fails;
- can send an optional Slack failure alert when
  `SLACK_BACKUP_ALERT_WEBHOOK` is configured.

Staging has a separate, manual-only workflow:
`.github/workflows/backup-postgresql-staging.yml`. It uses a different
database secret and refuses the known production host.

## Restore verification

A backup is not considered useful merely because `pg_dump` completed.

The repository contains separate production and staging restore-test workflows:

- `.github/workflows/test-restore-postgresql.yml`
- `.github/workflows/test-restore-postgresql-staging.yml`

What the production restore test proves on every run (weekly, plus manual
dispatch):

1. the newest production artifact decrypts and its SHA-256 matches;
2. `pg_restore` succeeds into a disposable CI PostgreSQL 18;
3. the restored alembic revision is a known revision of this repository
   (production legitimately lags `main` between releases);
4. `alembic upgrade head` succeeds on that real data -- a rehearsal of the
   next production deploy's migrations;
5. every application model table exists and core row counts are readable;
6. a real backend starts on the restored data and serves a login plus
   authenticated reads.

**Evidence history.** Scheduled runs failed from at least 2026-09-13 to
2026-09-27 -- not because backups were bad (decrypt/checksum/restore all
succeeded) but because verification demanded the repository head and listed a
table name that never existed (`session_audiences`). Fixed on the
stabilisation branch; the first fully verified run is
[37132802899](https://github.com/gengen2310/AAFC_TrainingManagementSystem/actions/runs/37132802899)
(2026-10-03): backup `postgresql-production-backup-20261002_215334`,
production at v64 `a4e9507a9c51`, upgraded through 10 migrations to
`c0e3a6b8d4f2`, 23/23 schema checks, 75/75 model tables, 8/8 API reads.
Earlier claims of a passing automated restore in
`docs/release/final_backup_restore_assessment.md` predate those failures;
treat that file as historical.

A literal human, keystroke-by-keystroke manual DR drill has still not been
completed.

Operator recovery instructions and GPG key handling live in
`deployment/backup-dr.md`. Do not invent an alternate recovery procedure in
an incident.

## Application-initiated backup

The System Console also exposes an application backup operation. Its
`last_backup_at` status refers only to backups initiated through the
application. Scheduled GitHub Actions backups are independent and do not write
their completion timestamp into the application database. The UI must not
present that field as "last backup of any kind."

## Local SQLite development

SQLite is a local/demo path, not the production disaster-recovery mechanism.

A developer who intentionally uses the local SQLite database can make a
point-in-time copy while the application is stopped:

```bash
cp backend/aafc_tms.db ~/backups/aafc_tms_$(date +%Y%m%d_%H%M%S).db
```

Restore it only into a local development environment:

```bash
cp ~/backups/aafc_tms_YYYYMMDD_HHMMSS.db backend/aafc_tms.db
```

Do not use these SQLite instructions for Railway/PostgreSQL production.

## Operational requirements

A production-ready backup regime requires all of the following, not just a
green scheduled dump:

1. the daily production workflow remains green;
2. restore-test evidence is refreshed after material schema/backup changes;
3. the private GPG key and passphrase remain recoverable by authorised
   operators and outside the database being backed up;
4. at least one backup copy needed for the organisation's retention objective
   exists outside the 30-day Actions-artifact window;
5. a manual DR rehearsal is periodically performed and its measured recovery
   time recorded;
6. backup/restore credentials and keys are rotated through the documented
   procedure and the next restore test is run after rotation.

The stabilisation release gate treats **verified restore**, not merely
"backup exists", as the relevant control.

## Known risks (owner decisions)

- **Public artifacts + co-located key.** Encrypted dumps are publicly
  downloadable, and the decryption key/passphrase are secrets of the same
  repository. Anyone who gains write access (or the owner account) can run a
  workflow that reads those secrets. Options: make the repository private, or
  move backup artifacts to private storage and keep the decryption key outside
  GitHub (restore tests would then need a separate trust path).
- **Retention.** Only the 30-day Actions window exists; no off-GitHub copy.
- **Silent schedule stop.** GitHub disables scheduled workflows in public
  repositories after 60 days without repository activity; neither the backup
  nor the restore test would then run, and no failure alert would fire.
- `test-restore-postgresql-staging.yml` (manual only, never run) still uses the
  old exact-head check.
