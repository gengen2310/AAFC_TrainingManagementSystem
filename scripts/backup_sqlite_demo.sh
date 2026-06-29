#!/usr/bin/env bash
# backup_sqlite_demo.sh — create a timestamped copy of the local SQLite demo database.
# Run from the project root directory.
#
# Usage:
#   bash scripts/backup_sqlite_demo.sh
#
# Output: backups/aafc_tms_backup_YYYYMMDD_HHMMSS.db

set -euo pipefail

DB_PATH="backend/aafc_tms.db"
BACKUP_DIR="backups"

if [ ! -f "$DB_PATH" ]; then
  echo "ERROR: Database not found at $DB_PATH"
  echo "Start the backend first to create the database."
  exit 1
fi

mkdir -p "$BACKUP_DIR"
TS=$(date +%Y%m%d_%H%M%S)
DEST="$BACKUP_DIR/aafc_tms_backup_${TS}.db"

cp "$DB_PATH" "$DEST"
SIZE=$(du -sh "$DEST" | cut -f1)

echo "Backup created: $DEST ($SIZE)"
echo
echo "To restore (local demo only):"
echo "  cp $DEST $DB_PATH"
echo "  Then restart the backend."
echo
echo "WARNING: SQLite file-copy backup is for local demo only."
echo "Production deployments must use managed PostgreSQL backups."
