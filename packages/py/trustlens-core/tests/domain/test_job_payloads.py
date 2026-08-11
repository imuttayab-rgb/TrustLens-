"""Job payload literals must name things that actually exist.

A job argument is a string on the wire, so a wrong value type-checks, passes
review, and returns 200 to the caller. It fails inside the worker minutes
later, where nobody is looking.

That is not hypothetical: `trigger="APPEAL"` and `trigger="MANUAL_REVIEW"`
both shipped. Neither is a `ScoreTrigger`, so every appeal resolution and
every admin review decision recorded its verdict, wrote its audit entry,
answered 200 - and never rescored the seller.

This scans the source for `trigger="..."` and parses each one, so the next
plausible-looking name fails here instead of in production.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from trustlens.core.domain.enums import ScoreTrigger

#: Repo root, from this file: domain -> tests -> trustlens-core -> py ->
#: packages -> root. `test_the_scan_finds_something` fails loudly if this
#: drifts, rather than letting every other assertion pass on an empty list.
_ROOT = Path(__file__).resolve().parents[5]

_SEARCH_ROOTS = ("apps", "packages")

_TRIGGER_RE = re.compile(r"""trigger\s*=\s*["']([A-Z_]+)["']""")


def _python_sources() -> list[Path]:
    files: list[Path] = []
    for root in _SEARCH_ROOTS:
        base = _ROOT / root
        if not base.is_dir():
            continue
        files.extend(
            path
            for path in base.rglob("*.py")
            if "__pycache__" not in path.parts
            and ".venv" not in path.parts
            and not path.name.startswith("test_")
        )
    return files


def _trigger_literals() -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    for path in _python_sources():
        text = path.read_text(encoding="utf-8", errors="ignore")
        found.extend((path, match) for match in _TRIGGER_RE.findall(text))
    return found


def test_the_scan_finds_something() -> None:
    """Guards the guard: a broken regex would make every assertion vacuous."""
    assert _trigger_literals(), "no trigger= literals found - the scan is broken"


@pytest.mark.parametrize(
    ("path", "literal"),
    [pytest.param(p, lit, id=f"{p.name}:{lit}") for p, lit in _trigger_literals()],
)
def test_trigger_literal_is_a_real_score_trigger(path: Path, literal: str) -> None:
    try:
        ScoreTrigger(literal)
    except ValueError:
        valid = ", ".join(sorted(t.value for t in ScoreTrigger))
        pytest.fail(
            f"{path.relative_to(_ROOT)} enqueues trigger={literal!r}, which is not a "
            f"ScoreTrigger. The job will raise ValueError after the request has "
            f"already succeeded. Valid values: {valid}"
        )
