"""Bounded Groq and Tavily HTTP clients. No paid fallback or vendor SDK."""

from __future__ import annotations

import json
import os
import math
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from dataclasses import dataclass, field
from typing import Any

import httpx


class AssistantUnavailable(Exception):
    """Only safe, public text belongs in this exception."""


class AssistantRateLimited(AssistantUnavailable):
    def __init__(self, message: str, retry_after: int = 60) -> None:
        super().__init__(message)
        self.retry_after = max(1, min(retry_after, 86400))


def retry_seconds(value: str | None) -> int:
    try:
        return max(1, min(math.ceil(float(value or "60")), 86400))
    except (ValueError, OverflowError):
        try:
            date = parsedate_to_datetime(value or "")
            return max(1, min(math.ceil((date - datetime.now(UTC)).total_seconds()), 86400))
        except (ValueError, TypeError, OverflowError):
            return 60


@dataclass(frozen=True)
class AssistantConfig:
    enabled: bool = False
    api_key: str = field(default="", repr=False)
    search_key: str = field(default="", repr=False)
    model: str = "openai/gpt-oss-120b"
    per_minute: int = 4
    daily_requests: int = 120
    monthly_searches: int = 900

    @classmethod
    def from_env(cls) -> AssistantConfig:
        def number(name: str, default: int, upper: int) -> int:
            try:
                return max(1, min(int(os.getenv(name, str(default))), upper))
            except ValueError:
                return default

        return cls(
            enabled=os.getenv("TRUSTLENS_CHAT_ENABLED", "false").lower() == "true",
            api_key=os.getenv("TRUSTLENS_GROQ_API_KEY", "").strip(),
            search_key=os.getenv("TRUSTLENS_TAVILY_API_KEY", "").strip(),
            model="openai/gpt-oss-120b",
            per_minute=number("TRUSTLENS_CHAT_PER_MINUTE", 4, 10),
            daily_requests=number("TRUSTLENS_CHAT_DAILY_REQUESTS", 120, 400),
            monthly_searches=number("TRUSTLENS_SEARCH_MONTHLY_LIMIT", 900, 1000),
        )

    @property
    def ready(self) -> bool:
        return self.enabled and bool(self.api_key)


class GroqProvider:
    def __init__(self, config: AssistantConfig, client: httpx.AsyncClient) -> None:
        self.config, self.client = config, client

    async def complete(
        self, system: str, data: dict[str, Any], *, tokens: int = 1800,
        images: list[str] | None = None,
    ) -> dict[str, Any]:
        if not self.config.ready:
            raise AssistantUnavailable("AI is not connected yet. You can still search listings.")
        response = await request_json(
            self.client,
            "https://api.groq.com/openai/v1/chat/completions",
            self.config.api_key,
            {
                "model": "qwen/qwen3.8-27b" if images else self.config.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": (
                        [{"type": "text", "text": json.dumps(data, ensure_ascii=False)},
                         *[{"type": "image_url", "image_url": {"url": img}} for img in images[:2]]]
                        if images else json.dumps(data, ensure_ascii=False)
                    )},
                ],
                "response_format": {"type": "json_object"},
                "reasoning_effort": "none" if images else "low",
                "max_completion_tokens": tokens,
                "temperature": 0.2,
                "stream": False,
            },
        )
        try:
            choice = response["choices"][0]
            if choice["finish_reason"] != "stop":
                raise ValueError("Incomplete response")
            # Hidden reasoning is never included in the user-facing reply.
            answer = json.loads(choice["message"]["content"])
            if not isinstance(answer, dict):
                raise ValueError("Expected object")
            return answer
        except (KeyError, TypeError, IndexError, ValueError) as exc:
            raise AssistantUnavailable(
                "AI could not finish this reply. Please try a shorter question."
            ) from exc


async def request_json(
    client: httpx.AsyncClient, url: str, key: str, payload: dict[str, Any]
) -> dict[str, Any]:
    try:
        response = await client.post(url, headers={"Authorization": f"Bearer {key}"}, json=payload)
    except httpx.HTTPError as exc:
        raise AssistantUnavailable(
            "The AI connection timed out. Please try again shortly."
        ) from exc
    if response.status_code in (429, 432, 433):
        raise AssistantRateLimited(
            "The free AI or search allowance is busy or exhausted. Your text is unchanged.",
            retry_seconds(response.headers.get("retry-after")),
        )
    if response.status_code in (401, 403):
        raise AssistantUnavailable("The AI connection needs attention from the site owner.")
    if response.is_error:
        raise AssistantUnavailable("The AI service is temporarily unavailable.")
    try:
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Expected object")
        return data
    except ValueError as exc:
        raise AssistantUnavailable("The AI service returned an unreadable reply.") from exc
