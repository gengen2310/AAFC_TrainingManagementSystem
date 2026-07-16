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

exec nginx -g "daemon off;"
