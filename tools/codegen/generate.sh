#!/usr/bin/env bash
# Regenerate the typed API client from the exported OpenAPI document.
#
# `make codegen` exports docs/api/openapi.json first, then runs this. CI runs
# the same target and fails on any diff, so a backend field rename breaks the
# frontend build in the SAME pull request rather than at runtime (ADR-0005).
#
# The generator itself lives in packages/api-client, which already declares
# openapi-typescript as a devDependency; this wrapper exists so the Makefile
# and package.json have one entry point that also checks its own inputs.
set -euo pipefail
cd "$(dirname "$0")/../.."

SPEC="docs/api/openapi.json"
OUT="packages/api-client/src/schema.gen.ts"

if [ ! -f "$SPEC" ]; then
  echo "!! $SPEC is missing. Run 'make openapi' first (make codegen does both)." >&2
  exit 1
fi

# An empty or truncated spec generates an empty client, which type-checks and
# then fails at runtime on every call. Cheaper to refuse here.
if ! node -e "const d=require('./$SPEC'); if(!d.paths||!Object.keys(d.paths).length) process.exit(1)"; then
  echo "!! $SPEC has no paths - the export produced nothing usable." >&2
  exit 1
fi

echo "==> Generating $OUT from $SPEC"
pnpm --filter @trustlens/api-client run codegen

# The generated file is committed, so it must satisfy the same formatter as
# everything else or the drift check fails on whitespace alone.
pnpm exec prettier --config configs/prettier.config.js --write "$OUT" >/dev/null

echo "==> API client regenerated"
