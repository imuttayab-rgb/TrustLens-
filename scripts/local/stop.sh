#!/usr/bin/env bash
# Stop this edition only. Named volumes and all stored records remain intact.
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
require_docker
require_config
dc stop
