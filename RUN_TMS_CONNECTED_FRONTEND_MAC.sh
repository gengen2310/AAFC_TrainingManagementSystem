#!/usr/bin/env bash
# AAFC TMS — Connected single-file client (alternative to the React frontend).
# Serves a locally-patched copy of connected-frontend/index.html on
# http://localhost:8080, pointed at the local backend.
# Pre-req: run RUN_TMS_BACKEND_MAC.sh first (the backend script's own CORS
# config already allows origin 8080).
#
# connected-frontend/index.html's checked-in <meta name="aafc-api-base">
# default points at the production backend on purpose -- Railway's
# docker-entrypoint.sh always overwrites it from AAFC_API_BASE on a real
# deploy, so the checked-in value only ever matters for this kind of
# unbuilt local run. This script patches a *copy* (never the checked-in
# file) to point at http://localhost:8000, the same substitution
# docker-entrypoint.sh performs for a real deploy -- so local dev talks to
# the local backend by default instead of silently hitting production.
# (See docs/beta/qualification_gap_register.md GAP-11.)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$SCRIPT_DIR/connected-frontend"
SERVE_DIR="$SRC_DIR/.local-dev"

rm -rf "$SERVE_DIR"
mkdir -p "$SERVE_DIR"
cp "$SRC_DIR/index.html" "$SERVE_DIR/index.html"
sed -i.bak \
  's|<meta name="aafc-api-base" content="[^"]*">|<meta name="aafc-api-base" content="http://localhost:8000">|' \
  "$SERVE_DIR/index.html"
rm -f "$SERVE_DIR/index.html.bak"

echo "Connected client: http://localhost:8080   (login code: ADMIN703)"
echo "API base patched to http://localhost:8000 for this local run only (source file untouched)."
cd "$SERVE_DIR"
exec python3 -m http.server 8080
