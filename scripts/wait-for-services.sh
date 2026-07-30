#!/usr/bin/env bash
# Block until the dev infrastructure is actually accepting connections.
set -euo pipefail
COMPOSE="docker compose -f docker/compose/docker-compose.dev.yml"
echo "==> Waiting for infrastructure..."
for i in $(seq 1 60); do
  if $COMPOSE ps --format json 2>/dev/null | grep -q '"Health":"starting"'; then sleep 1; continue; fi
  if $COMPOSE exec -T postgres pg_isready -U trustlens -d trustlens >/dev/null 2>&1 \
     && $COMPOSE exec -T redis redis-cli ping >/dev/null 2>&1; then
    echo "==> Infrastructure ready"; exit 0
  fi
  sleep 1
done
echo "!! Infrastructure did not become ready in 60s. Check: make logs" >&2
exit 1
