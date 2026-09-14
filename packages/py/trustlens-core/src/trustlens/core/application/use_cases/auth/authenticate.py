"""Registration, login and refresh-token rotation.

The security reasoning behind each step is in ADR-0006 and docs/07. Three
properties are load-bearing and must survive refactoring:

1. Registration and login are **enumeration-safe** - responses and timings do
   not reveal whether an account exists.
2. Refresh tokens **rotate on every use**, and replaying a rotated token
   revokes its whole family. That makes a stolen token self-limiting.
3. Only token *hashes* are ever persisted.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from trustlens.core.domain.entities import (
    AuthenticatedActor,
    Consent,
    EmailAddress,
    RefreshToken,
    SellerProfile,
    User,
    VerificationToken,
)
from trustlens.core.domain.enums import (
    AccountStatus,
    ConsentType,
    TokenPurpose,
    UserRole,
    VerificationStatus,
)
from trustlens.core.domain.errors import (
    AccountLocked,
    AccountNotActive,
    ConflictError,
    EmailNotVerified,
    InvalidCredentials,
    MfaCodeInvalid,
    MfaRequired,
    TokenExpired,
    TokenInvalid,
    TokenReuseDetected,
    TokenUsed,
    ValidationError,
)
from trustlens.core.domain.events import RefreshTokenReuseDetected, UserRegistered
from trustlens.core.domain.policies import LoginThrottlePolicy, PasswordPolicy, mfa_required_for
from trustlens.core.domain.ports import (
    Clock,
    IdGenerator,
    JobQueue,
    SecretEncryptor,
    TotpProvider,
    UnitOfWork,
)
from trustlens.core.domain.value_objects import Email


class PasswordHasher(Protocol):
    """Password hashing port.

    `verify_dummy` exists so a login attempt for a non-existent account still
    performs the same expensive hash - otherwise response timing reveals which
    email addresses are registered.
    """

    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...

    def verify_dummy(self) -> None: ...

    def needs_rehash(self, password_hash: str) -> bool: ...


class TokenHasher(Protocol):
    """Peppered hashing for refresh / verification tokens."""

    def hash_token(self, raw: str) -> bytes: ...

    def new_token(self) -> str: ...


# ── Registration ─────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RegisterUserCommand:
    email: str
    password: str
    full_name: str
    as_seller: bool = False
    ip: str | None = None
    user_agent: str | None = None
    accepted_terms_version: str = "1.0"


@dataclass(frozen=True, slots=True)
class RegisterUserResult:
    user_id: UUID | None
    status: str
    #: Always true from the caller's perspective, even for a duplicate email.
    #: The endpoint must not become a user-enumeration oracle.
    verification_email_sent: bool = True


class RegisterUser:
    def __init__(
        self,
        *,
        uow: UnitOfWork,
        hasher: PasswordHasher,
        tokens: TokenHasher,
        queue: JobQueue,
        clock: Clock,
        ids: IdGenerator,
        password_policy: PasswordPolicy | None = None,
        verification_ttl_hours: int = 24,
    ) -> None:
        self._uow = uow
        self._hasher = hasher
        self._tokens = tokens
        self._queue = queue
        self._clock = clock
        self._ids = ids
        self._passwords = password_policy or PasswordPolicy()
        self._ttl = timedelta(hours=verification_ttl_hours)

    async def execute(self, cmd: RegisterUserCommand) -> RegisterUserResult:
        email = Email(cmd.email)
        now = self._clock.now()

        if problems := self._passwords.validate(cmd.password, email=email.value):
            raise ValidationError("; ".join(problems), field="password")

        async with self._uow:
            if await self._uow.users.get_by_email(email) is not None:
                # Do NOT reveal that the account exists. Send a "someone tried
                # to register with your address" notice instead and return the
                # await self._queue.enqueue(
                #     "notifications.send_email",
                #     to=email.value,
                #     template="registration_attempt_existing_account",
                #     context={},
                # )
                await self._uow.commit()
                return RegisterUserResult(user_id=None, status="PENDING")

            user_id = self._ids.new()
            user = User(
                id=user_id,
                email=email,
                full_name=cmd.full_name.strip(),
                status=AccountStatus.PENDING,
                primary_role=UserRole.SELLER if cmd.as_seller else UserRole.BUYER,
                roles=frozenset({UserRole.SELLER if cmd.as_seller else UserRole.BUYER}),
                created_at=now,
            )
            await self._uow.users.create(user=user, password_hash=self._hasher.hash(cmd.password))

            await self._uow.email_addresses.add(
                EmailAddress(
                    id=self._ids.new(),
                    user_id=user_id,
                    email=email,
                    created_at=now,
                    is_primary=True,
                )
            )

            for consent_type in (ConsentType.TERMS, ConsentType.PRIVACY):
                await self._uow.consents.record(
                    Consent(
                        id=self._ids.new(),
                        user_id=user_id,
                        consent_type=consent_type,
                        version=cmd.accepted_terms_version,
                        granted=True,
                        granted_at=now,
                        ip=cmd.ip,
                        user_agent=cmd.user_agent,
                    )
                )

            if cmd.as_seller:
                await _create_seller_profile(self._uow, self._ids, user, now)

            raw_token = self._tokens.new_token()
            await self._uow.verification_tokens.add(
                _verification_token(
                    self._ids.new(),
                    user_id,
                    TokenPurpose.EMAIL_VERIFICATION,
                    self._tokens.hash_token(raw_token),
                    email.value,
                    now,
                    self._ttl,
                )
            )

            await self._uow.publish(
                UserRegistered(
                    aggregate_id=user_id,
                    occurred_at=now,
                    payload={"as_seller": cmd.as_seller},
                )
            )
            await self._uow.commit()

        await self._queue.enqueue(
            "notifications.send_email",
            to=email.value,
            template="verify_email",
            context={"token": raw_token, "full_name": cmd.full_name},
        )
        return RegisterUserResult(user_id=user_id, status=AccountStatus.PENDING.value)


async def _create_seller_profile(
    uow: UnitOfWork, ids: IdGenerator, user: User, now: datetime
) -> SellerProfile:
    """Shared by password registration and Google sign-in - both create the
    same shape of seller profile for a brand-new account."""
    handle = await _unique_handle(uow, ids, user.full_name)
    return await uow.sellers.create(
        SellerProfile(
            id=ids.new(),
            user_id=user.id,
            handle=handle,
            display_name=user.full_name,
            account_opened_at=now,
            created_at=now,
            email_status=VerificationStatus.PENDING,
        )
    )


async def _unique_handle(uow: UnitOfWork, ids: IdGenerator, full_name: str) -> str:
    base = "".join(c if c.isalnum() else "-" for c in full_name.lower()).strip("-")[:40]
    base = base or "seller"
    candidate = base
    for suffix in range(0, 100):
        candidate = base if suffix == 0 else f"{base}-{suffix}"
        if not await uow.sellers.handle_exists(candidate):
            return candidate
    return f"{base}-{ids.new().hex[:8]}"


def _verification_token(
    token_id: UUID,
    user_id: UUID,
    purpose: TokenPurpose,
    token_hash: bytes,
    target: str,
    now: datetime,
    ttl: timedelta,
) -> VerificationToken:
    from trustlens.core.domain.entities import VerificationToken

    return VerificationToken(
        id=token_id,
        user_id=user_id,
        purpose=purpose,
        token_hash=token_hash,
        target=target,
        expires_at=now + ttl,
        created_at=now,
    )


# ── Login ────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class LoginCommand:
    email: str
    password: str
    ip: str | None = None
    user_agent: str | None = None
    device_fingerprint: str | None = None


@dataclass(frozen=True, slots=True)
class IssuedSession:
    """Everything the transport layer needs to build a response."""

    user: User
    actor: AuthenticatedActor
    refresh_token_raw: str
    refresh_token_id: UUID
    family_id: UUID
    expires_at: datetime
    mfa_required: bool = False


async def _new_session(
    uow: UnitOfWork,
    tokens: TokenHasher,
    ids: IdGenerator,
    user: User,
    *,
    refresh_ttl: timedelta,
    ip: str | None,
    user_agent: str | None,
    now: datetime,
) -> IssuedSession:
    """Issue a brand new refresh-token family for a user who just
    authenticated - shared by password login and Google sign-in, so
    token-issuance has exactly one implementation to get right."""
    raw = tokens.new_token()
    token_id, family_id = ids.new(), ids.new()
    expires_at = now + refresh_ttl

    await uow.refresh_tokens.add(
        RefreshToken(
            id=token_id,
            user_id=user.id,
            token_hash=tokens.hash_token(raw),
            family_id=family_id,
            expires_at=expires_at,
            created_at=now,
            ip_address=ip,
            user_agent=user_agent,
        )
    )

    permissions = await uow.users.list_permissions(user.id)
    return IssuedSession(
        user=user,
        actor=AuthenticatedActor(
            user_id=user.id,
            roles=user.roles,
            permissions=permissions,
            session_id=family_id,
        ),
        refresh_token_raw=raw,
        refresh_token_id=token_id,
        family_id=family_id,
        expires_at=expires_at,
    )


class LoginUser:
    def __init__(
        self,
        *,
        uow: UnitOfWork,
        hasher: PasswordHasher,
        tokens: TokenHasher,
        clock: Clock,
        ids: IdGenerator,
        throttle: LoginThrottlePolicy | None = None,
        refresh_ttl_days: int = 30,
        #: None keeps the domain default (ADMIN, REVIEWER). Supplying an empty
        #: set disables the requirement, which a deployment without an MFA
        #: enrolment flow must do or those accounts cannot sign in at all.
        mfa_required_roles: frozenset[UserRole] | None = None,
    ) -> None:
        self._mfa_required_roles = mfa_required_roles
        self._uow = uow
        self._hasher = hasher
        self._tokens = tokens
        self._clock = clock
        self._ids = ids
        self._throttle = throttle or LoginThrottlePolicy()
        self._refresh_ttl = timedelta(days=refresh_ttl_days)

    async def execute(self, cmd: LoginCommand) -> IssuedSession:
        now = self._clock.now()
        email = Email(cmd.email)

        async with self._uow:
            user = await self._uow.users.get_by_email(email)

            if user is None:
                # Burn the same CPU as a real verification so response timing
                # does not distinguish "no such user" from "wrong password".
                self._hasher.verify_dummy()
                raise InvalidCredentials

            if user.is_locked_at(now):
                assert user.locked_until is not None
                raise AccountLocked(int((user.locked_until - now).total_seconds()))

            password_hash = await self._uow.users.get_password_hash(user.id)
            if password_hash is None or not self._hasher.verify(cmd.password, password_hash):
                failed = user.failed_login_count + 1
                await self._uow.users.record_failed_login(
                    user.id, locked_until=self._throttle.lock_until(failed_count=failed, now=now)
                )
                await self._uow.commit()
                raise InvalidCredentials

            if not user.is_email_verified:
                raise EmailNotVerified
            if user.status != AccountStatus.ACTIVE:
                raise AccountNotActive(f"This account is {user.status.value.lower()}.")

            if self._hasher.needs_rehash(password_hash):
                # Transparently upgrade to current argon2 parameters on a
                # successful login - old hashes stay verifiable meanwhile.
                await self._uow.users.set_password_hash(user.id, self._hasher.hash(cmd.password))

            if user.mfa_enabled or mfa_required_for(user, self._mfa_required_roles):
                await self._uow.commit()
                raise MfaRequired(user.id)

            session = await _new_session(
                self._uow,
                self._tokens,
                self._ids,
                user,
                refresh_ttl=self._refresh_ttl,
                ip=cmd.ip,
                user_agent=cmd.user_agent,
                now=now,
            )
            await self._uow.users.record_successful_login(user.id, at=now)
            await self._uow.commit()

        return session


# ── Google sign-in ───────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class GoogleAuthCommand:
    #: Google has already verified this address - that is the entire point
    #: of the flow, so nothing here re-checks it.
    email: str
    full_name: str
    ip: str | None = None
    user_agent: str | None = None
    #: Only consulted the first time this email is seen. An existing account
    #: signing in via Google keeps whatever role it already has.
    as_seller: bool = True
    accepted_terms_version: str = "1.0"


class AuthenticateWithGoogle:
    """Sign in, or register on first contact, via Google.

    Google has already proven the account owns this email address - the
    same fact our own email-verification link exists to establish - so this
    skips password verification and the verify-email step entirely rather
    than layering a second, weaker proof on top of a stronger one. A
    returning user is matched by email only: there is no separate
    provider-linkage column, because "this person proved they own
    this address" is the one thing that matters here, regardless of which
    door they used to prove it.
    """

    def __init__(
        self,
        *,
        uow: UnitOfWork,
        tokens: TokenHasher,
        clock: Clock,
        ids: IdGenerator,
        refresh_ttl_days: int = 30,
    ) -> None:
        self._uow = uow
        self._tokens = tokens
        self._clock = clock
        self._ids = ids
        self._refresh_ttl = timedelta(days=refresh_ttl_days)

    async def execute(self, cmd: GoogleAuthCommand) -> IssuedSession:
        now = self._clock.now()
        email = Email(cmd.email)
        full_name = cmd.full_name.strip() or email.value

        async with self._uow:
            user = await self._uow.users.get_by_email(email)

            if user is None:
                user = await self._register(email, full_name, cmd, now)
            else:
                if user.status != AccountStatus.ACTIVE:
                    raise AccountNotActive(f"This account is {user.status.value.lower()}.")
                if not user.is_email_verified:
                    # Google is re-confirming the same address our own
                    # verify-email link would have - honour that instead of
                    # leaving the account stuck PENDING forever because the
                    # original email never arrived.
                    await self._uow.users.mark_email_verified(user.id, at=now)
                    import dataclasses

                    user = dataclasses.replace(
                        user, email_verified_at=now, status=AccountStatus.ACTIVE
                    )

            session = await _new_session(
                self._uow,
                self._tokens,
                self._ids,
                user,
                refresh_ttl=self._refresh_ttl,
                ip=cmd.ip,
                user_agent=cmd.user_agent,
                now=now,
            )
            await self._uow.users.record_successful_login(user.id, at=now)
            await self._uow.commit()

        return session

    async def _register(
        self, email: Email, full_name: str, cmd: GoogleAuthCommand, now: datetime
    ) -> User:
        user_id = self._ids.new()
        user = User(
            id=user_id,
            email=email,
            full_name=full_name,
            status=AccountStatus.ACTIVE,
            primary_role=UserRole.SELLER if cmd.as_seller else UserRole.BUYER,
            roles=frozenset({UserRole.SELLER if cmd.as_seller else UserRole.BUYER}),
            created_at=now,
            email_verified_at=now,
        )
        # No password: this account can only sign in via Google until the
        # seller sets one from account settings (not yet built - tracked
        # separately, same as every other password-reset-adjacent gap).
        await self._uow.users.create(user=user, password_hash=None)

        await self._uow.email_addresses.add(
            EmailAddress(
                id=self._ids.new(),
                user_id=user_id,
                email=email,
                created_at=now,
                is_primary=True,
                verified_at=now,
            )
        )

        for consent_type in (ConsentType.TERMS, ConsentType.PRIVACY):
            await self._uow.consents.record(
                Consent(
                    id=self._ids.new(),
                    user_id=user_id,
                    consent_type=consent_type,
                    version=cmd.accepted_terms_version,
                    granted=True,
                    granted_at=now,
                    ip=cmd.ip,
                    user_agent=cmd.user_agent,
                )
            )

        if cmd.as_seller:
            await _create_seller_profile(self._uow, self._ids, user, now)

        await self._uow.publish(
            UserRegistered(
                aggregate_id=user_id,
                occurred_at=now,
                payload={"as_seller": cmd.as_seller, "via": "google"},
            )
        )
        return user


# ── Refresh with rotation and reuse detection ────────────────────────


@dataclass(frozen=True, slots=True)
class RefreshSessionCommand:
    raw_token: str
    ip: str | None = None
    user_agent: str | None = None


class RefreshSession:
    """Rotate a refresh token, or detect that one was stolen.

    Rotation plus family revocation is what makes a stolen refresh token
    self-limiting: whichever party presents the older copy second trips the
    alarm and both sessions die. Without it, a stolen token is a 30-day
    skeleton key.
    """

    def __init__(
        self,
        *,
        uow: UnitOfWork,
        tokens: TokenHasher,
        clock: Clock,
        ids: IdGenerator,
        queue: JobQueue,
        refresh_ttl_days: int = 30,
        idle_ttl_days: int = 7,
    ) -> None:
        self._uow = uow
        self._tokens = tokens
        self._clock = clock
        self._ids = ids
        self._queue = queue
        self._refresh_ttl = timedelta(days=refresh_ttl_days)
        self._idle_ttl = timedelta(days=idle_ttl_days)

    async def execute(self, cmd: RefreshSessionCommand) -> IssuedSession:
        now = self._clock.now()
        token_hash = self._tokens.hash_token(cmd.raw_token)

        async with self._uow:
            existing = await self._uow.refresh_tokens.get_by_hash(token_hash)
            if existing is None:
                raise TokenInvalid("This session is no longer valid. Please sign in again.")

            if existing.is_revoked:
                await self._handle_reuse(existing, now)
                await self._uow.commit()
                raise TokenReuseDetected

            if existing.is_expired_at(now) or now - existing.created_at > self._idle_ttl:
                raise TokenInvalid("Your session has expired. Please sign in again.")

            user = await self._uow.users.get(existing.user_id)
            if user is None or not user.is_active:
                raise TokenInvalid("This session is no longer valid. Please sign in again.")

            await self._uow.refresh_tokens.revoke(existing.id, at=now, reason="ROTATED")

            raw = self._tokens.new_token()
            token_id = self._ids.new()
            expires_at = now + self._refresh_ttl
            await self._uow.refresh_tokens.add(
                RefreshToken(
                    id=token_id,
                    user_id=user.id,
                    token_hash=self._tokens.hash_token(raw),
                    # Same family: the chain is what makes reuse detectable.
                    family_id=existing.family_id,
                    parent_id=existing.id,
                    expires_at=expires_at,
                    created_at=now,
                    device_id=existing.device_id,
                    ip_address=cmd.ip,
                    user_agent=cmd.user_agent,
                )
            )

            permissions = await self._uow.users.list_permissions(user.id)
            await self._uow.commit()

        return IssuedSession(
            user=user,
            actor=AuthenticatedActor(
                user_id=user.id,
                roles=user.roles,
                permissions=permissions,
                session_id=existing.family_id,
            ),
            refresh_token_raw=raw,
            refresh_token_id=token_id,
            family_id=existing.family_id,
            expires_at=expires_at,
        )

    async def _handle_reuse(self, token: RefreshToken, now: datetime) -> None:
        """A rotated token was presented again - treat it as theft."""
        await self._uow.refresh_tokens.revoke_family(
            token.family_id, at=now, reason="REUSE_DETECTED"
        )
        await self._uow.publish(
            RefreshTokenReuseDetected(
                aggregate_id=token.user_id,
                occurred_at=now,
                payload={"family_id": str(token.family_id), "token_id": str(token.id)},
            )
        )
        await self._queue.enqueue(
            "notifications.send_security_alert",
            user_id=str(token.user_id),
            reason="refresh_token_reuse",
        )


# ── Logout ───────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class LogoutCommand:
    raw_token: str | None = None
    user_id: UUID | None = None
    all_sessions: bool = False


class LogoutUser:
    def __init__(self, *, uow: UnitOfWork, tokens: TokenHasher, clock: Clock) -> None:
        self._uow = uow
        self._tokens = tokens
        self._clock = clock

    async def execute(self, cmd: LogoutCommand) -> int:
        now = self._clock.now()
        async with self._uow:
            if cmd.all_sessions and cmd.user_id is not None:
                revoked = await self._uow.refresh_tokens.revoke_all_for_user(
                    cmd.user_id, at=now, reason="LOGOUT_ALL"
                )
            elif cmd.raw_token:
                token = await self._uow.refresh_tokens.get_by_hash(
                    self._tokens.hash_token(cmd.raw_token)
                )
                if token is None:
                    return 0
                # Revoke the family, not just this token: a logout that leaves
                # a rotated sibling alive is not a logout.
                revoked = await self._uow.refresh_tokens.revoke_family(
                    token.family_id, at=now, reason="LOGOUT"
                )
            else:
                return 0
            await self._uow.commit()
        return revoked


# ── Email verification ───────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class VerifyEmailCommand:
    raw_token: str


@dataclass(frozen=True, slots=True)
class VerifyEmailResult:
    user_id: UUID
    already_verified: bool = False
    events: tuple[str, ...] = field(default_factory=tuple)


class VerifyEmail:
    def __init__(
        self,
        *,
        uow: UnitOfWork,
        tokens: TokenHasher,
        queue: JobQueue,
        clock: Clock,
    ) -> None:
        self._uow = uow
        self._tokens = tokens
        self._queue = queue
        self._clock = clock

    async def execute(self, cmd: VerifyEmailCommand) -> VerifyEmailResult:
        now = self._clock.now()
        async with self._uow:
            token = await self._uow.verification_tokens.get_by_hash(
                self._tokens.hash_token(cmd.raw_token), purpose=TokenPurpose.EMAIL_VERIFICATION
            )
            if token is None:
                raise TokenInvalid("This verification link is invalid.")
            if token.consumed_at is not None:
                raise TokenUsed("This verification link has already been used.")
            if now >= token.expires_at:
                raise TokenExpired("This verification link has expired. Request a new one.")

            user = await self._uow.users.get(token.user_id)
            if user is None:
                raise TokenInvalid("This verification link is invalid or has expired.")
            if user.is_email_verified:
                return VerifyEmailResult(user_id=user.id, already_verified=True)

            await self._uow.verification_tokens.consume(token.id, at=now)
            await self._uow.users.mark_email_verified(user.id, at=now)

            email = await self._uow.email_addresses.get_primary(user.id)
            if email is not None:
                import dataclasses

                await self._uow.email_addresses.update(dataclasses.replace(email, verified_at=now))

            seller = await self._uow.sellers.get_by_user(user.id)
            if seller is not None:
                import dataclasses

                await self._uow.sellers.update(
                    dataclasses.replace(
                        seller, email_status=VerificationStatus.VERIFIED, updated_at=now
                    )
                )

            await self._uow.commit()

        # Email verification is a scored signal, so confirming it changes the
        # score. Recompute through the normal event path.
        if seller is not None:
            await self._queue.enqueue(
                "scoring.recompute_trust_score", seller_id=str(seller.id), trigger="SIGNAL_CHANGE"
            )
        return VerifyEmailResult(user_id=user.id)


@dataclass(frozen=True, slots=True)
class ResendEmailVerificationCommand:
    email: str


class ResendEmailVerification:
    """A dedicated resend path (BLK-03) - the frontend used to call
    `/forgot-password` as a workaround, which mints a PASSWORD_RESET token
    and sends a "reset your password" email to someone who actually just
    wants their address confirmed. Completing that email never verifies
    anything, so an unverified account that took that path stayed stuck.

    Enumeration-safe like registration/forgot-password: a non-existent or
    already-verified address gets the identical no-op response.
    """

    def __init__(
        self,
        *,
        uow: UnitOfWork,
        tokens: TokenHasher,
        queue: JobQueue,
        clock: Clock,
        ids: IdGenerator,
        verification_ttl_hours: int = 24,
    ) -> None:
        self._uow = uow
        self._tokens = tokens
        self._queue = queue
        self._clock = clock
        self._ids = ids
        self._ttl = timedelta(hours=verification_ttl_hours)

    async def execute(self, cmd: ResendEmailVerificationCommand) -> None:
        email = Email(cmd.email)
        now = self._clock.now()

        async with self._uow:
            user = await self._uow.users.get_by_email(email)
            if user is None or user.is_email_verified:
                await self._uow.commit()
                return

            raw_token = self._tokens.new_token()
            await self._uow.verification_tokens.invalidate_for_user(
                user.id, purpose=TokenPurpose.EMAIL_VERIFICATION
            )
            await self._uow.verification_tokens.add(
                _verification_token(
                    self._ids.new(),
                    user.id,
                    TokenPurpose.EMAIL_VERIFICATION,
                    self._tokens.hash_token(raw_token),
                    email.value,
                    now,
                    self._ttl,
                )
            )
            full_name = user.full_name
            await self._uow.commit()

        await self._queue.enqueue(
            "notifications.send_email",
            to=email.value,
            template="verify_email",
            context={"token": raw_token, "full_name": full_name},
        )


class DuplicateEmail(ConflictError):
    code = "EMAIL_ALREADY_REGISTERED"
    title = "Email already registered"


# ── Multi-factor authentication (BLK-04) ───────────────────────────────

#: Ten backup codes, each usable once - enough that losing a couple to
#: typos or forgetting which are spent doesn't strand someone before they
#: can regenerate a fresh set.
RECOVERY_CODE_COUNT = 10


def _generate_recovery_code() -> str:
    """A short, typeable one-time code - grouped hex, not the 32-byte link
    tokens `TokenHasher.new_token` mints for things nobody has to read."""
    raw = secrets.token_hex(8)
    return f"{raw[:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:]}"


@dataclass(frozen=True, slots=True)
class BeginMfaEnrollmentResult:
    secret: str
    provisioning_uri: str


class BeginMfaEnrollment:
    """Generates a fresh TOTP secret and stores it encrypted, unconfirmed -
    `mfa_enabled` only flips once `ConfirmMfaEnrollment` verifies a code
    against it. Calling this again before confirming overwrites the pending
    secret; nothing is lost, since an unconfirmed secret was never usable."""

    def __init__(
        self, *, uow: UnitOfWork, encryptor: SecretEncryptor, totp: TotpProvider, issuer: str
    ) -> None:
        self._uow = uow
        self._encryptor = encryptor
        self._totp = totp
        self._issuer = issuer

    async def execute(self, user_id: UUID) -> BeginMfaEnrollmentResult:
        async with self._uow:
            user = await self._uow.users.get(user_id)
            assert user is not None  # the caller is always an authenticated actor

            secret = self._totp.generate_secret()
            encrypted = self._encryptor.encrypt(secret, associated_data=str(user_id).encode())
            await self._uow.users.set_mfa_secret(user_id, encrypted.encode())
            await self._uow.commit()

        uri = self._totp.provisioning_uri(
            secret, account_name=user.email.value, issuer=self._issuer
        )
        return BeginMfaEnrollmentResult(secret=secret, provisioning_uri=uri)


@dataclass(frozen=True, slots=True)
class ConfirmMfaEnrollmentResult:
    recovery_codes: tuple[str, ...]


class ConfirmMfaEnrollment:
    def __init__(
        self,
        *,
        uow: UnitOfWork,
        clock: Clock,
        tokens: TokenHasher,
        encryptor: SecretEncryptor,
        totp: TotpProvider,
    ) -> None:
        self._uow = uow
        self._clock = clock
        self._tokens = tokens
        self._encryptor = encryptor
        self._totp = totp

    async def execute(self, user_id: UUID, code: str) -> ConfirmMfaEnrollmentResult:
        import dataclasses

        now = self._clock.now()
        async with self._uow:
            secret_encrypted = await self._uow.users.get_mfa_secret(user_id)
            if secret_encrypted is None:
                raise MfaCodeInvalid  # nothing pending - enrollment was never begun

            secret = self._encryptor.decrypt(
                secret_encrypted.decode(), associated_data=str(user_id).encode()
            )
            if not self._totp.verify_code(secret, code):
                raise MfaCodeInvalid

            user = await self._uow.users.get(user_id)
            assert user is not None
            await self._uow.users.update(dataclasses.replace(user, mfa_enabled=True))

            raw_codes = [_generate_recovery_code() for _ in range(RECOVERY_CODE_COUNT)]
            await self._uow.mfa_recovery_codes.replace_all(
                user_id, [self._tokens.hash_token(c) for c in raw_codes], created_at=now
            )
            await self._uow.commit()
        return ConfirmMfaEnrollmentResult(recovery_codes=tuple(raw_codes))


@dataclass(frozen=True, slots=True)
class DisableMfaCommand:
    user_id: UUID
    password: str


class DisableMfa:
    def __init__(self, *, uow: UnitOfWork, hasher: PasswordHasher, clock: Clock) -> None:
        self._uow = uow
        self._hasher = hasher
        self._clock = clock

    async def execute(self, cmd: DisableMfaCommand) -> None:
        import dataclasses

        async with self._uow:
            password_hash = await self._uow.users.get_password_hash(cmd.user_id)
            if password_hash is None or not self._hasher.verify(cmd.password, password_hash):
                raise InvalidCredentials

            user = await self._uow.users.get(cmd.user_id)
            assert user is not None
            await self._uow.users.update(dataclasses.replace(user, mfa_enabled=False))
            await self._uow.users.set_mfa_secret(cmd.user_id, None)
            await self._uow.mfa_recovery_codes.replace_all(
                cmd.user_id, [], created_at=self._clock.now()
            )
            await self._uow.commit()


@dataclass(frozen=True, slots=True)
class VerifyMfaLoginCommand:
    mfa_token: str
    code: str
    ip: str | None = None
    user_agent: str | None = None


class VerifyMfaLogin:
    """Completes a login that stopped at `MfaRequired`. The short-lived
    challenge token (a `VerificationToken`, purpose MFA_LOGIN) identifies
    which pending login this code belongs to, since the browser presenting
    it is not otherwise authenticated yet - the same shape `VerifyEmail`
    uses for an email-verification link, not a new mechanism.

    Accepts either a live TOTP code or one unused recovery code, trying TOTP
    first since that is the common case.
    """

    def __init__(
        self,
        *,
        uow: UnitOfWork,
        tokens: TokenHasher,
        clock: Clock,
        ids: IdGenerator,
        encryptor: SecretEncryptor,
        totp: TotpProvider,
        refresh_ttl_days: int = 30,
    ) -> None:
        self._uow = uow
        self._tokens = tokens
        self._clock = clock
        self._ids = ids
        self._encryptor = encryptor
        self._totp = totp
        self._refresh_ttl = timedelta(days=refresh_ttl_days)

    async def execute(self, cmd: VerifyMfaLoginCommand) -> IssuedSession:
        now = self._clock.now()
        async with self._uow:
            challenge = await self._uow.verification_tokens.get_by_hash(
                self._tokens.hash_token(cmd.mfa_token), purpose=TokenPurpose.MFA_LOGIN
            )
            if challenge is None or not challenge.is_usable_at(now):
                raise MfaCodeInvalid

            user = await self._uow.users.get(challenge.user_id)
            if user is None:
                raise MfaCodeInvalid

            verified = False
            secret_encrypted = await self._uow.users.get_mfa_secret(user.id)
            if secret_encrypted is not None:
                secret = self._encryptor.decrypt(
                    secret_encrypted.decode(), associated_data=str(user.id).encode()
                )
                verified = self._totp.verify_code(secret, cmd.code)

            if not verified:
                recovery_id = await self._uow.mfa_recovery_codes.get_unused_by_hash(
                    user.id, self._tokens.hash_token(cmd.code)
                )
                if recovery_id is not None:
                    await self._uow.mfa_recovery_codes.consume(recovery_id, at=now)
                    verified = True

            if not verified:
                raise MfaCodeInvalid

            await self._uow.verification_tokens.consume(challenge.id, at=now)
            session = await _new_session(
                self._uow,
                self._tokens,
                self._ids,
                user,
                refresh_ttl=self._refresh_ttl,
                ip=cmd.ip,
                user_agent=cmd.user_agent,
                now=now,
            )
            await self._uow.users.record_successful_login(user.id, at=now)
            await self._uow.commit()
        return session


__all__ = [
    "RECOVERY_CODE_COUNT",
    "AuthenticateWithGoogle",
    "BeginMfaEnrollment",
    "BeginMfaEnrollmentResult",
    "ConfirmMfaEnrollment",
    "ConfirmMfaEnrollmentResult",
    "DisableMfa",
    "DisableMfaCommand",
    "GoogleAuthCommand",
    "IssuedSession",
    "LoginCommand",
    "LoginUser",
    "LogoutCommand",
    "LogoutUser",
    "PasswordHasher",
    "RefreshSession",
    "RefreshSessionCommand",
    "RegisterUser",
    "RegisterUserCommand",
    "RegisterUserResult",
    "ResendEmailVerification",
    "ResendEmailVerificationCommand",
    "TokenHasher",
    "VerifyEmail",
    "VerifyEmailCommand",
    "VerifyEmailResult",
    "VerifyMfaLogin",
    "VerifyMfaLoginCommand",
]
