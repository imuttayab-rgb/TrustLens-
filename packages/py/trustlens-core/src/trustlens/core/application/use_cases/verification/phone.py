"""Phone OTP verification (feature F2).

Two distinct attacks are defended separately, because they have different
shapes:

* **Guessing a code** - bounded by a per-code attempt counter, incremented
  atomically in the database so concurrent requests cannot race past the cap.
* **Using OTP sends as an SMS-cost / DoS vector** - bounded by per-user
  hourly and daily send throttles. This one costs real money, so it is capped
  independently of the guess counter.

The code itself is stored as an HMAC with a server pepper held outside the
database, so a database leak does not hand out live codes.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from trustlens.core.domain.entities import OtpCode, PhoneNumber
from trustlens.core.domain.enums import OtpPurpose, VerificationStatus
from trustlens.core.domain.errors import (
    EntityNotFound,
    OtpExpired,
    OtpInvalid,
    OtpMaxAttemptsExceeded,
    RateLimitExceeded,
)
from trustlens.core.domain.events import PhoneVerified
from trustlens.core.domain.ports import Clock, IdGenerator, JobQueue, UnitOfWork
from trustlens.core.domain.value_objects import PhoneE164


class OtpGenerator(Protocol):
    """Cryptographically secure numeric code generation and peppered hashing."""

    def generate(self, length: int) -> str: ...

    def hash_code(self, code: str) -> bytes: ...

    def verify_code(self, code: str, code_hash: bytes) -> bool: ...


@dataclass(frozen=True, slots=True)
class RequestOtpCommand:
    user_id: UUID
    phone_number: str


@dataclass(frozen=True, slots=True)
class RequestOtpResult:
    phone_number_id: UUID
    expires_at: datetime
    masked_number: str
    #: Only populated when the console SMS sender is active (development).
    #: Never returned to a client in any deployed environment.
    debug_code: str | None = None


class RequestPhoneOtp:
    def __init__(
        self,
        *,
        uow: UnitOfWork,
        otp: OtpGenerator,
        queue: JobQueue,
        clock: Clock,
        ids: IdGenerator,
        code_length: int = 6,
        ttl_seconds: int = 300,
        max_attempts: int = 5,
        limit_per_hour: int = 3,
        limit_per_day: int = 10,
        expose_debug_code: bool = False,
    ) -> None:
        self._uow = uow
        self._otp = otp
        self._queue = queue
        self._clock = clock
        self._ids = ids
        self._code_length = code_length
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_attempts = max_attempts
        self._limit_hour = limit_per_hour
        self._limit_day = limit_per_day
        self._expose_debug_code = expose_debug_code

    async def execute(self, cmd: RequestOtpCommand) -> RequestOtpResult:
        now = self._clock.now()
        e164 = PhoneE164(cmd.phone_number)

        async with self._uow:
            sent_last_hour = await self._uow.otps.count_sent_since(
                cmd.user_id, since=now - timedelta(hours=1)
            )
            if sent_last_hour >= self._limit_hour:
                raise RateLimitExceeded(
                    "Too many verification codes requested. Please try again later.",
                    retry_after=3600,
                )
            sent_today = await self._uow.otps.count_sent_since(
                cmd.user_id, since=now - timedelta(days=1)
            )
            if sent_today >= self._limit_day:
                raise RateLimitExceeded(
                    "Daily limit for verification codes reached.", retry_after=86400
                )

            # A first-class "locked" state (VER-02), not just an error thrown
            # at verify time: exceeding attempts on the current code blocks
            # *requesting a new one* too, for whatever's left of that code's
            # TTL. Without this, five wrong guesses were free to route around
            # by immediately asking for a fresh code - the guess counter
            # reset, the lockout never actually happened.
            active = await self._uow.otps.get_active(
                cmd.user_id, purpose=OtpPurpose.PHONE_VERIFICATION
            )
            if (
                active is not None
                and active.attempts >= active.max_attempts
                and now < active.expires_at
            ):
                raise RateLimitExceeded(
                    "Too many incorrect attempts. Try again in a few minutes.",
                    retry_after=int((active.expires_at - now).total_seconds()),
                )

            phone = await self._find_or_create(cmd.user_id, e164, now)

            code = self._otp.generate(self._code_length)
            expires_at = now + self._ttl
            await self._uow.otps.add(
                OtpCode(
                    id=self._ids.new(),
                    user_id=cmd.user_id,
                    phone_number_id=phone.id,
                    purpose=OtpPurpose.PHONE_VERIFICATION,
                    code_hash=self._otp.hash_code(code),
                    expires_at=expires_at,
                    created_at=now,
                    max_attempts=self._max_attempts,
                    sent_at=now,
                )
            )
            await self._uow.commit()

        await self._queue.enqueue(
            "contact.send_otp_sms", to=e164.value, code=code, ttl_minutes=self._ttl.seconds // 60
        )
        return RequestOtpResult(
            phone_number_id=phone.id,
            expires_at=expires_at,
            masked_number=e164.masked(),
            debug_code=code if self._expose_debug_code else None,
        )

    async def _find_or_create(self, user_id: UUID, e164: PhoneE164, now: datetime) -> PhoneNumber:
        existing_numbers = await self._uow.phone_numbers.list_for_user(user_id)
        for existing in existing_numbers:
            if existing.e164.value == e164.value:
                return existing
        return await self._uow.phone_numbers.add(
            PhoneNumber(
                id=self._ids.new(),
                user_id=user_id,
                e164=e164,
                created_at=now,
                # Only the very first number defaults to primary - a second
                # or later one (VER-02's "changing phone number" case) stays
                # a candidate, not the account's number of record, until it
                # actually clears OTP verification. Without this, every new
                # unverified number silently outranked an already-verified
                # one the moment it was created.
                is_primary=not existing_numbers,
            )
        )


@dataclass(frozen=True, slots=True)
class VerifyOtpCommand:
    user_id: UUID
    code: str


@dataclass(frozen=True, slots=True)
class VerifyOtpResult:
    phone_number_id: UUID
    verified: bool


class VerifyPhoneOtp:
    def __init__(
        self,
        *,
        uow: UnitOfWork,
        otp: OtpGenerator,
        queue: JobQueue,
        clock: Clock,
    ) -> None:
        self._uow = uow
        self._otp = otp
        self._queue = queue
        self._clock = clock

    async def execute(self, cmd: VerifyOtpCommand) -> VerifyOtpResult:
        now = self._clock.now()

        async with self._uow:
            active = await self._uow.otps.get_active(
                cmd.user_id, purpose=OtpPurpose.PHONE_VERIFICATION
            )
            if active is None:
                raise OtpExpired("No verification code is pending. Request a new one.")
            if now >= active.expires_at:
                raise OtpExpired("This code has expired. Request a new one.")

            # Atomic: a read-modify-write here would let concurrent requests
            # brute-force past the cap.
            attempts = await self._uow.otps.increment_attempts(active.id)
            if attempts > active.max_attempts:
                await self._uow.commit()
                raise OtpMaxAttemptsExceeded("Too many incorrect attempts. Request a new code.")

            if not self._otp.verify_code(cmd.code, active.code_hash):
                await self._uow.commit()
                raise OtpInvalid("That code is not correct.")

            await self._uow.otps.consume(active.id, at=now)

            if active.phone_number_id is None:
                raise EntityNotFound("phone_number", None)
            phone = await self._uow.phone_numbers.get(active.phone_number_id)
            if phone is None:
                raise EntityNotFound("phone_number", active.phone_number_id)

            await self._uow.phone_numbers.update(
                dataclasses.replace(phone, verified_at=now, is_primary=True)
            )
            # Confirming a new number is what actually completes a phone
            # change (VER-02) - demote every other number for this user so
            # `get_primary` reflects the one that just passed OTP, not
            # whichever was added first.
            for other in await self._uow.phone_numbers.list_for_user(cmd.user_id):
                if other.id != phone.id and other.is_primary:
                    await self._uow.phone_numbers.update(
                        dataclasses.replace(other, is_primary=False)
                    )

            seller = await self._uow.sellers.get_by_user(cmd.user_id)
            if seller is not None:
                await self._uow.sellers.update(
                    dataclasses.replace(
                        seller, phone_status=VerificationStatus.VERIFIED, updated_at=now
                    )
                )

            await self._uow.publish(
                PhoneVerified(
                    aggregate_id=cmd.user_id,
                    occurred_at=now,
                    payload={"phone_number_id": str(phone.id)},
                )
            )
            await self._uow.commit()

        # The carrier / line-type lookup is a separate job: it is a metered
        # third-party call, and the seller should not wait for it to see their
        # number confirmed.
        await self._queue.enqueue("contact.lookup_phone", phone_number_id=str(phone.id))
        if seller is not None:
            await self._queue.enqueue(
                "scoring.recompute_trust_score",
                seller_id=str(seller.id),
                trigger="SIGNAL_CHANGE",
            )

        return VerifyOtpResult(phone_number_id=phone.id, verified=True)


__all__ = [
    "OtpGenerator",
    "RequestOtpCommand",
    "RequestOtpResult",
    "RequestPhoneOtp",
    "VerifyOtpCommand",
    "VerifyOtpResult",
    "VerifyPhoneOtp",
]
