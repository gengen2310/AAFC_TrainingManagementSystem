# AAFC TMS — Disaster Recovery Rehearsal Procedure

Phase 19 — Next-Stage Development Program.
Written 2026-07-16. Target audience: System Admin, Wing Admin (observers).

This document defines the procedure for a **quarterly DR rehearsal** against the
staging environment. It proves that:

1. A production-equivalent backup can be created on demand.
2. The backup decrypts and restores completely to a fresh database.
3. The restored database passes application smoke tests.
4. Recovery Time Objective (RTO ≤ 60 minutes) is measured and recorded.

**Non-negotiable constraints:**
- The rehearsal targets **staging only** — never production.
- No real cadet or personal data may be present in staging (synthetic seed data only).
- No production `DATABASE_URL` or credentials are used at any step.
- The disposable restore target is torn down immediately after rehearsal.

---

## When to Run

| Trigger | Who | Frequency |
|---|---|---|
| Quarterly calendar rehearsal | System Admin | Every 3 months (Jan, Apr, Jul, Oct) |
| After any backup credential rotation | System Admin | Within 5 business days of rotation |
| After major schema migration to production | System Admin | Within 5 business days of deploy |
| On explicit governance request | System Admin | As directed |

Record each rehearsal in the evidence table at the bottom of this document.

---

## Prerequisites

| Item | How to verify |
|---|---|
| GitHub Actions access to `AAFC_TMS` repository | Can open Actions tab in browser |
| `BACKUP_GPG_PRIVATE_KEY` and `BACKUP_GPG_PASSPHRASE` secrets set in staging environment | Settings → Secrets → visible (value not readable, existence sufficient) |
| `SUPABASE_DB_URL` staging secret set | Same location |
| At least one successful staging backup artifact exists | Actions → `backup-postgresql.yml` → last successful run |
| `pg_restore` available on your local machine | `pg_restore --version` prints a version string |
| `gpg` available on your local machine | `gpg --version` prints a version string |

---

## Part 1 — On-Demand Backup of Staging

### Step 1: Trigger a manual backup

1. Open the repository on GitHub.
2. Go to **Actions** → **Backup PostgreSQL (staging)**.
3. Click **Run workflow** → select branch `next-stage/v1-operational` → click **Run workflow**.
4. Wait for the workflow to complete (typically 90–120 seconds).
5. Record the run ID from the URL (e.g. `run_id=12345678`).

### Step 2: Download the backup artifact

1. Open the completed run.
2. Under **Artifacts**, download `staging-db-backup-<date>.dump.gpg`.
3. Save to a **temporary directory** (e.g. `/tmp/dr-rehearsal/`).
4. Note the artifact size (expected: a few kilobytes for synthetic seed data).

---

## Part 2 — Restore to a Disposable Database

### Step 3: Start a disposable PostgreSQL container

```bash
# Requires Docker Desktop
docker run --rm --name dr-rehearsal-pg \
  -e POSTGRES_PASSWORD=rehearsal_only \
  -e POSTGRES_DB=rehearsal \
  -p 54321:5432 \
  -d postgres:16
```

Wait 5–10 seconds for the container to be ready:
```bash
docker exec dr-rehearsal-pg pg_isready -U postgres
# Expected: /var/run/postgresql:5432 - accepting connections
```

### Step 4: Decrypt the backup

```bash
# Requires the GPG private key loaded locally.
# Import from the key file you stored during initial setup (see deployment/backup-dr.md).
gpg --decrypt /tmp/dr-rehearsal/staging-db-backup-<date>.dump.gpg \
  > /tmp/dr-rehearsal/staging-db.dump
```

You will be prompted for the GPG passphrase. The plaintext `.dump` file must be
deleted immediately after step 5 is complete.

### Step 5: Restore to the disposable database

```bash
pg_restore \
  --host=localhost \
  --port=54321 \
  --username=postgres \
  --dbname=rehearsal \
  --no-owner \
  --no-privileges \
  --verbose \
  /tmp/dr-rehearsal/staging-db.dump
```

Expected output: a series of `pg_restore: processing item` lines with no errors.
Warnings about roles or extensions not existing are acceptable.

### Step 6: Delete plaintext dump immediately

```bash
rm /tmp/dr-rehearsal/staging-db.dump
```

---

## Part 3 — Smoke Test the Restored Database

### Step 7: Connect a local backend instance to the restored database

```bash
# From the backend directory
cd backend
source .venv/bin/activate

export DATABASE_URL="postgresql://postgres:rehearsal_only@localhost:54321/rehearsal"
export ENVIRONMENT="test"
export JWT_SECRET="rehearsal-test-secret-not-production"
export SECRET_KEY="rehearsal-test-secret-not-production"

uvicorn app.main:app --port 9000
```

### Step 8: Run smoke tests against the local instance

```bash
# In a second terminal
curl -s http://localhost:9000/api/health/ready | python3 -m json.tool
# Expected: {"status": "ready", "squadrons": N}  (N ≥ 1 for synthetic seed)

curl -s http://localhost:9000/api/health | python3 -m json.tool
# Expected: {"status": "ok"}
```

Also verify auth:
```bash
# Use a staging synthetic seed code (not a production code)
curl -s -X POST http://localhost:9000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"code": "<STAGING_ADMIN_CODE>"}' | python3 -m json.tool
# Expected: {"token": "...", "session": {...}}
```

Record the squadron count from `/api/health/ready`. This is your data integrity
baseline — it must match the count you see in the staging Planning Workspace.

### Step 9: Run the backend test suite against the restored DB (optional but recommended)

```bash
# Still in the backend directory with DATABASE_URL pointing to disposable DB
python -m pytest tests/ -q --tb=short
```

The test suite uses its own in-memory SQLite fixture; this step is optional but
verifies no environment-level issues prevent the app from starting.

---

## Part 4 — Tear Down and Record

### Step 10: Stop the disposable container

```bash
docker stop dr-rehearsal-pg
# Container is automatically removed (--rm flag)
```

### Step 11: Clean up the rehearsal directory

```bash
rm -rf /tmp/dr-rehearsal/
```

### Step 12: Record the rehearsal result

Fill in the row in the Evidence table below:

| Date | Run ID | Backup artifact size | Restore duration (sec) | Squadrons in restored DB | Smoke test result | Operator |
|---|---|---|---|---|---|---|
| | | | | | | |

**Restore duration** = wall time from `gpg --decrypt` starting to `pg_restore`
completing. This is your measured RTO for database-only recovery. The full RTO
(including backend restart and DNS/routing changes) is estimated at +5–10 minutes.

**Target RTO:** ≤ 60 minutes for full recovery (database restore + backend restart).

---

## Part 5 — Known Limitations and Gaps

| Limitation | Impact | Planned resolution |
|---|---|---|
| Rehearsal uses local pg_restore, not Railway PostgreSQL | Actual production restore would use Railway's restore feature or pg_restore against Supabase URL | Run one rehearsal against a Railway staging Postgres to calibrate |
| Backup artifact is 30-day retention on GitHub Actions | Gap if rehearsal is needed after artifact expiry | Download and archive the most recent monthly backup to secure offline storage |
| Key rotation not practiced in this procedure | Rotation may fail in practice | Add key rotation to the annual rehearsal cycle (separate procedure in deployment/backup-dr.md) |
| No automated alert if weekly restore test fails | Silent failure possible | Add GitHub Actions failure notification (email or Slack) |

---

## Evidence Table

Completed rehearsals are recorded here. A blank table means no rehearsal has been run yet
under this next-stage program.

| Date | Run ID | Artifact size | Restore duration | Squadrons restored | Smoke result | Operator |
|---|---|---|---|---|---|---|
| _(not yet run)_ | — | — | — | — | — | — |

---

## Support Contact

If the restore fails at any step, do NOT attempt to use production credentials or
production database to work around the failure. Raise a support incident with:

- The GitHub Actions run ID
- The `pg_restore` error output
- The encrypted artifact (do not decrypt outside a secure local machine)
