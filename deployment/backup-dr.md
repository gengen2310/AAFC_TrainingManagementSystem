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
git push origin deployment/staging-v17.1
```

---

## Step 4 — Add GitHub Secrets

Go to:
**GitHub → Repository → Settings → Secrets and variables → Actions → New repository secret**

Add all three secrets. Enter the values directly — never paste them into this conversation.

| Secret name | Value to enter | Where to find it |
|---|---|---|
| `SUPABASE_DB_URL` | Supabase Session Pooler URI (port 5432) | Supabase Dashboard → Settings → Database → Session Pooler |
| `BACKUP_GPG_PRIVATE_KEY` | Contents of `/tmp/backup-private-key.b64` | Generated in Step 2 |
| `BACKUP_GPG_PASSPHRASE` | Passphrase chosen when generating the key | Your password manager |

> `SUPABASE_DB_URL` may already be set if you followed the main deployment guide.
> If so, skip it — you do not need to create it again.

After adding all three, the Secrets page should show:
```
BACKUP_GPG_PASSPHRASE
BACKUP_GPG_PRIVATE_KEY
SUPABASE_DB_URL
```

---

## Step 5 — Run a manual backup to confirm setup

1. Go to: **GitHub → Actions → PostgreSQL Backup — Daily**
2. Click **Run workflow** → select `deployment/staging-v17.1` → **Run workflow**
3. Watch the run. All steps should pass.
4. On success, the run summary shows:
   ```
   Artifact: postgresql-backup-YYYYMMDD_HHMMSS
   ```
5. The artifact appears under **Actions → this run → Artifacts** — it is private and
   only accessible to repository members.

---

## Step 6 — Run a manual restore test

1. Go to: **GitHub → Actions → PostgreSQL Restore Test — Weekly**
2. Click **Run workflow** → select `deployment/staging-v17.1` → **Run workflow**
3. All steps should pass, ending with:
   ```
   RESTORE VERIFICATION PASSED — all 15 checks passed.
   ```
4. The service container used for the test is destroyed at the end of the run.
   No data touches staging or production.

---

## Manual backup procedure (emergency)

If you need a backup outside the scheduled window:

1. Go to **GitHub → Actions → PostgreSQL Backup — Daily**
2. Click **Run workflow**
3. Wait for completion (typically 2–5 minutes warm)
4. Download the artifact from the run summary

---

## Download and decrypt a backup

```bash
# 1. Go to: GitHub → Actions → PostgreSQL Backup — Daily
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

# For Supabase: use the Session Pooler host (port 5432, not 6543 or 5432 direct)
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
| `.github/workflows/backup-postgresql.yml` | Daily backup job |
| `.github/workflows/test-restore-postgresql.yml` | Weekly restore verification |
| `.github/backup-public-key.asc` | GPG public key (safe to commit) |

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

- Render's ephemeral filesystem (not used for application data)
- `STAGING_BOOTSTRAP_SYSADMIN_CODE` (one-time env var, discarded after first login)
- JWT_SECRET / SECRET_KEY (auto-generated per Render deploy; invalidates all sessions on rotate, which is acceptable for staging)

For production, add point-in-time recovery (Supabase PITR, available on paid plans) in addition to pg_dump backups.
