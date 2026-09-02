#!/usr/bin/env bash
# What commit is staging actually running?
#
# Read-only. No credentials, no Railway CLI, no deploy. Two curls and a compare.
#
#     bash scripts/verify-deployed-build.sh            # against local HEAD
#     bash scripts/verify-deployed-build.sh <sha>      # against a specific commit
#
# This exists because the question was, until now, only answerable by running a
# full deployment. On 2026-09-02 a deploy was believed to have succeeded while
# every staging service was still serving the previous day's build; finding that
# out took a hand-assembled sequence of curl, header inspection and
# `railway deployment list`. The deploy script's own comment records the same
# class of surprise on 2026-08-23 -- services "serving code from that morning
# while reporting commits from 11 August, 413 commits behind".
#
# Covers the two services that publish a build fingerprint. The backend's
# revision endpoint (/api/system/migrations) needs authentication, so this
# reports its liveness only and says so rather than implying more.
set -uo pipefail

GRN=$'\033[0;32m'; RED=$'\033[0;31m'; YLW=$'\033[0;33m'; NC=$'\033[0m'

FRONTEND="https://aafc-tms-frontend-staging.up.railway.app"
PW="https://aafc-tms-planning-workspace-preview-staging.up.railway.app"
BACKEND="https://aafc-tms-backend-staging.up.railway.app"

TARGET="${1:-$(git rev-parse HEAD 2>/dev/null)}"
TARGET_SHORT="${TARGET:0:8}"
[ -z "$TARGET" ] && { echo "No target commit: pass one, or run inside a git repo."; exit 2; }

echo
echo "  expecting: $TARGET_SHORT  ($(git log -1 --format=%s "$TARGET" 2>/dev/null || echo 'unknown commit'))"
echo

rc=0
check() {
  local url="$1" label="$2" body served stamp age_note
  # Cache-bust and refuse a cached answer: a stale reply here is the exact
  # failure this script exists to catch.
  body=$(curl -s -m 30 -H 'Cache-Control: no-cache' "$url/index.html?cb=$$" 2>/dev/null)
  if [ -z "$body" ]; then
    printf "  %-10s %sUNREACHABLE%s\n" "$label" "$RED" "$NC"; rc=1; return
  fi
  served=$(printf '%s' "$body" | grep -o 'name="app-build" content="[^"]*"' | head -1 \
           | sed -E 's/.*content="([^"|]*).*/\1/')
  stamp=$(printf '%s' "$body" | grep -o 'name="app-build" content="[^"]*"' | head -1 \
           | sed -E 's/.*\|([^"]*)".*/\1/')
  if [ -z "$served" ]; then
    printf "  %-10s %sNO FINGERPRINT%s — cannot identify the running build\n" "$label" "$RED" "$NC"; rc=1; return
  fi
  if [ "$served" = "$TARGET" ] || [ "${served:0:8}" = "$TARGET_SHORT" ]; then
    printf "  %-10s %sMATCH%s   %s  built %s\n" "$label" "$GRN" "$NC" "${served:0:8}" "$stamp"
  else
    printf "  %-10s %sSTALE%s   serving %s  built %s\n" "$label" "$RED" "$NC" "${served:0:8}" "$stamp"
    printf "  %-10s         expected %s\n" "" "$TARGET_SHORT"
    rc=1
  fi
}

check "$FRONTEND" "frontend"
check "$PW"       "pw"

code=$(curl -s -m 20 -o /dev/null -w '%{http_code}' "$BACKEND/api/health" 2>/dev/null)
if [ "$code" = "200" ]; then
  printf "  %-10s %sup%s      (liveness only — the revision endpoint needs auth,\n" "backend" "$YLW" "$NC"
  printf "  %-10s         so this says nothing about which commit it runs)\n" ""
else
  printf "  %-10s %sHTTP %s%s\n" "backend" "$RED" "$code" "$NC"; rc=1
fi

echo
if [ "$rc" = 0 ]; then
  echo "  ${GRN}Staging is serving $TARGET_SHORT.${NC}"
else
  echo "  ${RED}Staging is NOT serving $TARGET_SHORT.${NC} A deploy that reported success did not land."
fi
exit $rc
