#!/usr/bin/env bash
# Test matrix for guard_prod.sh. Run: bash .claude/hooks/test_guard_prod.sh
# Runs under /bin/bash (macOS 3.2) on purpose: that is what the hook gets.
set -u
H="$(cd "$(dirname "$0")" && pwd)/guard_prod.sh"
pass=0; fail=0
t(){ out=$(printf '%s' "$2" | /bin/bash "$H" 2>/dev/null); rc=$?
  if [ $rc = 2 ]; then d=block; elif [ $rc != 0 ]; then d="rc$rc"; elif [ -z "$out" ]; then d=allow
  else d=$(printf '%s' "$out" | jq -r .hookSpecificOutput.permissionDecision); fi
  if [ "$d" = "$1" ]; then pass=$((pass+1)); else fail=$((fail+1)); printf 'FAIL expect=%s got=%s | %.80s\n' "$1" "$d" "${3:-$2}"; fi; }
j(){ jq -cn --arg c "$1" '{tool_name:"Bash",tool_input:{command:$c}}'; }
PAD=$(head -c 300000 /dev/zero | tr '\0' 'x')

# Fails closed on bad input.
t block '{"tool_input":{"command":"x"}' malformed
t block 'not json' notjson

# Production: denied, whatever the spelling.
for c in 'railway up --environment 571a8028-3640-4542-a4ab-7a1ee6b1f693' 'railway connect Postgres --environment production' \
 'railway logs --environment=production' 'railway variables -e prod' 'bash scripts/deploy-production.sh' \
 'DATABASE_URL=postgresql://u:p@h/db python -m app.seeds.seed_all' 'railway run python -c "from app.seeds.seed_all import reset_db; reset_db()"' \
 'railway environment production' 'railway link --project f5d9524f --environment prod' 'railway env prod' \
 'railway up -eproduction' 'railway up --environment PRODUCTION' $'railway up --environment\\\nproduction' \
 "railway up --environment 'prod'" 'railway up --environment="production"' 'RAILWAY up -e Production' \
 'cd x && railway up --service backend --environment production --detach' 'bash scripts/DEPLOY-PRODUCTION.sh'; do
  t deny "$(j "$c")" "$c"; done
# A long command must not turn a match into a miss (no pipelines in the hook).
t deny "$(j "railway up --environment production # $PAD")" "env flag+300KB"
t deny "$(j "DATABASE_URL=postgresql://h/db python -m app.seeds.seed_all # $PAD")" "seed+300KB"

# Staging and local work: allowed.
for c in 'railway connect Postgres --environment 77a45568-5c16-46c2-9065-d5d339208b0e' 'railway status --environment staging' \
 'railway environment staging' 'railway link --project f5d9524f-8a57-44ff-86b7-ab66aec00e73 --environment 77a45568-5c16-46c2-9065-d5d339208b0e' \
 'DATABASE_URL=sqlite:///./dev.db python -m app.seeds.seed_all' 'python -m pytest tests/ -q' 'git log --oneline -5' \
 'grep -rn production docs/' 'cat docs/release/production_release_runbook.md' 'npm run build -- --mode production' 'railway status --json'; do
  t allow "$(j "$c")" "$c"; done
t allow '{"tool_name":"Bash","tool_input":{}}' nocommand

# An internal shell error (bash 3.2 reports it to EXIT with $? = 0) still blocks.
tmp=$(mktemp); sed 's/^raw=\(.*\)$/raw=\1\nbroken=${raw,,}/' "$H" > "$tmp"
printf '%s' "$(j 'git status')" | /bin/bash "$tmp" 2>/dev/null; rc=$?; rm -f "$tmp"
if [ $rc = 2 ]; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL injected shell error rc=$rc (expected 2)"; fi

echo "guard_prod.sh: pass=$pass fail=$fail"
[ $fail = 0 ]
