#!/usr/bin/env bash
# Convert the exported OpenAPI document into a Postman collection (P0-09).
#
# The proposal names Postman as a deliverable, and it is what the examiners
# will be handed to poke at the API. `make postman` exports the spec first.
set -euo pipefail
cd "$(dirname "$0")/.."

SPEC="docs/api/openapi.json"
OUT="docs/api/trustlens.postman_collection.json"

if [ ! -f "$SPEC" ]; then
  echo "!! $SPEC is missing. Run 'make openapi' first (make postman does both)." >&2
  exit 1
fi

# openapi-to-postmanv2 is not a project dependency: it is needed once per
# release, not on every install, so it is fetched on demand rather than added
# to a lockfile the whole team pays for.
echo "==> Converting $SPEC"
pnpm dlx openapi-to-postmanv2 \
  --spec "$SPEC" \
  --output "$OUT" \
  --pretty \
  --options folderStrategy=Tags,requestNameSource=Fallback

echo "==> $OUT"
