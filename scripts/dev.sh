#!/usr/bin/env bash
# Run api + worker + web + admin with prefixed, colour-coded logs.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "!! .env missing. Run: make setup" >&2; exit 1; }

trap 'kill 0' EXIT INT TERM

prefix() { local c=$1 n=$2; shift 2; "$@" 2>&1 | sed -u "s/^/$(printf '\033[%sm[%s]\033[0m ' "$c" "$n")/"; }

prefix 36 api    uv run uvicorn trustlens_api.main:app --reload --host 0.0.0.0 --port 8000 &
prefix 35 worker uv run arq trustlens_worker.main.WorkerSettings &
prefix 32 web    pnpm --filter @trustlens/web dev &
prefix 33 admin  pnpm --filter @trustlens/admin dev &

echo ""
echo "  web    http://localhost:3000"
echo "  admin  http://localhost:3001"
echo "  api    http://localhost:8000/docs"
echo "  mail   http://localhost:8025"
echo ""
wait
