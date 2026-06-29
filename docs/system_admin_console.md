# AAFC TMS — System Admin Console

## Overview

The System Console is visible only to accounts with the `system_admin` role. It provides platform-level administration, maintenance controls, backup management, and audit visibility.

The system_admin account is distinct from national_admin:
- **national_admin** — operational national training management role
- **system_admin** — technical platform administration role

## Accessing the System Console

1. Log in using the system_admin access code
2. The System Console appears as the landing page
3. It is also accessible from the "System" section in the sidebar

## Sections

### System Overview

Shows:
- Application version and package version
- Environment (development / staging / production)
- Database type
- Wing, squadron, and user counts
- Maintenance mode status
- Last backup timestamp

### Platform Health

Shows:
- Backend status
- Database connection status
- Cookie security setting (should be `true` in production)
- Configured CORS origins

### Scope Map

Shows all Wings and their Squadrons/Specialist Units in the system. Inactive units are shown with a strikethrough indicator.

### Maintenance Mode

Allows system_admin to:
- Enable maintenance mode with a message and optional return time
- Disable maintenance mode

**Enabling maintenance mode requires typed confirmation:** `ENABLE MAINTENANCE`

When maintenance mode is enabled:
- The setting is stored in the `system_settings` database table
- Normal users can still log in (the frontend does not currently block — a production deployment should add a backend middleware check)
- The audit log records the change with timestamp and actor

### Backup

For **local demo (SQLite):**
- Click "Create Backup Now" to copy `backend/aafc_tms.db` to `backend/backups/aafc_tms_backup_YYYYMMDD_HHMMSS.db`
- Existing backups are listed with filename, size, and creation timestamp
- Triggered via `POST /api/system/backups`

For **production (PostgreSQL):**
- Browser backup is not available — use your managed PostgreSQL provider's backup tools
- See `docs/backup_and_restore.md`

### Recent Audit Activity

Shows the most recent audit log entries. Filterable by action type.

Does **not** include:
- Access code hashes or plaintext codes
- JWT secrets
- Database credentials

Audit log is **immutable** — system_admin cannot edit or delete entries through this interface.

## Endpoints

All require `system_admin` role:

| Method | Path | Description |
|---|---|---|
| GET | `/api/system/overview` | System overview stats |
| GET | `/api/system/health` | Platform health |
| GET | `/api/system/version` | App/package version |
| GET | `/api/system/migrations` | Expected migration head |
| GET | `/api/system/maintenance` | Maintenance mode state |
| POST | `/api/system/maintenance/enable` | Enable maintenance mode |
| POST | `/api/system/maintenance/disable` | Disable maintenance mode |
| GET | `/api/system/scope-map` | All wings and units |
| GET | `/api/system/backups` | List backups |
| POST | `/api/system/backups` | Create backup (SQLite only) |
| GET | `/api/system/audit-summary` | Audit log entries |

The `/api/system/audit-summary` endpoint also allows `auditor` role.

## Security

- All system endpoints require an authenticated session with `system_admin` role
- All state-changing actions are recorded in the audit log (action, timestamp, user_id)
- No access-code hashes or plaintext codes are returned
- No arbitrary SQL execution or shell access is exposed
- Maintenance mode confirmation requires exact typed string to prevent accidental enabling
- Backup restore requires manual file operation — no browser-based restore is provided

## Known limitations (V17)

- Maintenance mode does not currently block normal user logins in the frontend — a production deployment should enforce this via backend middleware
- Scope Management (Wing/Squadron create/archive) is available through the existing Organisations endpoints, not the System Console UI directly
- Account management at all scopes is available through the existing `/api/accounts` endpoints
- Browser-based restore is intentionally not implemented — restore via `scripts/backup_sqlite_demo.sh` instructions
