#!/usr/bin/env bash
# Update a running localhost installation. Build first; preserve volumes/config;
# verify an encrypted DB snapshot before migrations; restore source/images on error.
set -Eeuo pipefail
umask 077
export MSYS_NO_PATHCONV=1 COMPOSE_PARALLEL_LIMIT=1
release_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
target_root="$(cd -- "${1:?Usage: bash scripts/local/update-existing.sh /path/to/existing/TrustLens [compose-project]}" && pwd)"
project="${2:-trustlens}"
[[ "$project" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || { echo 'Invalid project name.' >&2; exit 1; }
[[ "$release_root" != "$target_root" ]] || { echo 'Extract the release to a separate folder, then pass your existing folder.' >&2; exit 1; }
[[ -f "$target_root/.env.production" && -f "$release_root/MANIFEST.sha256" ]] || { echo 'Existing environment or release manifest is missing.' >&2; exit 1; }
command -v docker >/dev/null
docker info >/dev/null 2>&1 || { echo 'Start Docker Desktop first.' >&2; exit 1; }
mkdir "$target_root/.trustlens-update-lock" 2>/dev/null || { echo 'An update is already running. If it was interrupted, check its backup before removing the empty lock.' >&2; exit 1; }
cd "$target_root"
export TRUSTLENS_IMAGE_PREFIX="$project"
dc() { docker compose --project-name "$project" -f docker/compose/docker-compose.prod.yml --env-file .env.production --profile calls "$@"; }
source_native="$(cd "$release_root" && { pwd -W 2>/dev/null || pwd -P; })"
target_native="$(pwd -W 2>/dev/null || pwd -P)"
stamp="$(date -u +%Y%m%d-%H%M%S)-$$"
backup_rel=".trustlens-update-backups/$stamp"
old_images=(); services=(api worker web admin)
staged=0; paused=0
cleanup() { rmdir "$target_root/.trustlens-update-lock" 2>/dev/null || true; }
trap cleanup EXIT
rollback() {
  local failure=$?
  trap - ERR INT TERM
  set +e
  echo 'Update stopped. Restoring the previous source and application images.' >&2
  if [[ "$staged" == 1 ]]; then
    docker run --rm --network none --user 0 -v "$target_native:/target" -v "$source_native:/release:ro" --entrypoint python "${old_images[0]}" /release/scripts/local/update_source.py restore --target /target --backup "/target/$backup_rel"
  fi
  for i in "${!old_images[@]}"; do docker image tag "${old_images[$i]}" "$project-${services[$i]}:latest"; done
  if [[ "$paused" == 1 ]]; then
    dc up -d --no-build --no-deps api worker web admin
  fi
  rm -f "$target_root/$backup_rel/database.dump" "$target_root/$backup_rel/verify.dump"
  echo "Update incomplete. Database/volumes were not deleted. Backup: $target_root/$backup_rel" >&2
  echo 'Review the preceding rollback output before retrying.' >&2
  exit "${failure:-1}"
}
trap rollback ERR INT TERM
for service in "${services[@]}"; do
  container="$(dc ps -q "$service")"
  [[ -n "$container" ]] || { echo "Existing $project/$service must be running before updating." >&2; false; }
  if [[ "$service" == api ]]; then
    config_files="$(docker inspect --format '{{ index .Config.Labels "com.docker.compose.project.config_files" }}' "$container")"
    config_files="${config_files//\\//}"
    expected_config="$target_native/docker/compose/docker-compose.prod.yml"
    if [[ "${OSTYPE:-}" == msys* ]]; then config_files="${config_files,,}"; expected_config="${expected_config,,}"; fi
    [[ ",$config_files," == *",$expected_config,"* ]] || { echo 'The running Compose project belongs to a different checkout. Pass its actual folder/project.' >&2; false; }
  fi
  old_images+=("$(docker inspect --format '{{.Image}}' "$container")")
done
# The backup helper is from the verified release and uses only Python's stdlib.
echo '[1/6] Verifying release and backing up managed source'
# Set before staging so even a partial copy can be rolled back from its journal.
staged=1
docker run --rm --network none --user 0 -v "$target_native:/target" -v "$source_native:/release:ro" --entrypoint python "${old_images[0]}" /release/scripts/local/update_source.py stage --release /release --target /target --backup "/target/$backup_rel"
for i in "${!old_images[@]}"; do
  printf '%s %s\n' "${services[$i]}" "${old_images[$i]}" >> "$backup_rel/previous-images.txt"
  docker image tag "${old_images[$i]}" "$project-rollback-${services[$i]}:$stamp"
done
dc config --quiet
echo '[2/6] Building API, worker, web and admin; previous services remain running'
for service in "${services[@]}"; do dc build "$service"; done
echo '[3/6] Pausing writes and verifying an encrypted database backup'
paused=1
dc stop api worker
pg="$(dc ps -q postgres)"
remote_dump="/tmp/trustlens-update-$stamp.dump"
dc exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f "$1" && pg_restore --list "$1" >/dev/null' sh "$remote_dump"
docker cp "$pg:$remote_dump" "$backup_rel/database.dump" >/dev/null
dc exec -T postgres rm -f "$remote_dump"
backup_native="$target_native/$backup_rel"
dc run --rm --no-deps -T --user 0 -v "$backup_native:/backup" -v "$source_native:/release:ro" --entrypoint python api /release/scripts/local/verify_backup.py /backup
echo '[4/6] Applying migrations and reference data'
dc run --rm --no-deps -T migrate
echo '[5/6] Starting updated services'
dc up -d --no-build
echo '[6/6] Checking application readiness'
TRUSTLENS_LOCAL_PROJECT="$project" bash scripts/local/doctor.sh --wait
printf '%s\n' "$project" > .trustlens-local-project
printf 'SECURITY_UPDATE_COMPLETE\n' > "$backup_rel/COMPLETE"
trap - ERR INT TERM
printf '\nUPDATE COMPLETE\nOpen http://localhost:3000 and press Ctrl+Shift+R.\nBackup: %s\nExisting credentials, accounts, listings, chat and voice volumes were preserved.\n' "$target_root/$backup_rel"
