# Backup and Restore — Procedure

## Overview

AAFC TMS stores all operational data in a single SQLite database file (`backend/aafc_tms.db`). The backup procedure for the pilot is a scheduled file copy. For production, a PostgreSQL database with point-in-time recovery is recommended.

---

## Pilot Backup Procedure

### Manual backup (SQLite)

```bash
cp backend/aafc_tms.db ~/backups/aafc_tms_$(date +%Y%m%d_%H%M%S).db
```

Run daily at minimum. On macOS, add to crontab:

```cron
0 2 * * * cp /path/to/aafc_tms.db /path/to/backups/aafc_tms_$(date +\%Y\%m\%d).db
```

### What is backed up

- All user accounts and access codes (hashed)
- Entire unit hierarchy (NatHQ, Wing, Squadrons)
- All curriculum items, sessions, facilitators, parade nights
- All planning years, parade dates, holiday periods, anchor events
- All audit log entries

### What is NOT backed up

- Active JWT sessions (expire after 8 hours, no persistence needed)
- Temporary files in `/tmp`

---

## Restore Procedure

1. Stop the backend process:
   ```bash
   pkill -f uvicorn
   ```

2. Replace the database file:
   ```bash
   cp ~/backups/aafc_tms_YYYYMMDD.db backend/aafc_tms.db
   ```

3. Restart the backend:
   ```bash
   bash RUN_TMS_BACKEND_MAC.sh
   ```

4. Verify health:
   ```bash
   curl http://localhost:8000/api/health
   ```

---

## Clean Reset (for development)

```bash
rm -f backend/aafc_tms.db
bash RUN_TMS_BACKEND_MAC.sh
```

This triggers `seed_all()` on startup and restores all demo data including the 703 SQN planning year and WA 2026 holidays.

---

## Production Recommendations

For a production deployment:

1. Use PostgreSQL instead of SQLite
2. Enable WAL (Write-Ahead Logging) or streaming replication
3. Use `pg_dump` on a cron schedule
4. Store backups in a separate failure domain (S3, NAS)
5. Test restore quarterly

---

## Data Retention

Audit logs are append-only. Delete operations in the application use soft-delete (`is_archived = True`) rather than physical deletion, preserving the audit trail.
