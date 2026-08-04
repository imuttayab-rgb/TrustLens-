"""Authentication endpoints.

The refresh token is delivered as an httpOnly cookie and never appears in a
response body - an XSS payload must not be able to read it (ADR-0006).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Cookie, Request, Response, status

from trustlens.core.application.use_cases.auth import (
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
from trustlens.core.domain.errors import TokenInvalid
from trustlens.core.domain.policies import LoginThrottlePolicy, PasswordPolicy
from trustlens.db.unit_of_work import SqlAlchemyUnitOfWork
from trustlens_api.api.deps import ActorDep, ContainerDep, MetaDep, RequestMeta, UowDep
from trustlens_api.api.v1.schemas.auth import (
    ChangePasswordRequest,
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

router = APIRouter(prefix="/auth", tags=["Authentication"])


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


@router.post("/login", summary="Sign in")
async def login(
    body: LoginRequest,
    response: Response,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
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
