"""Buyer<->seller messaging endpoints.

Everything lives under /me/conversations: any signed-in user (buyer or
seller) may hold conversations, the same way /me/favorites asks nothing
about role. Polled by the frontend, not pushed - see the use-case module
for why.
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Query, status

from trustlens.core.application.use_cases.messaging import (
    ListConversations,
    ListConversationsQuery,
    SetConversationMuted,
    SetConversationMutedCommand,
)
from trustlens.core.domain.errors import RateLimitExceeded
from trustlens.shared.logging import get_logger
from trustlens_api.api.deps import ActorDep, ContainerDep, MetaDep, UowDep
from trustlens_api.api.v1.schemas.common import PageMeta, envelope
from trustlens_api.api.v1.schemas.messaging import (
    ConversationResponse,
    SendMessageRequest,
    SetMutedRequest,
)

log = get_logger(__name__)

from trustlens_api.api.private_route import PrivateChatRoute

router = APIRouter(tags=["Messaging"], route_class=PrivateChatRoute)


async def _throttle_send(container: ContainerDep, actor: ActorDep) -> None:
    """Per-sender limit against message spam/flooding (SOC-01) - separate
    from the anonymous per-IP limiters elsewhere, since the attacker here is
    a signed-in account, not an anonymous scraper. Cache outages return a retryable error to prevent unmetered abuse."""
    limits = container.settings.rate_limit
    if not limits.enabled or actor.user_id is None:
        return
    try:
        allowed, _remaining, retry_after = await container.rate_limiter.hit(
            f"message:send:{actor.user_id}",
            limit=limits.message_send_per_minute,
            window_seconds=60,
        )
    except Exception:
        from fastapi import HTTPException

        raise HTTPException(
            503, "Abuse protection temporarily unavailable", headers={"Retry-After": "30"}
        ) from None
    if not allowed:
        raise RateLimitExceeded(
            "You're sending messages too quickly. Slow down a moment.",
            retry_after=retry_after,
        )


def _to_conversation_response(summary: Any) -> ConversationResponse:
    c = summary.conversation
    return ConversationResponse(
        id=c.id,
        listing_id=c.listing_id,
        listing_title=summary.listing_title,
        counterpart_name=summary.counterpart_name,
        counterpart_user_id=summary.counterpart_user_id,
        last_message_at=c.last_message_at,
        last_message_preview=summary.last_message_preview,
        unread_count=summary.unread_count,
        created_at=c.created_at,
        muted=summary.muted,
        counterpart_seller_handle=summary.counterpart_seller_handle,
        counterpart_risk_level=summary.counterpart_risk_level,
        counterpart_score=summary.counterpart_score,
    )


@router.post(
    "/me/conversations",
    status_code=status.HTTP_201_CREATED,
    summary="Send a message, starting a new conversation or replying to one",
)
async def send_message(
    body: SendMessageRequest,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    await _throttle_send(container, actor)
    from trustlens_api.modules.profiles.service import require_profile

    await require_profile(uow, actor.user_id)
    from trustlens_api.modules.messaging.service import ChatService

    result = await ChatService(uow, container).send(
        actor.user_id,
        body=body.body,
        conversation_id=body.conversation_id,
        listing_id=body.listing_id,
        client_id=body.client_id,
        reply_to_id=body.reply_to_id,
        forward_id=body.forward_id,
    )
    return envelope(result, request_id=meta.request_id)


@router.get("/me/conversations", summary="List my conversations")
async def list_conversations(
    actor: ActorDep,
    uow: UowDep,
    meta: MetaDep,
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    folder: Literal["all", "buying", "selling", "unread", "important"] = Query(default="all"),
    q: str = Query(default="", max_length=100),
) -> dict[str, Any]:
    assert actor.user_id is not None
    page = await ListConversations(uow=uow).execute(
        ListConversationsQuery(
            user_id=actor.user_id, limit=limit, offset=offset, folder=folder, q=q
        )
    )
    from sqlalchemy import select

    from trustlens.db import models as m
    from trustlens.db.profiles import name_verified, profile_ready

    counterpart_ids = [item.counterpart_user_id for item in page.items]
    profiles = {}
    if counterpart_ids:
        rows = (
            await uow.session.execute(
                select(
                    m.AccountProfileModel,
                    profile_ready(m.AccountProfileModel.user_id),
                    name_verified(m.AccountProfileModel.user_id),
                ).where(m.AccountProfileModel.user_id.in_(counterpart_ids))
            )
        ).all()
        profiles = {p.user_id: (p, ready, named) for p, ready, named in rows}
    important = (
        set(
            (
                await uow.session.execute(
                    select(m.ConversationPreferenceModel.conversation_id).where(
                        m.ConversationPreferenceModel.user_id == actor.user_id,
                        m.ConversationPreferenceModel.important.is_(True),
                        m.ConversationPreferenceModel.conversation_id.in_(
                            [item.conversation.id for item in page.items]
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )
        if page.items
        else set()
    )
    items = []
    for item in page.items:
        data = _to_conversation_response(item).model_dump(by_alias=True)
        uid = item.counterpart_user_id
        p, ready, named = profiles.get(uid, (None, False, False))
        data["counterpartName"] = p.public_name if p and named else "Member"
        data["counterpartProfileUrl"] = f"/profile/{uid}"
        data["counterpartAvatarUrl"] = (
            f"/api/v1/public/profiles/{uid}/photo?v={p.approved_photo_id}" if p and ready else None
        )
        data["counterpartPhotoMatched"] = bool(ready)
        data["important"] = item.conversation.id in important
        items.append(data)
    return envelope(
        items,
        request_id=meta.request_id,
        pagination=PageMeta.build(
            page=(page.offset // page.limit) + 1, per_page=page.limit, total=page.total
        ),
    )


@router.get(
    "/me/conversations/{conversation_id}", summary="Conversation header for either participant"
)
async def get_conversation(
    conversation_id: UUID, actor: ActorDep, uow: UowDep, meta: MetaDep, container: ContainerDep
):
    from sqlalchemy import select

    from trustlens.core.domain.errors import EntityNotFound
    from trustlens.db import models as m
    from trustlens.db.profiles import name_verified, profile_ready

    participants = await uow.messaging.get_participants(conversation_id)
    if not participants or actor.user_id not in participants:
        raise EntityNotFound("conversation", conversation_id)
    c = await uow.messaging.get_conversation(conversation_id)
    if not c:
        raise EntityNotFound("conversation", conversation_id)
    uid = participants[1] if actor.user_id == participants[0] else participants[0]
    p = await uow.session.get(m.AccountProfileModel, uid)
    ready, named = (await uow.session.execute(select(profile_ready(uid), name_verified(uid)))).one()
    seller = (
        await uow.session.execute(
            select(m.SellerProfile).where(
                m.SellerProfile.user_id == uid, m.SellerProfile.deleted_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    score = await uow.trust_scores.get_current(seller.id) if seller else None
    return envelope(
        dict(
            id=str(c.id),
            listingId=str(c.listing_id) if c.listing_id else None,
            listingTitle=c.listing_title,
            counterpartName=p.public_name if p and named else "Member",
            counterpartUserId=str(uid),
            counterpartProfileUrl=f"/profile/{uid}",
            counterpartAvatarUrl=f"/api/v1/public/profiles/{uid}/photo?v={p.approved_photo_id}"
            if p and ready
            else None,
            counterpartPhotoMatched=bool(ready),
            lastMessageAt=c.last_message_at.isoformat(),
            lastMessagePreview=None,
            unreadCount=0,
            createdAt=c.created_at.isoformat(),
            muted=c.muted_by_buyer if actor.user_id == participants[0] else c.muted_by_seller,
            counterpartSellerHandle=seller.handle if seller else None,
            counterpartRiskLevel=score.risk_level.value if score else None,
            counterpartScore=int(score.score) if score else None,
            **(await ChatService(uow, container).policy(c, actor.user_id)),
        ),
        request_id=meta.request_id,
    )


@router.get(
    "/me/conversations/{conversation_id}/messages",
    summary="Read a conversation (marks the other party's messages as read)",
)
async def list_messages(
    conversation_id: UUID,
    actor: ActorDep,
    container: ContainerDep,
    uow: UowDep,
    meta: MetaDep,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    assert actor.user_id is not None
    from trustlens_api.modules.messaging.service import ChatService

    page = await ChatService(uow, container).timeline(conversation_id, actor.user_id, limit=limit)
    return envelope(page["items"], request_id=meta.request_id)


@router.put(
    "/me/conversations/{conversation_id}/muted",
    summary="Mute or unmute a conversation",
    description=(
        "A lighter tool than blocking (MOD-01) - stops this thread from "
        "standing out in the inbox without cutting the other party off."
    ),
)
async def set_conversation_muted(
    conversation_id: UUID,
    body: SetMutedRequest,
    actor: ActorDep,
    uow: UowDep,
    meta: MetaDep,
) -> dict[str, Any]:
    assert actor.user_id is not None
    await SetConversationMuted(uow=uow).execute(
        SetConversationMutedCommand(
            conversation_id=conversation_id, user_id=actor.user_id, muted=body.muted
        )
    )
    return envelope({"muted": body.muted}, request_id=meta.request_id)


__all__ = ["router"]


from pydantic import BaseModel, ConfigDict


class SetImportantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    important: bool


@router.put(
    "/me/conversations/{conversation_id}/important",
    summary="Mark a conversation important for yourself",
)
async def set_conversation_important(
    conversation_id: UUID, body: SetImportantRequest, actor: ActorDep, uow: UowDep, meta: MetaDep
):
    from sqlalchemy.dialects.postgresql import insert
    from trustlens.db.models import ConversationPreferenceModel
    from trustlens.core.domain.errors import EntityNotFound

    participants = await uow.messaging.get_participants(conversation_id)
    if not participants or actor.user_id not in participants:
        raise EntityNotFound("conversation", conversation_id)
    stmt = insert(ConversationPreferenceModel).values(
        user_id=actor.user_id, conversation_id=conversation_id, important=body.important
    )
    await uow.session.execute(
        stmt.on_conflict_do_update(
            index_elements=["user_id", "conversation_id"], set_={"important": body.important}
        )
    )
    await uow.commit()
    return envelope({"important": body.important}, request_id=meta.request_id)


# Extended participant endpoints keep the same authentication/profile gates.
from fastapi import Request, Response, Depends
from pydantic import Field
from trustlens_api.api.v1.schemas.common import Schema
from trustlens_api.modules.messaging.service import ChatService
from trustlens_api.modules.messaging.voice import MAX_VOICE_BYTES
from trustlens.core.domain.errors import ValidationError, EntityNotFound
from trustlens_api.api.deps import require_permissions
from sqlalchemy import select
from trustlens.db import models as m


class EditChatRequest(Schema):
    body: str = Field(min_length=1, max_length=4000)


class UndoClearRequest(Schema):
    undo_token: UUID


class ChatReportRequest(Schema):
    description: str = Field(min_length=10, max_length=4000)
    reason: Literal["sensitive_information", "delivery_issue", "harassment", "other"]
    message_id: UUID | None = None


class ModerateChatRequest(Schema):
    message_id: UUID
    reason: str = Field(min_length=10, max_length=1000)


@router.get("/me/conversations/{conversation_id}/timeline")
async def chat_timeline(
    conversation_id: UUID,
    actor: ActorDep,
    uow: UowDep,
    container: ContainerDep,
    meta: MetaDep,
    before: UUID | None = None,
    limit: int = Query(50, ge=1, le=100),
):
    return envelope(
        await ChatService(uow, container).timeline(
            conversation_id, actor.user_id, before=before, limit=limit
        ),
        request_id=meta.request_id,
    )


@router.post("/me/conversations/{conversation_id}/voice", status_code=201)
async def send_voice(
    conversation_id: UUID,
    request: Request,
    actor: ActorDep,
    uow: UowDep,
    container: ContainerDep,
    meta: MetaDep,
    client_id: UUID = Query(alias="clientId"),
    reply_to_id: UUID | None = Query(None, alias="replyToId"),
):
    service = ChatService(uow, container)
    await service.participant(conversation_id, actor.user_id)
    from trustlens_api.modules.profiles.service import require_profile

    await require_profile(uow, actor.user_id)
    await _throttle_send(container, actor)
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > MAX_VOICE_BYTES:
            raise ValidationError("Voice messages must be under 12 MB.")
    result = await service.send(
        actor.user_id,
        conversation_id=conversation_id,
        client_id=client_id,
        reply_to_id=reply_to_id,
        raw=bytes(raw),
    )
    return envelope(result, request_id=meta.request_id)


@router.patch("/me/chat-messages/{message_id}")
async def edit_chat(
    message_id: UUID,
    body: EditChatRequest,
    actor: ActorDep,
    uow: UowDep,
    container: ContainerDep,
    meta: MetaDep,
):
    return envelope(
        await ChatService(uow, container).change(message_id, actor.user_id, body=body.body),
        request_id=meta.request_id,
    )


@router.delete("/me/chat-messages/{message_id}")
async def delete_chat(
    message_id: UUID, actor: ActorDep, uow: UowDep, container: ContainerDep, meta: MetaDep
):
    return envelope(
        await ChatService(uow, container).change(message_id, actor.user_id, delete=True),
        request_id=meta.request_id,
    )


@router.post("/me/conversations/{conversation_id}/clear")
async def clear_chat(
    conversation_id: UUID, actor: ActorDep, uow: UowDep, container: ContainerDep, meta: MetaDep
):
    return envelope(
        await ChatService(uow, container).clear(conversation_id, actor.user_id),
        request_id=meta.request_id,
    )


@router.post("/me/conversations/{conversation_id}/clear/undo")
async def undo_clear(
    conversation_id: UUID,
    body: UndoClearRequest,
    actor: ActorDep,
    uow: UowDep,
    container: ContainerDep,
    meta: MetaDep,
):
    return envelope(
        await ChatService(uow, container).clear(
            conversation_id, actor.user_id, undo=body.undo_token
        ),
        request_id=meta.request_id,
    )


@router.get("/me/chat-messages/{message_id}/audio")
async def chat_audio(message_id: UUID, actor: ActorDep, uow: UowDep, container: ContainerDep):
    data = await ChatService(uow, container).audio(message_id, actor.user_id)
    return Response(
        data,
        media_type="audio/mp4",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/me/chat-messages/{message_id}/played")
async def voice_played(
    message_id: UUID, actor: ActorDep, uow: UowDep, container: ContainerDep, meta: MetaDep
):
    return envelope(
        await ChatService(uow, container).played(message_id, actor.user_id),
        request_id=meta.request_id,
    )


@router.post("/me/conversations/{conversation_id}/support", status_code=201)
async def chat_support(
    conversation_id: UUID,
    body: ChatReportRequest,
    actor: ActorDep,
    uow: UowDep,
    container: ContainerDep,
    meta: MetaDep,
):
    await _throttle_send(container, actor)
    return envelope(
        await ChatService(uow, container).report(
            conversation_id, actor.user_id, body.description, body.reason, body.message_id
        ),
        request_id=meta.request_id,
    )


async def _chat_case(uow, report_id):
    case = await uow.session.get(m.ChatCaseModel, report_id)
    if not case:
        raise EntityNotFound("chat case", report_id)
    return case


@router.get(
    "/admin/chat-cases/{report_id}", dependencies=[Depends(require_permissions("moderation:read"))]
)
async def review_chat_case(
    report_id: UUID,
    actor: ActorDep,
    uow: UowDep,
    container: ContainerDep,
    meta: MetaDep,
    before: UUID | None = None,
):
    case = await _chat_case(uow, report_id)
    service = ChatService(uow, container)
    query = select(m.MessageModel).where(m.MessageModel.conversation_id == case.conversation_id)
    if before:
        cursor = await uow.session.get(m.MessageModel, before)
        if not cursor or cursor.conversation_id != case.conversation_id:
            raise EntityNotFound("message", before)
        from sqlalchemy import or_, and_

        query = query.where(
            or_(
                m.MessageModel.created_at < cursor.created_at,
                and_(m.MessageModel.created_at == cursor.created_at, m.MessageModel.id < cursor.id),
            )
        )
    rows = list(
        (
            await uow.session.execute(
                query.order_by(m.MessageModel.created_at.desc(), m.MessageModel.id.desc()).limit(51)
            )
        ).scalars()
    )
    more = len(rows) > 50
    rows = rows[:50]
    versions = list(
        (
            await uow.session.execute(
                select(m.ChatVersionModel)
                .where(m.ChatVersionModel.message_id.in_([r.id for r in rows]))
                .order_by(m.ChatVersionModel.created_at)
            )
        ).scalars()
    )
    service.audit(
        actor.user_id,
        case.conversation_id,
        "staff_review",
        reportId=str(report_id),
        count=len(rows),
    )
    await uow.commit()
    return envelope(
        {
            "conversationId": str(case.conversation_id),
            "reason": case.reason,
            "nextCursor": str(rows[-1].id) if more else None,
            "messages": [
                {
                    "id": str(r.id),
                    "senderId": str(r.sender_id),
                    "kind": r.kind,
                    "original": r.body,
                    "current": r.edited_body,
                    "createdAt": r.created_at.isoformat(),
                    "deleted": bool(r.deleted_for_everyone_at),
                    "hidden": bool(r.moderated_at),
                    "versions": [
                        {"body": v.body, "at": v.created_at.isoformat()}
                        for v in versions
                        if v.message_id == r.id
                    ],
                }
                for r in reversed(rows)
            ],
        },
        request_id=meta.request_id,
    )


@router.get(
    "/admin/chat-cases/{report_id}/audio/{message_id}",
    dependencies=[Depends(require_permissions("moderation:read"))],
)
async def review_chat_audio(
    report_id: UUID, message_id: UUID, actor: ActorDep, uow: UowDep, container: ContainerDep
):
    case = await _chat_case(uow, report_id)
    row = await uow.session.get(m.MessageModel, message_id)
    if not row or row.conversation_id != case.conversation_id:
        raise EntityNotFound("message", message_id)
    service = ChatService(uow, container)
    service.audit(
        actor.user_id,
        case.conversation_id,
        "staff_audio_review",
        message_id,
        reportId=str(report_id),
    )
    await uow.commit()
    return Response(
        await service.audio_bytes(message_id),
        media_type="audio/mp4",
        headers={"Cache-Control": "private, no-store"},
    )


@router.post(
    "/admin/chat-cases/{report_id}/hide",
    dependencies=[Depends(require_permissions("moderation:resolve"))],
)
async def moderate_chat(
    report_id: UUID,
    body: ModerateChatRequest,
    actor: ActorDep,
    uow: UowDep,
    container: ContainerDep,
    meta: MetaDep,
):
    case = await _chat_case(uow, report_id)
    row = (
        await uow.session.execute(
            select(m.MessageModel)
            .where(
                m.MessageModel.id == body.message_id,
                m.MessageModel.conversation_id == case.conversation_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if not row:
        raise EntityNotFound("message", body.message_id)
    row.moderated_at = container.clock.now()
    ChatService(uow, container).audit(
        actor.user_id,
        case.conversation_id,
        "support_hidden",
        row.id,
        reportId=str(report_id),
        reason=body.reason,
    )
    await uow.commit()
    return envelope({"hidden": True}, request_id=meta.request_id)
