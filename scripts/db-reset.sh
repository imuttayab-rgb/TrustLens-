#!/usr/bin/env bash
# DESTRUCTIVE: drop, recreate, migrate and seed the development database.
set -euo pipefail
cd "$(dirname "$0")/.."
source .env 2>/dev/null || true
if [ "${ENV:-development}" = "production" ]; then
  echo "!! Refusing to reset a production database." >&2; exit 1
fi
read -rp "This deletes ALL local data. Type 'reset' to continue: " confirm
[ "$confirm" = "reset" ] || { echo "Aborted."; exit 1; }

COMPOSE="docker compose -f docker/compose/docker-compose.dev.yml"
$COMPOSE exec -T postgres psql -U trustlens -d postgres -c "DROP DATABASE IF EXISTS trustlens WITH (FORCE);"
$COMPOSE exec -T postgres psql -U trustlens -d postgres -c "CREATE DATABASE trustlens OWNER trustlens;"
make migrate seed seed-demo
echo "==> Database reset complete"
