#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p backups
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT="backups/trustlens-${STAMP}.dump"
docker compose -f docker/compose/docker-compose.dev.yml exec -T postgres \
  pg_dump -U trustlens -Fc trustlens > "$OUT"
echo "==> Wrote $OUT ($(du -h "$OUT" | cut -f1))"
