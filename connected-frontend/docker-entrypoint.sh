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

exec nginx -g "daemon off;"
