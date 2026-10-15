"""Run inside the API container. Prints status only; never keys, responses or PII."""

from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace

import httpx

from trustlens.shared.cache import RedisCache
from trustlens_api.assistant.provider import AssistantConfig, AssistantUnavailable
from trustlens_api.assistant.service import AssistantService


async def main() -> None:
    config = AssistantConfig.from_env()
    if not config.ready:
        print("GROQ_CONNECTION=NOT_CONFIGURED")
        print("TAVILY_CONNECTION=NOT_TESTED")
        return
    cache = RedisCache.from_url(os.environ["REDIS_URL"])
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(45, connect=10)) as client:
            service = AssistantService(SimpleNamespace(cache=cache), client, config)
            try:
                value = await service.model('Return JSON only: {"connected":true}.', {}, tokens=800)
                print(
                    "GROQ_CONNECTION="
                    + ("PASS" if value.get("connected") is True else "RETRY_NEEDED")
                )
            except AssistantUnavailable as error:
                print("GROQ_CONNECTION=NEEDS_ATTENTION: " + str(error))
            except Exception:
                print("GROQ_CONNECTION=CHECK_FAILED")
            if not config.search_key:
                print("TAVILY_CONNECTION=NOT_CONFIGURED")
            else:
                try:
                    sources = await service.web("Samsung official product support")
                    print("TAVILY_CONNECTION=" + ("PASS" if sources else "NO_RESULTS"))
                except AssistantUnavailable as error:
                    print("TAVILY_CONNECTION=NEEDS_ATTENTION: " + str(error))
                except Exception:
                    print("TAVILY_CONNECTION=CHECK_FAILED")
    finally:
        await cache.close()


if __name__ == "__main__":
    asyncio.run(main())
