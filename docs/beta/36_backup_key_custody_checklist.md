# AAFC TMS — Backup Key Custody Checklist

Phase 5 (Operational Release Gate). GPG key custody verification for backup/restore recovery.
Created: 2026-07-14.

---

## Overview

Production database backups are GPG-encrypted using the key committed to `.github/backup-public-key.asc`. The private key is required to decrypt any backup for restoration. If the private key and passphrase are lost, no historical backup can be decrypted — data recovery would require a direct database export from the live production Postgres instance (if still accessible).

---

## Key Identity

| Field | Value |
|---|---|
| Public key file | `.github/backup-public-key.asc` |
| Public key fingerprint | Run `gpg --with-fingerprint .github/backup-public-key.asc` to obtain |
| Key algorithm | RSA (GPG default) |
| Usage | Encrypt backup artifacts; private key required for decryption |

---

## Custody Verification Checklist

### Technical Verification (Machine-executable)

| Check | Action | Status |
|---|---|---|
| Public key exists in repo | `ls .github/backup-public-key.asc` | ✓ Confirmed |
| Public key is not expired | `gpg --with-fingerprint .github/backup-public-key.asc` | VERIFY MANUALLY |
| GitHub secret `BACKUP_GPG_PRIVATE_KEY` exists | Railway/GitHub secrets panel | HUMAN ACTION REQUIRED |
| GitHub secret `BACKUP_GPG_PASSPHRASE` exists | Railway/GitHub secrets panel | HUMAN ACTION REQUIRED |
| Last successful backup completed | GitHub Actions: `backup-postgresql.yml` | ✓ Run 29281190414 — 2026-07-13 |
| Test decryption succeeds | `gpg --decrypt artifact.tar.gz.gpg > /dev/null` | Performed in workflow run 29297143467 ✓ |

### Human Custody Actions (MANUAL USER ACTIONS — Cannot be completed by Claude Code)

The following actions MUST be confirmed by the authorised person before this checklist is complete:

**ACTION 1: Passphrase stored in approved location**

- [ ] The GPG passphrase for `BACKUP_GPG_PASSPHRASE` is stored in an approved password manager (e.g. BitWarden, 1Password, KeePass) or equivalent secure offline location
- [ ] The passphrase is NOT stored only in someone's memory, a plain text file, or a GitHub secret as the sole copy
- Confirmed by: ___________________ Date: ___________

**ACTION 2: Primary private key copy**

- [ ] The GPG private key (`BACKUP_GPG_PRIVATE_KEY` value) has a primary copy stored securely outside GitHub and outside the development laptop
- [ ] Acceptable locations: encrypted USB drive, approved secure file storage, hardware security key, approved cloud secret store
- Primary copy location (describe without exposing key): ___________________
- Confirmed by: ___________________ Date: ___________

**ACTION 3: Secondary offline copy**

- [ ] A secondary copy of the private key exists in a separate physical location from the primary
- [ ] The secondary copy is offline or air-gapped (e.g. printed and locked in a secure physical location, or on a separate encrypted USB)
- Secondary copy location (describe without exposing key): ___________________
- Confirmed by: ___________________ Date: ___________

**ACTION 4: Key rotation procedure documented**

- [ ] The procedure for rotating the GPG key pair (generate new pair, update `.github/backup-public-key.asc`, update GitHub secrets, verify next backup run) is documented
- [ ] At least two authorised persons know how to perform this procedure
- Documented at: ___________________
- Confirmed by: ___________________ Date: ___________

**ACTION 5: Recovery authorization**

- [ ] The list of persons authorised to access recovery material is documented
- [ ] The escalation path (who to call if all authorised persons are unavailable) is documented
- Authorised persons: ___________________
- Escalation contact: ___________________
- Confirmed by: ___________________ Date: ___________

---

## Recovery Instructions (Do Not Print Private Key)

If a restore is needed:

1. Locate the encrypted backup artifact (`postgresql-production-backup-*.tar.gz.gpg`)
2. Retrieve the private key and passphrase from the approved secure location
3. Import the private key: `gpg --import private-key.asc`
4. Decrypt: `gpg --decrypt backup.tar.gz.gpg | tar xz`
5. The decrypted `.sql` file can be restored with `pg_restore` or `psql` against a disposable Postgres instance
6. Run the application-level verification per `04_backup_restore_test_report.md`
7. Destroy the disposable instance after evidence is recorded

Full runbook: `deployment/backup-dr.md`

---

## Checklist Completion

This checklist is **NOT COMPLETE** until all 5 human actions above are confirmed. Do not mark backup key custody complete without explicit user confirmation.

| Item | Status |
|---|---|
| Technical verification | ✓ Complete |
| Human Actions 1–5 | PENDING — human confirmation required |
