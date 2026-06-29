#!/usr/bin/env bash
# AAFC Training Management System (TMS) — Backend run script (macOS/Linux).
# Purpose: start the FastAPI backend (Backend Source of Truth) for local pilot testing.
# Usage:   bash RUN_TMS_BACKEND_MAC.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/backend"

# 1. Virtual environment
if [ ! -d ".venv" ]; then python3 -m venv .venv; fi
# shellcheck disable=SC1091
source .venv/bin/activate

# 2. Dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# 3. Seed the database on first run (creates the dev SQLite DB).
if [ ! -f "aafc_tms.db" ]; then
  echo "Seeding database..."
  python manage.py --seed
fi

# 4. Run. CORS allows the React frontend (5173) and the connected client (8080).
export CORS_ALLOWED_ORIGINS="http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080"
export PORT="${PORT:-8000}"
echo "Backend Source of Truth: http://localhost:${PORT}"
echo "Health: http://localhost:${PORT}/api/health"
exec python manage.py --reload
