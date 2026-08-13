"""Worker supervisor (P9-09).

The failure this exists to prevent is silent: ARQ's `run_worker` returns when
Redis drops, the process exits, and the queue simply stops being consumed. No
error page, no failed request - jobs pile up and nobody is told.

Upstash closes idle connections by design, so on the deployed system this is
not an edge case, it is Tuesday.

These tests drive the retry loop with a fake worker rather than a real Redis,
because the property under test is *what the supervisor does about a failure*,
not whether redis-py raises.
"""

from __future__ import annotations

import asyncio
from typing import Any, ClassVar

import pytest

from trustlens_worker import supervisor


class FakeWorker:
    """Stands in for `arq.worker.Worker`.

    `behaviours` is consumed one entry per construction: an exception to raise
    from `async_run`, or None to return cleanly.
    """

    instances: ClassVar[list[FakeWorker]] = []
    #: BaseException, not Exception: CancelledError is a BaseException and
    #: one of the cases under test is that it propagates rather than being
    #: swallowed as a connection failure.
    behaviours: ClassVar[list[BaseException | None]] = []
    close_calls = 0
    fail_close = False

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs
        FakeWorker.instances.append(self)

    async def async_run(self) -> None:
        index = len(FakeWorker.instances) - 1
        behaviour = FakeWorker.behaviours[index] if index < len(FakeWorker.behaviours) else None
        if behaviour is not None:
            raise behaviour

    async def close(self) -> None:
        FakeWorker.close_calls += 1
        if FakeWorker.fail_close:
            raise ConnectionError("connection already gone")

    @classmethod
    def reset(cls) -> None:
        cls.instances = []
        cls.behaviours = []
        cls.close_calls = 0
        cls.fail_close = False


class DummySettings:
    """Only the attributes the supervisor is allowed to forward."""

    functions: ClassVar[list[Any]] = []
    max_jobs = 5
    job_timeout = 30
    # Deliberately not a Worker parameter: must be filtered out rather than
    # passed through as an unexpected keyword argument.
    not_a_worker_param = "should not reach Worker"


@pytest.fixture(autouse=True)
def _fast_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the schedule's shape, drop the wall-clock cost."""
    FakeWorker.reset()
    monkeypatch.setattr(supervisor, "Worker", FakeWorker)
    monkeypatch.setattr(supervisor, "INITIAL_BACKOFF_SECONDS", 0.001)
    monkeypatch.setattr(supervisor, "MAX_BACKOFF_SECONDS", 0.004)


class TestReconnect:
    @pytest.mark.asyncio
    async def test_a_dropped_connection_is_retried(self) -> None:
        # The whole point: one blip must not end the worker's life.
        FakeWorker.behaviours = [ConnectionError("Connection closed by server"), None]
        code = await supervisor.run_forever(DummySettings, max_restarts=5)

        assert code == 0
        assert len(FakeWorker.instances) == 2, "expected a reconnect after the drop"

    @pytest.mark.asyncio
    async def test_it_keeps_retrying_through_repeated_failures(self) -> None:
        FakeWorker.behaviours = [ConnectionError("boom")] * 4 + [None]
        code = await supervisor.run_forever(DummySettings, max_restarts=10)

        assert code == 0
        assert len(FakeWorker.instances) == 5

    @pytest.mark.asyncio
    async def test_it_gives_up_after_the_restart_ceiling(self) -> None:
        # Only the tests set a ceiling; production passes None. Without one, a
        # genuinely dead Redis would retry forever, which is correct in
        # production and untestable here.
        FakeWorker.behaviours = [ConnectionError("boom")] * 10
        code = await supervisor.run_forever(DummySettings, max_restarts=3)

        assert code == 1
        assert len(FakeWorker.instances) == 3

    @pytest.mark.asyncio
    async def test_a_clean_exit_is_not_retried(self) -> None:
        # ARQ returning normally means a burst limit or a deliberate close.
        # Restarting there would fight the thing that asked it to stop.
        FakeWorker.behaviours = [None]
        code = await supervisor.run_forever(DummySettings, max_restarts=5)

        assert code == 0
        assert len(FakeWorker.instances) == 1

    @pytest.mark.asyncio
    async def test_the_worker_is_closed_after_every_failure(self) -> None:
        # A leaked connection per retry turns a long outage into a socket leak.
        FakeWorker.behaviours = [ConnectionError("boom"), ConnectionError("boom"), None]
        await supervisor.run_forever(DummySettings, max_restarts=5)

        assert FakeWorker.close_calls == 3

    @pytest.mark.asyncio
    async def test_a_failing_close_does_not_stop_the_retry(self) -> None:
        # Closing a connection that is already gone frequently raises. That
        # must not mask the original error or abort recovery.
        FakeWorker.fail_close = True
        FakeWorker.behaviours = [ConnectionError("boom"), None]
        code = await supervisor.run_forever(DummySettings, max_restarts=5)

        assert code == 0
        assert len(FakeWorker.instances) == 2

    @pytest.mark.asyncio
    async def test_cancellation_propagates(self) -> None:
        # asyncio.CancelledError is the event loop shutting the task down, not
        # a Redis failure. Swallowing it would make the worker unkillable.
        FakeWorker.behaviours = [asyncio.CancelledError()]
        with pytest.raises(asyncio.CancelledError):
            await supervisor.run_forever(DummySettings, max_restarts=5)


class TestWorkerArguments:
    @pytest.mark.asyncio
    async def test_only_real_worker_parameters_are_forwarded(self) -> None:
        FakeWorker.behaviours = [None]
        await supervisor.run_forever(DummySettings, max_restarts=1)

        kwargs = FakeWorker.instances[0].kwargs
        assert "not_a_worker_param" not in kwargs
        assert kwargs["max_jobs"] == 5

    @pytest.mark.asyncio
    async def test_arq_signal_handling_is_disabled(self) -> None:
        # The supervisor owns SIGTERM so a deliberate stop can be told apart
        # from a dropped connection. If ARQ keeps its own handlers, SIGTERM
        # looks like an outage and gets "recovered" from.
        FakeWorker.behaviours = [None]
        await supervisor.run_forever(DummySettings, max_restarts=1)

        assert FakeWorker.instances[0].kwargs["handle_signals"] is False


class TestBackoff:
    def test_the_field_list_matches_the_installed_arq(self) -> None:
        # Guards against an arq upgrade silently dropping a parameter we
        # forward: better to fail here than with a TypeError at boot on a
        # platform with no shell.
        import inspect

        from arq.worker import Worker

        real = set(inspect.signature(Worker.__init__).parameters)
        unknown = supervisor._WORKER_FIELDS - real
        assert not unknown, f"no longer accepted by arq.Worker: {sorted(unknown)}"
