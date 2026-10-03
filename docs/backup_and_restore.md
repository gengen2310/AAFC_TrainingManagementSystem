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
- stores only the encrypted files as a private GitHub Actions artifact;
- retains that artifact for 30 days;
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

The current release evidence is recorded in
`docs/release/final_backup_restore_assessment.md`. That assessment records a
successful automated decrypt/restore/integrity/application-smoke path. It also
records the remaining distinction: a literal human, keystroke-by-keystroke
manual DR drill has not yet been completed.

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
