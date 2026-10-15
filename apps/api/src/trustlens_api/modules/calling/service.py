"""Retained call lifecycle; LiveKit carries audio, with no call recording.

PostgreSQL serializes participants across workers and browser devices.
"""

from __future__ import annotations

from datetime import timedelta
from sqlalchemy import func, or_, select, text
from trustlens.db import models as m
from trustlens.core.domain.errors import (
    EntityNotFound,
    InvalidStateError,
    PermissionDenied,
    RateLimitExceeded,
)
from trustlens_api.modules.messaging.service import ChatService, utc
from trustlens_api.modules.calling.media import CallMedia

ACTIVE = ("calling", "ringing", "connecting", "active")
RING_SECONDS = 45
LEASE_SECONDS = 45
MAX_SECONDS = 7200


class CallService(ChatService):
    def enabled(self):
        """Reject creation/control when the operator has disabled calling."""
        if not self.c.settings.calls.calls_enabled:
            raise InvalidStateError("Voice calling is currently unavailable.")

    @property
    def media(self):
        return getattr(self.c, "call_media", None) or CallMedia(self.c.settings, self.c.clock)

    async def get(self, call_id, user_id):
        """Lock a retained call only if this user is one of its participants."""
        row = (
            await self.s.execute(
                select(m.ChatCallModel)
                .where(
                    m.ChatCallModel.id == call_id,
                    or_(m.ChatCallModel.caller_id == user_id, m.ChatCallModel.callee_id == user_id),
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            raise EntityNotFound("call", call_id)
        return row

    def side(self, row, user_id):
        return "caller" if row.caller_id == user_id else "callee"

    def owner(self, row, user_id, device_id):
        """Require the tab/device holding this side's active call lease."""
        if getattr(row, self.side(row, user_id) + "_device") != device_id:
            raise PermissionDenied("This call is open in another browser tab or device.")

    def finish(self, row, reason, actor):
        """Transition once to ended and retain the reason in the audit trail."""
        if row.state == "ended":
            return
        row.state, row.reason, row.ended_at = "ended", reason, self.now()
        self.audit(
            actor,
            row.conversation_id,
            "call_ended",
            callId=str(row.id),
            reason=reason,
            connectedAt=row.connected_at.isoformat() if row.connected_at else None,
        )

    async def expire(self, row):
        """Close stale or no-longer-authorized calls from server-side deadlines and policy."""
        if row.state == "ended":
            return
        now = self.now()
        if not self.c.settings.calls.calls_enabled:
            self.finish(row, "unavailable", row.caller_id)
        elif row.state in ("calling", "ringing") and now >= utc(row.created_at) + timedelta(
            seconds=RING_SECONDS
        ):
            self.finish(row, "missed", row.caller_id)
        elif now >= utc(row.created_at) + timedelta(seconds=MAX_SECONDS):
            self.finish(row, "time_limit", row.caller_id)
        elif now >= utc(row.caller_seen_at) + timedelta(seconds=LEASE_SECONDS) or (
            row.callee_seen_at and now >= utc(row.callee_seen_at) + timedelta(seconds=LEASE_SECONDS)
        ):
            self.finish(row, "connection_lost", row.caller_id)
        elif row.state == "connecting" and now >= utc(row.accepted_at) + timedelta(seconds=45):
            self.finish(row, "failed", row.caller_id)
        else:
            conversation, _ = await self.participant(row.conversation_id, row.caller_id)
            allowed = await self.policy(conversation, row.caller_id)
            if not allowed["canSend"] or not all(
                [
                    await self.uow.users.session_allowed(row.caller_id),
                    await self.uow.users.session_allowed(row.callee_id),
                ]
            ):
                self.finish(row, "chat_unavailable", row.caller_id)

    async def serialize_call(self, row, user_id, device_id=None):
        """Expose call state and controls relevant to this user/device."""
        side = self.side(row, user_id)
        other = row.callee_id if side == "caller" else row.caller_id
        profile = await self.s.get(m.AccountProfileModel, other)
        conversation = await self.s.get(m.ConversationModel, row.conversation_id)
        result = {
            "id": str(row.id),
            "conversationId": str(row.conversation_id),
            "direction": "outgoing" if side == "caller" else "incoming",
            "counterpartName": (profile.public_name if profile else None) or "TrustLens user",
            "listingTitle": conversation.listing_title_snapshot or "Listing conversation",
            "state": row.state,
            "reason": row.reason,
            "createdAt": row.created_at.isoformat(),
            "connectedAt": row.connected_at.isoformat() if row.connected_at else None,
            "endedAt": row.ended_at.isoformat() if row.ended_at else None,
            "serverNow": self.now().isoformat(),
            "owned": bool(device_id and getattr(row, side + "_device") == device_id),
            "canAnswer": side == "callee" and row.state in ("calling", "ringing"),
        }
        result["remoteMuted"] = row.callee_muted if side == "caller" else row.caller_muted
        result["maxCallSeconds"] = MAX_SECONDS
        return result

    async def start(self, user_id, conversation_id, call_id, device_id):
        """Serialize participant availability, verify chat eligibility and allocate one media room."""
        self.enabled()
        from trustlens_api.modules.profiles.service import require_profile

        await require_profile(self.uow, user_id)
        conversation, participants = await self.participant(conversation_id, user_id)
        other = next((p for p in participants if p != user_id), None)
        if not other or not (await self.policy(conversation, user_id))["canSend"]:
            raise InvalidStateError("Calling is unavailable in this conversation.")
        if not await self.uow.users.session_allowed(other):
            raise InvalidStateError("This person is currently unavailable.")
        # Stable order serializes simultaneous starts across API workers and conversations.
        for uid in sorted([user_id, other], key=str):
            await self.s.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
                {"key": f"call-user:{uid}"},
            )
        previous = (
            await self.s.execute(
                select(m.ChatCallModel).where(m.ChatCallModel.id == call_id).with_for_update()
            )
        ).scalar_one_or_none()
        if previous:
            if previous.caller_id != user_id or previous.conversation_id != conversation_id:
                raise InvalidStateError("Please start a new call.")
            self.owner(previous, user_id, device_id)
            await self.expire(previous)
            await self.uow.commit()
            return await self.serialize_call(previous, user_id, device_id)
        rows = (
            (
                await self.s.execute(
                    select(m.ChatCallModel)
                    .where(
                        m.ChatCallModel.state.in_(ACTIVE),
                        or_(
                            m.ChatCallModel.caller_id.in_([user_id, other]),
                            m.ChatCallModel.callee_id.in_([user_id, other]),
                        ),
                    )
                    .order_by(m.ChatCallModel.id)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        for row in rows:
            await self.expire(row)
            if row.state != "ended":
                raise InvalidStateError("You or the other person are already in a call.")
        count = await self.s.scalar(
            select(func.count())
            .select_from(m.ChatCallModel)
            .where(
                m.ChatCallModel.caller_id == user_id,
                m.ChatCallModel.created_at > self.now() - timedelta(minutes=1),
            )
        )
        if count >= 5:
            raise RateLimitExceeded("Too many calls. Please wait a minute.", retry_after=60)
        now = self.now()
        row = m.ChatCallModel(
            id=call_id,
            conversation_id=conversation_id,
            caller_id=user_id,
            callee_id=other,
            caller_device=device_id,
            state="calling",
            created_at=now,
            caller_seen_at=now,
        )
        try:
            await self.media.create(call_id)
        except Exception:
            raise InvalidStateError(
                "Calling service is unavailable. Please try again shortly."
            ) from None
        self.s.add(row)
        await self.s.flush()
        self.s.add(m.ChatCallRuntimeModel(call_id=call_id))
        self.audit(user_id, conversation_id, "call_started", callId=str(call_id))
        await self.uow.commit()
        return await self.serialize_call(row, user_id, device_id)

    async def active(self, user_id, device_id):
        """Reconcile the user's current invitation/call against expiry and device ownership."""
        rows = (
            (
                await self.s.execute(
                    select(m.ChatCallModel)
                    .where(
                        m.ChatCallModel.state.in_(ACTIVE),
                        or_(
                            m.ChatCallModel.caller_id == user_id,
                            m.ChatCallModel.callee_id == user_id,
                        ),
                    )
                    .order_by(m.ChatCallModel.id)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        current = None
        for row in rows:
            await self.expire(row)
            if row.state != "ended":
                current = row
        await self.uow.commit()
        return await self.serialize_call(current, user_id, device_id) if current else None

    async def act(
        self, user_id, call_id, device_id, action, *, connected=False, muted=False, health=None
    ):
        """Apply an allowed signalling action while enforcing participant and lease ownership."""
        row = await self.get(call_id, user_id)
        await self.expire(row)
        side = self.side(row, user_id)
        if row.state != "ended":
            if action == "ring":
                if side != "callee":
                    raise PermissionDenied("Only the recipient can acknowledge ringing.")
                if row.state == "calling":
                    row.state = "ringing"
                    self.audit(user_id, row.conversation_id, "call_ringing", callId=str(row.id))
            elif action == "accept":
                if side != "callee":
                    raise PermissionDenied("Only the recipient can answer.")
                from trustlens_api.modules.profiles.service import require_profile

                await require_profile(self.uow, user_id)
                if row.state in ("calling", "ringing"):
                    row.callee_device, row.accepted_at, row.callee_seen_at, row.state = (
                        device_id,
                        self.now(),
                        self.now(),
                        "connecting",
                    )
                    self.audit(user_id, row.conversation_id, "call_accepted", callId=str(row.id))
                self.owner(row, user_id, device_id)
            elif action == "reject":
                if side != "callee" or row.state not in ("calling", "ringing"):
                    raise InvalidStateError("This call is no longer ringing.")
                self.finish(row, "declined", user_id)
            else:
                self.owner(row, user_id, device_id)
                if action in ("end", "failed"):
                    self.finish(
                        row,
                        "failed"
                        if action == "failed"
                        else "cancelled"
                        if row.state in ("calling", "ringing")
                        else "ended",
                        user_id,
                    )
                elif action == "sync":
                    setattr(row, side + "_seen_at", self.now())
                    setattr(row, side + "_muted", muted)
                    runtime = await self.s.get(m.ChatCallRuntimeModel, row.id)
                    if runtime and health:
                        setattr(runtime, side + "_health", health)
                    if connected and row.state in ("connecting", "active"):
                        setattr(row, side + "_connected", True)
                        if row.caller_connected and row.callee_connected and row.state != "active":
                            row.state, row.connected_at = "active", self.now()
                            self.audit(
                                user_id, row.conversation_id, "call_connected", callId=str(row.id)
                            )
        await self.uow.commit()
        return await self.serialize_call(row, user_id, device_id)

    async def join(self, user_id, call_id, device_id):
        """Issue short-lived room access after checking call state and device ownership."""
        row = await self.get(call_id, user_id)
        await self.expire(row)
        if row.state not in ("connecting", "active"):
            await self.uow.commit()
            raise InvalidStateError("The call must be accepted and active before joining.")
        self.owner(row, user_id, device_id)
        access = self.media.join(row, user_id, device_id)
        await self.uow.commit()
        return access

    async def history(self, user_id, conversation_id):
        """Return retained call history filtered by the requesting participant's clear cutoff."""
        await self.participant(conversation_id, user_id)
        cutoff = await self.cutoff(conversation_id, user_id)
        stmt = select(m.ChatCallModel).where(m.ChatCallModel.conversation_id == conversation_id)
        if cutoff:
            stmt = stmt.where(m.ChatCallModel.created_at > cutoff)
        rows = (
            (await self.s.execute(stmt.order_by(m.ChatCallModel.created_at.desc()).limit(30)))
            .scalars()
            .all()
        )
        return [await self.serialize_call(row, user_id) for row in rows]
