"""The read side of the notification center (NOT-01).

Writing a notification happens inline in whichever use case triggers it (see
`trustlens.core.application.notifications.notify`) - this module is only
the inbox screen: list, unread count, mark one read, mark all read.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from trustlens.core.domain.entities import Notification
from trustlens.core.domain.ports import Clock, UnitOfWork


@dataclass(frozen=True, slots=True)
class ListNotificationsQuery:
    user_id: UUID
    unread_only: bool = False
    limit: int = 50


@dataclass(frozen=True, slots=True)
class NotificationInbox:
    items: tuple[Notification, ...]
    unread_count: int


class ListNotifications:
    def __init__(self, *, uow: UnitOfWork) -> None:
        self._uow = uow

    async def execute(self, query: ListNotificationsQuery) -> NotificationInbox:
        limit = max(1, min(query.limit, 100))
        async with self._uow:
            items = await self._uow.notifications.list_for_user(
                query.user_id, unread_only=query.unread_only, limit=limit
            )
            unread_count = await self._uow.notifications.count_unread(query.user_id)
        return NotificationInbox(items=tuple(items), unread_count=unread_count)


@dataclass(frozen=True, slots=True)
class MarkNotificationReadCommand:
    user_id: UUID
    notification_id: UUID


class MarkNotificationRead:
    def __init__(self, *, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def execute(self, cmd: MarkNotificationReadCommand) -> None:
        async with self._uow:
            await self._uow.notifications.mark_read(
                cmd.notification_id, user_id=cmd.user_id, at=self._clock.now()
            )
            await self._uow.commit()


class MarkAllNotificationsRead:
    def __init__(self, *, uow: UnitOfWork, clock: Clock) -> None:
        self._uow = uow
        self._clock = clock

    async def execute(self, user_id: UUID) -> int:
        async with self._uow:
            count = await self._uow.notifications.mark_all_read(user_id, at=self._clock.now())
            await self._uow.commit()
        return count


__all__ = [
    "ListNotifications",
    "ListNotificationsQuery",
    "MarkAllNotificationsRead",
    "MarkNotificationRead",
    "MarkNotificationReadCommand",
    "NotificationInbox",
]
