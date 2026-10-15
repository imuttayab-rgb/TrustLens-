"""Private HTTP signalling works through the existing API origin/proxy."""

from uuid import UUID
from fastapi import APIRouter, Query
from trustlens_api.api.deps import ActorDep, ContainerDep, MetaDep, UowDep
from trustlens_api.api.v1.schemas.common import envelope
from trustlens_api.api.private_route import PrivateChatRoute
from trustlens_api.modules.calling.service import CallService
from trustlens_api.modules.calling.push import save_subscription, disable_subscription

router = APIRouter(tags=["Voice calls"], route_class=PrivateChatRoute)


from trustlens_api.api.v1.schemas.calls import StartCall, CallAction, Device, PushSubscription


@router.get("/me/calls/config")
async def config(actor: ActorDep, container: ContainerDep, meta: MetaDep):
    cfg = container.settings.calls
    return envelope(
        {
            "enabled": cfg.calls_enabled,
            "pushPublicKey": cfg.calls_vapid_public_key,
            "provider": "LiveKit self-hosted",
            "ringSeconds": 45,
            "maxCallSeconds": 7200,
        },
        request_id=meta.request_id,
    )


@router.post("/me/calls/push")
async def subscribe(
    body: PushSubscription, actor: ActorDep, container: ContainerDep, uow: UowDep, meta: MetaDep
):
    return envelope(
        await save_subscription(uow, container, actor.user_id, body.model_dump()),
        request_id=meta.request_id,
    )


@router.delete("/me/calls/push/{subscription_id}")
async def unsubscribe(
    subscription_id: UUID, actor: ActorDep, container: ContainerDep, uow: UowDep, meta: MetaDep
):
    await disable_subscription(uow, actor.user_id, subscription_id)
    return envelope({"disabled": True}, request_id=meta.request_id)


@router.post("/me/calls")
async def start(
    body: StartCall, actor: ActorDep, uow: UowDep, container: ContainerDep, meta: MetaDep
):
    result = await CallService(uow, container).start(
        actor.user_id, body.conversation_id, body.call_id, body.device_id
    )
    return envelope(result, request_id=meta.request_id)


@router.get("/me/calls/active")
async def active(
    actor: ActorDep,
    uow: UowDep,
    container: ContainerDep,
    meta: MetaDep,
    device_id: UUID = Query(alias="deviceId"),
):
    return envelope(
        await CallService(uow, container).active(actor.user_id, device_id),
        request_id=meta.request_id,
    )


@router.post("/me/calls/{call_id}/actions")
async def action(
    call_id: UUID,
    body: CallAction,
    actor: ActorDep,
    uow: UowDep,
    container: ContainerDep,
    meta: MetaDep,
):
    result = await CallService(uow, container).act(
        actor.user_id,
        call_id,
        body.device_id,
        body.action,
        connected=body.connected,
        muted=body.muted,
        health=body.health.model_dump(by_alias=True) if body.health else None,
    )
    return envelope(result, request_id=meta.request_id)


@router.get("/me/conversations/{conversation_id}/calls")
async def history(
    conversation_id: UUID, actor: ActorDep, uow: UowDep, container: ContainerDep, meta: MetaDep
):
    return envelope(
        await CallService(uow, container).history(actor.user_id, conversation_id),
        request_id=meta.request_id,
    )


@router.post("/me/calls/{call_id}/join")
async def join(
    call_id: UUID,
    body: Device,
    actor: ActorDep,
    uow: UowDep,
    container: ContainerDep,
    meta: MetaDep,
):
    return envelope(
        await CallService(uow, container).join(actor.user_id, call_id, body.device_id),
        request_id=meta.request_id,
    )
