"""FastAPI dependencies: DI, authentication, RBAC, pagination, request metadata.

FastAPI has no NestJS-style "guards"; the equivalent is a dependency that
raises. These compose:

    @router.post(
        "/admin/scoring-models/{id}/activate",
        dependencies=[Depends(require_permissions("scoring_model:activate"))],
    )
"""

from __future__ import annotations

import ipaddress
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Header, Query, Request

from trustlens.core.domain.entities import AuthenticatedActor, SellerProfile
from trustlens.core.domain.enums import UserRole
from trustlens.core.domain.errors import (
    ApiKeyInvalid,
    ApiKeyRevoked,
    ApiScopeMissing,
    AuthenticationError,
    EntityNotFound,
    PermissionDenied,
    TokenInvalid,
)
from trustlens.db.unit_of_work import SqlAlchemyUnitOfWork
from trustlens.shared.crypto import ApiKeyFactory
from trustlens.shared.logging import actor_id_var, actor_type_var
from trustlens_api.container import Container


def get_container(request: Request) -> Container:
    return request.app.state.container  # type: ignore[no-any-return]


ContainerDep = Annotated[Container, Depends(get_container)]


async def get_uow(container: ContainerDep) -> AsyncIterator[SqlAlchemyUnitOfWork]:
    """A request-scoped unit of work.

    Yielded rather than returned so the session is always closed, including
    when the handler raises.
    """
    uow = container.uow()
    async with uow:
        yield uow


UowDep = Annotated[SqlAlchemyUnitOfWork, Depends(get_uow)]


# ── Request metadata ─────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class RequestMeta:
    ip: str | None
    user_agent: str | None
    device_fingerprint: str | None
    request_id: str | None


def get_request_meta(
    request: Request,
    container: ContainerDep,
    x_device_fingerprint: Annotated[str | None, Header()] = None,
) -> RequestMeta:
    return RequestMeta(
        ip=_client_ip(request, container.settings.security.trusted_proxy_count),
        user_agent=request.headers.get("user-agent"),
        device_fingerprint=x_device_fingerprint,
        request_id=getattr(request.state, "request_id", None),
    )


def _valid_ip(value: str | None) -> str | None:
    """Return the value only if it really is an IP address.

    X-Forwarded-For is attacker-controlled and these values land in `inet`
    columns. Anything unparseable is dropped rather than propagated: a
    malformed header must not be able to 500 an endpoint, and a fabricated
    value must not be able to poison the NETWORK signal.
    """
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def _client_ip(request: Request, trusted_proxy_count: int) -> str | None:
    """Resolve the client IP, honouring only the number of proxies we trust.

    Getting this wrong makes every IP-based rate limit and the whole NETWORK
    signal spoofable by a header - so the count is explicit configuration
    rather than "take the first value in X-Forwarded-For".
    """
    direct = _valid_ip(request.client.host if request.client else None)

    if trusted_proxy_count <= 0:
        return direct

    forwarded = request.headers.get("x-forwarded-for")
    if not forwarded:
        return direct

    chain = [part.strip() for part in forwarded.split(",") if part.strip()]
    # Count from the right: the rightmost entries were added by OUR proxies
    # and are the only ones a client cannot forge.
    index = len(chain) - trusted_proxy_count
    candidate = chain[index] if 0 <= index < len(chain) else chain[0]
    return _valid_ip(candidate) or direct


MetaDep = Annotated[RequestMeta, Depends(get_request_meta)]


# ── Authentication ───────────────────────────────────────────────────


async def get_optional_actor(
    request: Request,
    container: ContainerDep,
    uow: UowDep,
) -> AuthenticatedActor | None:
    """Decode the bearer token if present. Never raises on absence."""
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return None

    token = header[7:].strip()
    try:
        claims = container.jwt.decode(token)
    except jwt.ExpiredSignatureError:
        raise TokenInvalid("Your session has expired. Please sign in again.") from None
    except jwt.PyJWTError:
        raise TokenInvalid("This session is no longer valid.") from None

    if claims.get("typ") != "access":
        raise TokenInvalid("Wrong token type.")

    user_id = UUID(claims["sub"])

    # `pv` (permission version) compared against a Redis counter: one cheap
    # GET makes a revoked role take effect in seconds instead of waiting out
    # the 15-minute token lifetime (ADR-0006).
    current_version = await container.cache.get(f"perm_version:{user_id}")
    if current_version is not None and int(current_version) != int(claims.get("pv", 0)):
        raise TokenInvalid("Your permissions changed. Please refresh your session.")

    actor = AuthenticatedActor(
        user_id=user_id,
        roles=frozenset(UserRole(r) for r in claims.get("roles", [])),
        permissions=frozenset(claims.get("perms", [])),
        session_id=UUID(claims["sid"]) if claims.get("sid") else None,
    )
    actor_id_var.set(str(user_id))
    actor_type_var.set("USER")
    return actor


OptionalActorDep = Annotated[AuthenticatedActor | None, Depends(get_optional_actor)]


async def get_current_actor(actor: OptionalActorDep) -> AuthenticatedActor:
    if actor is None:
        raise AuthenticationError("Authentication required.")
    return actor


ActorDep = Annotated[AuthenticatedActor, Depends(get_current_actor)]


async def get_current_seller(actor: ActorDep, uow: UowDep) -> SellerProfile:
    seller = await uow.sellers.get_by_user(actor.user_id) if actor.user_id else None
    if seller is None:
        raise EntityNotFound("seller_profile", actor.user_id)
    return seller


SellerDep = Annotated[SellerProfile, Depends(get_current_seller)]


# ── Authorization ────────────────────────────────────────────────────


def require_roles(*roles: UserRole) -> Callable[..., AuthenticatedActor]:
    """Coarse gate for whole route groups."""

    async def dependency(actor: ActorDep) -> AuthenticatedActor:
        if not actor.has_any_role(*roles):
            raise PermissionDenied()
        return actor

    return dependency


def require_permissions(*permissions: str) -> Callable[..., AuthenticatedActor]:
    """Fine gate on an individual action.

    Route-level permission answers "may this ROLE do this kind of thing".
    It does NOT answer "may this user touch THIS row" - that is
    `assert_owns_seller` below, and omitting it is IDOR.
    """

    async def dependency(actor: ActorDep) -> AuthenticatedActor:
        missing = [p for p in permissions if not actor.has_permission(p)]
        if missing:
            raise PermissionDenied(missing[0])
        return actor

    return dependency


async def assert_owns_seller(
    seller_id: UUID, actor: AuthenticatedActor, uow: SqlAlchemyUnitOfWork
) -> SellerProfile:
    """Object-level authorization. Mandatory on every resource-scoped route.

    Without this, `GET /api/v1/sellers/{id}/trust-score` with only a
    permission check would let any seller read any other seller's breakdown.
    """
    seller = await uow.sellers.get(seller_id)
    if seller is None:
        raise EntityNotFound("seller", seller_id)

    if actor.has_permission("seller:read:any"):
        return seller
    if seller.user_id == actor.user_id:
        return seller
    # 404, not 403: confirming the resource exists to someone who may not see
    # it is itself a small information leak.
    raise EntityNotFound("seller", seller_id)


# ── API-key authentication (public API) ──────────────────────────────


@dataclass(frozen=True, slots=True)
class ApiClientPrincipal:
    client_id: UUID
    key_id: UUID
    scopes: frozenset[str]
    rate_limit_tier: str
    monthly_quota: int


async def get_api_client(
    request: Request,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> ApiClientPrincipal:
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        raise ApiKeyInvalid("An API key is required.")

    parts = ApiKeyFactory.split(header[7:].strip())
    if parts is None:
        raise ApiKeyInvalid("Malformed API key.")
    prefix, secret = parts

    # Indexed equality on the prefix, THEN a constant-time hash comparison.
    # Hashing alone would require scanning every key to find a candidate.
    key = await uow.api_clients.get_key_by_prefix(prefix)
    if key is None or not container.api_keys.verify(secret, key.key_hash):
        raise ApiKeyInvalid("Invalid API key.")

    now = container.clock.now()
    if not key.is_usable_at(now):
        raise ApiKeyRevoked("This API key has been revoked or has expired.")

    client = await uow.api_clients.get(key.api_client_id)
    if client is None or not client.is_active:
        raise ApiKeyRevoked("This API client is not active.")

    if client.allowed_ips and meta.ip not in client.allowed_ips:
        raise ApiKeyInvalid("This API key is not permitted from this address.")

    actor_id_var.set(str(client.id))
    actor_type_var.set("API_CLIENT")

    return ApiClientPrincipal(
        client_id=client.id,
        key_id=key.id,
        scopes=key.scopes,
        rate_limit_tier=client.rate_limit_tier,
        monthly_quota=client.monthly_quota,
    )


ApiClientDep = Annotated[ApiClientPrincipal, Depends(get_api_client)]


def require_scope(scope: str) -> Callable[..., ApiClientPrincipal]:
    async def dependency(principal: ApiClientDep) -> ApiClientPrincipal:
        if scope not in principal.scopes:
            raise ApiScopeMissing(scope)
        return principal

    return dependency


# ── Pagination ───────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class PageParams:
    page: int
    per_page: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.per_page


def get_page_params(
    page: Annotated[int, Query(ge=1, le=10_000)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100, alias="perPage")] = 20,
) -> PageParams:
    """Offset pagination, for admin tables that need "page 7 of 12".

    Bounded at 100 per page: an unbounded page size is a trivial way to turn a
    list endpoint into a memory-exhaustion vector.
    """
    return PageParams(page=page, per_page=per_page)


PageDep = Annotated[PageParams, Depends(get_page_params)]


__all__ = [
    "ActorDep",
    "ApiClientDep",
    "ApiClientPrincipal",
    "ContainerDep",
    "MetaDep",
    "OptionalActorDep",
    "PageDep",
    "PageParams",
    "RequestMeta",
    "SellerDep",
    "UowDep",
    "assert_owns_seller",
    "get_container",
    "require_permissions",
    "require_roles",
    "require_scope",
]
