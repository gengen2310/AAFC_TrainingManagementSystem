#!/bin/sh
set -e

# Railway injects PORT; default to 8080 if not set
PORT="${PORT:-8080}"

# Optional: override the backend API URL without editing index.html.
# Set AAFC_API_BASE in Railway's environment variables panel.
# Example: https://aafc-tms-backend-staging.onrender.com
if [ -n "$AAFC_API_BASE" ]; then
  sed -i \
    "s|<meta name=\"aafc-api-base\" content=\"[^\"]*\">|<meta name=\"aafc-api-base\" content=\"${AAFC_API_BASE}\">|" \
    /usr/share/nginx/html/index.html
fi

# Inject the Planning Workspace URL so the nav link points to the correct environment.
# Set AAFC_PW_BASE in Railway's environment variables panel.
# Example staging: https://aafc-tms-planning-workspace-preview-staging.up.railway.app/planning
if [ -n "${AAFC_PW_BASE:-}" ]; then
  sed -i \
    "s|<meta name=\"aafc-pw-base\" content=\"[^\"]*\">|<meta name=\"aafc-pw-base\" content=\"${AAFC_PW_BASE}\">|" \
    /usr/share/nginx/html/index.html
fi

# Inject the runtime port into the nginx config
sed -i "s/__PORT__/${PORT}/g" /etc/nginx/conf.d/default.conf

# Inject CSP connect-src: if AAFC_API_BASE is set, allow that specific origin;
# otherwise fall back to 'https:' (all HTTPS origins) so the app still works.
CSP_CONNECT="${AAFC_API_BASE:-https:}"
sed -i "s|__CSP_CONNECT_SRC__|${CSP_CONNECT}|g" /etc/nginx/conf.d/default.conf

# Inject build fingerprint (commit SHA | build timestamp) into the app-build meta tag.
# RAILWAY_GIT_COMMIT_SHA is provided by Railway at runtime; falls back to "local" in dev.
BUILD_SHA="${RAILWAY_GIT_COMMIT_SHA:-local}"
BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
sed -i \
  "s#<meta name=\"app-build\" content=\"__APP_BUILD__\">#<meta name=\"app-build\" content=\"${BUILD_SHA}|${BUILD_TIME}\">#" \
  /usr/share/nginx/html/index.html

# Create /version.json for programmatic fingerprint verification
cat > /usr/share/nginx/html/version.json <<EOF
{"commit":"${BUILD_SHA}","source":"connected-frontend","built":"${BUILD_TIME}"}
EOF

# Production deployment guard: refuse to start if this environment is production
# but the resolved config still points at a staging/local target. Only checks the
# actual injected meta-tag lines, not the whole file -- index.html's own JS has
# legitimate dev-mode-detection code referencing "localhost", which is not a live
# config value and must not trip this guard. Cheaper than discovering it live in
# a user's browser -- see qualification_gap_register.md GAP-20 for the incident
# this guard exists to prevent from recurring silently.
if [ "${RAILWAY_ENVIRONMENT_NAME:-}" = "production" ]; then
  META_LINES="$(grep -E '<meta name="aafc-(api-base|pw-base)"' /usr/share/nginx/html/index.html)"
  for forbidden in "backend-staging" "frontend-staging" "planning-workspace-preview-staging" "localhost" "127.0.0.1"; do
    if echo "$META_LINES" | grep -q "$forbidden"; then
      echo "[entrypoint] FATAL: production build's resolved config contains forbidden reference '${forbidden}' — refusing to start." >&2
      echo "$META_LINES" >&2
      exit 1
    fi
  done
  # aafc-api-base specifically must resolve to a real, non-empty, fully-substituted
  # value -- an empty content="" (nothing ever set AAFC_API_BASE) or a leftover
  # "__"-style placeholder (matching this file's own __PORT__/__CSP_CONNECT_SRC__/
  # __APP_BUILD__ convention, in case a future refactor introduces one for this tag
  # too) is exactly as dangerous as pointing at the wrong environment.
  API_BASE_LINE="$(grep -E '<meta name="aafc-api-base"' /usr/share/nginx/html/index.html || true)"
  API_BASE_VALUE="$(echo "$API_BASE_LINE" | sed -n 's/.*content="\([^"]*\)".*/\1/p')"
  if [ -z "$API_BASE_VALUE" ]; then
    echo "[entrypoint] FATAL: production build's resolved aafc-api-base is empty — refusing to start." >&2
    exit 1
  fi
  if echo "$API_BASE_VALUE" | grep -q "__"; then
    echo "[entrypoint] FATAL: production build's resolved aafc-api-base looks like an unresolved placeholder ('${API_BASE_VALUE}') — refusing to start." >&2
    exit 1
  fi
fi

exec nginx -g "daemon off;"
