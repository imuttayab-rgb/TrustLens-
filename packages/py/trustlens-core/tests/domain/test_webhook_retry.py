"""Webhook retry rules (P6-05).

These decide what happens when a partner's server is having a bad afternoon.
Getting them wrong is not a subtle bug: too eager and TrustLens becomes a
denial-of-service against its own customers, too timid and a marketplace
silently stops hearing about high-risk sellers.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from trustlens.core.domain.policies import RetryPolicy, is_success, should_retry

NOW = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)


class TestBackoff:
    def test_delays_double(self) -> None:
        policy = RetryPolicy(base_delay_seconds=30)
        assert [policy.delay_for(n) for n in (1, 2, 3, 4)] == [30, 60, 120, 240]

    def test_the_delay_is_capped(self) -> None:
        # Without a cap, attempt 20 would schedule a retry years away, and the
        # row would sit PENDING forever looking like work in progress.
        policy = RetryPolicy(base_delay_seconds=30, max_delay_seconds=900)
        assert policy.delay_for(20) == 900

    def test_a_zeroth_attempt_does_not_wait(self) -> None:
        assert RetryPolicy().delay_for(0) == 0

    def test_next_retry_is_scheduled_from_now(self) -> None:
        policy = RetryPolicy(base_delay_seconds=30)
        assert policy.next_retry_at(attempt=1, now=NOW) == NOW + timedelta(seconds=30)

    def test_the_last_attempt_schedules_nothing(self) -> None:
        # None is the signal to stop; a policy that always returns a time
        # retries a dead endpoint forever.
        policy = RetryPolicy(max_attempts=5)
        assert policy.next_retry_at(attempt=5, now=NOW) is None

    def test_exhaustion_is_reported(self) -> None:
        policy = RetryPolicy(max_attempts=5)
        assert not policy.is_exhausted(4)
        assert policy.is_exhausted(5)


class TestWhatIsWorthRetrying:
    @pytest.mark.parametrize("status", [500, 502, 503, 504])
    def test_server_errors_are_retried(self, status: int) -> None:
        assert should_retry(status)

    def test_a_transport_failure_is_retried(self) -> None:
        # None means no answer at all: timeout, DNS failure, refused
        # connection. The most retryable case there is.
        assert should_retry(None)

    @pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
    def test_client_errors_are_not_retried(self, status: int) -> None:
        # The payload or the credentials are wrong and will be exactly as
        # wrong in four minutes. Retrying burns quota and hides the bug.
        assert not should_retry(status)

    @pytest.mark.parametrize("status", [408, 429])
    def test_timeout_and_rate_limit_are_retried(self, status: int) -> None:
        # These are the two 4xx codes that explicitly mean "not now, later".
        assert should_retry(status)


class TestSuccess:
    @pytest.mark.parametrize("status", [200, 201, 202, 204])
    def test_any_2xx_counts_as_delivered(self, status: int) -> None:
        # A partner returning 204 has acknowledged as much as one returning
        # 200; insisting on 200 would retry deliveries that already arrived.
        assert is_success(status)

    @pytest.mark.parametrize("status", [199, 301, 302, 400, 500])
    def test_everything_else_is_not_success(self, status: int) -> None:
        # A redirect is not a delivery: following it blindly would post a
        # signed payload to a host the partner never registered.
        assert not is_success(status)

    def test_no_response_is_not_success(self) -> None:
        assert not is_success(None)


class TestTheWholeSchedule:
    def test_the_retry_window_is_minutes_not_hours(self) -> None:
        # 30s + 1m + 2m + 4m = 7.5 minutes. Long enough to ride out a restart
        # or a brief blip; short enough that a delivery still pending an hour
        # later means something an operator should see, rather than a queue
        # quietly keeping a dead endpoint warm.
        policy = RetryPolicy()
        total = sum(policy.delay_for(n) for n in range(1, policy.max_attempts))
        assert total == 450
        assert 5 * 60 <= total <= 10 * 60
