#!/usr/bin/env bash
# Build and run a complete localhost installation. Does not stop older stacks.
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
require_docker
mkdir .trustlens-setup-lock 2>/dev/null || { echo 'Setup already running. If interrupted earlier, remove the empty .trustlens-setup-lock directory first.' >&2; exit 1; }
cleanup() { rmdir .trustlens-setup-lock 2>/dev/null || true; }
trap cleanup EXIT
trap 'echo "Setup stopped at line $LINENO. Existing data was not deleted. Resolve the error and rerun; Docker reuses completed layers." >&2' ERR
bash scripts/local/init-env.sh
dc config --quiet
# A second installation cannot bind the same ports. Refuse before a long build.
for port in 3000 3001 8000 8025 9000 9001 7880 7881 7882; do
  while IFS= read -r container; do
    [[ -z "$container" ]] && continue
    owner="$(docker inspect --format '{{ index .Config.Labels "com.docker.compose.project" }}' "$container")"
    [[ "$owner" == "$local_project" ]] || { echo "Port $port belongs to another container ($owner). Stop that stack normally, or configure different ports first." >&2; exit 1; }
  done < <(docker ps -q --filter "publish=$port")
done
printf '\n[1/5] Building API (first run downloads dependencies)\n'
dc build api
local_native_root="$(pwd -W 2>/dev/null || pwd -P)"
# Run the configuration tool with the image's Python; no host Python install.
printf '\n[2/5] Preparing local media keys\n'
dc run --rm --no-deps -T --user 0 --volume "$local_native_root:/workspace" --entrypoint python api /workspace/scripts/configure_calls.py --root /workspace
printf '\n[3/5] Building worker, web and admin sequentially\n'
dc build worker
dc build web
dc build admin
printf '\n[4/5] Starting services and running migrations\n'
dc up -d --no-build
# Check HTTP readiness and the LiveKit control API. Hardware audio is a manual check.
printf '\n[5/5] Checking services\n'
bash scripts/local/doctor.sh --wait
printf '\nTRUSTLENS READY\nWeb: http://localhost:3000\nAdmin: http://localhost:3001\nLocal email: http://localhost:8025\n'
printf 'Optional sample accounts: bash scripts/local/demo.sh\nCalling: use two accounts in separate browsers on this computer.\nRead START_HERE.md for setup, data transfer and deployment limits.\n'
