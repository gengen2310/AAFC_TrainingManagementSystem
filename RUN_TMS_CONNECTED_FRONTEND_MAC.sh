#!/usr/bin/env bash
# AAFC TMS — Connected single-file client (alternative to the React frontend).
# Serves a locally-patched copy of connected-frontend/index.html on
# http://localhost:8080, pointed at the local backend.
# Pre-req: run RUN_TMS_BACKEND_MAC.sh first (the backend script's own CORS
# config already allows origin 8080).
#
# The deployed image's docker-entrypoint.sh always rewrites
# <meta name="aafc-api-base"> from AAFC_API_BASE. This script performs the
# same substitution on a *copy* (never the checked-in file), so a local run
# always talks to the backend you name -- by default http://localhost:8000,
# or set AAFC_API_BASE (e.g. AAFC_API_BASE=http://localhost:8002) when that
# port is taken. (See docs/beta/qualification_gap_register.md GAP-11.)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$SCRIPT_DIR/connected-frontend"
SERVE_DIR="$SRC_DIR/.local-dev"
API_BASE="${AAFC_API_BASE:-http://localhost:8000}"

rm -rf "$SERVE_DIR"
mkdir -p "$SERVE_DIR"
# Serve exactly what the production image serves (connected-frontend/Dockerfile
# COPYs into /usr/share/nginx/html/): index.html plus the extracted js/ modules.
# Without js/, openModal/promptText are undefined and every dialog fails.
# frontend/src/tests/connectedFrontendParses.test.ts fails if the two drift.
cp "$SRC_DIR/index.html" "$SERVE_DIR/index.html"
cp -R "$SRC_DIR/js" "$SERVE_DIR/js"
sed -i.bak \
  "s|<meta name=\"aafc-api-base\" content=\"[^\"]*\">|<meta name=\"aafc-api-base\" content=\"${API_BASE}\">|" \
  "$SERVE_DIR/index.html"
rm -f "$SERVE_DIR/index.html.bak"

echo "Connected client: http://localhost:8080   (login code: ADMIN703)"
echo "API base patched to ${API_BASE} for this local run only (source file untouched)."
cd "$SERVE_DIR"
exec python3 -m http.server 8080
