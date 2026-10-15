"""Optional standards-based Web Push. Subscriptions stay encrypted and private."""

import asyncio
import base64
import hashlib
import json
from urllib.parse import urlparse
from uuid import uuid4
from sqlalchemy import func, select, text
from trustlens.db import models as m
from trustlens.core.domain.errors import (
    EntityNotFound,
    InvalidStateError,
    PermissionDenied,
    ValidationError,
)


def valid_subscription(value):
    try:
        url = urlparse(value["endpoint"])
        port = url.port
    except ValueError:
        raise ValidationError("Unsupported browser push endpoint.") from None
    host = (url.hostname or "").lower()
    allowed = (
        host in {"fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com"}
        or host.endswith(".push.apple.com")
        or host.endswith(".notify.windows.com")
    )
    if (
        not allowed
        or url.scheme != "https"
        or port not in (None, 443)
        or url.username
        or url.password
        or url.fragment
    ):
        raise ValidationError("Unsupported browser push endpoint.")
    try:
        key = base64.urlsafe_b64decode(value["keys"]["p256dh"] + "===")
        auth = base64.urlsafe_b64decode(value["keys"]["auth"] + "===")
        if len(key) != 65 or key[0] != 4 or len(auth) != 16:
            raise ValueError()
    except Exception:
        raise ValidationError("Invalid browser push keys.") from None


async def save_subscription(uow, container, user_id, value):
    if not container.settings.calls.calls_vapid_public_key:
        raise InvalidStateError("Browser notifications have not been configured.")
    valid_subscription(value)
    digest = hashlib.sha256(value["endpoint"].encode()).hexdigest()
    # Serialize subscription limits and duplicate endpoint registration.
    for key in sorted([f"push-user:{user_id}", f"push-endpoint:{digest}"]):
        await uow.session.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": key}
        )
    row = (
        await uow.session.execute(
            select(m.ChatPushSubscriptionModel)
            .where(m.ChatPushSubscriptionModel.endpoint_hash == digest)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if row and row.user_id != user_id:
        raise PermissionDenied("Unsubscribe this browser from the previous account first.")
    if not row or not row.enabled:
        count = await uow.session.scalar(
            select(func.count())
            .select_from(m.ChatPushSubscriptionModel)
            .where(
                m.ChatPushSubscriptionModel.user_id == user_id,
                m.ChatPushSubscriptionModel.enabled.is_(True),
            )
        )
        if count >= 8:
            raise InvalidStateError("Notification device limit reached.")
    if not row:
        row = m.ChatPushSubscriptionModel(
            id=uuid4(), user_id=user_id, endpoint_hash=digest, created_at=container.clock.now()
        )
        uow.session.add(row)
    row.encrypted_subscription = container.encryptor.encrypt(
        json.dumps(value), associated_data=f"call-push:{row.id}".encode()
    )
    row.enabled = True
    await uow.commit()
    return {"id": str(row.id)}


async def disable_subscription(uow, user_id, subscription_id):
    row = await uow.session.get(m.ChatPushSubscriptionModel, subscription_id)
    if not row or row.user_id != user_id:
        raise EntityNotFound("subscription", subscription_id)
    row.enabled = False
    await uow.commit()


async def notify_call(uow, container, call):
    cfg = container.settings.calls
    if not cfg.calls_vapid_private_key:
        return
    from pywebpush import webpush, WebPushException

    rows = (
        (
            await uow.session.execute(
                select(m.ChatPushSubscriptionModel).where(
                    m.ChatPushSubscriptionModel.user_id == call.callee_id,
                    m.ChatPushSubscriptionModel.enabled.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    payload = json.dumps(
        {
            "callId": str(call.id),
            "conversationId": str(call.conversation_id),
            "createdAt": call.created_at.isoformat(),
        }
    )

    async def send(row):
        try:
            value = json.loads(
                container.encryptor.decrypt(
                    row.encrypted_subscription, associated_data=f"call-push:{row.id}".encode()
                )
            )
            await asyncio.to_thread(
                webpush,
                subscription_info=value,
                data=payload,
                vapid_private_key=cfg.calls_vapid_private_key.get_secret_value(),
                vapid_claims={"sub": cfg.calls_vapid_subject},
                ttl=45,
                timeout=4,
                headers={"Urgency": "high", "Topic": str(call.id).replace("-", "")},
            )
        except WebPushException as exc:
            if exc.response is not None and exc.response.status_code in (404, 410):
                row.enabled = False
        except Exception:
            pass

    await asyncio.gather(*(send(row) for row in rows))
