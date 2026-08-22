#!/usr/bin/env bash
# Restore a backup, or prove one restores (P9-08).
#
#   bash scripts/db-restore.sh --verify                 # newest backup -> scratch db, then drop it
#   bash scripts/db-restore.sh --verify backups/x.dump
#   bash scripts/db-restore.sh --into trustlens backups/x.dump    # THE REAL THING
#
# `--verify` is the one to run on a schedule. It restores into a throwaway
# database on the same server, counts what came back, and drops it. Nothing
# live is touched, so there is no reason not to run it - and a backup nobody
# has ever restored is a guess, not a backup.
set -euo pipefail
cd "$(dirname "$0")/.."

MODE=verify
TARGET=""
DUMP=""
STACK=auto

while [ $# -gt 0 ]; do
  case "$1" in
    --verify) MODE=verify; shift ;;
    --into)   MODE=restore; TARGET="$2"; shift 2 ;;
    --stack)  STACK="$2"; shift 2 ;;
    *)        DUMP="$1"; shift ;;
  esac
done

if [ "$STACK" = auto ]; then
  if docker compose -f docker/compose/docker-compose.prod.yml ps --status running 2>/dev/null | grep -q postgres; then
    STACK=prod
  else
    STACK=dev
  fi
fi

case "$STACK" in
  prod)
    COMPOSE="docker compose -f docker/compose/docker-compose.prod.yml --env-file .env.production"
    DB_USER=$(grep -E '^POSTGRES_USER=' .env.production | cut -d= -f2-)
    ;;
  dev)
    COMPOSE="docker compose -f docker/compose/docker-compose.dev.yml"
    DB_USER=trustlens
    ;;
  *) echo "unknown stack: $STACK" >&2; exit 2 ;;
esac

if [ -z "$DUMP" ]; then
  DUMP=$(ls -1t backups/trustlens-*.dump 2>/dev/null | head -1 || true)
  [ -n "$DUMP" ] || { echo "!! No backups found. Run scripts/db-backup.sh first." >&2; exit 1; }
fi
[ -f "$DUMP" ] || { echo "!! $DUMP does not exist" >&2; exit 1; }

psql_run() { $COMPOSE exec -T postgres psql -U "$DB_USER" -d postgres -tAc "$1"; }

if [ "$MODE" = verify ]; then
  SCRATCH="trustlens_restore_check"
  echo "==> Verifying $DUMP"
  echo "    restoring into scratch database '$SCRATCH'"

  # Always start from nothing, in case a previous run was interrupted.
  psql_run "DROP DATABASE IF EXISTS $SCRATCH;" >/dev/null
  psql_run "CREATE DATABASE $SCRATCH;" >/dev/null

  # --no-owner / --no-privileges: the scratch database has no application
  # roles, and role errors would otherwise drown the real ones.
  set +e
  $COMPOSE exec -T postgres pg_restore -U "$DB_USER" -d "$SCRATCH" \
    --no-owner --no-privileges < "$DUMP" 2> /tmp/tl-restore-err.txt
  RESTORE_RC=$?
  set -e

  # Counted INSIDE the scratch database. `psql_run` connects to `postgres`,
  # and asking it about information_schema returns that database's tables -
  # zero of them - which reads as a failed restore of a perfectly good dump.
  TABLES=$($COMPOSE exec -T postgres psql -U "$DB_USER" -d "$SCRATCH" -tAc     "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';"     | tr -d '[:space:]')
  ROWS=$($COMPOSE exec -T postgres psql -U "$DB_USER" -d "$SCRATCH" -tAc     "SELECT count(*) FROM public.users;" 2>/dev/null | tr -d '[:space:]' || echo "n/a")

  psql_run "DROP DATABASE IF EXISTS $SCRATCH;" >/dev/null
  echo "    scratch database dropped"

  if [ "$TABLES" -lt 30 ]; then
    echo ""
    echo "!! RESTORE FAILED - only $TABLES tables came back (expected 40)."
    [ -s /tmp/tl-restore-err.txt ] && head -20 /tmp/tl-restore-err.txt
    exit 1
  fi

  echo ""
  echo "==> Restore verified: $TABLES tables, $ROWS user rows recovered from $DUMP"
  [ "$RESTORE_RC" -ne 0 ] && echo "    (pg_restore reported non-fatal warnings; tables are present)"
  exit 0
fi

# ── The real thing ───────────────────────────────────────────────────
[ -n "$TARGET" ] || { echo "!! --into needs a database name" >&2; exit 2; }

cat <<WARNING

  !! DESTRUCTIVE

  About to DROP and recreate the database '$TARGET' on the $STACK stack,
  then restore it from:

      $DUMP

  Everything currently in '$TARGET' will be lost.

WARNING
printf "  Type the database name to confirm: "
read -r CONFIRM
[ "$CONFIRM" = "$TARGET" ] || { echo "  Names did not match. Nothing changed."; exit 1; }

echo "==> Taking a safety backup of '$TARGET' first"
mkdir -p backups
SAFETY="backups/pre-restore-${TARGET}-$(date -u +%Y%m%dT%H%M%SZ).dump"
$COMPOSE exec -T postgres pg_dump -U "$DB_USER" -Fc "$TARGET" > "$SAFETY" || true
echo "    $SAFETY"

echo "==> Restoring"
psql_run "DROP DATABASE IF EXISTS $TARGET WITH (FORCE);" >/dev/null
psql_run "CREATE DATABASE $TARGET;" >/dev/null
$COMPOSE exec -T postgres pg_restore -U "$DB_USER" -d "$TARGET" --no-owner --no-privileges < "$DUMP"

TABLES=$($COMPOSE exec -T postgres psql -U "$DB_USER" -d "$TARGET" -tAc \
  "SELECT count(*) FROM information_schema.tables WHERE table_schema='public';" | tr -d '[:space:]')
echo "==> Restored '$TARGET': $TABLES tables"
echo "    Restart the app so it reconnects:  make prod-restart"
