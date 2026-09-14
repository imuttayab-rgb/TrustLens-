"""Staff MFA enrollment and management (feature BLK-04).

Lives under /me/mfa, the signed-in-user convention every other account-
security action (/auth/change-password, /auth/sessions) already follows -
grouped here rather than in auth.py since enrollment is real business
logic (a TOTP secret, recovery codes), not a thin pass-through.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from trustlens.core.application.use_cases.auth import (
    BeginMfaEnrollment,
    ConfirmMfaEnrollment,
    DisableMfa,
    DisableMfaCommand,
)
from trustlens.core.domain.enums import UserRole
from trustlens.core.domain.policies import mfa_required_for
from trustlens_api.api.deps import ActorDep, ContainerDep, MetaDep, UowDep
from trustlens_api.api.v1.schemas.auth import (
    MfaConfirmRequest,
    MfaConfirmResponse,
    MfaDisableRequest,
    MfaEnrollResponse,
    MfaStatusResponse,
)
from trustlens_api.api.v1.schemas.common import MessageResponse, envelope

router = APIRouter(prefix="/me/mfa", tags=["MFA"])


@router.get("/status", summary="Whether MFA is enabled, and whether it's required")
async def mfa_status(
    actor: ActorDep, container: ContainerDep, uow: UowDep, meta: MetaDep
) -> dict[str, Any]:
    assert actor.user_id is not None
    user = await uow.users.get(actor.user_id)
    assert user is not None
    # Mirrors LoginUser's own check exactly - "required" here must mean
    # "this deployment's SECURITY_MFA_REQUIRED_ROLES would actually gate
    # you at login," not just "your role is admin/reviewer." Those differ
    # whenever that setting is left empty, which is the default.
    required_roles = frozenset(
        UserRole(role) for role in container.settings.security.mfa_required_roles
    )
    return envelope(
        MfaStatusResponse(
            enabled=user.mfa_enabled, required=mfa_required_for(user, required_roles)
        ).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.post(
    "/enroll",
    summary="Begin MFA enrollment",
    description=(
        "Generates a new TOTP secret - render the provisioning URI as a QR "
        "code for an authenticator app, or show the secret for manual "
        "entry. MFA is not enabled yet; call /confirm with a code from the "
        "app to finish. Calling this again before confirming replaces the "
        "pending secret."
    ),
)
async def begin_enrollment(
    actor: ActorDep, container: ContainerDep, uow: UowDep, meta: MetaDep
) -> dict[str, Any]:
    assert actor.user_id is not None
    result = await BeginMfaEnrollment(
        uow=uow,
        encryptor=container.encryptor,
        totp=container.totp,
        issuer=container.settings.app_name,
    ).execute(actor.user_id)
    return envelope(
        MfaEnrollResponse(
            secret=result.secret, provisioning_uri=result.provisioning_uri
        ).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.post(
    "/confirm",
    summary="Confirm MFA enrollment",
    description=(
        "Verifies a code from the authenticator app against the pending "
        "secret from /enroll. On success, MFA is enabled and ten recovery "
        "codes are returned - shown once, never retrievable again."
    ),
)
async def confirm_enrollment(
    body: MfaConfirmRequest, actor: ActorDep, container: ContainerDep, uow: UowDep, meta: MetaDep
) -> dict[str, Any]:
    assert actor.user_id is not None
    result = await ConfirmMfaEnrollment(
        uow=uow,
        clock=container.clock,
        tokens=container.token_hasher,
        encryptor=container.encryptor,
        totp=container.totp,
    ).execute(actor.user_id, body.code)
    return envelope(
        MfaConfirmResponse(recovery_codes=list(result.recovery_codes)).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.post(
    "/disable",
    status_code=status.HTTP_200_OK,
    summary="Disable MFA",
    description="Requires the current password - MFA is a security control, not a preference.",
)
async def disable_mfa(
    body: MfaDisableRequest, actor: ActorDep, container: ContainerDep, uow: UowDep, meta: MetaDep
) -> dict[str, Any]:
    assert actor.user_id is not None
    await DisableMfa(uow=uow, hasher=container.password_hasher, clock=container.clock).execute(
        DisableMfaCommand(user_id=actor.user_id, password=body.password)
    )
    return envelope(
        MessageResponse(message="MFA disabled.").model_dump(by_alias=True),
        request_id=meta.request_id,
    )


__all__ = ["router"]
