"""In-app notification center (NOT-01).

Read-only from the client's point of view - notifications are written
inline by whichever use case triggers them (new message, offer response,
meetup response, transaction state change, report resolution), not through
an endpoint here.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, status

from trustlens.core.application.use_cases.notifications import (
    ListNotifications,
    ListNotificationsQuery,
    MarkAllNotificationsRead,
    MarkNotificationRead,
    MarkNotificationReadCommand,
)
from trustlens_api.api.deps import ActorDep, ContainerDep, MetaDep, UowDep
from trustlens_api.api.v1.schemas.common import envelope
from trustlens_api.api.v1.schemas.notification import NotificationResponse

router = APIRouter(tags=["Notifications"])


@router.get("/me/notifications", summary="List my notifications")
async def list_notifications(
    actor: ActorDep,
    uow: UowDep,
    meta: MetaDep,
    unread_only: bool = Query(default=False, alias="unreadOnly"),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    assert actor.user_id is not None
    inbox = await ListNotifications(uow=uow).execute(
        ListNotificationsQuery(user_id=actor.user_id, unread_only=unread_only, limit=limit)
    )
    items = [
        NotificationResponse(
            id=n.id,
            type=n.type,
            title=n.title,
            body=n.body,
            data=n.data,
            created_at=n.created_at,
            read_at=n.read_at,
        ).model_dump(by_alias=True)
        for n in inbox.items
    ]
    return envelope(
        items, request_id=meta.request_id, meta_extra={"unreadCount": inbox.unread_count}
    )


@router.put(
    "/me/notifications/{notification_id}/read",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Mark one notification read",
)
async def mark_notification_read(
    notification_id: UUID,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
) -> None:
    assert actor.user_id is not None
    await MarkNotificationRead(uow=uow, clock=container.clock).execute(
        MarkNotificationReadCommand(user_id=actor.user_id, notification_id=notification_id)
    )


@router.put("/me/notifications/read-all", summary="Mark every notification read")
async def mark_all_notifications_read(
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    count = await MarkAllNotificationsRead(uow=uow, clock=container.clock).execute(actor.user_id)
    return envelope({"markedRead": count}, request_id=meta.request_id)


__all__ = ["router"]
