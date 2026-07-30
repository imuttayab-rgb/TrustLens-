"""OpenAI adapter for listing analysis.

Interchangeable with AnthropicAnalyzer behind the `LlmAnalyzer` port: both
pass the same contract tests, so no use case can tell them apart.
"""

from __future__ import annotations

import time

from trustlens.ai.llm.base import parse_analysis_json
from trustlens.ai.llm.prompts.listing_analysis_v1 import build_messages
from trustlens.core.domain.errors import ExternalServiceError
from trustlens.core.domain.ports.ai import ListingAnalysisResult
from trustlens.shared.logging import get_logger

log = get_logger(__name__)


class OpenAiAnalyzer:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout: int = 30,
        max_retries: int = 3,
        max_output_tokens: int = 2048,
        prompt_version: str = "v1",
    ) -> None:
        self._model = model
        self._max_output_tokens = max_output_tokens
        self._prompt_version = prompt_version

        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout, max_retries=max_retries)

    async def analyze_listing(
        self,
        *,
        title: str,
        description: str,
        price: float | None,
        currency: str | None,
        category: str | None,
    ) -> ListingAnalysisResult:
        system, user = build_messages(
            title=title,
            description=description,
            price=price,
            currency=currency,
            category=category,
        )
        started = time.monotonic()

        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                max_tokens=self._max_output_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except Exception as exc:
            log.warning("llm_analysis_failed", provider="openai", error=str(exc))
            raise ExternalServiceError("openai", str(exc)) from exc

        latency_ms = int((time.monotonic() - started) * 1000)
        parsed = parse_analysis_json(response.choices[0].message.content or "")
        usage = response.usage

        return ListingAnalysisResult(
            risk_score=parsed["risk_score"],
            confidence=parsed["confidence"],
            labels=tuple(parsed["labels"]),
            findings=parsed["findings"],
            summary=parsed["summary"],
            provider="openai",
            model_name=self._model,
            model_version=response.model,
            prompt_version=self._prompt_version,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            latency_ms=latency_ms,
            raw={"finish_reason": response.choices[0].finish_reason},
        )


__all__ = ["OpenAiAnalyzer"]
