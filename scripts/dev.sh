#!/usr/bin/env bash
# Run api + worker + web + admin with prefixed, colour-coded logs.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] || { echo "!! .env missing. Run: make setup" >&2; exit 1; }

# ── Environment guard ────────────────────────────────────────────────
#
# On Windows this script can be launched into THREE different shells, and two
# of them fail in ways that look like the app is simply broken:
#
#   * WSL, because the Makefile sets SHELL := /bin/bash and Windows resolves
#     that to WSL's bash. node_modules then holds win32 SWC binaries that
#     Linux cannot load, and `uv` is usually absent, so the api and worker
#     never start while Next silently downloads a Linux toolchain.
#   * A shell without uv on PATH, where the api and worker die instantly and
#     only the two frontends come up - so localhost:3000 loads but nothing
#     it calls responds.
#
# Both used to fail quietly. Fail loudly instead.

if ! command -v uv >/dev/null 2>&1; then
  echo "!! 'uv' is not on PATH in this shell." >&2
  echo "   The API and worker cannot start, so the frontends would load with" >&2
  echo "   nothing behind them." >&2
  if grep -qi microsoft /proc/version 2>/dev/null; then
    echo "" >&2
    echo "   This shell is WSL. The project is installed for Windows:" >&2
    echo "   node_modules holds win32 binaries that Linux cannot load." >&2
    echo "   Run 'make dev' from Git Bash on Windows instead - or install uv" >&2
    echo "   and reinstall dependencies inside WSL and stay there." >&2
  fi
  exit 1
fi

if grep -qi microsoft /proc/version 2>/dev/null   && ls node_modules/.pnpm 2>/dev/null | grep -q "swc-win32"; then
  echo "!! Running under WSL, but node_modules was installed for Windows." >&2
  echo "   Next cannot load win32 SWC binaries on Linux and will appear to" >&2
  echo "   hang while it downloads a Linux toolchain." >&2
  echo "   Use Git Bash on Windows, or reinstall inside WSL - not both." >&2
  exit 1
fi

trap 'kill 0' EXIT INT TERM

prefix() { local c=$1 n=$2; shift 2; "$@" 2>&1 | sed -u "s/^/$(printf '\033[%sm[%s]\033[0m ' "$c" "$n")/"; }

prefix 36 api    uv run uvicorn trustlens_api.main:app --reload --host 0.0.0.0 --port 8000 &
prefix 35 worker uv run arq trustlens_worker.main.WorkerSettings &
prefix 32 web    pnpm --filter @trustlens/web dev &
prefix 33 admin  pnpm --filter @trustlens/admin dev &

echo ""
echo "  web     http://localhost:3000"
echo "  browse  http://localhost:3000/browse"
echo "  admin   http://localhost:3001"
echo "  api     http://localhost:8000/docs"
echo "  mail    http://localhost:8025"
echo ""
wait
