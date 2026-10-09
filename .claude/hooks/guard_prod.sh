#!/usr/bin/env bash
# PreToolUse(Bash) guard: refuse commands that would act on PRODUCTION.
# Production deployment and production data changes need a separate, explicit
# human approval naming the exact commit (see .claude/skills/beta-release), so
# an agent must never be able to reach production by accident.
#
# Reads the hook payload on stdin; denies via permissionDecision JSON.
# Staging (env 77a45568-...) and local commands pass through untouched.
#
# Fails CLOSED: any internal error (jq missing, malformed payload) exits 2,
# which Claude Code treats as a block; any other non-zero exit would let the
# command run. Matching uses bash [[ =~ ]] on a normalised copy of the command
# -- no pipelines, so no SIGPIPE/pipefail path can turn a match into a miss.
#
# Deliberately broad: any `railway` command mentioning production/prod as a
# word is refused rather than parsing CLI flag spellings (-eproduction,
# --environment=PRODUCTION, line continuations...). The cost is an occasional
# false positive on a harmless railway command; a person can run it instead.
# This is defence in depth, not a security boundary: shell indirection (an
# environment name held in a variable) is out of reach of any pattern match,
# so production credentials must still never be on this host.
set -euo pipefail
trap 'echo "guard_prod.sh: internal error; refusing the command (fail closed)" >&2; exit 2' ERR
# Shell-level errors bypass ERR, and on macOS /bin/bash 3.2 a bad
# substitution even reaches the EXIT trap with $? = 0. So exit codes are not
# trusted: only a deliberate decision sets decided=1; anything else blocks.
decided=0
trap 'if [ "$decided" != 1 ]; then echo "guard_prod.sh: did not reach a decision; refusing the command (fail closed)" >&2; exit 2; fi' EXIT
shopt -s nocasematch

raw=$(jq -er '.tool_input.command // ""')

deny() {
  jq -n --arg r "Blocked by .claude/hooks/guard_prod.sh: $1. Production actions need explicit human approval and must be run by a person." \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  decided=1
  exit 0
}

# Normalise: drop line continuations, flatten whitespace, then delete quotes
# and backslashes -- the shell rejoins rail""way / pro\duction into one word
# before running it, so the guard must too. (Case is ignored by nocasematch.)
cmd=${raw//$'\\\n'/ }
cmd=${cmd//[$'\n\t\r']/ }
cmd=${cmd//[\"\'\\]/}

prod_env_id='571a8028-3640-4542-a4ab-7a1ee6b1f693'
re_railway='(^|[^a-z0-9_])railway([^a-z0-9_]|$)'
re_prod_word='(^|[^a-z0-9_]|-e)(production|prod)([^a-z0-9_]|$)'
re_env_flag='(--environment[= ]+|(^|[[:space:]])-e[[:space:]]*)(production|prod)([^a-z0-9_]|$)'
re_deploy_glob='deploy-[^[:space:]]*[]*?[]'
re_seed='seed_all|reset_db'
re_explicit_sqlite='(^|[[:space:]])database_url=sqlite:'
# Any DATABASE_URL assignment whose value is not sqlite (a later assignment
# wins, so one sqlite URL does not vouch for the command).
re_other_db_url='(^|[[:space:]])database_url=([^s]|s[^q]|sq[^l]|sql[^i]|sqli[^t]|sqlit[^e]|sqlite[^:])'

if [[ $cmd == *"$prod_env_id"* ]]; then
  deny "command references the production Railway environment id"
fi
# deploy-prod covers deploy-production.sh; a glob over deploy-* could expand
# to it (scripts/ holds deploy-production.sh and deploy-staging.sh only).
if [[ $cmd == *deploy-prod* || $cmd =~ $re_deploy_glob ]]; then
  deny "command runs, or may glob-expand to, the production deploy script"
fi
# Any tool, not only railway: an explicit production environment flag.
if [[ $cmd =~ $re_env_flag ]]; then
  deny "command passes a production environment flag"
fi
if [[ $cmd =~ $re_railway && $cmd =~ $re_prod_word ]]; then
  deny "railway command mentions the production environment"
fi
# Allow-list, not deny-list: the target database may come from the
# environment, invisible here. Destructive seeding runs only when the command
# itself pins a local SQLite DATABASE_URL (every assignment), and never
# alongside any railway invocation (flags may precede run/connect/ssh).
if [[ $cmd =~ $re_seed ]] && { [[ ! $cmd =~ $re_explicit_sqlite ]] || [[ $cmd =~ $re_other_db_url ]] || [[ $cmd =~ $re_railway ]]; }; then
  deny "seed_all/reset_db is only allowed with an explicit DATABASE_URL=sqlite:... in the same command"
fi

decided=1
exit 0
