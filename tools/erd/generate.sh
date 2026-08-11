#!/usr/bin/env bash
# Render the ER diagram from the SQLAlchemy models (P0-09, feeds D-04).
set -euo pipefail
cd "$(dirname "$0")/../.."
uv run python tools/erd/generate.py "$@"
