#!/usr/bin/env bash
# Verify a running production stack, from outside it.
#
# `docker compose ps` says whether containers are up. Up is not the same as
# working: the API can be listening while the database is unreachable, and the
# worker can be running while consuming nothing. This checks what a user would
# actually experience.
#
#   make prod-check
set -uo pipefail

WEB=${WEB_BASE_URL:-http://localhost:3000}
ADMIN=${ADMIN_BASE_URL:-http://localhost:3001}
API=${API_BASE_URL:-http://localhost:8000}

pass=0
fail=0

check() {
  local name="$1" expected="$2" url="$3"
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$url" 2>/dev/null || echo 000)
  if [ "$code" = "$expected" ]; then
    printf '  \033[32mOK\033[0m    %-38s %s\n' "$name" "$code"
    pass=$((pass + 1))
  else
    printf '  \033[31mFAIL\033[0m  %-38s got %s, wanted %s\n' "$name" "$code" "$expected"
    fail=$((fail + 1))
  fi
}

echo ""
echo "==> Checking the running stack"
echo ""

check "API alive"                200 "$API/health/live"
check "API ready (db + redis)"   200 "$API/health/ready"
check "Seller app"               200 "$WEB/"
check "Admin app"                200 "$ADMIN/login"
check "Public API status"        200 "$API/public/v1/status"
# Anonymous, no key: this is the buyer page's own route (P0-12).
check "Buyer score route"        404 "$API/api/v1/public/sellers/definitely-not-a-real-handle/trust-score"
# Must stay locked. If this returns 200 the partner API has lost its auth.
check "Partner API needs a key"  401 "$API/public/v1/sellers/any/trust-score"

echo ""
echo "==> Worker"
worker=$(curl -s --max-time 15 "$API/health/worker" 2>/dev/null || echo '')
if echo "$worker" | grep -q '"status": *"ok"'; then
  printf '  \033[32mOK\033[0m    worker is consuming jobs\n'
  pass=$((pass + 1))
elif echo "$worker" | grep -q '"status": *"unknown"'; then
  printf '  \033[33mIDLE\033[0m  no heartbeat yet - the worker has run no jobs since starting.\n'
  printf '        Not a failure on a fresh stack. Register a user, then re-check.\n'
else
  printf '  \033[31mFAIL\033[0m  worker heartbeat is stale: %s\n' "$worker"
  fail=$((fail + 1))
fi

echo ""
if [ "$fail" -eq 0 ]; then
  printf '\033[32m==> %s checks passed. The stack is serving.\033[0m\n\n' "$pass"
  exit 0
fi
printf '\033[31m==> %s passed, %s FAILED.\033[0m\n' "$pass" "$fail"
echo "    make prod-logs     to see why"
echo "    make prod-ps       to see which container is unhealthy"
echo ""
exit 1
