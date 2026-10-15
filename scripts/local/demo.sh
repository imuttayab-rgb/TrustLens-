#!/usr/bin/env bash
# Explicit opt-in demo seed. Only use on a disposable local demonstration database.
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
require_docker
require_config
dc exec -T api python -m trustlens.db.seed.run demo
echo 'Sample account credentials: CREDENTIALS.dev.md (demo accounts only).'
