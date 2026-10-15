#!/usr/bin/env bash
# Follow bounded recent application logs. Review/redact personal data before sharing.
set -Eeuo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/common.sh"
require_docker
require_config
dc logs --tail=100 --follow api worker migrate web admin livekit
