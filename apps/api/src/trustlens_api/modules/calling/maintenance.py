"""Multi-worker-safe expiry, push outbox and SFU room cleanup."""

import asyncio
from sqlalchemy import select
from trustlens.db import models as m
from trustlens.shared.logging import get_logger
from trustlens_api.modules.calling.service import CallService, ACTIVE
from trustlens_api.modules.calling.push import notify_call

log = get_logger(__name__)


async def maintain_once(container):
    # Keyset batches visit every unfinished room, even above 100 concurrent calls.
    after = None
    cutoff = container.clock.now()
    while True:
        async with container.uow() as uow:
            query = (
                select(m.ChatCallModel.id)
                .join(m.ChatCallRuntimeModel)
                .where(
                    m.ChatCallRuntimeModel.room_closed.is_(False),
                    m.ChatCallModel.created_at <= cutoff,
                )
                .order_by(m.ChatCallModel.id)
                .limit(100)
            )
            if after is not None:
                query = query.where(m.ChatCallModel.id > after)
            ids = (await uow.session.execute(query)).scalars().all()
        if not ids:
            return
        after = ids[-1]
        for call_id in ids:
            async with container.uow() as uow:
                row = (
                    await uow.session.execute(
                        select(m.ChatCallModel)
                        .where(m.ChatCallModel.id == call_id)
                        .with_for_update(skip_locked=True)
                    )
                ).scalar_one_or_none()
                if not row:
                    continue
                runtime = await uow.session.get(m.ChatCallRuntimeModel, call_id)
                if runtime.room_closed:
                    continue
                service = CallService(uow, container)
                if row.state in ACTIVE:
                    await service.expire(row)
                if row.state == "ended":
                    try:
                        await service.media.delete(row.id)
                        runtime.room_closed = True
                    except Exception:
                        log.warning("call_room_cleanup_retry", call_id=str(row.id))
                elif not runtime.push_attempted:
                    if row.state in ("calling", "ringing"):
                        await notify_call(uow, container, row)
                    runtime.push_attempted = True
                await uow.commit()


async def maintain_calls(container):
    while True:
        try:
            await maintain_once(container)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.warning("call_maintenance_retry")
        await asyncio.sleep(3)
