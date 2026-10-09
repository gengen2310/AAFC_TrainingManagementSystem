#!/usr/bin/env bash
# PreToolUse(Bash) guard: refuse commands that would act on PRODUCTION.
# Production deployment and production data changes need a separate, explicit
# human approval naming the exact commit (see .claude/skills/beta-release), so
# an agent must never be able to reach production by accident.
#
# Reads the hook payload on stdin; denies via permissionDecision JSON.
# Staging (env 77a45568-...) and local commands pass through untouched.
set -euo pipefail

cmd=$(jq -r '.tool_input.command // ""')

PROD_ENV_ID='571a8028-3640-4542-a4ab-7a1ee6b1f693'

deny() {
  jq -n --arg r "Blocked by .claude/hooks/guard_prod.sh: $1. Production actions need explicit human approval and must be run by a person." \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  exit 0
}

case "$cmd" in
  *"$PROD_ENV_ID"*) deny "command references the production Railway environment id" ;;
  *deploy-production.sh*) deny "command runs the production deploy script" ;;
esac

# --environment production / --environment=production / -e production (railway CLI)
if printf '%s' "$cmd" | grep -Eq -- '(--environment[= ]+|(^|[[:space:]])-e[[:space:]]+)["'"'"']?(production|prod)["'"'"']?([[:space:]]|$)'; then
  deny "command targets the production environment"
fi

# Destructive seeding/reset against anything other than local SQLite.
if printf '%s' "$cmd" | grep -Eq 'seed_all|reset_db'; then
  if printf '%s' "$cmd" | grep -Eqi 'postgres(ql)?://|railway[[:space:]]+(run|connect|ssh)|DATABASE_URL=[^s[:space:]]'; then
    deny "seed_all/reset_db would run against a non-SQLite database"
  fi
fi

exit 0
