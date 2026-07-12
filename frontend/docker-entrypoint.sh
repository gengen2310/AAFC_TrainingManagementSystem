#!/bin/sh
set -e

# Railway injects PORT at runtime; default to 8080 if not set
PORT="${PORT:-8080}"

# Inject backend API URL into the Vite build's <meta name="aafc-api-base"> tag at startup.
# Primary: VITE_API_BASE_URL (matches the React client.ts env variable).
# Fallback: AAFC_API_BASE (already set in Railway — no dashboard change required to deploy).
# Either variable pointing to the Railway backend URL will work.
API_BASE="${VITE_API_BASE_URL:-${AAFC_API_BASE:-}}"
if [ -n "$API_BASE" ]; then
    sed -i \
        "s|<meta name=\"aafc-api-base\" content=\"[^\"]*\">|<meta name=\"aafc-api-base\" content=\"${API_BASE}\">|" \
        /usr/share/nginx/html/index.html
fi

# Inject module mode — when MODULE_MODE=true, replace login form with "Return to TMS" message.
if [ "${MODULE_MODE:-false}" = "true" ]; then
    sed -i \
        's|<meta name="aafc-module-mode" content="">|<meta name="aafc-module-mode" content="true">|' \
        /usr/share/nginx/html/index.html
fi

# Inject runtime port into nginx config
sed -i "s/__PORT__/${PORT}/g" /etc/nginx/conf.d/default.conf

exec nginx -g "daemon off;"
