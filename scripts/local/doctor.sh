#!/usr/bin/env bash
# Readiness checks are bounded; failures show the service, never environment secrets.
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
require_docker
require_config
attempts=1
[[ "${1:-}" == '--wait' ]] && attempts=60
for ((i=1; i<=attempts; i++)); do
  if dc exec -T api curl -fsS http://localhost:8000/health/ready >/dev/null 2>&1 \
    && dc exec -T web curl -fsS http://localhost:3000/ >/dev/null 2>&1 \
    && dc exec -T admin curl -fsS http://localhost:3000/ >/dev/null 2>&1; then
    dc exec -T api python -m trustlens_api.modules.calling.doctor
    dc ps
    echo 'APPLICATION_HTTP_READY=PASS'
    exit 0
  fi
  [[ "$i" -eq "$attempts" ]] || sleep 3
done
dc ps
echo 'Readiness failed. Run: bash scripts/local/logs.sh' >&2
exit 1
