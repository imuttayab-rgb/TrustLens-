"""Validated calling request bodies. No transport or media side effects."""

from typing import Literal
from uuid import UUID
from pydantic import Field
from .common import Schema


class StartCall(Schema):
    conversation_id: UUID
    call_id: UUID
    device_id: UUID


class Health(Schema):
    quality: Literal["unknown", "excellent", "good", "poor", "lost"] = "unknown"
    received_bytes: int = Field(default=0, ge=0, le=2**53 - 1)
    sent_bytes: int = Field(default=0, ge=0, le=2**53 - 1)
    packets_lost: int = Field(default=0, ge=0, le=2**31 - 1)


class CallAction(Schema):
    device_id: UUID
    action: Literal["ring", "accept", "reject", "sync", "end", "failed"]
    connected: bool = False
    muted: bool = False
    health: Health | None = None


class Device(Schema):
    device_id: UUID


class PushKeys(Schema):
    p256dh: str = Field(max_length=150)
    auth: str = Field(max_length=50)


class PushSubscription(Schema):
    endpoint: str = Field(max_length=2048)
    keys: PushKeys
