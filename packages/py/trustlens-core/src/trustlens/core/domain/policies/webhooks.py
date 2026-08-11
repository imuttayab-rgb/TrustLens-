"""Webhook delivery rules (P6-05).

A webhook is a promise to tell somebody else when something changed. The hard
part is not the HTTP call, it is what happens when the call fails - and it
will, because the other end is a marketplace's server on a Tuesday afternoon.

Three decisions live here, as pure functions, because they are the ones the
FYP is examined on and the ones a retry storm turns into an outage.

* **Retry with exponential backoff and a cap.** A partner having a bad ten
  minutes must not be hammered every second, and a partner who is gone for
  good must not be retried forever.
* **Only retry what retrying can fix.** A 500 is worth another attempt; a 400
  means the payload is wrong and will be exactly as wrong in an hour. Retrying
  a 4xx burns quota on both sides and hides the bug.
* **Give up loudly.** After the last attempt the delivery is EXHAUSTED, not
  silently dropped, so an operator can see which partner is missing events.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

#: Attempts include the first one, so there are four retries after it.
MAX_ATTEMPTS = 5

#: Base delay, doubled each attempt: 30s, 1m, 2m, 4m - 7.5 minutes of retrying
#: in total. That covers a restart or a brief blip; it deliberately does not
#: cover a partner who is down for an afternoon, because a delivery still
#: pending hours later is a page for an operator, not a queue to keep warm.
BASE_DELAY_SECONDS = 30

#: Never wait longer than this between attempts.
MAX_DELAY_SECONDS = 900

#: A slow partner should not hold a worker slot open indefinitely.
DELIVERY_TIMEOUT_SECONDS = 10


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = MAX_ATTEMPTS
    base_delay_seconds: int = BASE_DELAY_SECONDS
    max_delay_seconds: int = MAX_DELAY_SECONDS

    def delay_for(self, attempt: int) -> int:
        """Seconds to wait before `attempt` (1-based: attempt 1 is the first retry)."""
        if attempt < 1:
            return 0
        raw: int = self.base_delay_seconds * (2 ** (attempt - 1))
        return min(raw, self.max_delay_seconds)

    def next_retry_at(self, *, attempt: int, now: datetime) -> datetime | None:
        """When to try again, or None when the attempts are spent."""
        if attempt >= self.max_attempts:
            return None
        return now + timedelta(seconds=self.delay_for(attempt))

    def is_exhausted(self, attempt_count: int) -> bool:
        return attempt_count >= self.max_attempts


def should_retry(status_code: int | None) -> bool:
    """Whether a failed delivery is worth attempting again.

    `None` means the request never got an answer - a timeout, a DNS failure, a
    refused connection - which is the most retryable case there is.

    A 4xx is not retried: the payload or the credentials are wrong, and they
    will be equally wrong in four minutes. The two exceptions are 408 and 429,
    which explicitly mean "not now, later".
    """
    if status_code is None:
        return True
    if status_code == 408 or status_code == 429:
        return True
    if 400 <= status_code < 500:
        return False
    return status_code >= 500


def is_success(status_code: int | None) -> bool:
    """Any 2xx. A partner returning 204 has acknowledged as much as one returning 200."""
    return status_code is not None and 200 <= status_code < 300


__all__ = [
    "BASE_DELAY_SECONDS",
    "DELIVERY_TIMEOUT_SECONDS",
    "MAX_ATTEMPTS",
    "MAX_DELAY_SECONDS",
    "RetryPolicy",
    "is_success",
    "should_retry",
]
