"""Every enqueued job name must be registered by the worker.

This guards a failure mode that is invisible at runtime. The domain enqueues
jobs by string because it must not import the worker (ADR-0003), and ARQ names
a job after its Python function unless told otherwise. When the two drift,
Redis accepts the job and the worker discards it with "function not found" -
no exception reaches the caller, no test fails, and the only evidence is a
line in the worker log.

That is exactly what had happened: all seven enqueued names were unregistered,
so OCR, face matching, verification emails, OTP SMS and rescoring never ran.

Deliberately a source-text check rather than an import: importing
`WorkerSettings` evaluates `RedisSettings.from_dsn(...)` at class-creation
time, which would make this need a configured environment to answer a purely
static question.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
WORKER_MAIN = ROOT / "apps" / "worker" / "src" / "trustlens_worker" / "main.py"
SEARCH_ROOTS = (ROOT / "packages" / "py", ROOT / "apps")

#: `self._queue.enqueue("some.name"` / `container.queue.enqueue("some.name"`
ENQUEUE_RE = re.compile(r"queue\.enqueue\(\s*[\"']([a-z_]+\.[a-z_]+)[\"']", re.MULTILINE)
#: `func(module.callable, name="some.name")`
REGISTERED_RE = re.compile(r"name=[\"']([a-z_]+\.[a-z_]+)[\"']")


#: Tests are excluded, not only for speed: this file quotes an example
#: `queue.enqueue("some.name")` in its own docstring, and scanning itself
#: would report that illustration as a missing registration.
_SKIP_PARTS = {".venv", "__pycache__", "node_modules", "tests"}


def _python_files() -> list[Path]:
    seen: list[Path] = []
    for root in SEARCH_ROOTS:
        seen.extend(
            p for p in root.rglob("*.py") if not any(part in _SKIP_PARTS for part in p.parts)
        )
    return seen


def enqueued_names() -> set[str]:
    names: set[str] = set()
    for path in _python_files():
        names.update(ENQUEUE_RE.findall(path.read_text(encoding="utf-8")))
    return names


def registered_names() -> set[str]:
    source = WORKER_MAIN.read_text(encoding="utf-8")
    # Only the `functions = [...]` block; cron jobs are referenced by object.
    block = source.split("functions = [", 1)[1].split("]", 1)[0]
    return set(REGISTERED_RE.findall(block))


def test_worker_registers_every_enqueued_job() -> None:
    enqueued = enqueued_names()
    assert enqueued, "Found no enqueue call sites - the regex has drifted from the code."

    missing = sorted(enqueued - registered_names())
    assert not missing, (
        "These job names are enqueued but not registered in WorkerSettings.functions, "
        f"so they would be silently dropped at runtime: {missing}"
    )


def test_registered_names_are_namespaced() -> None:
    """A bare name means someone let ARQ default to the function name again."""
    for name in registered_names():
        assert "." in name, f"{name!r} is not namespaced"


@pytest.mark.parametrize(
    "name",
    [
        "identity.verify",
        "scoring.recompute_trust_score",
        "notifications.send_email",
        "contact.send_otp_sms",
        "contact.lookup_phone",
        "network.enrich_ip",
    ],
)
def test_known_job_names_stay_registered(name: str) -> None:
    """Pins the names that existing callers depend on.

    Renaming one of these breaks a caller that this file cannot see, so the
    rename should be a deliberate, visible edit here too.
    """
    assert name in registered_names()
