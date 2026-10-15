#!/usr/bin/env bash
# Export encrypted DB/chat backups without host-side Docker stdout pipelines.
# The snapshot retains all messages; keep encryption keys separately.
set -Eeuo pipefail
umask 077
backup_root="${1:?Usage: bash scripts/chat_backup.sh /path/to/backup-folder}"
mkdir -p "$backup_root"
backup_root="$(cd "$backup_root" && pwd)"
source "$(dirname -- "${BASH_SOURCE[0]}")/local/common.sh"
require_docker
require_config
stamp="$(date -u +%Y%m%d-%H%M%S)-$$"
target="$backup_root/chat-$stamp"
mkdir -p "$target"
api="$(dc ps -q api)"
pg="$(dc ps -q postgres)"
[[ -n "$api" && -n "$pg" ]] || { echo 'API and PostgreSQL must be running.' >&2; exit 1; }
remote_dump="/tmp/trustlens-chat-$stamp.dump"
cleanup() {
  rm -f "$target/database.dump" "$target/verify.dump"
  dc exec -T postgres rm -f "$remote_dump" >/dev/null 2>&1 || true
}
trap cleanup EXIT
dc exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f "$1" && pg_restore --list "$1" >/dev/null' sh "$remote_dump"
docker cp "$pg:$remote_dump" "$target/database.dump" >/dev/null
native_target="$(cd "$target" && { pwd -W 2>/dev/null || pwd -P; })"
native_root="$(pwd -W 2>/dev/null || pwd -P)"
dc run --rm --no-deps -T --user 0 -v "$native_target:/backup" -v "$native_root:/release:ro" --entrypoint python api /release/scripts/local/verify_backup.py /backup
remote="/tmp/trustlens-chat-backup-$stamp"
dc exec -T api python -m trustlens_api.modules.messaging.archive export "$remote"
dc exec -T api python -m trustlens_api.modules.messaging.archive verify "$remote"
docker cp "$api:$remote/." "$target/archive" >/dev/null
dc exec -T api python -c 'import shutil,sys; p=sys.argv[1]; assert p.startswith("/tmp/trustlens-chat-backup-"); shutil.rmtree(p)' "$remote"
printf 'BACKUP_VERIFIED=%s\n' "$target"
printf 'Copy this backup to independent storage and keep encryption keys separately. A full restore rehearsal needs an empty test database.\n'
