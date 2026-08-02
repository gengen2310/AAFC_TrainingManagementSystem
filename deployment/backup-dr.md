# AAFC TMS — Automated Backup and Disaster Recovery Guide

## Overview

| What | Detail |
|---|---|
| Backup schedule | Daily 02:00 AWST (18:00 UTC) |
| Backup format | pg_dump `--format=custom --no-owner --no-privileges` |
| Encryption | GPG public-key encryption (RSA 4096 or ed25519) |
| Storage | Private GitHub Actions artifact, 30-day retention |
| Restore test | Weekly Monday 03:00 AWST (Sunday 19:00 UTC) |
| Test target | Disposable PostgreSQL service container — never staging/production |
| Plaintext retention | Zero — all plaintext deleted even on failure |
| Credentials in logs | Never — DATABASE_URL parsed in Python, never passed on CLI |

---

## Step 1 — Generate a dedicated GPG keypair

Run these commands on your **local machine**, not in CI.

```bash
# Generate a dedicated keypair for AAFC TMS backups.
# When prompted for a passphrase, choose a strong value (≥20 chars).
# Store the passphrase in your password manager immediately.
gpg --full-generate-key
```

At the prompts:
- Key type: **RSA and RSA** (option 1) or **ECC (sign and encrypt)** (option 9)
- Key size: **4096** (for RSA) or **Curve 25519** (for ECC)
- Expiry: **2y** (rotate annually or biennially)
- Name: `AAFC TMS Backup`
- Email: `aafc-tms-backup@aafc.ca`
- Comment: leave blank

---

## Step 2 — Export and store the keys

```bash
# Export the public key (ASCII-armored).
# This value goes into the repo — public keys are not secrets.
gpg --armor --export aafc-tms-backup@aafc.ca > /tmp/backup-public-key.asc

# Verify it looks correct
head -2 /tmp/backup-public-key.asc
# Expected first line: -----BEGIN PGP PUBLIC KEY BLOCK-----

# Export the private key (ASCII-armored).
# This value goes into GitHub Secrets — never commit it to the repo.
gpg --armor --export-secret-keys aafc-tms-backup@aafc.ca > /tmp/backup-private-key.asc

# Base64-encode the private key for the GitHub Secret.
base64 --wrap=0 /tmp/backup-private-key.asc > /tmp/backup-private-key.b64
```

> **Offline key storage:**
> Save `/tmp/backup-private-key.asc` and the passphrase to an **encrypted offline medium**
> (encrypted USB drive, offline password manager). If GitHub is lost or unavailable during
> a disaster, you need this to decrypt stored backups. Delete the temp files from your
> local machine once stored.

---

## Step 3 — Put the public key in the repository

Replace the placeholder in `.github/backup-public-key.asc`:

```bash
cp /tmp/backup-public-key.asc \
  path/to/AAFC_TMS_National_Connected_Pilot_Package_v17_1_source/.github/backup-public-key.asc
```

Commit and push:
```bash
git add .github/backup-public-key.asc
git commit -m "chore: add GPG public key for automated backup encryption"
git push origin release/beta-2026-07-14 (or the current release branch)
```

---

## Step 4 — Add GitHub Secrets

Go to:
**GitHub → Repository → Settings → Secrets and variables → Actions → New repository secret**

Enter values directly — never paste them into a conversation with an AI assistant or
anywhere else outside the GitHub secret form.

**Backup/restore is split into separate production and staging workflows** (2026-07) —
each targets a different database and cannot be confused for the other's evidence:

| Secret name | Used by | Value to enter | Where to find it |
|---|---|---|---|
| `PROD_DATABASE_BACKUP_URL` | `backup-postgresql.yml` | Production Postgres URI (Railway's production Postgres, public proxy) | `railway variable list --service Postgres --environment production --json` → `DATABASE_PUBLIC_URL`. **As of 2026-08 (GAP-18 fix), production runs on Railway-native Postgres, not Supabase** — a prior version of this doc pointed here at a Supabase Session Pooler URL, which was a genuine, since-fixed defect (the backup was silently targeting the wrong physical database; see `docs/release/qualification_gap_register.md` GAP-18). Do not use the service's own internal `DATABASE_URL` — that's the private in-network address the app uses at runtime, not reachable from GitHub Actions. |
| `SUPABASE_DB_URL` | `backup-postgresql-staging.yml` | Staging Postgres URI (Railway's staging Postgres, public proxy, port 5432) | `railway variable list --service Postgres --environment staging --json` → `DATABASE_PUBLIC_URL`. Name kept for continuity with earlier setup — despite the name, this secret is **staging-only**. |
| `BACKUP_GPG_PRIVATE_KEY` | both restore-test workflows | Contents of `/tmp/backup-private-key.b64` | Generated in Step 2 |
| `BACKUP_GPG_PASSPHRASE` | both restore-test workflows | Passphrase chosen when generating the key | Your password manager |

Both backup workflows run a source-verification preflight that computes a non-secret
SHA-256 fingerprint of the target hostname and refuses to run if it matches the *other*
environment's known fingerprint — a copy/paste mistake between the two secrets fails
loudly instead of silently backing up (or overwriting evidence for) the wrong database.

After adding all secrets, the Secrets page should show:
```
BACKUP_GPG_PASSPHRASE
BACKUP_GPG_PRIVATE_KEY
PROD_DATABASE_BACKUP_URL
SUPABASE_DB_URL
```

---

## Step 5 — Run a manual backup to confirm setup

1. Go to: **GitHub → Actions → PostgreSQL Backup — Production — Daily** (or
   **PostgreSQL Backup — Staging — Manual** for a staging-only backup)
2. Click **Run workflow** → select the release branch → **Run workflow**
3. Watch the run. All steps should pass.
4. On success, the run summary shows:
   ```
   Artifact: postgresql-backup-YYYYMMDD_HHMMSS
   ```
5. The artifact appears under **Actions → this run → Artifacts** — it is private and
   only accessible to repository members.

---

## Step 6 — Run a manual restore test

1. Go to: **GitHub → Actions → PostgreSQL Restore Test — Production — Weekly**
2. Click **Run workflow** → select `release/beta-2026-07-14 (or the current release branch)` → **Run workflow**
3. All steps should pass, ending with:
   ```
   RESTORE VERIFICATION PASSED — all 15 checks passed.
   ```
4. The service container used for the test is destroyed at the end of the run.
   No data touches staging or production.

---

## Manual backup procedure (emergency)

If you need a backup outside the scheduled window:

1. Go to **GitHub → Actions → PostgreSQL Backup — Production — Daily**
2. Click **Run workflow**
3. Wait for completion (typically 2–5 minutes warm)
4. Download the artifact from the run summary

---

## Download and decrypt a backup

```bash
# 1. Go to: GitHub → Actions → PostgreSQL Backup — Production — Daily
#    Find the run whose backup you want → Artifacts → download the .zip

# 2. Unzip
unzip postgresql-backup-YYYYMMDD_HHMMSS.zip

# 3. Import your private key (if not already in your local keyring)
gpg --import /path/to/backup-private-key.asc

# 4. Decrypt the dump
gpg --decrypt \
    --output aafc_tms_backup.dump \
    aafc_tms_backup_YYYYMMDD_HHMMSS.dump.gpg

# 5. Verify the checksum
gpg --decrypt \
    --output aafc_tms_backup.sha256 \
    aafc_tms_backup_YYYYMMDD_HHMMSS.sha256.gpg

sha256sum -c aafc_tms_backup.sha256
# Expected: aafc_tms_backup_YYYYMMDD_HHMMSS.dump: OK
```

---

## Restore procedure (disaster recovery)

Use this when you need to restore to a target PostgreSQL database.

```bash
# Prerequisites:
#   - pg_restore installed (postgresql-client)
#   - Target database exists and is empty (or you are OK overwriting it)
#   - You have decrypted the dump (see above)

# Full restore (replace TARGET_DB_URL with your connection string)
PGPASSWORD="your-password" pg_restore \
  --host=your-host \
  --port=5432 \
  --username=your-user \
  --dbname=your-database \
  --no-owner \
  --no-privileges \
  --exit-on-error \
  aafc_tms_backup.dump

# Production (Railway-native Postgres): use the service's public proxy host
# (railway variable list --service Postgres --environment production --json
# → DATABASE_PUBLIC_URL), not the internal railway.internal address.
```

---

## Key rotation

Rotate the backup key annually or if the private key may be compromised.

```bash
# 1. Generate a new keypair (Step 1 above with a new expiry)
# 2. Export new public and private keys
# 3. Replace .github/backup-public-key.asc in the repo → commit + push
# 4. Update BACKUP_GPG_PRIVATE_KEY and BACKUP_GPG_PASSPHRASE secrets
# 5. Verify with a manual backup run
# 6. Retain the OLD private key for at least 31 days (to decrypt remaining
#    artifacts that were encrypted with the old key)
# 7. Revoke the old key in your local keyring when all old artifacts expire:
gpg --gen-revoke aafc-tms-backup@aafc.ca
```

---

## Disaster recovery testing checklist

Run this checklist quarterly:

- [ ] Trigger a manual backup run — confirm it passes
- [ ] Download the artifact and decrypt it locally
- [ ] Verify the SHA-256 checksum matches
- [ ] Trigger a manual restore test run — confirm all verification checks pass
- [ ] Confirm the restore test used a temporary container (not staging/production)
- [ ] Check that no credentials appeared in any workflow logs
- [ ] Verify the private key and passphrase are still accessible from offline storage
- [ ] Confirm key expiry date — rotate if within 60 days

---

## Workflow files

| File | Purpose |
|---|---|
| `.github/workflows/backup-postgresql.yml` | Daily production backup job (scheduled + manual) |
| `.github/workflows/backup-postgresql-staging.yml` | Manual-only staging backup job |
| `.github/workflows/test-restore-postgresql.yml` | Weekly production restore verification (scheduled + manual) |
| `.github/workflows/test-restore-postgresql-staging.yml` | Manual-only staging restore verification |
| `.github/backup-public-key.asc` | GPG public key (safe to commit) |
| `backend/scripts/compute_alembic_head.py` | Computes the expected Alembic head from the checked-out migration files at restore-test time — never hardcode this value in a workflow again |

---

## Retention and limits

| Metric | Value |
|---|---|
| Artifact retention | 30 days |
| Artifacts per run | 1 (dump + checksum, both encrypted) |
| GitHub free plan artifact storage | 500 MB total; each staging dump is < 10 MB |
| pg_dump format | Custom (binary, efficient, supports selective restore) |
| Restore test DB | Destroyed at end of every CI run |

---

## What the backup does NOT cover

- Railway's ephemeral container filesystem (not used for application data)
- `STAGING_BOOTSTRAP_SYSADMIN_CODE` (one-time env var, discarded after first login)
- JWT_SECRET / SECRET_KEY (set per-environment via `railway variable set`, never
  auto-rotated; rotating either invalidates all sessions on that environment)

For production, check whether Railway's own native Postgres plugin offers a
point-in-time-recovery option on the current plan, in addition to these pg_dump
backups — not yet confirmed either way (see `final_backup_restore_assessment.md`
if/when that stage is completed).

*(This section previously referenced Render and Supabase — both stale from an
earlier architecture; corrected 2026-08 alongside the GAP-18 fix above.)*
