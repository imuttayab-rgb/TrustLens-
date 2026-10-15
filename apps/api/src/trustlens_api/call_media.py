"""Small adapter for LiveKit's documented JWT and Twirp room-service API."""

from __future__ import annotations
from datetime import timedelta
import httpx
import jwt


class CallMedia:
    def __init__(self, settings, clock):
        self.cfg, self.clock = settings.calls, clock

    def token(self, grant, *, identity=None, name=None, ttl=60):
        now = self.clock.now()
        payload = {
            "iss": self.cfg.calls_livekit_api_key,
            "nbf": int(now.timestamp()) - 5,
            "exp": int((now + timedelta(seconds=ttl)).timestamp()),
            "video": grant,
        }
        if identity:
            payload["sub"] = identity
        if name:
            payload["name"] = name
        return jwt.encode(
            payload, self.cfg.calls_livekit_api_secret.get_secret_value(), algorithm="HS256"
        )

    @staticmethod
    def room(call_id):
        return f"tl-call-{call_id}"

    async def rpc(self, method, body, grant):
        async with httpx.AsyncClient(timeout=4, follow_redirects=False) as client:
            response = await client.post(
                f"{self.cfg.calls_livekit_internal_url.rstrip('/')}/twirp/livekit.RoomService/{method}",
                json=body,
                headers={"Authorization": f"Bearer {self.token(grant)}"},
            )
        if method == "DeleteRoom" and response.status_code == 404:
            return {}
        response.raise_for_status()
        return response.json()

    async def create(self, call_id):
        return await self.rpc(
            "CreateRoom",
            {
                "name": self.room(call_id),
                "empty_timeout": 90,
                "departure_timeout": 15,
                "max_participants": 2,
            },
            {"roomCreate": True},
        )

    async def delete(self, call_id):
        return await self.rpc("DeleteRoom", {"room": self.room(call_id)}, {"roomCreate": True})

    def join(self, row, user_id, device_id):
        grant = {
            "roomJoin": True,
            "room": self.room(row.id),
            "canPublish": True,
            "canPublishSources": ["microphone"],
            "canSubscribe": True,
            "canPublishData": False,
            "canUpdateOwnMetadata": False,
        }
        return {
            "url": self.cfg.calls_livekit_url,
            "token": self.token(grant, identity=f"{user_id}:{device_id}"),
            "room": self.room(row.id),
            "expiresIn": 60,
        }
