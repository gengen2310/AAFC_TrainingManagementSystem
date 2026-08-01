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

# Inject the connected-frontend TMS URL so "Return to TMS" links are environment-aware.
# Set AAFC_TMS_BASE to the URL of the connected-frontend service for this environment.
# Example staging: https://aafc-tms-frontend-staging.up.railway.app
if [ -n "${AAFC_TMS_BASE:-}" ]; then
    sed -i \
        "s|<meta name=\"aafc-tms-base\" content=\"[^\"]*\">|<meta name=\"aafc-tms-base\" content=\"${AAFC_TMS_BASE}\">|" \
        /usr/share/nginx/html/index.html
fi

# Inject runtime port into nginx config
sed -i "s/__PORT__/${PORT}/g" /etc/nginx/conf.d/default.conf

# Inject the CSP connect-src origin — the backend this app actually calls. Falls back to
# https: (any HTTPS origin) if neither VITE_API_BASE_URL nor AAFC_API_BASE is set, mirroring
# connected-frontend's nginx.conf fallback behaviour for the same placeholder.
CSP_CONNECT_SRC="${API_BASE:-https:}"
sed -i \
    "s#__CSP_CONNECT_SRC__#${CSP_CONNECT_SRC}#" \
    /etc/nginx/conf.d/default.conf

# Inject build fingerprint (commit SHA | build timestamp).
# RAILWAY_GIT_COMMIT_SHA is provided by Railway at runtime; falls back to "local" in dev.
BUILD_SHA="${RAILWAY_GIT_COMMIT_SHA:-local}"
BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
sed -i \
  "s#<meta name=\"app-build\" content=\"__APP_BUILD__\">#<meta name=\"app-build\" content=\"${BUILD_SHA}|${BUILD_TIME}\">#" \
  /usr/share/nginx/html/index.html

# Create /version.json for programmatic fingerprint verification
cat > /usr/share/nginx/html/version.json <<EOF
{"commit":"${BUILD_SHA}","source":"frontend","built":"${BUILD_TIME}"}
EOF

# Production deployment guard: refuse to start if this environment is production
# but the resolved config still points at a staging/local target. Only checks the
# actual injected meta-tag lines, not the whole file -- index.html's own template
# comments give "e.g. http://localhost:8000" as operator guidance, which is not a
# live config value and must not trip this guard. Cheaper than discovering it live
# in a user's browser -- see qualification_gap_register.md GAP-20 for the incident
# this guard exists to prevent from recurring silently.
if [ "${RAILWAY_ENVIRONMENT_NAME:-}" = "production" ]; then
  META_LINES="$(grep -E '<meta name="aafc-(api-base|tms-base)"' /usr/share/nginx/html/index.html)"
  for forbidden in "backend-staging" "frontend-staging" "planning-workspace-preview-staging" "localhost" "127.0.0.1"; do
    if echo "$META_LINES" | grep -q "$forbidden"; then
      echo "[entrypoint] FATAL: production build's resolved config contains forbidden reference '${forbidden}' — refusing to start." >&2
      echo "$META_LINES" >&2
      exit 1
    fi
  done
  # aafc-api-base specifically must resolve to a real, non-empty, fully-substituted
  # value -- an empty content="" (neither VITE_API_BASE_URL nor AAFC_API_BASE set)
  # or a leftover "__"-style placeholder (matching this file's own __PORT__/
  # __CSP_CONNECT_SRC__/__APP_BUILD__ convention) is exactly as dangerous as
  # pointing at the wrong environment.
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
  # The checks above are a blocklist (reject known-bad substrings) and, on
  # their own, only catch values someone thought to list -- an unlisted
  # mistake (a typo'd domain, a plain http:// URL, an IP address, a bare
  # hostname) would silently pass. Require the shape of a real production
  # HTTPS URL as a positive check on top, not just the absence of a known-bad
  # one.
  case "$API_BASE_VALUE" in
    https://*.*) : ;;
    *)
      echo "[entrypoint] FATAL: production build's resolved aafc-api-base ('${API_BASE_VALUE}') does not look like a production HTTPS URL — refusing to start." >&2
      exit 1
      ;;
  esac
fi

exec nginx -g "daemon off;"
