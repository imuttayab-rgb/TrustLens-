#!/usr/bin/env python3
"""Fail if .env is missing any key present in .env.example, or still holds a CHANGEME."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def keys(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip()
    return out


def main() -> int:
    example, actual = keys(ROOT / ".env.example"), keys(ROOT / ".env")
    if not actual:
        print("!! .env not found. Run: cp .env.example .env", file=sys.stderr)
        return 1

    missing = sorted(set(example) - set(actual))
    placeholders = sorted(k for k, v in actual.items() if "CHANGEME" in v)

    for k in missing:
        print(f"!! missing in .env: {k}", file=sys.stderr)
    for k in placeholders:
        print(f"!! still a placeholder: {k}  (run scripts/generate-keys.sh)", file=sys.stderr)

    if missing or placeholders:
        return 1
    print(f"env OK ({len(actual)} variables)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
