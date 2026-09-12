"""Authentication endpoints.

The refresh token is delivered as an httpOnly cookie and never appears in a
response body - an XSS payload must not be able to read it (ADR-0006).
"""

from __future__ import annotations

import secrets
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Request, Response, status
from fastapi.responses import RedirectResponse

from trustlens.core.application.use_cases.auth import (
    AuthenticateWithGoogle,
    GoogleAuthCommand,
    IssuedSession,
    LoginCommand,
    LoginUser,
    LogoutCommand,
    LogoutUser,
    RefreshSession,
    RefreshSessionCommand,
    RegisterUser,
    RegisterUserCommand,
    VerifyEmail,
    VerifyEmailCommand,
)
from trustlens.core.domain.enums import UserRole
from trustlens.core.domain.errors import RateLimitExceeded, TokenInvalid
from trustlens.core.domain.policies import LoginThrottlePolicy, PasswordPolicy
from trustlens.db.unit_of_work import SqlAlchemyUnitOfWork
from trustlens.shared.logging import get_logger
from trustlens_api.api.deps import ActorDep, ContainerDep, MetaDep, RequestMeta, UowDep
from trustlens_api.api.v1.schemas.auth import (
    ChangePasswordRequest,
    DeleteAccountRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    RegisterResponse,
    ResetPasswordRequest,
    SessionSummary,
    UserSummary,
    VerifyEmailRequest,
)
from trustlens_api.api.v1.schemas.common import MessageResponse, envelope
from trustlens_api.container import Container
from trustlens_api.core.cookies import clear_refresh_cookie, set_refresh_cookie
from trustlens_api.google_oauth import GoogleOAuthError, build_authorize_url, exchange_code

log = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

#: Short-lived, single-purpose - only proves the callback belongs to the
#: browser that started this specific login attempt (CSRF), never read
#: anywhere else.
_OAUTH_STATE_COOKIE = "tl_oauth_state"
_OAUTH_STATE_PATH = "/api/v1/auth/google"


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
    description=(
        "Creates a PENDING account and emails a verification link. "
        "Responds identically whether or not the address is already "
        "registered, so the endpoint cannot be used to enumerate users."
    ),
)
async def register(
    body: RegisterRequest,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
    request: Request,
) -> dict[str, Any]:
    use_case = RegisterUser(
        uow=uow,
        hasher=container.password_hasher,
        tokens=container.token_hasher,
        queue=container.queue,
        clock=container.clock,
        ids=container.ids,
        password_policy=PasswordPolicy(container.settings.security.password_min_length),
    )
    result = await use_case.execute(
        RegisterUserCommand(
            email=body.email,
            password=body.password,
            full_name=body.full_name,
            as_seller=body.as_seller,
            ip=meta.ip,
            user_agent=meta.user_agent,
        )
    )
    return envelope(
        RegisterResponse(user_id=result.user_id, status=result.status).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


async def _throttle_login_by_ip(container: Container, meta: RequestMeta) -> None:
    """Per-IP login throttle, on top of the per-account lockout (P10-03).

    `LoginThrottlePolicy` locks an ACCOUNT after repeated failures, which stops
    someone grinding one password. It does nothing about the other shape of the
    same attack: one IP trying one password against a thousand different
    addresses. Every attempt hits an account that does not exist, so no counter
    anywhere goes up, and a security scan of the login endpoint comes back
    clean while the spray runs.

    Counted on every attempt rather than only on failures, because at this
    point we have not checked the credentials yet - and deciding whether to
    count first would leak whether the account exists through response timing.

    **Fails OPEN.** If Redis is unavailable this lets the request through: the
    per-account lockout still applies, and a cache blip must not lock every
    user out of the product. That is the opposite of the partner API's choice,
    and deliberately so - there, refusing traffic protects cost; here, refusing
    traffic IS the outage.
    """
    limits = container.settings.rate_limit
    if not limits.enabled or meta.ip is None:
        return

    try:
        allowed, _remaining, retry_after = await container.rate_limiter.hit(
            f"login:ip:{meta.ip}",
            limit=limits.login_ip_per_15min,
            window_seconds=900,
        )
    except Exception:
        log.warning("login_ip_throttle_unavailable_failing_open", ip=meta.ip)
        return

    if not allowed:
        log.warning("login_ip_throttled", ip=meta.ip)
        raise RateLimitExceeded(
            "Too many sign-in attempts from this address. Try again shortly.",
            retry_after=retry_after,
        )


@router.post("/login", summary="Sign in")
async def login(
    body: LoginRequest,
    response: Response,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    await _throttle_login_by_ip(container, meta)

    use_case = LoginUser(
        uow=uow,
        hasher=container.password_hasher,
        tokens=container.token_hasher,
        clock=container.clock,
        ids=container.ids,
        throttle=LoginThrottlePolicy(soft_limit=container.settings.rate_limit.login_per_15min),
        refresh_ttl_days=container.settings.security.refresh_token_ttl_days,
        # Makes SECURITY_MFA_REQUIRED_ROLES real. It was previously a setting
        # nothing read: the domain hardcoded ADMIN and REVIEWER, so with no MFA
        # enrolment endpoint those accounts could not sign in at all and no
        # configuration could change it.
        mfa_required_roles=frozenset(
            UserRole(role) for role in container.settings.security.mfa_required_roles
        ),
    )
    session = await use_case.execute(
        LoginCommand(
            email=body.email,
            password=body.password,
            ip=meta.ip,
            user_agent=meta.user_agent,
            device_fingerprint=body.device_fingerprint or meta.device_fingerprint,
        )
    )
    return await _issue_session_response(session, response, container, uow, meta)


@router.get(
    "/google/login",
    summary="Start Google sign-in",
    description=(
        "Redirects to Google's consent screen. Not JSON: the browser must "
        "navigate here directly (a link or `window.location`), not fetch it."
    ),
)
async def google_login(container: ContainerDep) -> RedirectResponse:
    if not container.settings.google_auth.is_configured:
        raise TokenInvalid("Google sign-in is not configured on this deployment.")

    state = secrets.token_urlsafe(24)
    redirect = RedirectResponse(
        build_authorize_url(container.settings.google_auth, state=state),
        status_code=status.HTTP_302_FOUND,
    )
    redirect.set_cookie(
        key=_OAUTH_STATE_COOKIE,
        value=state,
        max_age=600,
        httponly=True,
        secure=container.settings.env.is_deployed,
        samesite="lax",
        path=_OAUTH_STATE_PATH,
    )
    return redirect


@router.get(
    "/google/callback",
    summary="Google redirects back here after consent",
    description=(
        "Exchanges the authorization code, signs the user in (or registers "
        "them on first contact), sets the refresh cookie exactly like "
        "/login does, and redirects into the app. The frontend never talks "
        "to this endpoint directly - it only ever receives a browser "
        "redirect starting at /google/login."
    ),
)
async def google_callback(
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    tl_oauth_state: Annotated[str | None, Cookie()] = None,
) -> RedirectResponse:
    failure = RedirectResponse(
        f"{container.settings.web_base_url}/login?error=google",
        status_code=status.HTTP_302_FOUND,
    )
    failure.delete_cookie(key=_OAUTH_STATE_COOKIE, path=_OAUTH_STATE_PATH)

    # Constant-shape check on purpose: a missing cookie (state expired or
    # cookies blocked), a missing code (user denied consent), and a state
    # mismatch (CSRF) all fail the same way rather than leaking which one.
    if (
        error
        or not code
        or not state
        or not tl_oauth_state
        or not secrets.compare_digest(state, tl_oauth_state)
    ):
        return failure

    try:
        google_user = await exchange_code(container.settings.google_auth, code=code)
    except GoogleOAuthError:
        log.warning("google_oauth_exchange_failed")
        return failure

    session = await AuthenticateWithGoogle(
        uow=uow,
        tokens=container.token_hasher,
        clock=container.clock,
        ids=container.ids,
        refresh_ttl_days=container.settings.security.refresh_token_ttl_days,
    ).execute(
        GoogleAuthCommand(
            email=google_user.email,
            full_name=google_user.name,
            ip=meta.ip,
            user_agent=meta.user_agent,
        )
    )

    # No JSON response to hand back an access token to - this is a full
    # page navigation, not a fetch. The refresh cookie is the handoff:
    # landing on /dashboard, the frontend's existing session bootstrap
    # (useSession -> refreshSession) finds no in-memory access token, sees
    # this cookie, and exchanges it exactly like it would after any other
    # hard reload. No new frontend session-handling code needed.
    redirect = RedirectResponse(
        f"{container.settings.web_base_url}/dashboard", status_code=status.HTTP_302_FOUND
    )
    set_refresh_cookie(
        redirect, container.settings, token=session.refresh_token_raw, expires_at=session.expires_at
    )
    redirect.delete_cookie(key=_OAUTH_STATE_COOKIE, path=_OAUTH_STATE_PATH)
    return redirect


@router.post(
    "/refresh",
    summary="Rotate the session",
    description=(
        "Exchanges the refresh cookie for a new access token and a new "
        "refresh token. Presenting an already-rotated token revokes the whole "
        "token family - a stolen token is therefore self-limiting."
    ),
)
async def refresh(
    response: Response,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
    tl_rt: Annotated[str | None, Cookie()] = None,
) -> dict[str, Any]:
    if not tl_rt:
        raise TokenInvalid("No session found. Please sign in.")

    use_case = RefreshSession(
        uow=uow,
        tokens=container.token_hasher,
        clock=container.clock,
        ids=container.ids,
        queue=container.queue,
        refresh_ttl_days=container.settings.security.refresh_token_ttl_days,
        idle_ttl_days=container.settings.security.refresh_idle_ttl_days,
    )
    session = await use_case.execute(
        RefreshSessionCommand(raw_token=tl_rt, ip=meta.ip, user_agent=meta.user_agent)
    )
    return await _issue_session_response(session, response, container, uow, meta)


@router.post("/logout", summary="Sign out of this session")
async def logout(
    response: Response,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
    tl_rt: Annotated[str | None, Cookie()] = None,
) -> dict[str, Any]:
    if tl_rt:
        await LogoutUser(uow=uow, tokens=container.token_hasher, clock=container.clock).execute(
            LogoutCommand(raw_token=tl_rt)
        )
    clear_refresh_cookie(response, container.settings)
    return envelope(
        MessageResponse(message="Signed out.").model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.post("/logout-all", summary="Sign out of every session")
async def logout_all(
    response: Response,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    revoked = await LogoutUser(
        uow=uow, tokens=container.token_hasher, clock=container.clock
    ).execute(LogoutCommand(user_id=actor.user_id, all_sessions=True))
    clear_refresh_cookie(response, container.settings)
    return envelope(
        MessageResponse(message=f"Signed out of {revoked} sessions.").model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.post("/verify-email", summary="Confirm an email address")
async def verify_email(
    body: VerifyEmailRequest,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    result = await VerifyEmail(
        uow=uow,
        tokens=container.token_hasher,
        queue=container.queue,
        clock=container.clock,
    ).execute(VerifyEmailCommand(raw_token=body.token))

    message = (
        "This email address was already confirmed."
        if result.already_verified
        else "Email address confirmed. You can now sign in."
    )
    return envelope(
        MessageResponse(message=message).model_dump(by_alias=True), request_id=meta.request_id
    )


@router.post(
    "/forgot-password",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a password reset",
    description=(
        "Always returns 202, whether or not the address exists. Revealing "
        "which addresses are registered would make this a phishing target list."
    ),
)
async def forgot_password(
    body: ForgotPasswordRequest,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    from datetime import timedelta

    from trustlens.core.domain.entities import VerificationToken
    from trustlens.core.domain.enums import TokenPurpose
    from trustlens.core.domain.value_objects import Email

    email = Email(body.email)
    user = await uow.users.get_by_email(email)

    if user is not None:
        now = container.clock.now()
        raw = container.token_hasher.new_token()
        await uow.verification_tokens.invalidate_for_user(
            user.id, purpose=TokenPurpose.PASSWORD_RESET
        )
        await uow.verification_tokens.add(
            VerificationToken(
                id=container.ids.new(),
                user_id=user.id,
                purpose=TokenPurpose.PASSWORD_RESET,
                token_hash=container.token_hasher.hash_token(raw),
                target=email.value,
                # Short-lived: a reset link is a full account takeover
                # primitive for as long as it is valid.
                expires_at=now + timedelta(hours=1),
                created_at=now,
            )
        )
        await uow.commit()
        await container.queue.enqueue(
            "notifications.send_email",
            to=email.value,
            template="reset_password",
            context={"token": raw},
        )

    return envelope(
        MessageResponse(
            message="If that address has an account, a reset link is on its way."
        ).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.post("/reset-password", summary="Complete a password reset")
async def reset_password(
    body: ResetPasswordRequest,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    from trustlens.core.domain.enums import TokenPurpose
    from trustlens.core.domain.errors import ValidationError

    now = container.clock.now()
    token = await uow.verification_tokens.get_by_hash(
        container.token_hasher.hash_token(body.token), purpose=TokenPurpose.PASSWORD_RESET
    )
    if token is None or not token.is_usable_at(now):
        raise TokenInvalid("This reset link is invalid or has expired.")

    user = await uow.users.get(token.user_id)
    if user is None:
        raise TokenInvalid("This reset link is invalid or has expired.")

    policy = PasswordPolicy(container.settings.security.password_min_length)
    if problems := policy.validate(body.password, email=user.email.value):
        raise ValidationError("; ".join(problems), field="password")

    await uow.verification_tokens.consume(token.id, at=now)
    await uow.users.set_password_hash(user.id, container.password_hasher.hash(body.password))
    # A password reset invalidates every existing session: if the reset was
    # triggered by a compromise, leaving the attacker's session alive defeats
    # the entire point.
    await uow.refresh_tokens.revoke_all_for_user(user.id, at=now, reason="PASSWORD_RESET")
    await uow.commit()

    return envelope(
        MessageResponse(
            message="Password updated. All other sessions have been signed out."
        ).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.post("/change-password", summary="Change your password")
async def change_password(
    body: ChangePasswordRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    from trustlens.core.domain.errors import InvalidCredentials, ValidationError

    assert actor.user_id is not None
    current_hash = await uow.users.get_password_hash(actor.user_id)
    if current_hash is None or not container.password_hasher.verify(
        body.current_password, current_hash
    ):
        raise InvalidCredentials

    user = await uow.users.get(actor.user_id)
    assert user is not None
    policy = PasswordPolicy(container.settings.security.password_min_length)
    if problems := policy.validate(body.new_password, email=user.email.value):
        raise ValidationError("; ".join(problems), field="newPassword")

    now = container.clock.now()
    await uow.users.set_password_hash(
        actor.user_id, container.password_hasher.hash(body.new_password)
    )
    await uow.refresh_tokens.revoke_all_for_user(actor.user_id, at=now, reason="PASSWORD_CHANGE")
    await uow.commit()

    return envelope(
        MessageResponse(message="Password changed.").model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.get("/sessions", summary="List active sessions")
async def list_sessions(actor: ActorDep, uow: UowDep, meta: MetaDep) -> dict[str, Any]:
    assert actor.user_id is not None
    tokens = await uow.refresh_tokens.list_active_for_user(actor.user_id)
    return envelope(
        [
            SessionSummary(
                id=token.id,
                created_at=token.created_at,
                expires_at=token.expires_at,
                ip_address=token.ip_address,
                user_agent=token.user_agent,
                is_current=token.family_id == actor.session_id,
            ).model_dump(by_alias=True)
            for token in tokens
        ],
        request_id=meta.request_id,
    )


@router.delete("/sessions/{session_id}", summary="Revoke a specific session")
async def revoke_session(
    session_id: str,
    actor: ActorDep,
    uow: UowDep,
    meta: MetaDep,
    container: ContainerDep,
) -> dict[str, Any]:
    from uuid import UUID

    assert actor.user_id is not None

    try:
        family_uuid = UUID(session_id)
    except ValueError:
        from trustlens.core.domain.errors import ValidationError

        raise ValidationError("Invalid session ID", field="sessionId") from None

    # In trustlens-db, we don't have a direct method to get a session by family_id to check owner
    # But revoke_all_for_user allows revoking all except one.
    # We can just revoke all sessions with this family_id where the user is the owner.
    # Wait, the repo has `revoke_family` but it doesn't take user_id.
    # Let's just fetch active sessions for the user and see if this family_id is in them.
    tokens = await uow.refresh_tokens.list_active_for_user(actor.user_id)
    if not any(t.family_id == family_uuid for t in tokens):
        from trustlens.core.domain.errors import EntityNotFound

        raise EntityNotFound("session", family_uuid)

    await uow.refresh_tokens.revoke_family(
        family_uuid, at=container.clock.now(), reason="USER_REVOKED"
    )
    await uow.commit()

    return envelope(
        MessageResponse(message="Session revoked.").model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.get("/me/export", summary="Export your data")
async def export_data(
    actor: ActorDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    user = await uow.users.get(actor.user_id)
    seller = await uow.sellers.get_by_user(actor.user_id)
    return envelope(
        {
            "user": user,
            "seller_profile": seller,
            "message": "Data export complete. Additional logs can be requested via support.",
        },
        request_id=meta.request_id,
    )


@router.delete("/me", summary="Delete your account")
async def delete_account(
    body: DeleteAccountRequest,
    actor: ActorDep,
    uow: UowDep,
    meta: MetaDep,
    container: ContainerDep,
    response: Response,
) -> dict[str, Any]:
    from trustlens.core.domain.errors import InvalidCredentials

    assert actor.user_id is not None
    current_hash = await uow.users.get_password_hash(actor.user_id)
    if current_hash is None or not container.password_hasher.verify(body.password, current_hash):
        raise InvalidCredentials

    user = await uow.users.get(actor.user_id)
    assert user is not None

    # Soft delete the user
    # Or queue an account deletion task
    await container.queue.enqueue("accounts.purge", user_id=str(actor.user_id))

    # Revoke all sessions and clear cookie
    await uow.refresh_tokens.revoke_all_for_user(
        actor.user_id, at=container.clock.now(), reason="ACCOUNT_DELETED"
    )
    await uow.commit()
    clear_refresh_cookie(response, container.settings)

    return envelope(
        MessageResponse(message="Account deletion initiated. Your data will be purged.").model_dump(
            by_alias=True
        ),
        request_id=meta.request_id,
    )


# ── helpers ──────────────────────────────────────────────────────────


async def _issue_session_response(
    session: IssuedSession,
    response: Response,
    container: Container,
    uow: SqlAlchemyUnitOfWork,
    meta: RequestMeta,
) -> dict[str, Any]:
    """Build the login/refresh response and set the refresh cookie."""
    now = container.clock.now()

    # Bumped in Redis whenever roles change; the claim lets the auth
    # dependency reject a stale token within seconds.
    perm_version = await container.cache.get(f"perm_version:{session.user.id}")
    access_token, expires_at = container.jwt.issue_access_token(
        user_id=session.user.id,
        roles=[role.value for role in session.user.roles],
        permissions=sorted(session.actor.permissions),
        permission_version=int(perm_version or 0),
        session_id=session.family_id,
        jti=container.ids.new(),
        now=now,
    )

    set_refresh_cookie(
        response,
        container.settings,
        token=session.refresh_token_raw,
        expires_at=session.expires_at,
    )

    seller = await uow.sellers.get_by_user(session.user.id)

    return envelope(
        LoginResponse(
            access_token=access_token,
            expires_in=int((expires_at - now).total_seconds()),
            user=UserSummary(
                id=session.user.id,
                email=session.user.email.value,
                full_name=session.user.full_name,
                status=session.user.status.value,
                roles=[role.value for role in session.user.roles],
                permissions=sorted(session.actor.permissions),
                email_verified=session.user.is_email_verified,
                mfa_enabled=session.user.mfa_enabled,
                has_seller_profile=seller is not None,
            ),
        ).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


__all__ = ["router"]
