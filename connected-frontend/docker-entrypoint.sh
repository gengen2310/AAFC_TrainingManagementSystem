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

# Inject the runtime port into the nginx config
sed -i "s/__PORT__/${PORT}/g" /etc/nginx/conf.d/default.conf

exec nginx -g "daemon off;"
