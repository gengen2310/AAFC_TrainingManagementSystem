#!/usr/bin/env bash
# Deletes accumulated E2E fixture planning years (year >= 3000) from the dev DB.
# These accumulate because seedSession() creates years in range 3000-3999 and
# the old afterAll hook only cleaned up parade nights, not years.
#
# Each fixture year in the DB costs one extra /api/planning/years/:id/holidays
# API call inside loadData(). With 226 fixture years, loadData() fires 180
# requests per call -- exceeding the 300 req/60s rate limit when two
# reloadAndRender() calls run in sequence, causing parade nights to return
# empty (p_pns silently catches the 429 and returns []).
#
# Run from repo root: bash frontend/scripts/cleanup-fixture-years.sh
set -euo pipefail

BASE="${E2E_BACKEND_BASE_URL:-http://localhost:8000}"
ADMIN_CODE="ADMIN703"

echo "Connecting to $BASE ..."
USER_ID=$(curl -sf -X POST "$BASE/api/auth/lookup" \
  -H "Content-Type: application/json" \
  -d '{"unit_type":"squadron","identifier":"703","role":"sqn_admin"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['user_id'])")

TOKEN=$(curl -sf -X POST "$BASE/api/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"code\":\"$ADMIN_CODE\",\"user_id\":\"$USER_ID\"}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('token') or d.get('access_token',''))")

echo "Fetching planning years ..."
YEARS=$(curl -sf "$BASE/api/planning/years?include_unmaterialised=true" \
  -H "Authorization: Bearer $TOKEN")

FIXTURE_IDS=$(echo "$YEARS" | python3 -c "
import sys, json
years = json.load(sys.stdin)
ids = [y['planning_year_id'] for y in years if y.get('year', 0) >= 3000 and y.get('planning_year_id')]
print('\n'.join(ids))
")

COUNT=$(echo "$FIXTURE_IDS" | grep -c . || true)
echo "Found $COUNT fixture years (year >= 3000) to delete ..."

DELETED=0
FAILED=0
while IFS= read -r yid; do
  [ -z "$yid" ] && continue
  STATUS=$(curl -sf -o /dev/null -w "%{http_code}" -X DELETE \
    "$BASE/api/planning/years/$yid" \
    -H "Authorization: Bearer $TOKEN" 2>/dev/null || echo "000")
  if [[ "$STATUS" == "200" || "$STATUS" == "204" ]]; then
    DELETED=$((DELETED + 1))
  else
    FAILED=$((FAILED + 1))
  fi
done <<< "$FIXTURE_IDS"

echo "Done: deleted=$DELETED, failed=$FAILED"

# Report remaining holiday-fetch load
REMAINING=$(curl -sf "$BASE/api/planning/years?include_unmaterialised=true" \
  -H "Authorization: Bearer $TOKEN" | python3 -c "
import sys, json
years = json.load(sys.stdin)
active = [y for y in years if y.get('active_status') and y.get('planning_year_id') and y.get('state') != 'past']
print(len(active))
")
echo "Active non-past years remaining: $REMAINING"
echo "loadData() will now fire approx $((26 + REMAINING)) requests per call (limit: 300)"
