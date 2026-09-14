"""Shared helper for writing an in-app notification (NOT-01).

Every use case below that triggers one already holds an open `UnitOfWork`
transaction - this just builds the `Notification` entity and appends the
`add()` call, so a dozen call sites don't each hand-roll the same six-field
constructor. It does not commit; the caller's existing `await
self._uow.commit()` covers it, same transaction as the state change that
triggered it.
"""

from __future__ import annotations

from uuid import UUID

from trustlens.core.domain.entities import Notification
from trustlens.core.domain.ports import Clock, IdGenerator, UnitOfWork


async def notify(
    uow: UnitOfWork,
    ids: IdGenerator,
    clock: Clock,
    *,
    user_id: UUID,
    type: str,  # noqa: A002 - matches the Notification field name
    title: str,
    body: str,
    data: dict[str, object] | None = None,
) -> None:
    await uow.notifications.add(
        Notification(
            id=ids.new(),
            user_id=user_id,
            type=type,
            title=title,
            body=body,
            created_at=clock.now(),
            data=data or {},
        )
    )


__all__ = ["notify"]
