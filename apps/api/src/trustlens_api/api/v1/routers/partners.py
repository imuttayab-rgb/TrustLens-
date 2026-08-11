"""Partner and API key administration (feature F9).

Staff-only. The public API these keys unlock is the one place TrustLens data
leaves the building, so every route here is permission-gated individually and
every mutation is audit-logged by the use case.

The plaintext key appears in exactly one response body in this whole system -
the one that creates it - and is never retrievable afterwards. That is a
deliberate constraint, not an oversight: a design where support can read a
partner's key back to them is a design where a database dump is a set of live
credentials.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from trustlens.core.application.use_cases.public_api import (
    CLIENT_ACTIVE,
    CLIENT_PENDING,
    CLIENT_SUSPENDED,
    SCOPE_SCORE_READ,
    SCOPES,
    IssueApiKey,
    IssueApiKeyCommand,
    ListApiClients,
    ListApiKeys,
    RegisterApiClient,
    RegisterApiClientCommand,
    RevokeApiKey,
    RevokeApiKeyCommand,
    RotateApiKey,
    RotateApiKeyCommand,
    SetApiClientStatus,
    SetApiClientStatusCommand,
    expiry_for,
)
from trustlens.core.domain.entities import ApiClient, ApiKey, AuthenticatedActor
from trustlens.core.domain.errors import PermissionDenied
from trustlens_api.api.deps import (
    ActorDep,
    ContainerDep,
    MetaDep,
    UowDep,
    require_permissions,
)
from trustlens_api.api.v1.schemas.common import envelope

router = APIRouter(prefix="/admin/partners", tags=["partners"])


class PartnerModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    name: str
    slug: str
    contact_email: str = Field(serialization_alias="contactEmail")
    status: str
    rate_limit_tier: str = Field(serialization_alias="rateLimitTier")
    monthly_quota: int = Field(serialization_alias="monthlyQuota")
    used_this_month: int = Field(serialization_alias="usedThisMonth")
    remaining: int
    percent_used: float = Field(serialization_alias="percentUsed")
    created_at: Any = Field(serialization_alias="createdAt")


class KeyModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: UUID
    name: str
    #: The lookup half only. The secret half exists once, in the issue
    #: response, and is not stored anywhere in a readable form.
    key_prefix: str = Field(serialization_alias="keyPrefix")
    scopes: list[str]
    status: str
    state: str = Field(description="active | revoked | expired | expires <date>")
    created_at: Any = Field(serialization_alias="createdAt")
    last_used_at: Any = Field(default=None, serialization_alias="lastUsedAt")
    expires_at: Any = Field(default=None, serialization_alias="expiresAt")


class IssuedKeyModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    key: KeyModel
    #: Shown once. Copy it now - it cannot be retrieved later, only rotated.
    plaintext: str = Field(
        serialization_alias="plaintext",
        description="The full API key. This is the only time it is ever returned.",
    )


class RegisterPartnerRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=60)
    contact_email: str = Field(alias="contactEmail")
    contact_name: str | None = Field(default=None, alias="contactName")
    rate_limit_tier: str = Field(default="free", alias="rateLimitTier")
    monthly_quota: int = Field(default=10_000, alias="monthlyQuota", ge=1)


class SetStatusRequest(BaseModel):
    status: str = Field(description=f"{CLIENT_PENDING} | {CLIENT_ACTIVE} | {CLIENT_SUSPENDED}")


class IssueKeyRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(min_length=1, max_length=120)
    scopes: list[str] = Field(default_factory=lambda: [SCOPE_SCORE_READ])
    expires_in_days: int | None = Field(default=None, alias="expiresInDays", ge=1, le=3650)


def _actor_id(actor: AuthenticatedActor) -> UUID:
    """Issuing a credential must be attributable to a person, not a key."""
    if actor.user_id is None:
        raise PermissionDenied("api_client:create")
    return actor.user_id


def _partner_model(client: ApiClient, used: int, remaining: int, percent: float) -> PartnerModel:
    return PartnerModel(
        id=client.id,
        name=client.name,
        slug=client.slug,
        contact_email=client.contact_email,
        status=client.status,
        rate_limit_tier=client.rate_limit_tier,
        monthly_quota=client.monthly_quota,
        used_this_month=used,
        remaining=remaining,
        percent_used=percent,
        created_at=client.created_at,
    )


def _key_model(key: ApiKey, state: str) -> KeyModel:
    return KeyModel(
        id=key.id,
        name=key.name,
        key_prefix=key.key_prefix,
        scopes=sorted(key.scopes),
        status=key.status.value,
        state=state,
        created_at=key.created_at,
        last_used_at=key.last_used_at,
        expires_at=key.expires_at,
    )


# Declared before `/{client_id}/...`: FastAPI matches in definition order, so
# a literal path registered after a parameterised one is unreachable - the
# router would try to parse "scopes" as a UUID and 422.
@router.get(
    "/scopes",
    summary="Scopes a key can be granted",
    dependencies=[Depends(require_permissions("api_client:read"))],
)
async def list_scopes(meta: MetaDep) -> dict[str, Any]:
    return envelope(sorted(SCOPES), request_id=meta.request_id)


@router.get(
    "",
    summary="Every partner, with usage against quota",
    dependencies=[Depends(require_permissions("api_client:read"))],
)
async def list_partners(uow: UowDep, meta: MetaDep) -> dict[str, Any]:
    usages = await ListApiClients(uow=uow).execute()
    return envelope(
        [
            _partner_model(u.client, u.used_this_month, u.remaining, u.percent_used).model_dump(
                by_alias=True
            )
            for u in usages
        ],
        request_id=meta.request_id,
    )


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Register a partner",
    description="Created as PENDING. Approve it before issuing a key.",
    dependencies=[Depends(require_permissions("api_client:create"))],
)
async def register_partner(
    body: RegisterPartnerRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    client = await RegisterApiClient(uow=uow, clock=container.clock, ids=container.ids).execute(
        RegisterApiClientCommand(
            name=body.name,
            slug=body.slug,
            contact_email=body.contact_email,
            contact_name=body.contact_name,
            rate_limit_tier=body.rate_limit_tier,
            monthly_quota=body.monthly_quota,
            actor_id=_actor_id(actor),
        )
    )
    return envelope(
        _partner_model(client, 0, client.monthly_quota, 0.0).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.post(
    "/{client_id}/status",
    summary="Approve, suspend or reinstate a partner",
    description=(
        "Suspending stops all of a partner's traffic at once, without having "
        "to hunt down every key they hold."
    ),
    dependencies=[Depends(require_permissions("api_client:update"))],
)
async def set_partner_status(
    client_id: UUID,
    body: SetStatusRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    client = await SetApiClientStatus(uow=uow, clock=container.clock, ids=container.ids).execute(
        SetApiClientStatusCommand(
            client_id=client_id, status=body.status, actor_id=_actor_id(actor)
        )
    )
    return envelope(
        _partner_model(client, 0, client.monthly_quota, 0.0).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.get(
    "/{client_id}/keys",
    summary="Keys held by a partner",
    dependencies=[Depends(require_permissions("api_client:read"))],
)
async def list_keys(
    client_id: UUID, container: ContainerDep, uow: UowDep, meta: MetaDep
) -> dict[str, Any]:
    keys = await ListApiKeys(uow=uow).execute(client_id)
    now = container.clock.now()
    return envelope(
        [_key_model(k, expiry_for(k, now)).model_dump(by_alias=True) for k in keys],
        request_id=meta.request_id,
    )


@router.post(
    "/{client_id}/keys",
    status_code=status.HTTP_201_CREATED,
    summary="Issue a key",
    description=(
        "The response contains the only copy of the key that will ever "
        "exist. It is argon2-hashed before storage, so it cannot be shown "
        "again - a lost key is rotated, not recovered."
    ),
    dependencies=[Depends(require_permissions("api_client:create"))],
)
async def issue_key(
    client_id: UUID,
    body: IssueKeyRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    issued = await IssueApiKey(
        uow=uow, keys=container.api_keys, clock=container.clock, ids=container.ids
    ).execute(
        IssueApiKeyCommand(
            client_id=client_id,
            name=body.name,
            scopes=frozenset(body.scopes),
            expires_in_days=body.expires_in_days,
            actor_id=_actor_id(actor),
        )
    )
    now = container.clock.now()
    return envelope(
        IssuedKeyModel(
            key=_key_model(issued.key, expiry_for(issued.key, now)),
            plaintext=issued.plaintext,
        ).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.post(
    "/keys/{key_id}/rotate",
    summary="Rotate a key",
    description=(
        "Issues a replacement and expires the old key after a 24-hour "
        "overlap, so the partner can redeploy without an outage. Use revoke "
        "instead when a key is known to be compromised."
    ),
    dependencies=[Depends(require_permissions("api_client:create"))],
)
async def rotate_key(
    key_id: UUID,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    issued = await RotateApiKey(
        uow=uow, keys=container.api_keys, clock=container.clock, ids=container.ids
    ).execute(RotateApiKeyCommand(key_id=key_id, actor_id=_actor_id(actor)))
    now = container.clock.now()
    return envelope(
        IssuedKeyModel(
            key=_key_model(issued.key, expiry_for(issued.key, now)),
            plaintext=issued.plaintext,
        ).model_dump(by_alias=True),
        request_id=meta.request_id,
    )


@router.delete(
    "/keys/{key_id}",
    summary="Revoke a key immediately",
    description="No overlap. Use this when a key has leaked.",
    dependencies=[Depends(require_permissions("api_client:revoke"))],
)
async def revoke_key(
    key_id: UUID,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    await RevokeApiKey(uow=uow, clock=container.clock, ids=container.ids).execute(
        RevokeApiKeyCommand(key_id=key_id, actor_id=_actor_id(actor))
    )
    return envelope({"revoked": True}, request_id=meta.request_id)


__all__ = ["router"]
