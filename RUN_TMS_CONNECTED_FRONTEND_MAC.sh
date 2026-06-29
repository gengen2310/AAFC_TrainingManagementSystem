#!/usr/bin/env bash
# AAFC TMS — Connected single-file client (alternative to the React frontend).
# Serves connected-frontend/index.html on http://localhost:8080.
# Pre-req: run RUN_TMS_BACKEND_MAC.sh first. The client points at http://localhost:8000
# via <meta name="aafc-api-base">. The backend must allow origin 8080 (the backend
# script above already does).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/connected-frontend"
echo "Connected client: http://localhost:8080   (login code: ADMIN703)"
exec python3 -m http.server 8080
