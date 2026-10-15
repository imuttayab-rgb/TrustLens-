#!/usr/bin/env bash
# Shared Compose identity: keeps this complete edition separate from older installs.
set -Eeuo pipefail
export MSYS_NO_PATHCONV=1
export COMPOSE_PARALLEL_LIMIT=1
LOCAL_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$LOCAL_ROOT"
saved_project=trustlens-clean
[[ ! -f .trustlens-local-project ]] || read -r saved_project < .trustlens-local-project
export TRUSTLENS_IMAGE_PREFIX="${TRUSTLENS_LOCAL_PROJECT:-$saved_project}"
local_project="$TRUSTLENS_IMAGE_PREFIX"
[[ "$local_project" =~ ^[a-z0-9][a-z0-9_-]*$ ]] || { echo 'Invalid TRUSTLENS_LOCAL_PROJECT.' >&2; exit 1; }
dc() { docker compose --project-name "$local_project" -f docker/compose/docker-compose.prod.yml --env-file .env.production --profile calls "$@"; }
require_docker() {
  command -v docker >/dev/null || { echo 'Install and start Docker Desktop (Linux containers).' >&2; exit 1; }
  docker compose version >/dev/null || { echo 'Docker Compose v2 is required.' >&2; exit 1; }
  docker info >/dev/null 2>&1 || { echo 'Start Docker Desktop and wait for its engine to be ready.' >&2; exit 1; }
}
require_config() { [[ -f .env.production ]] || { echo 'Run START_LOCAL.bat / bash scripts/local/start.sh first.' >&2; exit 1; }; }
