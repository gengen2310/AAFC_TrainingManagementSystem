#!/usr/bin/env bash
# Self-test of deploy-production.sh pre-deploy gates (backup freshness and
# verification, CORS origins, explicit API_RATE_LIMIT). No network: the script is
# sourced with DEPLOY_FUNCTIONS_ONLY=1 and only the gate functions are called.
cd "$(dirname "$0")/.."
DEPLOY_FUNCTIONS_ONLY=1 source scripts/deploy-production.sh
pass=0; fail=0; t(){ if eval "$2"; then pass=$((pass+1)); else fail=$((fail+1)); echo "FAIL: $1"; fi; }
now=$(date +%s); iso(){ python3 -c "import datetime,sys;print(datetime.datetime.fromtimestamp(float(sys.argv[1]),datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))" "$1"; }
B="$BACKUP_WORKFLOW_NAME"; R="$RESTORE_WORKFLOW_NAME"
good_b="{\"workflowName\":\"$B\",\"conclusion\":\"success\",\"createdAt\":\"$(iso $((now-3600)))\"}"
good_r="{\"workflowName\":\"$R\",\"conclusion\":\"success\",\"createdAt\":\"$(iso $((now-1800)))\"}"
t "fresh verified backup passes"            'check_backup_gate "$good_b" "$good_r" $now >/dev/null 2>&1'
t "stale backup (7 h) refused"              '! check_backup_gate "{\"workflowName\":\"$B\",\"conclusion\":\"success\",\"createdAt\":\"$(iso $((now-25200)))\"}" "$good_r" $now >/dev/null 2>&1'
t "failed backup refused"                   '! check_backup_gate "{\"workflowName\":\"$B\",\"conclusion\":\"failure\",\"createdAt\":\"$(iso $((now-3600)))\"}" "$good_r" $now >/dev/null 2>&1'
t "wrong workflow refused"                  '! check_backup_gate "{\"workflowName\":\"Backend Tests\",\"conclusion\":\"success\",\"createdAt\":\"$(iso $((now-3600)))\"}" "$good_r" $now >/dev/null 2>&1'
t "restore before backup refused"           '! check_backup_gate "$good_b" "{\"workflowName\":\"$R\",\"conclusion\":\"success\",\"createdAt\":\"$(iso $((now-7200)))\"}" $now >/dev/null 2>&1'
t "unreadable run details refused"          '! check_backup_gate "{}" "{}" $now >/dev/null 2>&1'
fe="https://$EXPECTED_PRODUCTION_FRONTEND_DOMAIN"; pw="https://$EXPECTED_PRODUCTION_PW_DOMAIN"
t "both origins + explicit limit pass"      'check_prod_config "$fe,$pw" 1200 >/dev/null'
t "spaces in origin list tolerated"         'check_prod_config "$fe, $pw" 300 >/dev/null'
t "missing PW origin refused"               '! check_prod_config "$fe" 1200 >/dev/null'
t "lookalike origin refused"                '! check_prod_config "$fe.evil.example,$pw" 1200 >/dev/null'
t "unset limit refused"                     '! check_prod_config "$fe,$pw" "" >/dev/null'
echo "prod gate tests: $pass passed, $fail failed"; [ $fail -eq 0 ]
