#!/usr/bin/env bash
# Take a database backup (P9-08).
#
#   bash scripts/db-backup.sh              # from whichever stack is running
#   bash scripts/db-backup.sh --stack prod
#
# Custom format (-Fc), not plain SQL: it is compressed, and pg_restore can
# read it selectively and in parallel. A plain dump of this schema restores as
# one long serial transaction.
#
# An untested backup is not a backup. `scripts/db-restore.sh --verify` proves
# this file can actually be read back, and `make prod-backup-verify` runs the
# whole loop into a scratch database.
set -euo pipefail
cd "$(dirname "$0")/.."

STACK=auto
KEEP=${BACKUP_KEEP:-10}

while [ $# -gt 0 ]; do
  case "$1" in
    --stack) STACK="$2"; shift 2 ;;
    --keep)  KEEP="$2";  shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

# Which stack is actually up? Guessing wrong backs up an empty database and
# reports success, which is worse than failing.
detect_stack() {
  if docker ps --format '{{.Names}}' | grep -q '^trustlens-postgres-1$\|^trustlens-postgres$'; then
    if docker compose -f docker/compose/docker-compose.prod.yml ps --status running 2>/dev/null \
        | grep -q postgres; then
      echo prod; return
    fi
  fi
  echo dev
}
[ "$STACK" = auto ] && STACK=$(detect_stack)

case "$STACK" in
  prod)
    COMPOSE="docker compose -f docker/compose/docker-compose.prod.yml --env-file .env.production"
    # Read the real credentials rather than assuming the defaults.
    DB_USER=$(grep -E '^POSTGRES_USER=' .env.production | cut -d= -f2-)
    DB_NAME=$(grep -E '^POSTGRES_DB=' .env.production | cut -d= -f2-)
    ;;
  dev)
    COMPOSE="docker compose -f docker/compose/docker-compose.dev.yml"
    DB_USER=trustlens
    DB_NAME=trustlens
    ;;
  *) echo "unknown stack: $STACK (want dev or prod)" >&2; exit 2 ;;
esac

mkdir -p backups
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT="backups/trustlens-${STACK}-${STAMP}.dump"

echo "==> Backing up the $STACK stack ($DB_NAME as $DB_USER)"
$COMPOSE exec -T postgres pg_dump -U "$DB_USER" -Fc "$DB_NAME" > "$OUT"

# A pg_dump that fails mid-stream still leaves a file behind, and shell
# redirection has already created it. Refuse to call that a backup.
SIZE=$(wc -c < "$OUT")
if [ "$SIZE" -lt 1024 ]; then
  echo "!! Backup is only ${SIZE} bytes - treating as failed" >&2
  rm -f "$OUT"
  exit 1
fi

# Prove it is readable now, not on the day it is needed.
if ! pg_restore --list "$OUT" >/dev/null 2>&1; then
  if ! docker run --rm -i postgres:16-alpine pg_restore --list < "$OUT" >/dev/null 2>&1; then
    echo "!! Backup is not readable by pg_restore - treating as failed" >&2
    rm -f "$OUT"
    exit 1
  fi
fi

echo "==> Wrote $OUT ($(du -h "$OUT" | cut -f1)), table of contents verified"

# Keep the last N. Unbounded backups fill the disk that the database is on,
# which turns a backup policy into an outage.
COUNT=$(ls -1 backups/trustlens-*.dump 2>/dev/null | wc -l)
if [ "$COUNT" -gt "$KEEP" ]; then
  ls -1t backups/trustlens-*.dump | tail -n +$((KEEP + 1)) | while read -r old; do
    echo "    pruning $old"
    rm -f "$old"
  done
fi
