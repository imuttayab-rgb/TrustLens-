"""Participant-scoped chat. Original records are append-only evidence.

No public method returns original versions or storage keys to participants.
"""

from __future__ import annotations
import base64
from datetime import UTC, timedelta
from uuid import uuid4
from sqlalchemy import and_, or_, select, text
from trustlens.db import models as m
from trustlens.core.domain.errors import (
    EntityNotFound,
    InvalidStateError,
    PermissionDenied,
    ValidationError,
)
from trustlens.core.application.use_cases.messaging.manage import (
    SendMessage,
    SendMessageCommand,
    _clean_body,
)
from trustlens.core.domain.enums import ReportTargetType, ReportCategory, ReportStatus
from trustlens_api.chat_voice import validate_voice


def utc(value):
    return value.replace(tzinfo=UTC) if value and value.tzinfo is None else value


def public_body(row):
    if row.moderated_at:
        return "Message hidden by support"
    if row.deleted_for_everyone_at:
        return "This message was deleted"
    return row.edited_body if row.edited_body is not None else row.body


def editable(row, user_id, now):
    return (
        row.sender_id == user_id
        and not row.deleted_for_everyone_at
        and not row.moderated_at
        and utc(now) < utc(row.created_at) + timedelta(seconds=60)
    )


class ChatService:
    def __init__(self, uow, container):
        self.uow, self.c, self.s = uow, container, uow.session

    def now(self):
        return self.c.clock.now()

    def audit(self, user_id, conversation_id, action, message_id=None, **details):
        self.s.add(
            m.ChatAuditModel(
                id=uuid4(),
                actor_id=user_id,
                conversation_id=conversation_id,
                message_id=message_id,
                action=action,
                details=details,
                created_at=self.now(),
            )
        )

    async def participant(self, conversation_id, user_id, *, lock=False):
        participants = await self.uow.messaging.get_participants(conversation_id)
        if not participants or user_id not in participants:
            raise EntityNotFound("conversation", conversation_id)
        stmt = select(m.ConversationModel).where(m.ConversationModel.id == conversation_id)
        if lock:
            stmt = stmt.with_for_update()
        row = (await self.s.execute(stmt)).scalar_one()
        return row, participants

    async def cutoff(self, conversation_id, user_id):
        row = await self.s.get(m.ChatClearModel, (user_id, conversation_id))
        return utc(row.cleared_before) if row else None

    async def visible_message(self, message_id, user_id, *, conversation_id=None, lock=False):
        row = await self.s.get(m.MessageModel, message_id)
        if row is None or (conversation_id and row.conversation_id != conversation_id):
            raise EntityNotFound("message", message_id)
        await self.participant(row.conversation_id, user_id, lock=lock)
        if lock:
            await self.s.refresh(row, with_for_update=True)
        cutoff = await self.cutoff(row.conversation_id, user_id)
        if cutoff and utc(row.created_at) <= cutoff:
            raise EntityNotFound("message", message_id)
        return row

    async def policy(self, conversation, user_id, *, lock=False):
        if lock and conversation.listing_id:
            # Serializes send against every listing status writer, including workers.
            await self.s.execute(
                select(m.ListingModel.id)
                .where(m.ListingModel.id == conversation.listing_id)
                .with_for_update()
            )
        state = (
            await self.s.get(m.ChatLifecycleModel, conversation.listing_id)
            if conversation.listing_id
            else None
        )
        if state:
            await self.s.refresh(state)
        closes = (
            utc(state.inactive_since) + timedelta(hours=72)
            if state and state.inactive_since
            else None
        )
        readonly = (
            (closes is not None and self.now() >= closes)
            or conversation.listing_id is None
            or state is None
        )
        participants = await self.uow.messaging.get_participants(conversation.id)
        other = next((p for p in participants or [] if p != user_id), None)
        blocked = bool(other and await self.uow.blocks.is_blocked_either_way(user_id, other))
        return {
            "serverNow": self.now().isoformat(),
            "listingStatus": state.status if state else "UNAVAILABLE",
            "inactiveSince": state.inactive_since.isoformat()
            if state and state.inactive_since
            else None,
            "closesAt": closes.isoformat() if closes else None,
            "readOnly": readonly,
            "canSend": not readonly and not blocked,
            "blocked": blocked,
        }

    async def serialize(self, rows, user_id):
        ids = [r.id for r in rows]
        voices = (
            {
                v.message_id: v
                for v in (
                    await self.s.execute(
                        select(m.ChatVoiceModel).where(m.ChatVoiceModel.message_id.in_(ids))
                    )
                ).scalars()
            }
            if ids
            else {}
        )
        reply_ids = {r.reply_to_id for r in rows if r.reply_to_id}
        replies = (
            {
                r.id: r
                for r in (
                    await self.s.execute(
                        select(m.MessageModel).where(m.MessageModel.id.in_(reply_ids))
                    )
                ).scalars()
            }
            if reply_ids
            else {}
        )
        cutoffs = {
            cid: await self.cutoff(cid, user_id) for cid in {r.conversation_id for r in rows}
        }
        result = []
        for r in rows:
            hidden = bool(r.deleted_for_everyone_at or r.moderated_at)
            v = voices.get(r.id)
            reply = replies.get(r.reply_to_id)
            cutoff = cutoffs.get(r.conversation_id)
            reply_visible = reply and (not cutoff or utc(reply.created_at) > cutoff)
            result.append(
                {
                    "id": str(r.id),
                    "conversationId": str(r.conversation_id),
                    "senderId": str(r.sender_id),
                    "body": public_body(r),
                    "kind": r.kind,
                    "createdAt": r.created_at.isoformat(),
                    "readAt": r.read_at.isoformat() if r.read_at else None,
                    "playedAt": r.played_at.isoformat() if r.played_at else None,
                    "editedAt": r.edited_at.isoformat() if r.edited_at and not hidden else None,
                    "deleted": hidden,
                    "editableUntil": (utc(r.created_at) + timedelta(seconds=60)).isoformat(),
                    "replyTo": {
                        "id": str(reply.id),
                        "body": public_body(reply)[:160]
                        if reply.kind == "text"
                        or reply.deleted_for_everyone_at
                        or reply.moderated_at
                        else "Voice message",
                    }
                    if reply_visible
                    else None,
                    "forwarded": bool(r.forwarded_from_id),
                    "voice": {"duration": v.duration_seconds, "waveform": v.waveform}
                    if v and not hidden
                    else None,
                }
            )
        return result

    async def send(
        self,
        user_id,
        *,
        body="",
        conversation_id=None,
        listing_id=None,
        client_id=None,
        reply_to_id=None,
        forward_id=None,
        raw=None,
    ):
        from trustlens_api.profile_service import require_profile

        await require_profile(self.uow, user_id)
        client_id = client_id or uuid4()
        # One sender lock makes retries and first-message conversation creation atomic.
        await self.s.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),
            {"key": f"chat-send:{user_id}"},
        )
        previous = (
            await self.s.execute(
                select(m.MessageModel).where(
                    m.MessageModel.sender_id == user_id, m.MessageModel.client_id == client_id
                )
            )
        ).scalar_one_or_none()
        if previous:
            if conversation_id and previous.conversation_id != conversation_id:
                raise ValidationError("This retry key belongs to another conversation.")
            await self.visible_message(previous.id, user_id)
            return {
                "conversationId": str(previous.conversation_id),
                "message": (await self.serialize([previous], user_id))[0],
            }
        if conversation_id and listing_id:
            raise ValidationError("Choose a conversation or listing, not both.")
        usecase = SendMessage(uow=self.uow, clock=self.c.clock, ids=self.c.ids)
        conv = await usecase._resolve_conversation(
            SendMessageCommand(
                sender_id=user_id,
                body="Voice message" if raw else body or "Forwarded message",
                conversation_id=conversation_id,
                listing_id=listing_id,
            ),
            self.now(),
        )
        # Lock listing before conversation consistently for sends/clear/mutations.
        policy = await self.policy(conv, user_id, lock=True)
        c, _ = await self.participant(conv.id, user_id, lock=True)
        if not policy["canSend"]:
            raise InvalidStateError(
                "This chat is read-only. You can still read messages and contact support."
            )
        forward = None
        voice = None
        if forward_id:
            forward = await self.visible_message(forward_id, user_id)
            if forward.deleted_for_everyone_at or forward.moderated_at:
                raise InvalidStateError("This message is no longer available to forward.")
            body = public_body(forward)
            if forward.kind == "voice":
                voice = await self.s.get(m.ChatVoiceModel, forward.id)
        if reply_to_id:
            reply = await self.visible_message(reply_to_id, user_id, conversation_id=c.id)
            if reply.deleted_for_everyone_at or reply.moderated_at:
                raise InvalidStateError("This message is no longer available to reply to.")
        payload = await validate_voice(raw) if raw is not None else None
        kind = "voice" if payload or voice else "text"
        body = "Voice message" if kind == "voice" else _clean_body(body)
        # Validate again after decoding/upload: a recording may cross the deadline.
        if not (await self.policy(conv, user_id))["canSend"]:
            raise InvalidStateError("The 72-hour grace period has ended.")
        now = self.now()
        mid = uuid4()
        if payload:
            bucket = self.c.settings.storage.storage_bucket_documents
            root = f"chat-voice/{c.id}/{mid}"
            # App encryption also works with local MinIO without KMS. Never use public links.
            for suffix, data in [("original", raw), ("playback", payload["playback"])]:
                encrypted = self.c.encryptor.encrypt(
                    base64.b64encode(data).decode(), associated_data=str(mid).encode()
                ).encode()
                await self.c.storage.put(
                    bucket=bucket,
                    object_key=f"{root}/{suffix}.enc",
                    data=encrypted,
                    content_type="application/octet-stream",
                    server_side_encryption=False,
                )
            voice = m.ChatVoiceModel(
                message_id=mid,
                bucket=bucket,
                original_key=f"{root}/original.enc",
                playback_key=f"{root}/playback.enc",
                sha256=payload["sha256"],
                size_bytes=len(raw),
                duration_seconds=payload["duration"],
                waveform=payload["waveform"],
            )
        elif voice:
            # A new immutable encrypted copy, with its own authentication context.
            source = voice
            bucket = source.bucket
            root = f"chat-voice/{c.id}/{mid}"
            for suffix, key in [
                ("original", source.original_key),
                ("playback", source.playback_key),
            ]:
                data = await self.c.storage.get(bucket=bucket, object_key=key)
                plaintext = self.c.encryptor.decrypt(
                    data.decode(), associated_data=str(source.message_id).encode()
                )
                encrypted = self.c.encryptor.encrypt(
                    plaintext, associated_data=str(mid).encode()
                ).encode()
                await self.c.storage.put(
                    bucket=bucket,
                    object_key=f"{root}/{suffix}.enc",
                    data=encrypted,
                    content_type="application/octet-stream",
                    server_side_encryption=False,
                )
            voice = m.ChatVoiceModel(
                message_id=mid,
                bucket=bucket,
                original_key=f"{root}/original.enc",
                playback_key=f"{root}/playback.enc",
                sha256=source.sha256,
                size_bytes=source.size_bytes,
                duration_seconds=source.duration_seconds,
                waveform=source.waveform,
            )
        now = self.now()
        if not (await self.policy(conv, user_id))["canSend"]:
            raise InvalidStateError("The 72-hour grace period has ended.")
        row = m.MessageModel(
            id=mid,
            conversation_id=c.id,
            sender_id=user_id,
            body=body,
            kind=kind,
            created_at=now,
            client_id=client_id,
            reply_to_id=reply_to_id,
            forwarded_from_id=forward_id,
        )
        self.s.add(row)
        await self.s.flush()
        if voice:
            self.s.add(voice)
        c.last_message_at = now
        self.audit(user_id, c.id, "sent", mid, kind=kind)
        # Notifications deliberately never duplicate private message contents.
        await usecase._notify_recipient(
            conv, user_id, "New voice message" if kind == "voice" else "New message"
        )
        await self.uow.commit()
        return {"conversationId": str(c.id), "message": (await self.serialize([row], user_id))[0]}

    async def timeline(self, cid, user_id, *, before=None, limit=50):
        await self.participant(cid, user_id)
        stmt = select(m.MessageModel).where(m.MessageModel.conversation_id == cid)
        cutoff = await self.cutoff(cid, user_id)
        if cutoff:
            stmt = stmt.where(m.MessageModel.created_at > cutoff)
        if before:
            cursor = await self.visible_message(before, user_id, conversation_id=cid)
            stmt = stmt.where(
                or_(
                    m.MessageModel.created_at < cursor.created_at,
                    and_(
                        m.MessageModel.created_at == cursor.created_at,
                        m.MessageModel.id < cursor.id,
                    ),
                )
            )
        rows = list(
            (
                await self.s.execute(
                    stmt.order_by(m.MessageModel.created_at.desc(), m.MessageModel.id.desc()).limit(
                        limit + 1
                    )
                )
            ).scalars()
        )
        more = len(rows) > limit
        rows = rows[:limit]
        now = self.now()
        for row in rows:
            if row.sender_id != user_id and row.read_at is None:
                row.read_at = now
        await self.uow.commit()
        return {
            "items": await self.serialize(list(reversed(rows)), user_id),
            "nextCursor": str(rows[-1].id) if more else None,
            "serverNow": now.isoformat(),
        }

    async def change(self, mid, user_id, *, body=None, delete=False):
        row = await self.visible_message(mid, user_id, lock=True)
        if not editable(row, user_id, self.now()):
            raise PermissionDenied(
                "Editing and delete-for-everyone are available to the sender for 60 seconds only."
            )
        if delete:
            row.deleted_for_everyone_at = self.now()
            action = "deleted_for_everyone"
        else:
            if row.kind != "text":
                raise ValidationError("Voice recordings cannot be edited after sending.")
            cleaned = _clean_body(body or "")
            row.edited_body = cleaned
            row.edited_at = self.now()
            action = "edited"
            self.s.add(
                m.ChatVersionModel(
                    id=uuid4(),
                    message_id=mid,
                    actor_id=user_id,
                    body=cleaned,
                    created_at=self.now(),
                )
            )
        self.audit(user_id, row.conversation_id, action, mid)
        await self.uow.commit()
        return (await self.serialize([row], user_id))[0]

    async def clear(self, cid, user_id, *, undo=None):
        await self.participant(cid, user_id, lock=True)
        row = await self.s.get(m.ChatClearModel, (user_id, cid))
        now = self.now()
        if undo:
            if (
                not row
                or row.undo_token != undo
                or not row.undo_until
                or now >= utc(row.undo_until)
            ):
                raise InvalidStateError("The 10-second undo window has ended.")
            row.cleared_before = row.previous_before
            row.undo_token = None
            row.undo_until = None
            self.audit(user_id, cid, "clear_undone")
        else:
            if not row:
                row = m.ChatClearModel(user_id=user_id, conversation_id=cid)
                self.s.add(row)
            row.previous_before = row.cleared_before
            row.cleared_before = now
            row.undo_until = now + timedelta(seconds=10)
            row.undo_token = uuid4()
            self.audit(user_id, cid, "cleared_for_self", cutoff=now.isoformat())
        await self.uow.commit()
        return {
            "undoToken": str(row.undo_token) if row.undo_token else None,
            "undoUntil": row.undo_until.isoformat() if row.undo_until else None,
        }

    async def audio(self, mid, user_id):
        row = await self.visible_message(mid, user_id)
        if row.deleted_for_everyone_at or row.moderated_at:
            raise EntityNotFound("voice", mid)
        return await self.audio_bytes(mid)

    async def audio_bytes(self, mid, *, original=False):
        voice = await self.s.get(m.ChatVoiceModel, mid)
        if not voice:
            raise EntityNotFound("voice", mid)
        encrypted = await self.c.storage.get(
            bucket=voice.bucket, object_key=voice.original_key if original else voice.playback_key
        )
        return base64.b64decode(
            self.c.encryptor.decrypt(encrypted.decode(), associated_data=str(mid).encode())
        )

    async def played(self, mid, user_id):
        row = await self.visible_message(mid, user_id, lock=True)
        if row.kind != "voice" or row.deleted_for_everyone_at or row.moderated_at:
            raise EntityNotFound("voice", mid)
        if row.sender_id != user_id and row.played_at is None:
            row.played_at = self.now()
        await self.uow.commit()
        return {"playedAt": row.played_at.isoformat() if row.played_at else None}

    async def report(self, cid, user_id, description, reason, mid=None):
        await self.participant(cid, user_id)
        if mid:
            await self.visible_message(mid, user_id, conversation_id=cid)
        if reason not in ("sensitive_information", "delivery_issue", "harassment", "other"):
            raise ValidationError("Choose a supported issue type.")
        if len(description.strip()) < 10:
            raise ValidationError("Describe the issue in at least 10 characters.")
        rid = uuid4()
        self.s.add(
            m.ReportModel(
                id=rid,
                reporter_id=user_id,
                target_type=ReportTargetType.MESSAGE if mid else ReportTargetType.OTHER,
                target_id=mid or cid,
                category=ReportCategory.HARASSMENT
                if reason == "harassment"
                else ReportCategory.OTHER,
                description=description.strip(),
                status=ReportStatus.OPEN,
                created_at=self.now(),
            )
        )
        await self.s.flush()
        self.s.add(
            m.ChatCaseModel(report_id=rid, conversation_id=cid, message_id=mid, reason=reason)
        )
        self.audit(user_id, cid, "support_requested", mid, reportId=str(rid), reason=reason)
        await self.uow.commit()
        return {"reportId": str(rid)}
