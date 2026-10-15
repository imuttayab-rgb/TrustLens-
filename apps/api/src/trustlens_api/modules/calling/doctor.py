"""Check configured media reachability without sending a user invitation."""

import asyncio
from datetime import datetime, UTC
from types import SimpleNamespace
from uuid import uuid4
from trustlens.shared.config import get_settings
from trustlens_api.modules.calling.media import CallMedia


async def main():
    settings = get_settings()
    if not settings.calls.calls_enabled:
        raise SystemExit("CALLS_ENABLED is false.")
    media = CallMedia(settings, SimpleNamespace(now=lambda: datetime.now(UTC)))
    id = uuid4()
    try:
        await media.create(id)
        await media.delete(id)
    except Exception:
        raise SystemExit(
            "MEDIA_CHECK_FAILED: check internal URL, matching keys and LiveKit service logs. No secrets printed."
        ) from None
    print("MEDIA_API_CREATE_DELETE=PASS")
    print(
        "PUBLIC_AUDIO_CHECK=REQUIRES_TWO_BROWSERS; this check does not certify firewall, microphone or TURN."
    )


if __name__ == "__main__":
    asyncio.run(main())
