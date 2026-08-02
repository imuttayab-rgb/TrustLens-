"""Dump the OpenAPI document to stdout.

`make openapi` redirects this into docs/api/openapi.json, which is the input
to `pnpm codegen` and therefore the source of every frontend request type
(ADR-0005). CI regenerates both and fails on drift, so renaming a backend
field breaks the frontend type-check in the same pull request.

Run as a module so nothing has to import FastAPI at package import time:

    uv run python -m trustlens_api.openapi_export > docs/api/openapi.json
"""

from __future__ import annotations

import json
import sys


def main() -> int:
    # Imported inside main so `--help`-style tooling and import-linter do not
    # pay for building the whole application graph.
    from trustlens_api.main import app

    document = app.openapi()
    # sort_keys keeps the committed file stable, so a diff shows real contract
    # changes rather than dictionary ordering noise.
    json.dump(document, sys.stdout, indent=2, sort_keys=True, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
